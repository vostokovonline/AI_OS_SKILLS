"""
Skill Input Generator

Преобразует goal description в inputs для skill.
Это ключевой компонент для работы pipeline:
goal → skill_input → skill → artifact
"""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


class SkillInputGenerator:
    """
    Генерирует inputs для skills на основе goal.
    
    Поддерживает:
    1. Keyword-based - по ключевым словам в description
    2. LLM-based - через LLM (если доступен)
    3. Template-based - по шаблонам
    """
    
    # Keyword → Skill → Default inputs mapping
    KEYWORD_SKILL_MAP = {
        'echo': {'skill': 'core.echo', 'inputs': {'text': '{description}'}},
        'write': {'skill': 'core.write_file', 'inputs': {'content': '{description}', 'path': '/tmp/output.txt'}},
        'file': {'skill': 'core.file_read', 'inputs': {'path': '/tmp/input.txt'}},
        'read': {'skill': 'core.file_read', 'inputs': {'path': '/tmp/input.txt'}},
        'list': {'skill': 'core.file_list', 'inputs': {'path': '.'}},
        'search': {'skill': 'core.file_search', 'inputs': {'query': '{title}', 'path': '.'}},
        'command': {'skill': 'core.run_command', 'inputs': {'command': 'echo test'}},
        'run': {'skill': 'core.run_command', 'inputs': {'command': 'echo test'}},
        'summarize': {'skill': 'core.summarize_text', 'inputs': {'text': '{description}'}},
        'analyze': {'skill': 'core.analyze_text', 'inputs': {'text': '{description}'}},
        'research': {'skill': 'core.web_research', 'inputs': {'query': '{title}'}},
        'web': {'skill': 'core.web_research', 'inputs': {'query': '{title}'}},
        'create directory': {'skill': 'core.create_directory', 'inputs': {'path': '/tmp/new_dir'}},
        'directory': {'skill': 'core.create_directory', 'inputs': {'path': '/tmp/new_dir'}},
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_skill_input(self, goal_id: UUID) -> dict:
        """
        Генерирует skill input для goal.
        
        Returns:
            dict с skill_name и inputs
        """
        # Get goal info
        result = await self.session.execute(text("""
            SELECT title, description, goal_type
            FROM goals
            WHERE id = :goal_id
        """), {'goal_id': goal_id})
        
        row = result.fetchone()
        if not row:
            return None
        
        title, description, goal_type = row
        
        # Combine title and description
        text_input = f"{title}. {description or ''}"
        
        # Try keyword-based matching
        skill_input = self._keyword_based_input(text_input, title)
        
        if skill_input:
            logger.info(
                "skill_input_generated",
                goal_id=str(goal_id),
                skill=skill_input['skill_name']
            )
            return skill_input
        
        # Fallback: use echo with goal text
        return {
            'skill_name': 'core.echo',
            'inputs': {'text': text_input[:1000]}
        }
    
    def _keyword_based_input(self, text: str, title: str) -> dict:
        """Поиск по ключевым словам"""
        text_lower = text.lower()
        
        for keyword, config in self.KEYWORD_SKILL_MAP.items():
            if keyword in text_lower:
                inputs = {}
                for key, value in config['inputs'].items():
                    # Replace placeholders
                    if '{description}' in value:
                        value = value.replace('{description}', text[:500])
                    if '{title}' in value:
                        value = value.replace('{title}', title[:100])
                    inputs[key] = value
                
                return {
                    'skill_name': config['skill'],
                    'inputs': inputs
                }
        
        return None


class SkillInputEnricher:
    """
    Обогащает skill inputs дополнительными данными.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def enrich_goal_inputs(self, goal_id: UUID, skill_name: str, inputs: dict) -> dict:
        """
        Обогащает inputs контекстом из goal.
        """
        # Get goal context
        result = await self.session.execute(text("""
            SELECT title, description, domains, user_id
            FROM goals
            WHERE id = :goal_id
        """), {'goal_id': goal_id})
        
        row = result.fetchone()
        if row:
            title, description, domains, user_id = row
            
            # Add context
            inputs['_context'] = {
                'goal_id': str(goal_id),
                'title': title,
                'domains': domains or []
            }
        
        return inputs


class GoalSkillMatcher:
    """
    Определяет какой skill нужен для goal.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def match_skill(self, goal_id: UUID) -> dict:
        """
        Находит лучший skill для goal.
        
        Returns:
            dict с skill_name и inputs
        """
        # Generate inputs
        generator = SkillInputGenerator(self.session)
        return await generator.generate_skill_input(goal_id)
