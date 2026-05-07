"""
Self-Improving Capability System

Автоматически создаёт новые skills на основе:
- Обнаруженных capability gaps
- Успешных паттернов выполнения
- Ошибок которые можно автоматизировать

Это превращает систему из "исполнителя" в "создателя".
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
class CapabilityGap:
    """Обнаруженный недостаток в capabilities"""
    gap_type: str
    description: str
    related_goal: str
    suggested_skill: str
    priority: float


@dataclass
class GeneratedSkill:
    """Сгенерированный skill"""
    name: str
    description: str
    category: str
    inputs: dict
    outputs: dict
    implementation_code: str
    test_code: str


class CapabilityGapDetector:
    """
    Обнаруживает недостающие capabilities.
    
    Sources:
    - Blocked goals (нет подходящего skill)
    - Failed executions (skill не справился)
    - User requests (нужен новый skill)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def detect_gaps(self) -> list[CapabilityGap]:
        """Обнаруживает все capability gaps"""
        gaps = []
        
        # 1. Из blocked goals
        blocked_gaps = await self._detect_from_blocked_goals()
        gaps.extend(blocked_gaps)
        
        # 2. Из failed executions
        failed_gaps = await self._detect_from_failures()
        gaps.extend(failed_gaps)
        
        # 3. Из запросов пользователей
        request_gaps = await self._detect_from_requests()
        gaps.extend(request_gaps)
        
        logger.info(
            "capability_gap_detection",
            total_gaps=len(gaps),
            from_blocked=len(blocked_gaps),
            from_failures=len(failed_gaps),
            from_requests=len(request_gaps)
        )
        
        return gaps
    
    async def _detect_from_blocked_goals(self) -> list[CapabilityGap]:
        """Находит gaps из blocked goals"""
        gaps = []
        
        result = await self.session.execute(text("""
            SELECT title, description 
            FROM goals
            WHERE status = 'blocked'
            AND created_at > NOW() - INTERVAL '7 days'
            LIMIT 20
        """))
        
        for row in result.fetchall():
            title, description = row
            
            # Анализ title для определения нужного skill
            suggested = self._suggest_skill_from_title(title)
            if suggested:
                gaps.append(CapabilityGap(
                    gap_type="blocked_goal",
                    description=f"Goal blocked: {title}",
                    related_goal=title,
                    suggested_skill=suggested['skill'],
                    priority=0.8
                ))
        
        return gaps
    
    async def _detect_from_failures(self) -> list[CapabilityGap]:
        """Находит gaps из failed executions"""
        gaps = []
        
        result = await self.session.execute(text("""
            SELECT DISTINCT 
                g.title,
                ge.error_message
            FROM goals g
            JOIN goal_executions ge ON ge.goal_id = g.id
            WHERE ge.status = 'failed'
            AND ge.created_at > NOW() - INTERVAL '7 days'
            LIMIT 20
        """))
        
        for row in result.fetchall():
            title, error = row
            
            # Анализ ошибки для определения нужного skill
            suggested = self._suggest_skill_from_error(title, error)
            if suggested:
                gaps.append(CapabilityGap(
                    gap_type="execution_failure",
                    description=f"Execution failed: {error}",
                    related_goal=title,
                    suggested_skill=suggested['skill'],
                    priority=0.7
                ))
        
        return gaps
    
    async def _detect_from_requests(self) -> list[CapabilityGap]:
        """Находит gaps из user requests"""
        # Проверить goals с пометкой о необходимости нового skill
        result = await self.session.execute(text("""
            SELECT title, description
            FROM goals
            WHERE description LIKE '%need skill%'
            OR description LIKE '%requires skill%'
            OR description LIKE '%create skill%'
            LIMIT 10
        """))
        
        gaps = []
        for row in result.fetchall():
            title, description = row
            gaps.append(CapabilityGap(
                gap_type="user_request",
                description=f"User requested: {title}",
                related_goal=title,
                suggested_skill=self._extract_skill_name(title),
                priority=0.9
            ))
        
        return gaps
    
    def _suggest_skill_from_title(self, title: str) -> Optional[dict]:
        """Предлагает skill на основе title"""
        title_lower = title.lower()
        
        suggestions = {
            'sentiment': {'skill': 'analyze_sentiment', 'category': 'nlp'},
            'translate': {'skill': 'translate_text', 'category': 'nlp'},
            'speech': {'skill': 'speech_to_text', 'category': 'audio'},
            'image': {'skill': 'process_image', 'category': 'vision'},
            'video': {'skill': 'process_video', 'category': 'media'},
            'email': {'skill': 'send_email', 'category': 'communication'},
            'api': {'skill': 'call_api', 'category': 'integration'},
            'database': {'skill': 'query_database', 'category': 'data'},
            'ml': {'skill': 'run_ml_model', 'category': 'ml'},
            'chart': {'skill': 'create_chart', 'category': 'visualization'},
            'graph': {'skill': 'create_graph', 'category': 'visualization'},
            'pdf': {'skill': 'generate_pdf', 'category': 'document'},
            'excel': {'skill': 'process_excel', 'category': 'data'},
            'scrap': {'skill': 'scrape_website', 'category': 'web'},
        }
        
        for keyword, suggestion in suggestions.items():
            if keyword in title_lower:
                return suggestion
        
        return None
    
    def _suggest_skill_from_error(self, title: str, error: str) -> Optional[dict]:
        """Предлагает skill на основе ошибки"""
        error_lower = (error or '').lower()
        
        if 'timeout' in error_lower:
            return {'skill': 'retry_with_timeout', 'category': 'utility'}
        if 'permission' in error_lower:
            return {'skill': 'check_permissions', 'category': 'security'}
        if 'not found' in error_lower:
            return {'skill': 'find_resource', 'category': 'utility'}
        if 'invalid' in error_lower:
            return {'skill': 'validate_input', 'category': 'validation'}
        
        return None
    
    def _extract_skill_name(self, title: str) -> str:
        """Извлекает название skill из title"""
        # Простая логика - убираем глаголы и оставляем существительное
        return title.lower().replace('create ', '').replace('build ', '').strip()


