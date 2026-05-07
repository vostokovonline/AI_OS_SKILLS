"""
Goal Dependency DAG System

Implements dependency tracking between goals:
- A goal can depend on multiple prerequisites
- When all prerequisites are DONE, dependent goal becomes pending
- Circular dependencies are prevented
"""
from uuid import UUID, uuid4
from datetime import datetime
from typing import List
from sqlalchemy import Column, String, ForeignKey, DateTime, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class GoalDependency(Base):
    """
    Dependency relationship between goals.
    
    Example:
        Goal B depends on Goal A
        -> goal_id = B, depends_on_goal_id = A
    """
    __tablename__ = "goal_dependencies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    depends_on_goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    goal = relationship("Goal", foreign_keys=[goal_id], back_populates="dependencies")
    depends_on_goal = relationship("Goal", foreign_keys=[depends_on_goal_id])
    
    def __repr__(self):
        return f"<GoalDependency {self.goal_id} -> {self.depends_on_goal_id}>"


class DependencyResolver:
    """
    Service for managing goal dependencies.
    
    Responsibilities:
    - Add/remove dependencies
    - Check if dependencies are satisfied
    - Auto-unblock goals when prerequisites complete
    - Detect circular dependencies
    """
    
    def __init__(self, session):
        self.session = session
    
    async def add_dependency(
        self,
        goal_id: UUID,
        depends_on_goal_id: UUID
    ) -> GoalDependency:
        """
        Add a dependency relationship.
        
        Args:
            goal_id: The goal that has a prerequisite
            depends_on_goal_id: The prerequisite goal (must be DONE first)
        
        Returns:
            GoalDependency object
        
        Raises:
            ValueError: If circular dependency detected
        """
        # Check for circular dependency
        if await self._would_create_cycle(goal_id, depends_on_goal_id):
            raise ValueError(
                f"Circular dependency detected: {goal_id} depends on {depends_on_goal_id} "
                f"which transitively depends on {goal_id}"
            )
        
        # Create dependency
        dependency = GoalDependency(
            goal_id=goal_id,
            depends_on_goal_id=depends_on_goal_id
        )
        
        self.session.add(dependency)
        
        return dependency
    
    async def get_dependencies(self, goal_id: UUID) -> List[GoalDependency]:
        """
        Get all dependencies for a goal.
        
        Args:
            goal_id: Goal to check
        
        Returns:
            List of GoalDependency objects
        """
        result = await self.session.execute(
            select(GoalDependency).where(GoalDependency.goal_id == goal_id)
        )
        return list(result.scalars().all())
    
    async def get_dependents(self, goal_id: UUID) -> List[GoalDependency]:
        """
        Get all goals that depend on this goal.
        
        Args:
            goal_id: Goal that just completed
        
        Returns:
            List of GoalDependency objects where depends_on_goal_id = goal_id
        """
        result = await self.session.execute(
            select(GoalDependency).where(
                GoalDependency.depends_on_goal_id == goal_id
            )
        )
        return list(result.scalars().all())
    
    async def dependencies_satisfied(self, goal_id: UUID) -> bool:
        """
        Check if all dependencies for a goal are satisfied.
        
        A dependency is satisfied if the prerequisite goal has status='done'.
        
        Args:
            goal_id: Goal to check
        
        Returns:
            True if all prerequisites are done, False otherwise
        """
        dependencies = await self.get_dependencies(goal_id)
        
        if not dependencies:
            return True  # No dependencies = satisfied
        
        from models import Goal
        
        for dep in dependencies:
            # Check if prerequisite is done
            result = await self.session.execute(
                select(Goal._status).where(Goal.id == dep.depends_on_goal_id)
            )
            status = result.scalar_one_or_none()
            
            if status != "done":
                return False  # Found unsatisfied dependency
        
        return True  # All dependencies done

    async def unblock_dependent_goals(self, completed_goal_id: UUID) -> List[UUID]:
        """
        When a goal completes, check if any dependent goals can be unblocked.

        Args:
            completed_goal_id: Goal that just finished

        Returns:
            List of goal_ids that were unblocked
        """
        # Find all goals that depend on the completed goal
        dependents = await self.get_dependents(completed_goal_id)

        unblocked = []

        for dep in dependents:
            # Check if ALL dependencies are satisfied
            if await self.dependencies_satisfied(dep.goal_id):
                # Return the goal ID (caller is responsible for transition)
                unblocked.append(dep.goal_id)

        return unblocked

    async def unblock_dependent_goals_batch(self, completed_goal_id: UUID) -> dict:
        """
        BATCH VERSION: Unblock multiple dependent goals in a single SQL UPDATE.

        When a goal completes, check if any dependent goals can be unblocked
        and transition them ALL in one database operation.

        Performance: 1000 dependents → 1 UPDATE instead of 1000 UPDATEs

        Args:
            completed_goal_id: Goal that just finished

        Returns:
            {
                "total_found": int,
                "unblocked": int,
                "goal_ids": List[UUID]
            }
        """
        from sqlalchemy import update, and_
        from models import Goal

        # Find all goals that depend on the completed goal
        dependents = await self.get_dependents(completed_goal_id)
        dependent_ids = [d.goal_id for d in dependents]

        if not dependent_ids:
            return {"total_found": 0, "unblocked": 0, "goal_ids": []}

        # Filter to only goals with ALL dependencies satisfied
        # (This is still O(N) but only in-memory, not DB calls)
        ready_to_unblock = []
        for goal_id in dependent_ids:
            if await self.dependencies_satisfied(goal_id):
                ready_to_unblock.append(goal_id)

        if not ready_to_unblock:
            return {"total_found": len(dependent_ids), "unblocked": 0, "goal_ids": []}

        # BATCH UPDATE: Single SQL operation
        # UPDATE goals SET _status='pending', updated_at=NOW()
        # WHERE id IN (...) AND _status='blocked'

        stmt = (
            update(Goal)
            .where(
                and_(
                    Goal.id.in_(ready_to_unblock),
                    Goal._status == 'blocked'
                )
            )
            .values(
                _status='pending',
                updated_at=datetime.utcnow()
            )
            .returning(Goal.id)
        )

        result = await self.session.execute(stmt)
        unblocked_ids = list(result.scalars().all())

        return {
            "total_found": len(dependent_ids),
            "unblocked": len(unblocked_ids),
            "goal_ids": unblocked_ids
        }
    
    async def _would_create_cycle(
        self,
        goal_id: UUID,
        depends_on_goal_id: UUID
    ) -> bool:
        """
        Check if adding a dependency would create a cycle.
        
        Uses DFS to find if depends_on_goal_id can reach goal_id
        through existing dependencies.
        
        Args:
            goal_id: The goal that would have the dependency
            depends_on_goal_id: The prerequisite goal
        
        Returns:
            True if cycle detected, False otherwise
        """
        # DFS to find path from depends_on_goal_id to goal_id
        visited = set()
        stack = [depends_on_goal_id]
        
        while stack:
            current = stack.pop()
            
            if current == goal_id:
                return True  # Cycle found!
            
            if current in visited:
                continue
            
            visited.add(current)
            
            # Get all goals that current depends on
            deps = await self.session.execute(
                select(GoalDependency.depends_on_goal_id).where(
                    GoalDependency.goal_id == current
                )
            )
            deps = list(deps.scalars().all())
            
            stack.extend(deps)
        
        return False  # No cycle


# Singleton instance factory
def get_dependency_resolver(session):
    """Get DependencyResolver instance for this session."""
    return DependencyResolver(session)
