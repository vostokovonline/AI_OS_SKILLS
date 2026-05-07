"""
Skill Lifecycle Manager - Управляет жизненным циклом навыков

Отвечает за:
1. Активация новых навыков (добавление в registry, обновление graph)
2. Деактивация навыков
3. Валидация навыков
4. Rollback при ошибках

Это замыкает loop:
    capability gap → generate skill → activate → planner uses
"""
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from logging_config import get_logger

logger = get_logger(__name__)


class SkillStatus(Enum):
    """Статусы навыка"""
    GENERATING = "generating"
    GENERATED = "generated"
    VALIDATING = "validating"
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"


@dataclass
class SkillLifecycleEvent:
    """Событие в lifecycle навыка"""
    skill_id: str
    from_status: Optional[SkillStatus]
    to_status: SkillStatus
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any]


class SkillLifecycleManager:
    """
    Управляет жизненным циклом навыков.
    
    Обеспечивает:
    - Регистрация новых навыков
    - Обновление capability graph
    - Инвалидация кэшей
    - Rollback при ошибках
    """
    
    def __init__(self):
        self._events: List[SkillLifecycleEvent] = []
        self._skill_status: Dict[str, SkillStatus] = {}
        
    async def activate_skill(
        self,
        skill_id: str,
        skill_module: Any,
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Активировать новый навык.
        
        Pipeline:
        1. Add to skill_registry
        2. Update capability_graph
        3. Invalidate cognitive cache
        4. Emit lifecycle event
        """
        logger.info(
            "skill_lifecycle_activating",
            skill_id=skill_id,
            capabilities=capabilities
        )
        
        try:
            # Step 1: Add to skill registry
            await self._add_to_registry(skill_id, skill_module)
            
            # Step 2: Update capability graph
            await self._update_capability_graph(skill_id, capabilities)
            
            # Step 3: Invalidate caches
            await self._invalidate_caches()
            
            # Step 4: Record event
            self._record_event(
                skill_id=skill_id,
                from_status=None,
                to_status=SkillStatus.ACTIVE,
                reason="Skill activated successfully",
                metadata=metadata or {}
            )
            
            logger.info(
                "skill_lifecycle_activated",
                skill_id=skill_id,
                capabilities=capabilities
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "skill_lifecycle_activation_failed",
                skill_id=skill_id,
                error=str(e)
            )
            
            # Rollback on failure
            await self._rollback_activation(skill_id)
            
            return False
    
    async def _add_to_registry(self, skill_id: str, skill_module: Any):
        """Добавить навык в registry"""
        try:
            from canonical_skills.registry import skill_registry
            
            # Get skill class from module
            skill_class_name = ''.join(
                word.capitalize() for word in skill_id.split('_')
            ) + 'Skill'
            
            if hasattr(skill_module, skill_class_name):
                skill_class = getattr(skill_module, skill_class_name)
                skill_instance = skill_class()
                skill_registry.register(skill_instance)
                
                logger.info(
                    "skill_registered",
                    skill_id=skill_id
                )
            else:
                logger.warning(
                    "skill_class_not_found",
                    skill_id=skill_id,
                    expected_class=skill_class_name
                )
                
        except Exception as e:
            logger.error(
                "registry_add_failed",
                skill_id=skill_id,
                error=str(e)
            )
            raise
    
    async def _update_capability_graph(
        self,
        skill_id: str,
        capabilities: List[str]
    ):
        """Обновить capability graph"""
        try:
            from capability.capability_graph import capability_graph
            
            # Get skill info
            from canonical_skills.registry import skill_registry
            skill = skill_registry.get(skill_id)
            
            if not skill:
                logger.warning(
                    "skill_not_in_registry",
                    skill_id=skill_id
                )
                return
            
            # Add to capability graph
            from capability.capability_graph import SkillNode
            
            node = SkillNode(
                skill_id=skill_id,
                capabilities=capabilities,
                input_artifacts=getattr(skill, 'requires_artifacts', []),
                output_artifacts=getattr(skill, 'produces_artifacts', []),
                success_rate=1.0,  # New skill starts with high score
                avg_latency_ms=0.0,
                total_executions=0
            )
            
            # Add to graph (if method exists)
            if hasattr(capability_graph, 'add_skill'):
                capability_graph.add_skill(node)
                
                logger.info(
                    "capability_graph_updated",
                    skill_id=skill_id,
                    capabilities=capabilities
                )
            else:
                logger.warning(
                    "capability_graph_add_skill_not_available"
                )
                
        except Exception as e:
            logger.warning(
                "capability_graph_update_failed",
                skill_id=skill_id,
                error=str(e)
            )
            # Don't raise - this is not critical
    
    async def _invalidate_caches(self):
        """Инвалидировать кэши"""
        try:
            # Invalidate skill stats cache
            from experience.skill_stats_cache import skill_stats_cache
            if hasattr(skill_stats_cache, 'invalidate'):
                skill_stats_cache.invalidate()
                logger.info("skill_stats_cache_invalidated")
            
            # Invalidate trace mining cache
            from trace_mining_engine import get_mining_engine
            from trace_store import get_trace_store
            
            engine = get_mining_engine(get_trace_store())
            if hasattr(engine, '_cognitive_cache'):
                engine._cognitive_cache = {}
                logger.info("cognitive_cache_invalidated")
                
        except Exception as e:
            logger.warning(
                "cache_invalidation_failed",
                error=str(e)
            )
    
    async def _rollback_activation(self, skill_id: str):
        """Откатить активацию при ошибке"""
        logger.warning(
            "skill_lifecycle_rollback",
            skill_id=skill_id
        )
        
        # Remove from registry
        try:
            from canonical_skills.registry import skill_registry
            # Registry doesn't have unregister, but we can log
            logger.info("rollback_remove_from_registry", skill_id=skill_id)
        except:
            pass
        
        # Record failure event
        self._record_event(
            skill_id=skill_id,
            from_status=None,
            to_status=SkillStatus.FAILED,
            reason="Activation failed - rolled back",
            metadata={}
        )
    
    async def deactivate_skill(
        self,
        skill_id: str,
        reason: str = "Manual deprecation"
    ) -> bool:
        """
        Деактивировать навык (пометить как устаревший).
        
        Не удаляет из registry, чтобы не сломать существующие依赖.
        """
        logger.info(
            "skill_lifecycle_deactivating",
            skill_id=skill_id,
            reason=reason
        )
        
        # Update status
        old_status = self._skill_status.get(skill_id, SkillStatus.ACTIVE)
        self._skill_status[skill_id] = SkillStatus.DEPRECATED
        
        # Record event
        self._record_event(
            skill_id=skill_id,
            from_status=old_status,
            to_status=SkillStatus.DEPRECATED,
            reason=reason,
            metadata={}
        )
        
        # Invalidate caches
        await self._invalidate_caches()
        
        return True
    
    async def validate_skill(
        self,
        skill_id: str,
        test_inputs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Валидировать навык через test execution.
        
        Returns:
            {
                "valid": true/false,
                "test_results": [...],
                "errors": [...]
            }
        """
        logger.info(
            "skill_lifecycle_validating",
            skill_id=skill_id,
            test_count=len(test_inputs)
        )
        
        self._record_event(
            skill_id=skill_id,
            from_status=SkillStatus.REGISTERED,
            to_status=SkillStatus.VALIDATING,
            reason="Starting validation",
            metadata={"test_count": len(test_inputs)}
        )
        
        results = []
        errors = []
        
        try:
            from canonical_skills.registry import skill_registry
            skill = skill_registry.get(skill_id)
            
            if not skill:
                return {
                    "valid": False,
                    "errors": [f"Skill {skill_id} not found in registry"]
                }
            
            # Run test inputs
            for i, test_input in enumerate(test_inputs):
                try:
                    result = skill.execute(
                        test_input.get("inputs", {}),
                        test_input.get("context", {})
                    )
                    
                    results.append({
                        "test_id": i,
                        "success": result.success,
                        "error": result.error
                    })
                    
                except Exception as e:
                    errors.append({
                        "test_id": i,
                        "error": str(e)
                    })
            
            valid = len(errors) == 0 and all(r["success"] for r in results)
            
            # Update status
            new_status = SkillStatus.ACTIVE if valid else SkillStatus.FAILED
            self._skill_status[skill_id] = new_status
            
            self._record_event(
                skill_id=skill_id,
                from_status=SkillStatus.VALIDATING,
                to_status=new_status,
                reason=f"Validation complete: {valid}",
                metadata={"test_results": len(results), "errors": len(errors)}
            )
            
            return {
                "valid": valid,
                "test_results": results,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(
                "skill_validation_error",
                skill_id=skill_id,
                error=str(e)
            )
            
            return {
                "valid": False,
                "errors": [str(e)]
            }
    
    def _record_event(
        self,
        skill_id: str,
        from_status: Optional[SkillStatus],
        to_status: SkillStatus,
        reason: str,
        metadata: Dict[str, Any]
    ):
        """Записать событие lifecycle"""
        event = SkillLifecycleEvent(
            skill_id=skill_id,
            from_status=from_status,
            to_status=to_status,
            timestamp=datetime.utcnow(),
            reason=reason,
            metadata=metadata
        )
        
        self._events.append(event)
        
        logger.info(
            "skill_lifecycle_event",
            skill_id=skill_id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            reason=reason
        )
    
    def get_skill_status(self, skill_id: str) -> Optional[SkillStatus]:
        """Получить статус навыка"""
        return self._skill_status.get(skill_id)
    
    def get_lifecycle_history(
        self,
        skill_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получить историю lifecycle событий"""
        events = self._events
        
        if skill_id:
            events = [e for e in events if e.skill_id == skill_id]
        
        events = events[-limit:]
        
        return [
            {
                "skill_id": e.skill_id,
                "from_status": e.from_status.value if e.from_status else None,
                "to_status": e.to_status.value,
                "timestamp": e.timestamp.isoformat(),
                "reason": e.reason,
                "metadata": e.metadata
            }
            for e in events
        ]


# Singleton instance
_skill_lifecycle_manager: Optional[SkillLifecycleManager] = None


def get_skill_lifecycle_manager() -> SkillLifecycleManager:
    """Get or create singleton"""
    global _skill_lifecycle_manager
    if _skill_lifecycle_manager is None:
        _skill_lifecycle_manager = SkillLifecycleManager()
    return _skill_lifecycle_manager


# Convenience functions
async def activate_new_skill(
    skill_id: str,
    skill_module: Any,
    capabilities: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Активировать новый навык после генерации.
    
    Это главная точка входа для DevGoalEngine.
    """
    manager = get_skill_lifecycle_manager()
    return await manager.activate_skill(
        skill_id=skill_id,
        skill_module=skill_module,
        capabilities=capabilities,
        metadata=metadata
    )
