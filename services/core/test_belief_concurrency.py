"""
Concurrency stress test for BeliefState model.

Tests:
1. Parallel writes to store
2. Read during write
3. Index consistency
"""
import asyncio
import uuid
import time
from typing import List

def run_concurrency_tests():
    print("=" * 70)
    print("CONCURRENCY STRESS TESTS")
    print("=" * 70)
    
    results = []
    
    # TEST 1: Parallel writes
    print("\n" + "=" * 70)
    print("TEST 1: PARALLEL WRITES (10 concurrent)")
    print("=" * 70)
    
    from autonomy.propositions import (
        get_proposition_store, reset_propositions, Proposition
    )
    
    reset_propositions()
    store = get_proposition_store()
    
    async def write_propositions(worker_id: int, count: int):
        for i in range(count):
            prop = Proposition(
                id=uuid.uuid4(),
                subject_type='test',
                subject_id=f'worker_{worker_id}',
                predicate=f'prop_{i}',
                value=True,
                confidence=0.8
            )
            store.add(prop)
    
    async def run_parallel_writes():
        tasks = [write_propositions(i, 100) for i in range(10)]
        await asyncio.gather(*tasks)
    
    start = time.time()
    asyncio.run(run_parallel_writes())
    duration = time.time() - start
    
    expected = 10 * 100
    actual = len(store.get_all())
    
    print(f"\nExpected propositions: {expected}")
    print(f"Actual propositions: {actual}")
    print(f"Duration: {duration:.3f}s")
    
    if actual == expected:
        print("\nPASS: All writes succeeded")
        results.append(True)
    else:
        print(f"\nFAIL: Lost {expected - actual} propositions")
        results.append(False)
    
    # TEST 2: Index consistency
    print("\n" + "=" * 70)
    print("TEST 2: INDEX CONSISTENCY")
    print("=" * 70)
    
    # Check all indexes match
    by_subject_total = sum(len(v) for v in store._by_subject.values())
    by_goal_total = sum(len(v) for v in store._by_goal.values())
    
    print(f"\nMain store: {len(store._propositions)}")
    print(f"by_subject index: {by_subject_total}")
    print(f"by_goal index: {by_goal_total}")
    
    if len(store._propositions) == by_subject_total == by_goal_total:
        print("\nPASS: All indexes consistent")
        results.append(True)
    else:
        print("\nFAIL: Index mismatch")
        results.append(False)
    
    # TEST 3: Read during write
    print("\n" + "=" * 70)
    print("TEST 3: READ DURING WRITE")
    print("=" * 70)
    
    reset_propositions()
    
    read_counts = []
    write_completed = False
    
    async def continuous_read():
        while not write_completed:
            props = store.get_all()
            read_counts.append(len(props))
            await asyncio.sleep(0.001)
    
    async def continuous_write():
        for i in range(1000):
            prop = Proposition(
                id=uuid.uuid4(),
                subject_type='test',
                subject_id='concurrent',
                predicate=f'prop_{i}',
                value=True,
                confidence=0.9
            )
            store.add(prop)
            await asyncio.sleep(0.001)
    
    async def run_concurrent_rw():
        global write_completed
        read_task = asyncio.create_task(continuous_read())
        await continuous_write()
        write_completed = True
        await read_task
    
    asyncio.run(run_concurrent_rw())
    
    print(f"\nRead operations: {len(read_counts)}")
    print(f"Min count observed: {min(read_counts)}")
    print(f"Max count observed: {max(read_counts)}")
    print(f"Final count: {len(store.get_all())}")
    
    # Check if we observed intermediate states
    observed_growth = max(read_counts) > 0 and max(read_counts) < 1000
    
    if len(store.get_all()) == 1000:
        print("\nPASS: All writes visible after completion")
        results.append(True)
    else:
        print(f"\nFAIL: Expected 1000, got {len(store.get_all())}")
        results.append(False)
    
    # TEST 4: BeliefStateBuilder during concurrent modification
    print("\n" + "=" * 70)
    print("TEST 4: BELIEF BUILDING DURING MODIFICATION")
    print("=" * 70)
    
    reset_propositions()
    
    # Initial population
    for i in range(100):
        prop = Proposition(
            id=uuid.uuid4(),
            subject_type='goal',
            subject_id='test_goal',
            predicate='status',
            value=True,
            confidence=0.7
        )
        store.add(prop)
    
    from autonomy.beliefs import BeliefStateBuilder
    
    builder = BeliefStateBuilder()
    
    errors = []
    
    async def modify_store():
        for i in range(100):
            prop = Proposition(
                id=uuid.uuid4(),
                subject_type='goal',
                subject_id='test_goal',
                predicate='status',
                value=i % 2 == 0,
                confidence=0.5 + (i % 5) * 0.1
            )
            store.add(prop)
            await asyncio.sleep(0.001)
    
    async def build_beliefs():
        for i in range(50):
            try:
                world = builder.build(store.get_all())
                if 'goal:test_goal:status' in world.belief_states:
                    bs = world.belief_states['goal:test_goal:status']
                else:
                    pass  # Belief state might not exist yet
            except Exception as e:
                errors.append(str(e))
            await asyncio.sleep(0.002)
    
    async def run_builder_test():
        await asyncio.gather(modify_store(), build_beliefs())
    
    asyncio.run(run_builder_test())
    
    print(f"\nBuilder calls: 50")
    print(f"Errors: {len(errors)}")
    print(f"Final proposition count: {len(store.get_all())}")
    
    if len(errors) == 0:
        print("\nPASS: No errors during concurrent build")
        results.append(True)
    else:
        print(f"\nFAIL: {len(errors)} errors: {errors[:3]}")
        results.append(False)
    
    # SUMMARY
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    test_names = [
        "Parallel Writes",
        "Index Consistency", 
        "Read During Write",
        "Belief Building Under Modification"
    ]
    
    for name, passed in zip(test_names, results):
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<35}: {status}")
    
    print(f"\nPassed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✅ ALL CONCURRENCY TESTS PASSED")
    else:
        print("\n⚠️  SOME CONCURRENCY TESTS FAILED")
        print("\nRECOMMENDATION: Add threading.Lock to PropositionStore")

if __name__ == "__main__":
    run_concurrency_tests()
