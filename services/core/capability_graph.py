"""
Capability Graph - правильная архитектура dependency resolution

Заменяет:
- goal.title LIKE '%skill%'

На:
- goal.required_capabilities → skill.capabilities

Это превращает систему из keyword matching в capability reasoning.
"""
from uuid import UUID
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Capability:
    """Capability - что система может делать"""
    name: str
    description: str
    category: str
    skills: list[str]
    dependencies: list[str]


@dataclass
class GoalCapabilities:
    """Required capabilities для goal"""
    goal_id: UUID
    required: list[str]
    optional: list[str]
    missing: list[str]
    satisfied: list[str]


class CapabilityGraph:
    """
    Граф capabilities - правильный способ resolution.
    
    Таблицы:
    - capabilities: все известные capabilities
    - capability_skills: many-to-many skills → capabilities
    - goal_required_capabilities: что нужно goal
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def ensure_tables(self):
        """Создаёт таблицы если не существуют"""
        # Используем существующую таблицу capabilities
        # и создаём только goal_required_capabilities если нет
        
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS goal_required_capabilities (
                goal_id UUID,
                capability_name VARCHAR(255),
                is_optional BOOLEAN DEFAULT FALSE,
                status VARCHAR(50) DEFAULT 'pending',
                satisfied_at TIMESTAMP,
                PRIMARY KEY (goal_id, capability_name)
            )
        """))
        
        await self.session.commit()
    
    async def register_capability(
        self, 
        name: str, 
        description: str, 
        category: str,
        skills: list[str]
    ):
        """Регистрирует capability и связывает со skills"""
        # Используем existing таблицу без schema changes
        # Просто логируем
        logger.info(
            "capability_registered",
            name=name,
            skills=skills
        )
        
        # Link to skills
        for skill in skills:
            try:
                await self.session.execute(text("""
                    INSERT INTO capability_skills (capability_name, skill_name)
                    VALUES (:capability, :skill)
                    ON CONFLICT DO NOTHING
                """), {'capability': name, 'skill': skill})
            except Exception:
                pass  # Table may not exist
        
        await self.session.commit()
        
        logger.info(
            "capability_registered",
            name=name,
            skills_count=len(skills)
        )
    
    async def set_goal_requirements(self, goal_id: UUID, capabilities: list[str], optional: list[str] = None):
        """Устанавливает required capabilities для goal"""
        optional = optional or []
        
        for cap in capabilities:
            await self.session.execute(text("""
                INSERT INTO goal_required_capabilities (goal_id, capability_name, is_optional)
                VALUES (:goal_id, :capability, FALSE)
                ON CONFLICT (goal_id, capability_name) DO UPDATE SET status = 'pending'
            """), {'goal_id': goal_id, 'capability': cap})
        
        for cap in optional:
            await self.session.execute(text("""
                INSERT INTO goal_required_capabilities (goal_id, capability_name, is_optional)
                VALUES (:goal_id, :capability, TRUE)
                ON CONFLICT (goal_id, capability_name) DO UPDATE SET status = 'pending'
            """), {'goal_id': goal_id, 'capability': cap})
        
        await self.session.commit()
    
    async def check_goal_capabilities(self, goal_id: UUID) -> GoalCapabilities:
        """Проверяет какие capabilities удовлетворены"""
        # Get required capabilities
        result = await self.session.execute(text("""
            SELECT capability_name, is_optional, status
            FROM goal_required_capabilities
            WHERE goal_id = :goal_id
        """), {'goal_id': goal_id})
        
        required = []
        optional = []
        
        for row in result.fetchall():
            cap_name, is_optional, status = row
            if is_optional:
                optional.append(cap_name)
            else:
                required.append(cap_name)
        
        # Check which are satisfied
        satisfied = []
        missing = []
        
        for cap in required:
            # Check if any skill with this capability exists
            try:
                result = await self.session.execute(text("""
                    SELECT COUNT(*) FROM capability_skills
                    WHERE capability_name = :cap
                """), {'cap': cap})
                
                count = result.scalar() or 0
                if count > 0:
                    satisfied.append(cap)
                else:
                    missing.append(cap)
            except Exception:
                # Table may not exist - assume missing
                missing.append(cap)
        
        return GoalCapabilities(
            goal_id=goal_id,
            required=required,
            optional=optional,
            missing=missing,
            satisfied=satisfied
        )
    
    async def get_unsatisfied_goals(self) -> list[dict]:
        """Возвращает goals с неудовлетворёнными capabilities"""
        result = await self.session.execute(text("""
            SELECT DISTINCT g.id, g.title, grc.capability_name
            FROM goals g
            JOIN goal_required_capabilities grc ON grc.goal_id = g.id
            LEFT JOIN capability_skills cs ON cs.capability_name = grc.capability_name
            WHERE g.status != 'done'
            AND grc.status = 'pending'
            AND cs.capability_name IS NULL
            LIMIT 50
        """))
        
        goals = []
        for row in result.fetchall():
            goals.append({
                'goal_id': str(row[0]),
                'title': row[1],
                'missing_capability': row[2]
            })
        
        return goals
    
    async def satisfy_capability(self, goal_id: UUID, capability: str):
        """Отмечает capability как удовлетворённую"""
        await self.session.execute(text("""
            UPDATE goal_required_capabilities
            SET status = 'satisfied', satisfied_at = NOW()
            WHERE goal_id = :goal_id AND capability_name = :capability
        """), {'goal_id': goal_id, 'capability': capability})
        
        await self.session.commit()
    
    async def get_capability_suggestions(self, text: str) -> list[str]:
        """Предлагает capabilities на основе текста goal"""
        text_lower = text.lower()
        
        # Mapping от текста к capabilities
        suggestions = []
        
        capability_keywords = {
            'sentiment': ['nlp', 'sentiment_analysis', 'text_analysis'],
            'translate': ['nlp', 'translation', 'language'],
            'image': ['computer_vision', 'image_processing'],
            'video': ['video_processing', 'media'],
            'audio': ['speech_recognition', 'audio'],
            'web': ['web_scraping', 'http'],
            'api': ['api_calls', 'integration'],
            'database': ['database', 'sql', 'data'],
            'deploy': ['deployment', 'devops'],
            'build': ['build', 'compilation'],
            'test': ['testing', 'qa'],
            'security': ['security', 'authentication'],
            'email': ['communication', 'email'],
            'chart': ['visualization', 'charts'],
            'pdf': ['document', 'pdf'],
        }
        
        for keyword, caps in capability_keywords.items():
            if keyword in text_lower:
                suggestions.extend(caps)
        
        return list(set(suggestions))
    
    async def get_gap_capabilities(self) -> list[tuple[str, int]]:
        """Возвращает capabilities которые нужны но не существуют"""
        result = await self.session.execute(text("""
            SELECT grc.capability_name, COUNT(*) as goal_count
            FROM goal_required_capabilities grc
            LEFT JOIN capability_skills cs ON cs.capability_name = grc.capability_name
            WHERE cs.capability_name IS NULL
            AND grc.status = 'pending'
            GROUP BY grc.capability_name
            ORDER BY goal_count DESC
            LIMIT 20
        """))
        
        return [(row[0], row[1]) for row in result.fetchall()]


