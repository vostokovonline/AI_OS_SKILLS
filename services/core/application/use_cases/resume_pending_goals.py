"""
Resume Pending Goals Use-Case

Transitions pending goals to active when their dependencies are satisfied.
"""
from typing import TYPE_CHECKING
from dataclasses import dataclass
from uuid import UUID

from logging_config import get_logger

if TYPE_CHECKING:
    from infrastructure.uow import UnitOfWork

logger = get_logger(__name__)


@dataclass
class ResumeResult:
    """Result of resume operation"""
    total_found: int
    activated: int
    skipped: int
    failed: int
    activated_atomic: int
    activated_directional: int

    @classmethod
    def empty(cls) -> "ResumeResult":
        return cls(
            total_found=0, 
            activated=0, 
            skipped=0, 
            failed=0,
            activated_atomic=0,
            activated_directional=0
        )


class ResumePendingGoalsUseCase:
    """
    Use-Case: Resume pending goals when dependencies are satisfied.
    
    CRITICAL INVARIANTS:
        1. Goal only activated if ALL dependencies are done
        2. Goals without dependencies can be activated immediately
        3. Batch operation - one transaction for all
        4. Non-atomic goals (directional/continuous) handled separately - no dependencies needed
    """

    def __init__(self, uow_factory, bulk_engine):
        self._uow_factory = uow_factory
        self._bulk_engine = bulk_engine

    async def run(
        self,
        *,
        limit: int | None = None,
        actor: str = "system"
    ) -> ResumeResult:
        """
        Find pending goals and activate those with satisfied dependencies.
        
        Pipeline:
            1. SELECT pending atomic goals with satisfied dependencies
            2. SELECT pending non-atomic goals (directional/continuous) - no dependencies needed
            3. ACTIVATE all eligible goals
            4. COMMIT in one transaction
        """
        from sqlalchemy import text
        
        async with self._uow_factory() as uow:
            limit_clause = f"LIMIT {limit}" if limit else ""
            
            # ========================================
            # Part 1: Atomic goals (need dependencies satisfied)
            # ========================================
            atomic_stmt = text(f"""
                SELECT g.id, g.title
                FROM goals g
                WHERE g.status = 'pending'
                AND g.is_atomic = true
                AND (g.progress < 1.0 OR g.progress IS NULL)
                AND NOT EXISTS (
                    SELECT 1 FROM goal_dependencies gd
                    JOIN goals gp ON gp.id = gd.depends_on_goal_id
                    WHERE gd.goal_id = g.id 
                    AND gp.status NOT IN ('done', 'archived')
                )
                ORDER BY g.created_at ASC
                {limit_clause}
            """)
            
            result = await uow.session.execute(atomic_stmt)
            atomic_pending = [(row[0], row[1]) for row in result.fetchall()]
            
            # ========================================
            # Part 2: Non-atomic goals (directional, continuous, etc.)
            # These don't need dependencies - just activate them
            # ========================================
            non_atomic_stmt = text(f"""
                SELECT g.id, g.title
                FROM goals g
                WHERE g.status = 'pending'
                AND g.is_atomic = false
                AND (g.progress < 1.0 OR g.progress IS NULL)
                AND NOT EXISTS (
                    SELECT 1 FROM goal_dependencies gd
                    JOIN goals gp ON gp.id = gd.depends_on_goal_id
                    WHERE gd.goal_id = g.id 
                    AND gp.status NOT IN ('done', 'archived')
                )
                ORDER BY g.created_at ASC
                {limit_clause}
            """)
            
            result = await uow.session.execute(non_atomic_stmt)
            non_atomic_pending = [(row[0], row[1]) for row in result.fetchall()]
            
            # Combine both lists
            all_pending = atomic_pending + non_atomic_pending
            
            if not all_pending:
                return ResumeResult.empty()
            
            logger.info(
                f"resume_scan: atomic={len(atomic_pending)}, "
                f"non_atomic={len(non_atomic_pending)}, "
                f"total={len(all_pending)}"
            )
            
            # Activate all goals in batch
            activated_atomic = 0
            activated_directional = 0
            failed = 0
            
            # EVENT-DRIVEN: Emit event for each activation
            try:
                from application.events.pipeline import get_pipeline, PipelineEvent, PipelineEventType
                pipeline = get_pipeline()
            except Exception:
                pipeline = None
            
            for goal_id, title in all_pending:
                try:
                    # Use bulk_engine for atomic transition
                    await self._bulk_engine.transition_goal(
                        uow=uow,
                        goal_id=goal_id,
                        new_state="active",
                        reason=f"Activated by {actor} - dependencies satisfied or no dependencies needed",
                        actor=actor
                    )
                    
                    # Track which type was activated
                    is_atomic = goal_id in [g[0] for g in atomic_pending]
                    if is_atomic:
                        activated_atomic += 1
                    else:
                        activated_directional += 1
                    
                    # EVENT-DRIVEN: Emit activation event
                    if pipeline:
                        await pipeline.emit(PipelineEvent(
                            event_type=PipelineEventType.GOAL_ACTIVATED,
                            goal_id=str(goal_id),
                            data={"title": title}
                        ))
                except Exception as e:
                    logger.error(f"[RESUME FAILED] goal_id={goal_id}, title={title}, error={str(e)[:100]}")
                    failed += 1
            
            return ResumeResult(
                total_found=len(all_pending),
                activated=activated_atomic + activated_directional,
                skipped=0,
                failed=failed,
                activated_atomic=activated_atomic,
                activated_directional=activated_directional
            )


__all__ = ["ResumePendingGoalsUseCase", "ResumeResult"]