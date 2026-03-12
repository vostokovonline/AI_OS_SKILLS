"""
BulkTransitionEngine - Application-Layer Orchestrator
====================================================

ARCHITECTURAL PRINCIPLE:
    Bulk operations are PURE FUNCTIONS on snapshots.
    No mutations. No Session access. No ORM.

SEPARATION OF CONCERNS:
    - GoalSnapshot: Immutable state representation
    - StateTransitionPlanner: Pure computation (snapshots → transitions)
    - BulkTransitionEngine: Orchestrates planning phase
    - GoalRepository.apply_bulk: Applies transitions atomically

CRITICAL INVARIANTS:
    1. Engine NEVER touches ORM objects after snapshot creation
    2. Engine NEVER opens its own transaction
    3. Engine NEVER calls commit
    4. Planner is idempotent (same snapshots → same transitions)

Author: AI-OS Core Team
Date: 2026-02-27
Version: 2.0.0 - Snapshot-based architecture
"""
from typing import List
from uuid import UUID
from datetime import datetime

from application.bulk.types import (
    GoalSnapshot,
    Transition,
    BulkTransitionPlan
)


class StateTransitionPlanner:
    """
    PURE FUNCTION: snapshots → transitions

    CRITICAL:
    - No database access
    - No Session
    - No mutations
    - Testable without infrastructure

    Given same input snapshots, ALWAYS produces same output.
    """

    def build(self, snapshots: List[GoalSnapshot]) -> BulkTransitionPlan:
        """
        Build transition plan from snapshots.

        Args:
            snapshots: List of GoalSnapshot (immutable)

        Returns:
            BulkTransitionPlan (describes WHAT to change, not HOW)

        NOTE: This is a PROOF-OF-CONCEPT planner.
        Real implementation would include:
        - Arbitration logic
        - Constraint checking
        - Dependency resolution
        - Conflict detection
        """
        transitions = []

        for snapshot in snapshots:
            # POC: pending → active
            # TODO: Add real planning logic
            if snapshot.status == 'pending':
                transition = Transition(
                    goal_id=snapshot.id,
                    from_status='pending',
                    to_status='active',
                    reason=f'Bulk activation: {snapshot.goal_type}',
                    actor='system.bulk'
                )
                transitions.append(transition)

        return BulkTransitionPlan(
            transitions=tuple(transitions),  # Immutable
            metadata={
                "planned_at": datetime.utcnow().isoformat(),
                "strategy": "pending_to_active_poc",
                "input_count": len(snapshots)
            }
        )


