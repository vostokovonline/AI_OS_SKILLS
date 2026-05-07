"""
Unified Skill Service
=====================
Single Source of Truth for Skills in AI-OS

Flow:
canonical_skills/*.py → SkillLoader → SKILL_REGISTRY + DB

This unifies:
- Autoloader (canonical_skills)
- Skill Router (execution)
- Database (skill_manifests)

Author: Claude
Date: 2026-03-03
"""

import os
import importlib
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from logging_config import get_logger
from dataclasses import dataclass

logger = get_logger(__name__)


@dataclass
class UnifiedSkill:
    """Unified skill representation"""
    name: str
    version: str
    description: str
    category: str
    capabilities: List[str]
    contracts: Dict[str, Any]
    handler: Optional[Callable] = None
    skill_class: Optional[Any] = None
    source_file: str = ""


class UnifiedSkillService:
    """
    Single Source of Truth for Skills.
    
    Loads from canonical_skills, registers in Router,
    optionally syncs to DB.
    """
    
    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            current_dir = Path(__file__).parent
            skills_dir = current_dir / "canonical_skills"
        
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, UnifiedSkill] = {}
        
    def load_all(self) -> int:
        """Load all skills from canonical_skills"""
        loaded = 0
        
        for py_file in self.skills_dir.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name in ["base.py", "registry.py"]:
                continue
            
            try:
                module_name = f"canonical_skills.{py_file.stem}"
                module = importlib.import_module(module_name)
                
                # Find Skill classes
                skills_found = self._extract_skills(module, py_file.stem)
                
                for name, skill in skills_found.items():
                    self.skills[name] = skill
                    loaded += 1
                    logger.info("skill_loaded", skill=name, file=py_file.name)
                    
            except Exception as e:
                logger.warning("skill_load_failed", file=py_file.name, error=str(e)[:100])
                
        logger.info("skills_loading_complete", total=loaded)
        return loaded
    
    def _extract_skills(self, module, filename: str) -> Dict[str, UnifiedSkill]:
        """Extract skills from module"""
        skills = {}
        
        # Look for Skill classes
        for attr_name in dir(module):
            if attr_name.endswith("Skill") and not attr_name.startswith("_"):
                cls = getattr(module, attr_name)
                
                if not hasattr(cls, 'execute'):
                    continue
                    
                skill = UnifiedSkill(
                    name=getattr(cls, 'id', attr_name.lower()),
                    version=getattr(cls, 'version', '1.0.0'),
                    description=getattr(cls, 'description', ''),
                    category=getattr(cls, '__module__', 'general').split('.')[-1],
                    capabilities=getattr(cls, 'capabilities', []),
                    contracts={
                        'max_time': 30,
                        'max_memory': '64MB',
                        'max_tokens': 1000
                    },
                    skill_class=cls,
                    source_file=filename
                )
                
                # Clean name (remove core. prefix)
                skill.name = skill.name.replace('core.', '')
                
                skills[skill.name] = skill
                
        return skills
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all skills as dict list"""
        return [
            {
                "skill_id": s.name,
                "version": s.version,
                "description": s.description,
                "category": s.category,
                "capabilities": s.capabilities,
                "contracts": s.contracts,
                "source": s.source_file
            }
            for s in self.skills.values()
        ]
    
    def get(self, name: str) -> Optional[UnifiedSkill]:
        """Get skill by name"""
        return self.skills.get(name)
    
    def register_in_router(self):
        """Register all skills in Skill Router"""
        from skill_router import create_skill
        
        for name, skill in self.skills.items():
            # Determine routing based on category
            if skill.category in ['test', 'echo']:
                routing_mode = "static"
                static_model = "local-coder"
            else:
                routing_mode = "dynamic"
                static_model = None
                
            create_skill(
                name=name,
                description=skill.description,
                goal_type="precise_reasoning",
                preferred_models=["local-coder", "deepseek-reasoner"],
                max_tokens=skill.contracts.get('max_tokens', 1000),
                timeout_sec=skill.contracts.get('max_time', 30),
                routing_mode=routing_mode,
                static_model=static_model,
                auto_register=True
            )
            
        logger.info("skills_registered_in_router", count=len(self.skills))


# Global instance
unified_skill_service = UnifiedSkillService()


def load_and_register_skills():
    """Load skills and register in router"""
    count = unified_skill_service.load_all()
    unified_skill_service.register_in_router()
    return count
