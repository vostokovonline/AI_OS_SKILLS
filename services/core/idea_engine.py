"""
Idea Engine - генератор новых целей для AI-OS

Генерирует новые цели на основе:
- Reflection (анализ прошлых результатов)
- Capability gaps (недостающие capabilities)
- Strategic alignment (соответствие стратегии)

Это превращает систему из "исполнителя" в "мыслителя".
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
class GeneratedIdea:
    """Сгенерированная идея"""
    title: str
    description: str
    goal_type: str
    priority: float
    source: str  # reflection, capability_gap, strategic, manual
    expected_impact: str


class IdeaEngine:
    """
    Генерирует новые цели для системы.
    
    Sources of ideas:
    1. Reflection - анализ успехов/неудач
    2. Capability gaps - недостающие навыки
    3. Strategic - соответствие стратегии
    4. Manual - от пользователя
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_ideas(self, max_ideas: int = 10) -> list[GeneratedIdea]:
        """Генерирует новые идеи из всех источников"""
        ideas = []
        
        # 1. Из reflection (анализ прошлых выполнений)
        reflection_ideas = await self._generate_from_reflection()
        ideas.extend(reflection_ideas)
        
        # 2. Из capability gaps
        capability_ideas = await self._generate_from_capability_gaps()
        ideas.extend(capability_ideas)
        
        # 3. Strategic ideas
        strategic_ideas = await self._generate_strategic_ideas()
        ideas.extend(strategic_ideas)
        
        # Sort by priority and limit
        ideas.sort(key=lambda x: x.priority, reverse=True)
        
        logger.info(
            "idea_generation_complete",
            total_ideas=len(ideas),
            from_reflection=len(reflection_ideas),
            from_capability=len(capability_ideas),
            from_strategic=len(strategic_ideas)
        )
        
        return ideas[:max_ideas]
    
    async def _generate_from_reflection(self) -> list[GeneratedIdea]:
        """Анализирует прошлые выполнения и генерирует идеи"""
        ideas = []
        
        # Найти недавно завершённые цели
        result = await self.session.execute(text("""
            SELECT g.id, g.title, g.status, g.evaluation_result, g.completion_criteria
            FROM goals g
            WHERE g.status IN ('done', 'failed')
            AND g.completed_at > NOW() - INTERVAL '7 days'
            ORDER BY g.completed_at DESC
            LIMIT 20
        """))
        
        recent_goals = result.fetchall()
        
        # Анализировать неудачи
        failed_goals = [g for g in recent_goals if g[2] == 'failed']
        
        for goal in failed_goals:
            goal_id, title, status, eval_result, criteria = goal
            
            # Генерировать идеи для улучшения
            ideas.append(GeneratedIdea(
                title=f"Improve: {title[:50]}",
                description=f"Анализ неудачи: {title}. Необходимо понять причину и улучшить стратегию.",
                goal_type="achievable",
                priority=0.8,
                source="reflection",
                expected_impact="Улучшение success rate"
            ))
        
        return ideas
    
    async def _generate_from_capability_gaps(self) -> list[GeneratedIdea]:
        """Находит недостающие capabilities и генерирует идеи"""
        ideas = []
        
        # Найти цели которые не удалось выполнить из-за отсутствия skills
        result = await self.session.execute(text("""
            SELECT DISTINCT title, description
            FROM goals
            WHERE status = 'blocked'
            AND title LIKE '%analyze%'
            OR title LIKE '%sentiment%'
            OR title LIKE '%translate%'
            LIMIT 10
        """))
        
        blocked_goals = result.fetchall()
        
        for goal in blocked_goals:
            title, description = goal
            
            # Предложить создание skill
            ideas.append(GeneratedIdea(
                title=f"Create skill for: {title[:40]}",
                description=f"Обнаружена blocked goal '{title}'. Рекомендуется создать соответствующий skill.",
                goal_type="meta",
                priority=0.7,
                source="capability_gap",
                expected_impact="Расширение capability coverage"
            ))
        
        return ideas
    
    async def _generate_strategic_ideas(self) -> list[GeneratedIdea]:
        """Генерирует стратегические идеи"""
        ideas = []
        
        # Проверить сколько времени прошло с последних strategic goals
        result = await self.session.execute(text("""
            SELECT COUNT(*) FROM goals
            WHERE goal_type IN ('strategic', 'meta')
            AND created_at > NOW() - INTERVAL '14 days'
        """))
        
        strategic_count = result.scalar()
        
        # Если мало strategic goals - предложить
        if strategic_count < 3:
            ideas.append(GeneratedIdea(
                title="Define strategic goals for AI-OS",
                description="Система давно не получала стратегических целей. Определите направление развития.",
                goal_type="strategic",
                priority=0.9,
                source="strategic",
                expected_impact="Направление развития системы"
            ))
        
        # Проверить баланс между exploration и exploitation
        result = await self.session.execute(text("""
            SELECT 
                COUNT(CASE WHEN goal_type = 'exploratory' THEN 1 END) as exploratory,
                COUNT(CASE WHEN goal_type = 'achievable' THEN 1 END) as achievable
            FROM goals
            WHERE created_at > NOW() - INTERVAL '7 days'
        """))
        
        row = result.fetchone()
        exploratory, achievable = row[0], row[1]
        
        # Если слишком много achievable - предложить exploration
        if achievable > 10 and exploratory < 2:
            ideas.append(GeneratedIdea(
                title="Explore new capability domains",
                description="Система сосредоточена на достижимых целях. Нужно исследовать новые области.",
                goal_type="exploratory",
                priority=0.6,
                source="strategic",
                expected_impact="Обнаружение новых возможностей"
            ))
        
        return ideas
    
    async def create_goal_from_idea(self, idea: GeneratedIdea) -> UUID:
        """Создаёт цель из идеи"""
        result = await self.session.execute(text("""
            INSERT INTO goals (id, title, description, goal_type, status, is_atomic, created_at, updated_at)
            VALUES (gen_random_uuid(), :title, :description, :goal_type, 'pending', true, NOW(), NOW())
            RETURNING id
        """), {
            'title': idea.title,
            'description': idea.description,
            'goal_type': idea.goal_type
        })
        
        goal_id = result.scalar()
        await self.session.commit()
        
        logger.info(
            "goal_created_from_idea",
            goal_id=str(goal_id),
            title=idea.title,
            source=idea.source
        )
        
        return goal_id


