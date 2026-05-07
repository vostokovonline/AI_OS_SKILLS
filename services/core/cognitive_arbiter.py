"""
Cognitive Arbiter - мозг AI-OS

Выбирает КАКИЕ цели выполнять сейчас на основе:
- Impact Score
- Learning Value
- Urgency
- Cost Estimate
- Strategic Alignment

Принцип: не "дай мне N целей", а "дай мне лучшие цели для текущего момента"
"""
from uuid import UUID
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalScore:
    goal_id: UUID
    title: str
    impact_score: float = 0.0
    learning_value: float = 0.0
    urgency_score: float = 0.0
    cost_estimate: float = 0.0
    strategic_alignment: float = 0.0
    total_score: float = 0.0
    
    def calculate_total(self, weights: dict) -> float:
        """Рассчитывает общий score"""
        self.total_score = (
            self.impact_score * weights.get('impact', 0.3) +
            self.learning_value * weights.get('learning', 0.2) +
            self.urgency_score * weights.get('urgency', 0.2) +
            self.strategic_alignment * weights.get('strategic', 0.2) -
            self.cost_estimate * weights.get('cost', 0.1)
        )
        return self.total_score


class CognitiveArbiter:
    """
    Мозг системы - выбирает оптимальный набор целей для выполнения.
    
    Заменяет простой "SELECT LIMIT N" на умный scoring.
    """
    
    DEFAULT_WEIGHTS = {
        'impact': 0.30,      # Насколько важна цель
        'learning': 0.20,    # Сколько система научится
        'urgency': 0.20,    # Насколько срочно
        'strategic': 0.20,  # Соответствие стратегии
        'cost': 0.10,       # Стоимость выполнения (штраф)
    }
    
    def __init__(self, session: AsyncSession, weights: Optional[dict] = None):
        self.session = session
        self.weights = weights or self.DEFAULT_WEIGHTS
    
    async def select_goals(
        self, 
        limit: int = 20,
        budget: float = 30.0
    ) -> list[GoalScore]:
        """
        Главный метод: выбрать лучшие цели для выполнения.
        
        Returns:
            Список GoalScore отсортированный по total_score DESC
        """
        # 1. Получить готовые цели
        ready_goals = await self._get_ready_goals()
        
        if not ready_goals:
            return []
        
        # 2. Оценить каждую цель
        scored_goals = []
        total_cost = 0.0
        
        for goal in ready_goals:
            if total_cost >= budget:
                break
                
            score = await self._evaluate_goal(goal)
            score.calculate_total(self.weights)
            
            if score.total_score > 0:  # Только положительные score
                scored_goals.append(score)
                total_cost += score.cost_estimate
        
        # 3. Отсортировать и вернуть top N
        scored_goals.sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(
            "cognitive_arbiter_selection",
            total_ready=len(ready_goals),
            selected=len(scored_goals),
            total_cost=total_cost,
            top_score=scored_goals[0].total_score if scored_goals else 0
        )
        
        return scored_goals[:limit]
    
    async def _get_ready_goals(self, check_dependencies: bool = True) -> list[dict]:
        """Получить цели готовые к выполнению"""
        
        # Base query without dependency check
        base_query = """
            SELECT g.id, g.title, g.description, g.status, g.progress, 
                   g.goal_type, g.depth_level, g.created_at, g.updated_at,
                   g.execution_started_at
            FROM goals g
            WHERE g.status = 'pending'
            AND g.is_atomic = true
            AND (g.progress < 1.0 OR g.progress IS NULL)
        """
        
        if check_dependencies:
            base_query += """
            AND NOT EXISTS (
                SELECT 1 FROM goal_dependencies gd
                JOIN goals gp ON gp.id = gd.depends_on_goal_id
                WHERE gd.goal_id = g.id AND gp.status != 'done'
            )
            """
        
        base_query += " ORDER BY g.created_at ASC LIMIT 100"
        
        result = await self.session.execute(text(base_query))
        
        goals = []
        for row in result.fetchall():
            goals.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'status': row[3],
                'progress': row[4],
                'goal_type': row[5],
                'depth_level': row[6],
                'created_at': row[7],
                'updated_at': row[8],
                'execution_started_at': row[9],
            })
        return goals
    
    async def _evaluate_goal(self, goal: dict) -> GoalScore:
        """Оценить одну цель по всем метрикам"""
        score = GoalScore(
            goal_id=goal['id'],
            title=goal['title'],
        )
        
        # 1. Impact Score (0-1)
        score.impact_score = self._calculate_impact(goal)
        
        # 2. Learning Value (0-1)
        score.learning_value = self._calculate_learning_value(goal)
        
        # 3. Urgency Score (0-1)
        score.urgency_score = self._calculate_urgency(goal)
        
        # 4. Strategic Alignment (0-1)
        score.strategic_alignment = self._calculate_strategic(goal)
        
        # 5. Cost Estimate (0-1, где 1 = дорогая)
        score.cost_estimate = self._estimate_cost(goal)
        
        return score
    
    def _calculate_impact(self, goal: dict) -> float:
        """Насколько важна/ценна цель"""
        title = (goal.get('title') or '').lower()
        goal_type = goal.get('goal_type', '')
        
        # Strategic goals have higher impact
        if goal_type in ['strategic', 'meta']:
            return 0.9
        
        # Core system goals
        if any(kw in title for kw in ['core', 'system', 'architecture', 'foundation']):
            return 0.8
        
        # High impact keywords
        if any(kw in title for kw in ['build', 'create', 'implement', 'deploy', 'production']):
            return 0.7
        
        # Medium impact
        if any(kw in title for kw in ['improve', 'optimize', 'enhance', 'refactor']):
            return 0.5
        
        # Lower impact
        return 0.3
    
    def _calculate_learning_value(self, goal: dict) -> float:
        """Сколько система научится от выполнения"""
        title = (goal.get('title') or '').lower()
        description = (goal.get('description') or '').lower()
        
        # Exploration has high learning value
        if goal.get('goal_type') == 'exploratory':
            return 0.9
        
        # Research tasks
        if any(kw in title for kw in ['research', 'analyze', 'investigate', 'explore']):
            return 0.8
        
        # Learning opportunities
        if any(kw in title for kw in ['learn', 'understand', 'discover', 'new']):
            return 0.7
        
        # Novelty check - new goals have more learning value
        created_at = goal.get('created_at')
        if created_at:
            # Handle both naive and aware datetimes
            now = datetime.utcnow()
            if created_at.tzinfo is not None:
                created_at = created_at.replace(tzinfo=None)
            if (now - created_at).days < 1:
                return 0.6
        
        return 0.3
    
    def _calculate_urgency(self, goal: dict) -> float:
        """Насколько срочно нужно выполнить"""
        updated_at = goal.get('updated_at')
        
        if not updated_at:
            return 0.5
        
        # Handle both naive and aware datetimes
        now = datetime.utcnow()
        if updated_at.tzinfo is not None:
            updated_at = updated_at.replace(tzinfo=None)
        
        # How long since last update
        hours_stale = (now - updated_at).total_seconds() / 3600
        
        # Very stale = high urgency
        if hours_stale > 24:
            return 0.9
        elif hours_stale > 12:
            return 0.7
        elif hours_stale > 6:
            return 0.5
        elif hours_stale > 2:
            return 0.3
        else:
            return 0.2
    
    def _calculate_strategic(self, goal: dict) -> float:
        """Соответствие стратегии"""
        title = (goal.get('title') or '').lower()
        
        # Core AI-OS strategic keywords
        strategic_keywords = [
            'autonomous', 'self', 'evolving', 'intelligence',
            'core', 'foundation', 'architecture', 'platform'
        ]
        
        if any(kw in title for kw in strategic_keywords):
            return 0.9
        
        # Development keywords
        if any(kw in title for kw in ['develop', 'build', 'create']):
            return 0.7
        
        # Maintenance
        if any(kw in title for kw in ['fix', 'bug', 'repair', 'maintain']):
            return 0.4
        
        return 0.5
    
    def _estimate_cost(self, goal: dict) -> float:
        """Оценить стоимость выполнения (0-1, где 1 = дорого)"""
        title = (goal.get('title') or '').lower()
        
        # High cost tasks
        if any(kw in title for kw in ['build', 'deploy', 'kubernetes', 'infrastructure']):
            return 0.8
        
        # Medium cost
        if any(kw in title for kw in ['create', 'implement', 'research', 'analyze']):
            return 0.5
        
        # Low cost
        return 0.2