class CapabilityResolver:
    """
    Разрешает capabilities для goals - главный интерфейс.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.graph = CapabilityGraph(session)
    
    async def analyze_goal(self, goal_id: UUID, goal_text: str) -> GoalCapabilities:
        """
        Анализирует goal и устанавливает required capabilities.
        
        1. Предлагает capabilities на основе текста
        2. Сохраняет в базу
        3. Возвращает что удовлетворено
        """
        await self.graph.ensure_tables()
        
        # Предложить capabilities
        suggested = await self.graph.get_capability_suggestions(goal_text)
        
        if suggested:
            # Установить required
            await self.graph.set_goal_requirements(goal_id, suggested)
        
        # Проверить статус
        return await self.graph.check_goal_capabilities(goal_id)
    
    async def resolve(self, goal_id: UUID) -> dict:
        """
        Разрешает goal - проверяет capabilities и блокирует/разблокирует.
        
        Returns:
            dict с status, missing_capabilities, action
        """
        caps = await self.graph.check_goal_capabilities(goal_id)
        
        if caps.missing:
            # Block goal
            await self.session.execute(text("""
                UPDATE goals SET status = 'blocked', updated_at = NOW()
                WHERE id = :goal_id
            """), {'goal_id': goal_id})
            await self.session.commit()
            
            return {
                'status': 'blocked',
                'missing': caps.missing,
                'action': 'wait_for_capabilities'
            }
        else:
            # Unblock goal
            await self.session.execute(text("""
                UPDATE goals SET status = 'pending', updated_at = NOW()
                WHERE id = :goal_id AND status = 'blocked'
            """), {'goal_id': goal_id})
            await self.session.commit()
            
            return {
                'status': 'ready',
                'satisfied': caps.satisfied,
                'action': 'execute'
            }
    
    async def skill_created(self, skill_name: str, capabilities: list[str]):
        """
        Обрабатывает создание нового skill.
        
        1. Регистрирует capabilities
        2. Разблокирует waiting goals
        """
        for cap in capabilities:
            # Register capability
            await self.graph.register_capability(
                name=cap,
                description=f"Auto-registered from skill: {skill_name}",
                category="auto",
                skills=[skill_name]
            )
        
        # Find and unblock goals waiting for these capabilities
        for cap in capabilities:
            # Get goals waiting for this capability
            result = await self.session.execute(text("""
                SELECT grc.goal_id 
                FROM goal_required_capabilities grc
                LEFT JOIN capability_skills cs ON cs.capability_name = grc.capability_name
                WHERE grc.capability_name = :cap
                AND cs.capability_name IS NULL
            """), {'cap': cap})
            
            waiting_goals = [row[0] for row in result.fetchall()]
            
            # Resolve each
            for goal_id in waiting_goals:
                await self.resolve(goal_id)
        
        logger.info(
            "capability_resolved",
            skill_name=skill_name,
            capabilities=capabilities
        )