class ReflectionEngine:
    """
    Анализирует прошлые выполнения и извлекает уроки.
    
    Это "мозг" который позволяет системе учиться на ошибках.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def analyze_recent_execution(self) -> dict:
        """Анализирует последние выполнения"""
        result = await self.session.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked
            FROM goals
            WHERE completed_at > NOW() - INTERVAL '24 hours'
        """))
        
        row = result.fetchone()
        
        return {
            'total': row[0] or 0,
            'completed': row[1] or 0,
            'failed': row[2] or 0,
            'blocked': row[3] or 0,
            'success_rate': (row[1] or 0) / max(row[0] or 1, 1)
        }
    
    async def get_failure_patterns(self) -> list[dict]:
        """Находит паттерны неудач"""
        result = await self.session.execute(text("""
            SELECT 
                g.title,
                ge.error_message,
                COUNT(*) as count
            FROM goals g
            JOIN goal_executions ge ON ge.goal_id = g.id
            WHERE ge.status = 'failed'
            AND ge.created_at > NOW() - INTERVAL '7 days'
            GROUP BY g.title, ge.error_message
            ORDER BY count DESC
            LIMIT 10
        """))
        
        patterns = []
        for row in result.fetchall():
            patterns.append({
                'title': row[0],
                'error': row[1],
                'count': row[2]
            })
        
        return patterns
    
    async def generate_insights(self) -> list[str]:
        """Генерирует инсайты из анализа"""
        insights = []
        
        # Анализ success rate
        stats = await self.analyze_recent_execution()
        
        if stats['success_rate'] < 0.3:
            insights.append("⚠️ Low success rate - consider capability expansion")
        elif stats['success_rate'] > 0.7:
            insights.append("✅ High success rate - system is healthy")
        
        # Анализ failure patterns
        failures = await self.get_failure_patterns()
        
        if failures:
            top_failure = failures[0]
            insights.append(f"🔴 Top failure: {top_failure['title']} - {top_failure['error']}")
        
        # Анализ stuck goals
        result = await self.session.execute(text("""
            SELECT COUNT(*) FROM goals
            WHERE status = 'active'
            AND updated_at < NOW() - INTERVAL '1 hour'
        """))
        
        stuck_count = result.scalar()
        if stuck_count > 5:
            insights.append(f"⚠️ {stuck_count} goals stuck for >1 hour")
        
        return insights