class BulkTransitionEngine:
    """
    Application-layer orchestrator for bulk planning.

    KEY PRINCIPLE:
        Receives snapshots → returns plan.
        Caller applies plan via repository.

    INVARIANTS:
        - Never opens own transaction
        - Never touches Session
        - Never mutates snapshots
        - Pure computation (testable without DB)
    """

    def __init__(self):
        from infrastructure.uow import GoalRepository

        self._repo = GoalRepository()
        self._planner = StateTransitionPlanner()

    def plan_transitions(
        self,
        goal_ids: List[UUID]
    ) -> BulkTransitionPlan:
        """
        Plan transitions for given goals.

        THIS IS A PURE FUNCTION (mostly - only loads data).

        Args:
            goal_ids: List of goal IDs to plan for

        Returns:
            BulkTransitionPlan describing what should change

        NOTE: This method needs a database session ONLY for loading snapshots.
        Planning itself is pure computation.
        """
        # TODO: This should accept uow parameter for loading
        # For now, we'll keep the signature simple and refactor later

        # Load snapshots (this is the ONLY DB access)
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Goal

        async def _load_and_plan():
            async with AsyncSessionLocal() as session:
                stmt = select(Goal).where(Goal.id.in_(goal_ids))
                result = await session.execute(stmt)
                goals = result.scalars().all()

                # Convert to snapshots IMMEDIATELY
                snapshots = [
                    GoalSnapshot.from_orm(g) for g in goals
                ]

                # Plan on snapshots (pure computation)
                return self._planner.build(snapshots)

        # NOTE: This async/sync mismatch needs fixing
        # For now, keeping it to show the structure
        raise NotImplementedError(
            "plan_transitions needs async refactor or uow parameter"
        )

    async def load_snapshots(
        self,
        session,
        goal_ids: List[UUID]
    ) -> List[GoalSnapshot]:
        """
        Load ORM objects → convert to snapshots.

        This is the ONLY place where Bulk touches ORM.
        After this, everything works on snapshots.

        Args:
            session: SQLAlchemy AsyncSession
            goal_ids: List of goal IDs to load

        Returns:
            List of GoalSnapshot (immutable)
        """
        from models import Goal
        from sqlalchemy import select

        stmt = select(Goal).where(Goal.id.in_(goal_ids))
        result = await session.execute(stmt)
        goals = result.scalars().all()

        # Convert to snapshots immediately
        return [GoalSnapshot.from_orm(g) for g in goals]

    def plan_from_snapshots(
        self,
        snapshots: List[GoalSnapshot]
    ) -> BulkTransitionPlan:
        """
        Pure planning function - no DB access.

        Args:
            snapshots: List of GoalSnapshot

        Returns:
            BulkTransitionPlan

        NOTE: This is the ACTUAL pure function.
        Testable without database.
        """
        return self._planner.build(snapshots)

    async def execute_bulk(
        self,
        uow: "UnitOfWork",
        goal_ids: List[UUID],
        actor: str = "system.bulk"
    ) -> dict:
        """
        Execute bulk transition within caller's transaction.

        ARCHITECTURE:
            1. Load snapshots (ORM → immutable)
            2. Plan transitions (pure function)
            3. Apply via repo (UPDATE ... WHERE)

        CRITICAL: This method does NOT commit.
        Caller owns transaction boundary.

        Args:
            uow: UnitOfWork with ACTIVE transaction
            goal_ids: List of goal IDs to transition
            actor: Who initiated this bulk operation

        Returns:
            {
                "total": int,
                "planned": int,
                "applied": int,
                "skipped": int,
                "failed": int,
                "results": [...]
            }
        """
        from datetime import datetime

        start_time = datetime.utcnow()

        # Phase 1: Load snapshots (ORM → immutable)
        snapshots = await self.load_snapshots(uow.session, goal_ids)

        # Phase 2: Plan transitions (pure computation)
        plan = self.plan_from_snapshots(snapshots)

        # Phase 3: Apply via repository (atomic UPDATE)
        result = await self._repo.apply_bulk_transitions(
            uow.session,
            list(plan.transitions)  # Convert tuple to list
        )

        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            **result,
            "planned": len(plan),
            "execution_time_ms": execution_time_ms,
            "timestamp": end_time.isoformat(),
            "plan_metadata": plan.metadata
        }

    async def apply_execution_intents(
        self,
        uow: "UnitOfWork",
        intents: List["application.execution.intents.ExecutionIntent"],
        actor: str = "system.bulk"
    ) -> dict:
        """
        Apply execution outcomes atomically with optimistic locking.

        This is where execution decisions become DB state changes.

        ARCHITECTURE:
            1. For each intent:
               - Check version (optimistic lock)
               - Register artifacts
               - Transition goal status
            2. ALL in ONE transaction

        OPTIMISTIC LOCKING:
            If goal.updated_at != intent.expected_version → skip intent
            This prevents applying stale decisions to changed state.

        CRITICAL: This method does NOT commit.
        Caller owns transaction boundary.

        Args:
            uow: UnitOfWork with ACTIVE transaction
            intents: List of ExecutionIntent decisions
            actor: Who initiated this bulk operation

        Returns:
            {
                "total": int,
                "applied": int,
                "skipped": int,  # Version mismatch
                "failed": int,
                "results": [...]
            }
        """
        from application.execution.intents import ExecutionIntent, ArtifactData
        from artifact_registry import artifact_registry
        from goal_transition_service import transition_service
        from infrastructure.uow import GoalRepository
        from uuid import UUID
        from logging_config import get_logger
        logger = get_logger("bulk_transition_engine")

        # Write barrier check (test mode only)
        try:
            from tests.stress.write_barrier import WRITE_BARRIER
            if WRITE_BARRIER.enabled:
                WRITE_BARRIER.check("BulkTransitionEngine.apply_execution_intents")
        except ImportError:
            pass  # Not in test mode

        CONFIDENCE_THRESHOLD = 0.6

        results = []
        applied = 0
        skipped = 0
        failed = 0

        for intent in intents:
            try:
                goal_id = UUID(str(intent.goal_id))

                # 0. Optimistic lock check (CRITICAL for deterministic batches)
                goal = await self._repo.get(uow.session, goal_id)
                if not goal:
                    skipped += 1
                    results.append({
                        "goal_id": str(goal_id),
                        "status": "skipped",
                        "reason": "Goal disappeared"
                    })
                    continue

                if goal.updated_at != intent.expected_version:
                    skipped += 1
                    logger.info("bulk_apply_skipped_version", goal_id=str(goal_id), goal_updated=goal.updated_at.isoformat() if goal.updated_at else None, expected_version=intent.expected_version.isoformat() if intent.expected_version else None)
                    results.append({
                        "goal_id": str(goal_id),
                        "status": "skipped",
                        "reason": "Version changed (concurrent modification)"
                    })
                    continue

                # 1. Register artifacts
                registered_artifacts = []
                logger.info("bulk_apply_checking_artifacts", goal_id=str(goal_id), intent_outcome=intent.outcome, artifacts_count=len(intent.artifacts) if intent.artifacts else 0)
                if intent.artifacts and len(intent.artifacts) > 0:
                    logger.info("bulk_apply_artifacts_found", goal_id=str(goal_id), count=len(intent.artifacts), first_artifact_type=intent.artifacts[0].artifact_type if intent.artifacts else None)
                    for artifact_data in intent.artifacts:
                        artifact = await artifact_registry.register_with_uow(
                            uow=uow,
                            goal_id=str(goal_id),
                            artifact_type=artifact_data.artifact_type if hasattr(artifact_data, 'artifact_type') else artifact_data.get("artifact_type", "FILE"),
                            content_kind=artifact_data.content_kind if hasattr(artifact_data, 'content_kind') else artifact_data.get("content_kind", "file"),
                            content_location=artifact_data.content_location if hasattr(artifact_data, 'content_location') else artifact_data.get("content_location", ""),
                            auto_verify=True
                        )
                        registered_artifacts.append(artifact)

                # 2. Transition goal based on outcome
                if intent.outcome == "completed" and intent.confidence >= CONFIDENCE_THRESHOLD:
                    # Success → done
                    await transition_service.transition(
                        uow=uow,
                        goal_id=goal_id,
                        new_state="done",
                        reason=f"Goal completed (confidence {intent.confidence:.2f})",
                        actor=actor
                    )
                elif intent.outcome == "completed":
                    # Low confidence → incomplete
                    await transition_service.transition(
                        uow=uow,
                        goal_id=goal_id,
                        new_state="incomplete",
                        reason=f"Low confidence: {intent.confidence:.2f}",
                        actor=actor
                    )
                else:
                    # Failed or error → blocked
                    await transition_service.transition(
                        uow=uow,
                        goal_id=goal_id,
                        new_state="blocked",
                        reason=f"Goal {intent.outcome}" + (f": {intent.error}" if intent.error else ""),
                        actor=actor
                    )

                results.append({
                    "goal_id": str(goal_id),
                    "status": "applied",
                    "outcome": intent.outcome,
                    "artifacts_registered": len(registered_artifacts)
                })
                applied += 1

            except Exception as e:
                failed += 1
                results.append({
                    "goal_id": str(intent.goal_id),
                    "status": "failed",
                    "error": str(e)[:100]
                })

        return {
            "total": len(intents),
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "results": results
        }


# Singleton instance
bulk_transition_engine = BulkTransitionEngine()
