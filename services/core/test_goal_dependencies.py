"""
Test Goal Dependency DAG System
"""
import pytest
from uuid import uuid4
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Goal
from goal_dependencies import GoalDependency, get_dependency_resolver


@pytest.mark.asyncio
async def test_add_dependency():
    """Test adding a dependency relationship."""
    async with AsyncSessionLocal() as session:
        # Create two goals
        goal_a = Goal(
            id=uuid4(),
            title="Goal A (prerequisite)",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B (depends on A)",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        await session.commit()
        
        # Add dependency: B depends on A
        resolver = get_dependency_resolver(session)
        dep = await resolver.add_dependency(goal_b.id, goal_a.id)
        
        assert dep is not None
        assert dep.goal_id == goal_b.id
        assert dep.depends_on_goal_id == goal_a.id


@pytest.mark.asyncio
async def test_dependencies_satisfied():
    """Test checking if dependencies are satisfied."""
    async with AsyncSessionLocal() as session:
        # Create goals: A -> B
        goal_a = Goal(
            id=uuid4(),
            title="Goal A",
            _status="done",  # A is done
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        await session.commit()
        
        # Add dependency
        resolver = get_dependency_resolver(session)
        await resolver.add_dependency(goal_b.id, goal_a.id)
        await session.commit()
        
        # Check satisfied
        satisfied = await resolver.dependencies_satisfied(goal_b.id)
        assert satisfied is True  # A is done, so B's dependencies are satisfied


@pytest.mark.asyncio
async def test_dependencies_not_satisfied():
    """Test unsatisfied dependencies."""
    async with AsyncSessionLocal() as session:
        # Create goals: A -> B
        goal_a = Goal(
            id=uuid4(),
            title="Goal A",
            _status="pending",  # A is NOT done
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        await session.commit()
        
        # Add dependency
        resolver = get_dependency_resolver(session)
        await resolver.add_dependency(goal_b.id, goal_a.id)
        await session.commit()
        
        # Check satisfied
        satisfied = await resolver.dependencies_satisfied(goal_b.id)
        assert satisfied is False  # A is pending, so B's dependencies are NOT satisfied


@pytest.mark.asyncio
async def test_circular_dependency_detection():
    """Test that circular dependencies are prevented."""
    async with AsyncSessionLocal() as session:
        # Create goals
        goal_a = Goal(
            id=uuid4(),
            title="Goal A",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        await session.commit()
        
        resolver = get_dependency_resolver(session)
        
        # Add A -> B
        await resolver.add_dependency(goal_b.id, goal_a.id)
        await session.commit()
        
        # Try to add B -> A (should fail - circular!)
        with pytest.raises(ValueError, match="Circular dependency"):
            await resolver.add_dependency(goal_a.id, goal_b.id)


@pytest.mark.asyncio
async def test_get_dependents():
    """Test finding goals that depend on a completed goal."""
    async with AsyncSessionLocal() as session:
        # Create goals: A -> B, A -> C
        goal_a = Goal(
            id=uuid4(),
            title="Goal A",
            _status="done",
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B",
            _status="blocked",
            goal_type="achievable",
            is_atomic=True
        )
        goal_c = Goal(
            id=uuid4(),
            title="Goal C",
            _status="blocked",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        session.add(goal_c)
        await session.commit()
        
        # Add dependencies
        resolver = get_dependency_resolver(session)
        await resolver.add_dependency(goal_b.id, goal_a.id)
        await resolver.add_dependency(goal_c.id, goal_a.id)
        await session.commit()
        
        # Get dependents of A
        dependents = await resolver.get_dependents(goal_a.id)
        
        assert len(dependents) == 2
        dependent_ids = {d.goal_id for d in dependents}
        assert goal_b.id in dependent_ids
        assert goal_c.id in dependent_ids


@pytest.mark.asyncio
async def test_multiple_dependencies():
    """Test goal with multiple prerequisites (AND logic)."""
    async with AsyncSessionLocal() as session:
        # Create goals: A -> C, B -> C
        goal_a = Goal(
            id=uuid4(),
            title="Goal A",
            _status="done",
            goal_type="achievable",
            is_atomic=True
        )
        goal_b = Goal(
            id=uuid4(),
            title="Goal B",
            _status="pending",  # B is NOT done
            goal_type="achievable",
            is_atomic=True
        )
        goal_c = Goal(
            id=uuid4(),
            title="Goal C (depends on A AND B)",
            _status="pending",
            goal_type="achievable",
            is_atomic=True
        )
        
        session.add(goal_a)
        session.add(goal_b)
        session.add(goal_c)
        await session.commit()
        
        # Add dependencies
        resolver = get_dependency_resolver(session)
        await resolver.add_dependency(goal_c.id, goal_a.id)
        await resolver.add_dependency(goal_c.id, goal_b.id)
        await session.commit()
        
        # Check satisfied (should be False - B is not done)
        satisfied = await resolver.dependencies_satisfied(goal_c.id)
        assert satisfied is False  # Both A AND B must be done


if __name__ == "__main__":
    import asyncio
    
    # Run single test
    async def run_test():
        print("Testing: Add dependency")
        await test_add_dependency()
        print("✅ PASS")
        
        print("\nTesting: Dependencies satisfied")
        await test_dependencies_satisfied()
        print("✅ PASS")
        
        print("\nTesting: Dependencies not satisfied")
        await test_dependencies_not_satisfied()
        print("✅ PASS")
        
        print("\nTesting: Circular dependency detection")
        await test_circular_dependency_detection()
        print("✅ PASS")
        
        print("\nTesting: Get dependents")
        await test_get_dependents()
        print("✅ PASS")
        
        print("\nTesting: Multiple dependencies (AND logic)")
        await test_multiple_dependencies()
        print("✅ PASS")
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✅")
        print("="*50)
    
    asyncio.run(run_test())
