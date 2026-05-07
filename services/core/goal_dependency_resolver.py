"""
Goal Dependency Resolver

Manages goal dependencies and unblocking in a DAG.
"""

from typing import List, Optional, Set
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


class GoalDependencyResolver:
    """
    Resolves goal dependencies and manages DAG operations.
    """
    
    async def add_dependency(
        self,
        goal_id: UUID,
        depends_on_goal_id: UUID
    ) -> bool:
        """
        Add a dependency between goals.
        
        Returns False if cycle would be created.
        """
        # Check for cycle
        if await self._would_create_cycle(goal_id, depends_on_goal_id):
            logger.warning(
                "dependency_cycle_rejected",
                goal_id=str(goal_id),
                depends_on=str(depends_on_goal_id)
            )
            return False
        
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO goal_dependencies (goal_id, depends_on_goal_id, created_at)
                        VALUES (:goal_id, :depends_on, NOW())
                        ON CONFLICT DO NOTHING
                    """),
                    {"goal_id": goal_id, "depends_on": depends_on_goal_id}
                )
                await session.commit()
                
                logger.info(
                    "dependency_added",
                    goal_id=str(goal_id),
                    depends_on=str(depends_on_goal_id)
                )
                return True
                
            except Exception as e:
                logger.error("dependency_add_failed", error=str(e))
                return False
    
    async def get_dependencies(self, goal_id: UUID) -> List[UUID]:
        """Get all goals this goal depends on."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT depends_on_goal_id 
                    FROM goal_dependencies 
                    WHERE goal_id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            return [row[0] for row in result.fetchall()]
    
    async def get_dependents(self, goal_id: UUID) -> List[UUID]:
        """Get all goals that depend on this goal."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT goal_id 
                    FROM goal_dependencies 
                    WHERE depends_on_goal_id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            return [row[0] for row in result.fetchall()]
    
    async def dependencies_satisfied(self, goal_id: UUID) -> bool:
        """Check if all dependencies for a goal are satisfied (done)."""
        async with AsyncSessionLocal() as session:
            # Get all dependencies
            result = await session.execute(
                text("""
                    SELECT depends_on_goal_id 
                    FROM goal_dependencies 
                    WHERE goal_id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            deps = [row[0] for row in result.fetchall()]
            
            if not deps:
                return True  # No dependencies = satisfied
            
            # Check if all are done
            placeholders = ", ".join([f"'{d}'" for d in deps])
            result = await session.execute(
                text(f"""
                    SELECT COUNT(*) 
                    FROM goals 
                    WHERE id IN ({placeholders})
                    AND status = 'done'
                """)
            )
            done_count = result.scalar()
            
            return done_count == len(deps)
    
    async def on_goal_completed(self, completed_goal_id: UUID) -> List[UUID]:
        """
        Called when a goal is completed.
        
        Returns list of goals that should be unblocked.
        """
        # Find all goals that depend on this one
        dependents = await self.get_dependents(completed_goal_id)
        
        unblocked = []
        
        for dependent_id in dependents:
            # Check if ALL dependencies are now satisfied
            if await self.dependencies_satisfied(dependent_id):
                unblocked.append(dependent_id)
                
                # Update status: blocked -> pending
                await self._unblock_goal(dependent_id)
                
                logger.info(
                    "goal_unblocked",
                    goal_id=str(dependent_id),
                    reason=f"dependency {completed_goal_id} completed"
                )
        
        return unblocked
    
    async def _unblock_goal(self, goal_id: UUID) -> None:
        """Change goal status from blocked to pending."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    UPDATE goals 
                    SET status = 'pending', updated_at = NOW()
                    WHERE id = :goal_id AND status = 'blocked'
                """),
                {"goal_id": goal_id}
            )
            await session.commit()
    
    async def _would_create_cycle(
        self,
        goal_id: UUID,
        depends_on_goal_id: UUID
    ) -> bool:
        """Check if adding this dependency would create a cycle."""
        # BFS to find if depends_on_goal_id can reach goal_id
        visited: Set[UUID] = set()
        queue = [goal_id]
        
        while queue:
            current = queue.pop(0)
            if current == depends_on_goal_id:
                return True  # Cycle detected
            
            if current in visited:
                continue
            visited.add(current)
            
            # Get what current depends on
            deps = await self.get_dependencies(current)
            queue.extend(deps)
        
        return False


# Singleton
goal_dependency_resolver = GoalDependencyResolver()


# Convenience functions
async def add_goal_dependency(goal_id: UUID, depends_on: UUID) -> bool:
    return await goal_dependency_resolver.add_dependency(goal_id, depends_on)


async def on_goal_done(goal_id: UUID) -> List[UUID]:
    """Called when a goal completes - returns unblocked goals."""
    return await goal_dependency_resolver.on_goal_completed(goal_id)


async def get_blocked_goals() -> List[dict]:
    """Get all blocked goals with their dependencies."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT 
                    g.id,
                    g.title,
                    g.status,
                    ARRAY_AGG(gd.depends_on_goal_id) as dependencies
                FROM goals g
                LEFT JOIN goal_dependencies gd ON g.id = gd.goal_id
                WHERE g.status = 'blocked'
                GROUP BY g.id, g.title, g.status
            """)
        )
        rows = result.fetchall()
        
        return [
            {
                "goal_id": str(r[0]),
                "title": r[1],
                "status": r[2],
                "dependencies": [str(d) for d in (r[3] or [])]
            }
            for r in rows
        ]


if __name__ == "__main__":
    import asyncio
    
    async def test():
        from uuid import uuid4
        
        resolver = GoalDependencyResolver()
        
        # Create test goals (simulated)
        goal_a = uuid4()
        goal_b = uuid4()
        
        # Add dependency: B depends on A
        result = await resolver.add_dependency(goal_b, goal_a)
        print(f"Dependency added: {result}")
        
        # Check dependencies
        deps = await resolver.get_dependencies(goal_b)
        print(f"B depends on: {deps}")
        
        # Simulate completion
        unblocked = await resolver.on_goal_completed(goal_a)
        print(f"Unblocked goals: {unblocked}")
    
    asyncio.run(test())