class BudgetAllocator:
    """
    Распределяет бюджет между категориями целей.
    
    Обеспечивает баланс между:
    - Exploration (новые области)
    - Exploitation (улучшение существующего)
    - Maintenance (исправления)
    """
    
    DEFAULT_ALLOCATION = {
        'strategic': 0.30,  # Долгосрочные цели
        'operational': 0.30,  # Операционные
        'tactical': 0.25,   # Тактические
        'maintenance': 0.15, # Исправления
    }
    
    def __init__(self, total_budget: float = 30.0):
        self.total_budget = total_budget
        self.allocation = self.DEFAULT_ALLOCATION.copy()
    
    def allocate(self, goals: list[GoalScore]) -> dict[str, list[GoalScore]]:
        """Распределить цели по категориям"""
        allocated = {
            'strategic': [],
            'operational': [],
            'tactical': [],
            'maintenance': [],
        }
        
        for goal in goals:
            category = self._categorize_goal(goal.title)
            allocated[category].append(goal)
        
        # Cut to budget
        budget_per_category = {
            k: v * self.total_budget 
            for k, v in self.allocation.items()
        }
        
        return allocated
    
    def _categorize_goal(self, title: str) -> str:
        """Определить категорию цели"""
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ['autonomous', 'self-evolving', 'architecture', 'core']):
            return 'strategic'
        
        if any(kw in title_lower for kw in ['build', 'create', 'implement', 'deploy']):
            return 'operational'
        
        if any(kw in title_lower for kw in ['improve', 'optimize', 'enhance']):
            return 'tactical'
        
        return 'maintenance'