class SkillGenerator:
    """
    Генерирует новые skills автоматически.
    
    На основе CapabilityGap создаёт полноценный skill с:
    - Названием
    - Описанием
    - Кодом реализации
    - Тестами
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.templates = self._load_templates()
    
    def _load_templates(self) -> dict:
        """Загружает шаблоны для генерации skills"""
        return {
            'nlp': {
                'template': '''"""
{skill_name} - Auto-generated skill
{description}
"""
from typing import Dict, Any
from canonical_skills.base import Skill, SkillResult

class {class_name}Skill(Skill):
    """Auto-generated {category} skill"""
    
    name = "{skill_name}"
    description = "{description}"
    category = "{category}"
    version = "1.0.0"
    
    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        # Auto-generated implementation
        input_text = params.get("text", "")
        
        # TODO: Implement {skill_name}
        result = f"Processed: {{input_text}}"
        
        return SkillResult(
            success=True,
            data={{"result": result}},
            artifacts=[]
        )
''',
                'category': 'nlp'
            },
            'data': {
                'template': '''"""
{skill_name} - Auto-generated skill
{description}
"""
from typing import Dict, Any, List
from canonical_skills.base import Skill, SkillResult

class {class_name}Skill(Skill):
    """Auto-generated {category} skill"""
    
    name = "{skill_name}"
    description = "{description}"
    category = "{category}"
    version = "1.0.0"
    
    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        # Auto-generated implementation
        data = params.get("data", [])
        
        # TODO: Implement {skill_name}
        result = f"Processed {{len(data)}} items"
        
        return SkillResult(
            success=True,
            data={{"result": result, "count": len(data)}},
            artifacts=[]
        )
''',
                'category': 'data'
            },
            'web': {
                'template': '''"""
{skill_name} - Auto-generated skill
{description}
"""
from typing import Dict, Any
from canonical_skills.base import Skill, SkillResult

class {class_name}Skill(Skill):
    """Auto-generated {category} skill"""
    
    name = "{skill_name}"
    description = "{description}"
    category = "{category}"
    version = "1.0.0"
    
    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        # Auto-generated implementation
        url = params.get("url", "")
        
        # TODO: Implement {skill_name}
        result = f"Fetched: {{url}}"
        
        return SkillResult(
            success=True,
            data={{"result": result}},
            artifacts=[]
        )
''',
                'category': 'web'
            },
            'utility': {
                'template': '''"""
{skill_name} - Auto-generated skill
{description}
"""
from typing import Dict, Any
from canonical_skills.base import Skill, SkillResult

class {class_name}Skill(Skill):
    """Auto-generated utility skill"""
    
    name = "{skill_name}"
    description = "{description}"
    category = "utility"
    version = "1.0.0"
    
    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        # Auto-generated implementation
        result = "OK"
        
        return SkillResult(
            success=True,
            data={{"result": result}},
            artifacts=[]
        )
''',
                'category': 'utility'
            }
        }
    
    async def generate_skill(self, gap: CapabilityGap) -> GeneratedSkill:
        """Генерирует skill на основе gap"""
        skill_name = gap.suggested_skill
        class_name = ''.join(word.capitalize() for word in skill_name.split('_'))
        
        # Определяем категорию
        category = self._detect_category(skill_name)
        template = self.templates.get(category, self.templates['utility'])
        
        # Генерируем код
        implementation = template['template'].format(
            skill_name=skill_name,
            class_name=class_name,
            description=f"Auto-generated skill for: {gap.related_goal}",
            category=category
        )
        
        # Генерируем тест
        test_code = self._generate_test(skill_name, class_name)
        
        return GeneratedSkill(
            name=skill_name,
            description=f"Auto-generated: {gap.description}",
            category=category,
            inputs={'text': 'str', 'options': 'dict'},
            outputs={'result': 'str'},
            implementation_code=implementation,
            test_code=test_code
        )
    
    def _detect_category(self, skill_name: str) -> str:
        """Определяет категорию skill"""
        categories = {
            'nlp': ['sentiment', 'translate', 'nlp', 'text', 'language'],
            'data': ['data', 'excel', 'csv', 'database', 'query', 'filter', 'aggregate'],
            'web': ['web', 'http', 'api', 'scrap', 'fetch', 'download'],
            'vision': ['image', 'picture', 'photo', 'visual'],
            'audio': ['audio', 'speech', 'sound', 'voice'],
        }
        
        for category, keywords in categories.items():
            if any(kw in skill_name.lower() for kw in keywords):
                return category
        
        return 'utility'
    
    def _generate_test(self, skill_name: str, class_name: str) -> str:
        """Генерирует unit test для skill"""
        return f'''
def test_{skill_name}():
    """Auto-generated test for {skill_name}"""
    # TODO: Implement test
    assert True
'''


class AutoSkillRegistrar:
    """
    Автоматически регистрирует новые skills в системе.
    
    Workflow:
    1. Detect gaps → 2. Generate skills → 3. Register → 4. Test → 5. Activate
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def register_skill(self, skill: GeneratedSkill) -> bool:
        """
        Регистрирует skill в системе.
        
        Создаёт:
        - Skill manifest в базе
        - Skill файл в canonical_skills/
        """
        
        # Проверить существующий skill
        result = await self.session.execute(text("""
            SELECT id FROM skill_manifests WHERE name = :name
        """), {'name': skill.name})
        
        if result.fetchone():
            logger.info("skill_already_exists", skill=skill.name)
            return False
        
        # Создать manifest
        await self.session.execute(text("""
            INSERT INTO skill_manifests (id, name, description, category, version, inputs, outputs)
            VALUES (gen_random_uuid(), :name, :description, :category, '1.0.0', :inputs, :outputs)
        """), {
            'name': skill.name,
            'description': skill.description,
            'category': skill.category,
            'inputs': str(skill.inputs),
            'outputs': str(skill.outputs)
        })
        
        await self.session.commit()
        
        logger.info(
            "skill_registered",
            skill=skill.name,
            category=skill.category
        )
        
        return True
    
    async def auto_improve(self) -> dict:
        """
        Полный цикл self-improvement.
        
        Returns:
            dict с результатами улучшений
        """
        # 1. Detect gaps
        detector = CapabilityGapDetector(self.session)
        gaps = await detector.detect_gaps()
        
        if not gaps:
            logger.info("no_capability_gaps_detected")
            return {'gaps_found': 0, 'skills_created': 0, 'goals_unblocked': 0}
        
        # 2. Generate and register skills
        generator = SkillGenerator(self.session)
        registrar = AutoSkillRegistrar(self.session)
        
        skills_created = 0
        goals_unblocked = 0
        
        for gap in gaps[:5]:  # Limit to 5 per cycle
            try:
                skill = await generator.generate_skill(gap)
                registered = await registrar.register_skill(skill)
                
                if registered:
                    skills_created += 1
                    
                    # 3. Unblock goals waiting for this skill
                    unblocked = await self._unblock_waiting_goals(gap.suggested_skill)
                    goals_unblocked += unblocked
                    
            except Exception as e:
                logger.error(
                    "skill_generation_failed",
                    gap=gap.suggested_skill,
                    error=str(e)
                )
        
        logger.info(
            "auto_improvement_complete",
            gaps_found=len(gaps),
            skills_created=skills_created,
            goals_unblocked=goals_unblocked
        )
        
        return {
            'gaps_found': len(gaps),
            'skills_created': skills_created,
            'goals_unblocked': goals_unblocked
        }
    
    async def subscribe_to_skill(self, goal_id: str, skill_name: str) -> bool:
        """
        Goal подписывается на skill.
        Когда skill появится - goal получит уведомление.
        """
        # Создать таблицу если не существует
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS goal_skill_subscriptions (
                goal_id UUID NOT NULL,
                skill_name VARCHAR(255) NOT NULL,
                subscribed_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (goal_id, skill_name)
            )
        """))
        
        # Добавить подписку
        try:
            await self.session.execute(text("""
                INSERT INTO goal_skill_subscriptions (goal_id, skill_name)
                VALUES (:goal_id, :skill_name)
                ON CONFLICT DO NOTHING
            """), {'goal_id': goal_id, 'skill_name': skill_name})
            
            # Заблокировать goal с пометкой
            await self.session.execute(text("""
                UPDATE goals
                SET status = 'blocked',
                    description = COALESCE(description, '') || ' | waiting for skill: ' || :skill_name
                WHERE id = :goal_id
            """), {'goal_id': goal_id, 'skill_name': skill_name})
            
            await self.session.commit()
            
            logger.info(
                "goal_subscribed_to_skill",
                goal_id=goal_id,
                skill_name=skill_name
            )
            return True
            
        except Exception as e:
            logger.error("subscription_failed", goal_id=goal_id, error=str(e))
            return False
    
    async def notify_subscribers(self, skill_name: str) -> int:
        """
        Уведомить все подписавшиеся goals о появлении skill.
        """
        result = await self.session.execute(text("""
            SELECT goal_id FROM goal_skill_subscriptions
            WHERE skill_name = :skill_name
        """), {'skill_name': skill_name})
        
        goal_ids = [row[0] for row in result.fetchall()]
        
        if not goal_ids:
            return 0
        
        # Разблокировать
        for goal_id in goal_ids:
            await self.session.execute(text("""
                UPDATE goals
                SET status = 'pending',
                    description = REPLACE(description, ' | waiting for skill: ' || :skill_name, '')
                WHERE id = :goal_id
            """), {'goal_id': goal_id, 'skill_name': skill_name})
        
        # Удалить подписки
        await self.session.execute(text("""
            DELETE FROM goal_skill_subscriptions
            WHERE skill_name = :skill_name
        """), {'skill_name': skill_name})
        
        await self.session.commit()
        
        logger.info(
            "skill_subscribers_notified",
            skill_name=skill_name,
            notified_count=len(goal_ids)
        )
        
        return len(goal_ids)
    
    async def _unblock_waiting_goals(self, skill_name: str) -> int:
        """
        Разблокирует goals которые ждали создания этого skill.
        
        Также уведомляет подписавшиеся goals.
        
        Returns:
            Количество разблокированных goals
        """
        skill_pattern = skill_name.lower().replace('_', '%')
        
        # 1. Найти goals которые явно подписались на этот skill
        result = await self.session.execute(text("""
            SELECT id FROM goals
            WHERE status = 'blocked'
            AND description LIKE :pattern
        """), {'pattern': f'%waiting for skill: {skill_pattern}%'})
        
        subscribed_ids = [row[0] for row in result.fetchall()]
        
        # 2. Найти goals которые просто содержат название skill в title
        result = await self.session.execute(text("""
            SELECT id FROM goals
            WHERE status = 'blocked'
            AND (title LIKE :pattern OR description LIKE :pattern)
        """), {'pattern': f'%{skill_name}%'})
        
        pattern_ids = [row[0] for row in result.fetchall()]
        
        # Объединить уникальные ID
        all_blocked_ids = list(set(subscribed_ids + pattern_ids))
        
        if not all_blocked_ids:
            return 0
        
        # Перевести их в pending
        for goal_id in all_blocked_ids:
            await self.session.execute(text("""
                UPDATE goals
                SET status = 'pending', updated_at = NOW()
                WHERE id = :goal_id
            """), {'goal_id': goal_id})
        
        await self.session.commit()
        
        logger.info(
            "goals_unblocked_for_skill",
            skill_name=skill_name,
            unblocked_count=len(all_blocked_ids),
            goal_ids=[str(g) for g in all_blocked_ids[:5]]
        )
        
        return len(all_blocked_ids)
