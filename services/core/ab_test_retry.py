#!/usr/bin/env python3
"""
A/B Test: Retry Strategy Effectiveness

RULE: If delta < 5%, DELETE retry layer. No reinterpretation.

Groups:
  A: max_attempts = 1 (no retry)
  B: max_attempts = 2 (with retry)

Assignment: Random 50/50 per goal
Seed: Logged in execution_trace.ab_test_seed
"""

import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict, List

AB_TEST_CONFIG = {
    "total_goals": 300,
    "max_attempts_A": 1,
    "max_attempts_B": 2,
    "assignment_ratio": 0.5,
    "decision_threshold_delete": 0.05,
    "decision_threshold_keep": 0.08,
    "frozen_date": "2026-02-24",
    "review_date": "2026-02-26"
}


class ABTestRunner:
    def __init__(self, seed: int = None):
        self.seed = seed or int(datetime.now().timestamp())
        random.seed(self.seed)
        self.results = {
            "A": {"goals": [], "completed": 0, "blocked": 0, "total_confidence": 0.0},
            "B": {"goals": [], "completed": 0, "blocked": 0, "total_confidence": 0.0}
        }
        self.assignments = []
    
    def assign_group(self, goal_id: str) -> tuple[str, int]:
        """Assign goal to group A or B randomly."""
        is_group_b = random.random() >= AB_TEST_CONFIG["assignment_ratio"]
        group = "B" if is_group_b else "A"
        max_attempts = AB_TEST_CONFIG["max_attempts_B"] if is_group_b else AB_TEST_CONFIG["max_attempts_A"]
        
        assignment = {
            "goal_id": goal_id,
            "group": group,
            "max_attempts": max_attempts,
            "seed": self.seed,
            "assigned_at": datetime.utcnow().isoformat()
        }
        self.assignments.append(assignment)
        
        return group, max_attempts
    
    async def create_test_goal(self, goal_num: int, session) -> str:
        """Create a test goal and assign to A/B group."""
        goal_id = str(uuid.uuid4())
        
        group, max_attempts = self.assign_group(goal_id)
        
        from sqlalchemy import text
        await session.execute(text(f'''
            INSERT INTO goals (
                id, title, description, goal_type, is_atomic,
                status, progress, created_at, depth_level,
                execution_trace
            )
            VALUES (
                '{goal_id}',
                'A/B Test Goal {goal_num}',
                'Test goal for retry effectiveness study',
                'achievable',
                true,
                'active',
                0.0,
                NOW(),
                3,
                jsonb_build_object(
                    'ab_test', true,
                    'ab_group', '{group}',
                    'ab_max_attempts', {max_attempts},
                    'ab_seed', {self.seed}
                )
            )
        '''))
        
        self.results[group]["goals"].append(goal_id)
        
        return goal_id
    
    async def execute_goal_with_group_config(self, goal_id: str, max_attempts: int) -> Dict:
        """Execute goal respecting A/B group assignment."""
        from goal_executor_v2 import GoalExecutorV2
        
        executor = GoalExecutorV2()
        
        original_max = 2
        try:
            import goal_executor_v2
            original_max = goal_executor_v2.MAX_ATTEMPTS
            goal_executor_v2.MAX_ATTEMPTS = max_attempts
        except:
            pass
        
        try:
            result = await executor.execute_goal(goal_id)
            return result
        finally:
            try:
                goal_executor_v2.MAX_ATTEMPTS = original_max
            except:
                pass
    
    async def run_batch(self, batch_size: int = 10, delay_seconds: int = 30):
        """Run a batch of goals with delay between batches."""
        from database import AsyncSessionLocal
        
        print(f"\n{'='*60}")
        print(f"A/B TEST BATCH")
        print(f"Seed: {self.seed}")
        print(f"Batch size: {batch_size}")
        print(f"{'='*60}\n")
        
        for i in range(batch_size):
            async with AsyncSessionLocal() as session:
                goal_id = await self.create_test_goal(i, session)
                await session.commit()
            
            assignment = self.assignments[-1]
            print(f"Goal {i+1}/{batch_size}: {goal_id[:8]} → Group {assignment['group']} (max_attempts={assignment['max_attempts']})")
            
            result = await self.execute_goal_with_group_config(
                goal_id,
                assignment["max_attempts"]
            )
            
            group = assignment["group"]
            if result.get("status") == "completed":
                self.results[group]["completed"] += 1
            elif result.get("status") == "failed":
                self.results[group]["blocked"] += 1
            
            confidence = result.get("final_confidence", 0.0)
            self.results[group]["total_confidence"] += confidence
            
            print(f"  → {result.get('status')}, confidence={confidence:.2f}")
            
            await asyncio.sleep(2)
        
        print(f"\nBatch complete. Sleeping {delay_seconds}s...\n")
        await asyncio.sleep(delay_seconds)
    
    def compute_metrics(self) -> Dict:
        """Compute A/B test metrics."""
        metrics = {}
        
        for group in ["A", "B"]:
            total = len(self.results[group]["goals"])
            completed = self.results[group]["completed"]
            blocked = self.results[group]["blocked"]
            total_conf = self.results[group]["total_confidence"]
            
            metrics[group] = {
                "total": total,
                "completed": completed,
                "blocked": blocked,
                "completion_rate": completed / total if total > 0 else 0.0,
                "block_rate": blocked / total if total > 0 else 0.0,
                "avg_confidence": total_conf / completed if completed > 0 else 0.0
            }
        
        delta = metrics["B"]["completion_rate"] - metrics["A"]["completion_rate"]
        
        metrics["delta"] = delta
        metrics["delta_percent"] = delta * 100
        metrics["decision"] = self._make_decision(delta)
        
        return metrics
    
    def _make_decision(self, delta: float) -> str:
        """Make decision based on delta."""
        if delta >= AB_TEST_CONFIG["decision_threshold_keep"]:
            return "KEEP: Retry validated, freeze implementation"
        elif delta >= AB_TEST_CONFIG["decision_threshold_delete"]:
            return "MARGINAL: Keep retry, NO enhancements allowed"
        else:
            return "DELETE: Retry does not provide sufficient value"
    
    def print_summary(self):
        """Print final summary."""
        metrics = self.compute_metrics()
        
        print(f"\n{'='*60}")
        print("A/B TEST RESULTS")
        print(f"{'='*60}")
        print(f"Seed: {self.seed}")
        print(f"Total assignments: {len(self.assignments)}")
        print()
        
        for group in ["A", "B"]:
            m = metrics[group]
            print(f"Group {group} (max_attempts={AB_TEST_CONFIG[f'max_attempts_{group}']}):")
            print(f"  Total:      {m['total']}")
            print(f"  Completed:  {m['completed']}")
            print(f"  Blocked:    {m['blocked']}")
            print(f"  Completion: {m['completion_rate']:.2%}")
            print(f"  Avg Conf:   {m['avg_confidence']:.2f}")
            print()
        
        print(f"DELTA: {metrics['delta_percent']:.2f}%")
        print(f"\nDECISION: {metrics['decision']}")
        print(f"{'='*60}\n")
        
        if metrics['delta'] < AB_TEST_CONFIG["decision_threshold_delete"]:
            print("⚠️  RETRY LAYER WILL BE DELETED")
        elif metrics['delta'] >= AB_TEST_CONFIG["decision_threshold_keep"]:
            print("✅ RETRY VALIDATED - FREEZE IMPLEMENTATION")
        else:
            print("📊 MARGINAL - KEEP SIMPLE, MONITOR")


async def run_ab_test():
    """Run complete A/B test."""
    runner = ABTestRunner()
    
    print(f"\n{'='*60}")
    print("STARTING A/B TEST")
    print(f"{'='*60}")
    print(f"Config: {AB_TEST_CONFIG}")
    print(f"Decision rule: delta < 5% → DELETE, delta ≥ 8% → KEEP")
    print(f"{'='*60}\n")
    
    batches = 30
    batch_size = 10
    
    for batch_num in range(batches):
        print(f"\nBatch {batch_num + 1}/{batches}")
        await runner.run_batch(batch_size=batch_size, delay_seconds=60)
    
    runner.print_summary()
    
    return runner


if __name__ == "__main__":
    asyncio.run(run_ab_test())
