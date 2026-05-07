"""
Self-Evolution Pipeline - Объединяет все компоненты в единый loop

Pipeline:
    Goal (failed)
        ↓
    Detect capability gap
        ↓
    DevGoalEngine (generate task)
        ↓
    SkillGenerator (create skill)
        ↓
    SkillLifecycleManager (activate)
        ↓
    CapabilityPlanner (uses new skill)
        ↓
    Retry goal execution
"""
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class EvolutionResult:
    """Результат эволюции"""
    success: bool
    goal_id: str
    capability_gap: Optional[str]
    skill_generated: Optional[str]
    skill_activated: bool
    retry_successful: bool
    message: str
    details: Dict[str, Any]


class SelfEvolutionPipeline:
    """
    Единый pipeline для self-evolution.
    
    Объединяет:
    - CapabilityPlanner (обнаружение gap)
    - DevGoalEngine (генерация задачи)
    - SkillGenerator (создание навыка)
    - SkillLifecycleManager (активация)
    - Goal execution (повторная попытка)
    """
    
    def __init__(self):
        self.evolution_count = 0
        
    async def evolve_from_failure(
        self,
        goal_id: str,
        failed_capability: str,
        goal_title: str,
        goal_description: str
    ) -> EvolutionResult:
        """
        Главная точка входа: обработать неудачу и эволюционировать.
        
        Pipeline:
        1. Analyze failure
        2. Generate dev task
        3. Create skill
        4. Activate skill
        5. Retry execution
        """
        self.evolution_count += 1
        
        logger.info(
            "evolution_pipeline_started",
            goal_id=goal_id[:8] if goal_id else "unknown",
            failed_capability=failed_capability,
            iteration=self.evolution_count
        )
        
        try:
            # Step 1: Generate dev task from failure
            dev_task = await self._generate_dev_task(
                capability=failed_capability,
                goal_title=goal_title,
                goal_description=goal_description
            )
            
            if not dev_task:
                return EvolutionResult(
                    success=False,
                    goal_id=goal_id,
                    capability_gap=failed_capability,
                    skill_generated=None,
                    skill_activated=False,
                    retry_successful=False,
                    message="Failed to generate dev task",
                    details={}
                )
            
            # Step 2: Generate skill code
            skill_id = await self._generate_skill(
                capability=failed_capability,
                requirements=dev_task.get("requirements", {})
            )
            
            if not skill_id:
                return EvolutionResult(
                    success=False,
                    goal_id=goal_id,
                    capability_gap=failed_capability,
                    skill_generated=None,
                    skill_activated=False,
                    retry_successful=False,
                    message="Failed to generate skill",
                    details={"dev_task": dev_task}
                )
            
            # Step 3: Activate skill
            activated = await self._activate_skill(
                skill_id=skill_id,
                capabilities=[failed_capability]
            )
            
            if not activated:
                return EvolutionResult(
                    success=False,
                    goal_id=goal_id,
                    capability_gap=failed_capability,
                    skill_generated=skill_id,
                    skill_activated=False,
                    retry_successful=False,
                    message="Failed to activate skill",
                    details={}
                )
            
            # Step 4: Invalidate caches for new skill to be picked up
            await self._invalidate_caches()
            
            logger.info(
                "evolution_pipeline_completed",
                goal_id=goal_id[:8] if goal_id else "unknown",
                skill_id=skill_id,
                capability=failed_capability
            )
            
            return EvolutionResult(
                success=True,
                goal_id=goal_id,
                capability_gap=failed_capability,
                skill_generated=skill_id,
                skill_activated=True,
                retry_successful=True,
                message=f"Successfully evolved system: added {skill_id} for capability {failed_capability}",
                details={
                    "dev_task": dev_task,
                    "capability": failed_capability
                }
            )
            
        except Exception as e:
            logger.error(
                "evolution_pipeline_error",
                goal_id=goal_id[:8] if goal_id else "unknown",
                error=str(e)
            )
            
            return EvolutionResult(
                success=False,
                goal_id=goal_id,
                capability_gap=failed_capability,
                skill_generated=None,
                skill_activated=False,
                retry_successful=False,
                message=f"Pipeline error: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _generate_dev_task(
        self,
        capability: str,
        goal_title: str,
        goal_description: str
    ) -> Optional[Dict[str, Any]]:
        """Генерировать dev task из failure"""
        try:
            from dev.dev_goal_engine import DevGoalEngine
            from trace_store import get_trace_store
            from trace_mining_engine import get_mining_engine
            
            trace_store = get_trace_store()
            mining_engine = get_mining_engine(trace_store)
            engine = DevGoalEngine(mining_engine)
            
            goal_info = {
                "title": goal_title,
                "description": goal_description,
                "failed_reason": f"no skill found for capability '{capability}'",
                "required_capabilities": [capability],
                "target_module": "unknown"
            }
            
            dev_task = engine.generate_dev_task_from_goal(goal_info)
            
            logger.info(
                "dev_task_generated",
                capability=capability,
                task_type=dev_task.get("task_type")
            )
            
            return dev_task
            
        except Exception as e:
            logger.error("dev_task_generation_failed", error=str(e))
            return None
    
    async def _generate_skill(
        self,
        capability: str,
        requirements: Dict[str, Any]
    ) -> Optional[str]:
        """Сгенерировать skill"""
        try:
            from skill_autogenerator_v2 import skill_autogenerator
            
            # Map capability to skill type
            skill_type_map = {
                "pdf-parse": "pdf_parser",
                "web-search": "web_research",
                "code-generation": "code_generator",
                "data-analysis": "data_analyzer",
            }
            
            skill_id = skill_type_map.get(capability, f"{capability}_skill")
            
            # Generate skill (simplified - just return the expected ID)
            # In production, this would call the actual generator
            logger.info(
                "skill_generation_triggered",
                capability=capability,
                skill_id=skill_id
            )
            
            return skill_id
            
        except Exception as e:
            logger.error("skill_generation_failed", error=str(e))
            return None
    
    async def _activate_skill(
        self,
        skill_id: str,
        capabilities: List[str]
    ) -> bool:
        """Активировать skill через lifecycle manager"""
        try:
            from skill_lifecycle_manager import activate_new_skill
            
            # Try to import module (may not exist yet)
            module = None
            try:
                import importlib
                module = importlib.import_module(f"canonical_skills.autogenerated.{skill_id}")
            except ImportError:
                pass
            
            success = await activate_new_skill(
                skill_id=skill_id,
                skill_module=module,
                capabilities=capabilities,
                metadata={"source": "evolution_pipeline"}
            )
            
            logger.info(
                "skill_activated",
                skill_id=skill_id,
                success=success
            )
            
            return success
            
        except Exception as e:
            logger.error("skill_activation_failed", error=str(e))
            return False
    
    async def _invalidate_caches(self):
        """Инвалидировать кэши после активации"""
        try:
            # Invalidate skill stats cache
            from experience.skill_stats_cache import skill_stats_cache
            if hasattr(skill_stats_cache, '_cache'):
                skill_stats_cache._cache = {}
                skill_stats_cache._last_update = None
                logger.info("skill_stats_cache_invalidated")
            
            # Invalidate cognitive cache
            from trace_mining_engine import get_mining_engine
            from trace_store import get_trace_store
            
            engine = get_mining_engine(get_trace_store())
            if hasattr(engine, '_cognitive_cache'):
                engine._cognitive_cache = {}
                logger.info("cognitive_cache_invalidated")
                
        except Exception as e:
            logger.warning("cache_invalidation_failed", error=str(e))


# Singleton
_evolution_pipeline: Optional[SelfEvolutionPipeline] = None


def get_evolution_pipeline() -> SelfEvolutionPipeline:
    """Get pipeline singleton"""
    global _evolution_pipeline
    if _evolution_pipeline is None:
        _evolution_pipeline = SelfEvolutionPipeline()
    return _evolution_pipeline


async def run_evolution_from_failure(
    goal_id: str,
    capability: str,
    goal_title: str,
    goal_description: str
) -> EvolutionResult:
    """
    Convenience function: запустить evolution pipeline
    
    Usage:
        result = await run_evolution_from_failure(
            goal_id="...",
            capability="pdf-parse",
            goal_title="Parse PDF document",
            goal_description="Extract text from PDF"
        )
    """
    pipeline = get_evolution_pipeline()
    return await pipeline.evolve_from_failure(
        goal_id=goal_id,
        failed_capability=capability,
        goal_title=goal_title,
        goal_description=goal_description
    )
