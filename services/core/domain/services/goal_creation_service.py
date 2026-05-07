"""
Goal Creation Service - Pure Domain Logic
=========================================

Responsibility:
    Create goals with validation, classification, and contract generation

Does NOT:
    - Commit transactions
    - Log events (use structured logging from caller)
    - Send notifications
    - Manage state transitions

Author: AI-OS Architecture v2.0
Date: 2026-03-10
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from logging_config import get_logger

logger = get_logger(__name__)


class GoalCreationService:
    """
    Pure domain service for goal creation.

    All operations within UoW transaction.
    No side effects.
    """

    def __init__(self):
        # Dependencies (injected)
        self._decomposer = None
        self._contract_validator = None
        self._goal_repository = None

    async def create(
        self,
        uow: "UnitOfWork",
        title: str,
        description: str = "",
        goal_type: Optional[str] = None,
        auto_classify: bool = True,
        is_atomic: bool = False,
        depth_level: Optional[int] = None,
        parent_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        domains: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> "Goal":
        """
        Create a new goal within UoW transaction.

        Args:
            uow: UnitOfWork with active session
            title: Goal title (required)
            description: Goal description
            goal_type: Type of goal (achievable, continuous, etc.)
            auto_classify: Auto-classify goal type if not provided
            is_atomic: Is this an atomic (executable) goal?
            depth_level: Depth in goal hierarchy (0=Mission, 3=Atomic)
            parent_id: Parent goal UUID
            user_id: User UUID for personalization
            domains: Domain tags for categorization
            constraints: Execution constraints

        Returns:
            Goal: Created goal object (NOT committed yet)

        Raises:
            ValidationError: If invariants violated
            ValueError: If parent goal not found or invalid depth

        Example:
            >>> async with get_uow() as uow:
            ...     service = GoalCreationService()
            ...     goal = await service.create(
            ...         uow=uow,
            ...         title="Write documentation",
            ...         description="Create API docs",
            ...         is_atomic=True
            ...     )
            ...     # UoW commits on exit
        """
        from models import Goal
        from infrastructure.uow import GoalRepository

        # Lazy load dependencies to avoid circular imports
        if self._decomposer is None:
            from goal_decomposer import goal_decomposer
            self._decomposer = goal_decomposer

        if self._contract_validator is None:
            from goal_contract_validator import goal_contract_validator
            self._contract_validator = goal_contract_validator

        if self._goal_repository is None:
            self._goal_repository = GoalRepository()

        # ================================================================
        # STEP 1: Classify goal (if requested)
        # ================================================================
        final_goal_type = goal_type
        final_domains = domains or []

        if auto_classify and not goal_type:
            classification = await self._decomposer.safe_classify_goal(title, description, timeout=10.0)
            final_goal_type = classification.get("goal_type", "achievable")

            if not final_domains:
                final_domains = await self._decomposer.safe_analyze_domains(title, description, timeout=10.0)

        # Default to achievable if not set
        if not final_goal_type:
            final_goal_type = "achievable"

        # ================================================================
        # STEP 2: Calculate depth level
        # ================================================================
        calculated_depth = depth_level
        if calculated_depth is None:
            calculated_depth = await self._calculate_depth(
                uow=uow,
                parent_id=parent_id
            )

        # ================================================================
        # STEP 3: Generate goal contract
        # ================================================================
        goal_contract = self._contract_validator.create_default_contract(
            goal_type=final_goal_type,
            depth_level=calculated_depth
        )

        # ================================================================
        # STEP 4: Validate invariants
        # ================================================================
        self._validate_invariants(
            goal_type=final_goal_type,
            depth_level=calculated_depth,
            is_atomic=is_atomic,
            parent_id=parent_id
        )

        # ================================================================
        # STEP 5: Create goal entity
        # ================================================================
        goal = Goal(
            title=title,
            description=description or title,
            goal_type=final_goal_type,
            domains=final_domains if final_domains else None,
            constraints=constraints,
            depth_level=calculated_depth,
            is_atomic=is_atomic,
            goal_contract=goal_contract,
            parent_id=parent_id,
            user_id=user_id,
            _status="pending",  # Initial state
            progress=0.0
        )

        # ================================================================
        # STEP 6: Persist via UoW (NO commit here!)
        # ================================================================
        await self._goal_repository.save(uow.session, goal)

        logger.info(
            "goal_created",
            goal_id=str(goal.id),
            title=goal.title,
            goal_type=goal.goal_type,
            depth_level=goal.depth_level,
            is_atomic=goal.is_atomic
        )

        return goal

    async def _calculate_depth(
        self,
        uow: "UnitOfWork",
        parent_id: Optional[UUID]
    ) -> int:
        """
        Calculate depth level based on parent.

        Rules:
            - No parent → depth 0 (Mission)
            - Has parent → parent.depth + 1
            - Max depth is 3 (Atomic)
        """
        if parent_id is None:
            return 0

        from infrastructure.uow import GoalRepository

        repo = GoalRepository()
        parent = await repo.get(uow.session, parent_id)

        if parent is None:
            # Parent not found, default to level 1
            return 1

        parent_depth = parent.depth_level or 0
        new_depth = parent_depth + 1

        # Validate max depth
        if new_depth > 3:
            raise ValueError(
                f"Max depth exceeded: parent depth={parent_depth}, "
                f"would create depth={new_depth}, max allowed=3"
            )

        return new_depth

    def _validate_invariants(
        self,
        goal_type: str,
        depth_level: int,
        is_atomic: bool,
        parent_id: Optional[UUID]
    ):
        """
        Validate goal creation invariants.

        Raises:
            ValueError: If invariants violated
        """
        # Valid goal types
        valid_types = {"achievable", "continuous", "directional", "exploratory", "meta"}
        if goal_type not in valid_types:
            raise ValueError(
                f"Invalid goal_type: {goal_type}. "
                f"Must be one of: {valid_types}"
            )

        # Depth range
        if not (0 <= depth_level <= 3):
            raise ValueError(
                f"Invalid depth_level: {depth_level}. "
                f"Must be between 0 and 3"
            )

        # Atomic goals at depth 3 only
        if is_atomic and depth_level != 3:
            logger.warning(
                "atomic_goal_at_non_leaf_depth",
                depth_level=depth_level,
                expected_depth=3
            )

        # Continuous goals cannot be atomic
        if goal_type == "continuous" and is_atomic:
            raise ValueError(
                "Continuous goals cannot be atomic. "
                "Continuous goals are ongoing processes."
            )

        # Directional goals cannot be atomic
        if goal_type == "directional" and is_atomic:
            raise ValueError(
                "Directional goals cannot be atomic. "
                "Directional goals are principles, not tasks."
            )


# Singleton instance
goal_creation_service = GoalCreationService()
