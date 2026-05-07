#!/usr/bin/env python3
"""
Load Test Script - 24 hour continuous test
Generates goals and monitors system health
"""

import asyncio
import httpx
import time
import random
from datetime import datetime
from typing import Dict, List, Optional
import json


class LoadTest24h:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Metrics tracking
        self.goals_created = 0
        self.goals_completed = 0
        self.goals_failed = 0
        self.errors: List[str] = []
        self.backlog_history: List[Dict] = []
        self.status_distribution: Dict[str, int] = {}
        
        # Test config
        self.cycle_duration_hours = 2  # Run for 2 hours for quick test
        self.cycle_interval = 5  # Create goal every 5 seconds
        self.metrics_interval = 60  # Collect metrics every 60 seconds
        
    async def close(self):
        await self.client.aclose()
    
    async def create_goal(self, goal_type: str = "achievable") -> Optional[str]:
        """Create a new goal via API"""
        titles = {
            "fast": f"Fast test goal {random.randint(1000, 9999)}",
            "medium": f"Medium test goal {random.randint(1000, 9999)} - requires processing",
            "fail": f"Failing test goal {random.randint(1000, 9999)}",
        }
        
        data = {
            "title": titles.get(goal_type, titles["fast"]),
            "description": f"Load test goal - {goal_type}",
            "goal_type": goal_type,
            "is_atomic": True,
            "domain": "testing",
            "priority": random.choice(["low", "normal", "high"])
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/goals/create",
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                goal_id = result.get("goal_id")
                if goal_id:
                    self.goals_created += 1
                    return goal_id
            else:
                self.errors.append(f"Create goal failed: {response.status_code}")
        except Exception as e:
            self.errors.append(f"Create goal error: {str(e)}")
        
        return None
    
    async def collect_metrics(self) -> Dict:
        """Collect system metrics"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "goals_created": self.goals_created,
            "goals_completed": self.goals_completed,
            "goals_failed": self.goals_failed,
            "backlog": 0,
            "status_distribution": {},
            "active_goals": 0,
            "pending_goals": 0,
            "done_goals": 0,
        }
        
        try:
            # Get goals list
            response = await self.client.get(f"{self.base_url}/goals/list?page_size=1000")
            if response.status_code == 200:
                data = response.json()
                goals = data.get("goals", [])
                
                # Count by status
                status_counts: Dict[str, int] = {}
                for goal in goals:
                    status = goal.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                metrics["status_distribution"] = status_counts
                metrics["backlog"] = status_counts.get("pending", 0)
                metrics["active_goals"] = status_counts.get("active", 0)
                metrics["pending_goals"] = status_counts.get("pending", 0)
                metrics["done_goals"] = status_counts.get("done", 0)
                
        except Exception as e:
            self.errors.append(f"Collect metrics error: {str(e)}")
        
        return metrics
    
    async def check_scheduler_health(self) -> Dict:
        """Check if scheduler is running"""
        health = {
            "scheduler_running": False,
            "jobs_count": 0,
        }
        
        try:
            # Check if atomic execution happened recently by looking at recently updated goals
            response = await self.client.get(f"{self.base_url}/goals/list?page_size=10")
            if response.status_code == 200:
                data = response.json()
                goals = data.get("goals", [])
                
                # Check if any goals were updated in last 2 minutes
                now = datetime.now()
                recently_updated = 0
                for goal in goals:
                    updated = goal.get("updated_at")
                    if updated:
                        try:
                            goal_time = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            if (now - goal_time).total_seconds() < 120:
                                recently_updated += 1
                        except:
                            pass
                
                health["recently_updated_goals"] = recently_updated
                
        except Exception as e:
            self.errors.append(f"Health check error: {str(e)}")
        
        return health
    
    async def run_cycle(self):
        """Run one cycle of goal creation"""
        # Randomly choose goal type
        goal_type = random.choices(
            ["fast", "medium", "fail"],
            weights=[0.7, 0.2, 0.1]
        )[0]
        
        goal_id = await self.create_goal(goal_type)
        if goal_id:
            print(f"  [CYCLE] Created goal: {goal_id[:8]}... ({goal_type})")
    
    async def run_metrics_collection(self):
        """Collect and display metrics"""
        metrics = await self.collect_metrics()
        health = await self.check_scheduler_health()
        
        self.backlog_history.append({
            "timestamp": metrics["timestamp"],
            "backlog": metrics["backlog"],
            "created": self.goals_created,
            "completed": metrics["done_goals"],
        })
        
        print(f"\n{'='*60}")
        print(f"METRICS at {metrics['timestamp']}")
        print(f"{'='*60}")
        print(f"Goals Created: {metrics['goals_created']}")
        print(f"Goals Done:     {metrics['done_goals']}")
        print(f"Backlog:       {metrics['backlog']}")
        print(f"Status Dist:   {metrics['status_distribution']}")
        print(f"Scheduler:     recently_updated={health.get('recently_updated_goals', 0)}")
        print(f"Errors:        {len(self.errors)}")
        print(f"{'='*60}\n")
        
        return metrics, health
    
    def print_summary(self):
        """Print final summary"""
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total Goals Created: {self.goals_created}")
        print(f"Total Errors: {len(self.errors)}")
        
        if self.backlog_history:
            max_backlog = max(h["backlog"] for h in self.backlog_history)
            min_backlog = min(h["backlog"] for h in self.backlog_history)
            print(f"Backlog - Max: {max_backlog}, Min: {min_backlog}")
        
        print(f"\nErrors ({len(self.errors)}):")
        for err in self.errors[-10:]:  # Show last 10 errors
            print(f"  - {err}")
        
        # Determine status
        recent_errors = len([e for e in self.errors if "last 5 min" in e])  # Could track timestamps
        
        if self.backlog_history:
            final_backlog = self.backlog_history[-1]["backlog"]
            if final_backlog == 0:
                print("\n✅ STATUS: Survived - All goals processed!")
            elif final_backlog < self.goals_created * 0.5:
                print("\n⚠️ STATUS: Degraded - Some backlog remains")
            else:
                print("\n❌ STATUS: Failed - Backlog growing")
        else:
            print("\n❓ STATUS: Unknown - No metrics collected")
        
        print(f"{'='*60}")
    
    async def run(self):
        """Main test loop"""
        print(f"\n{'='*60}")
        print("Starting 24h Load Test (shortened to 2h)")
        print(f"Base URL: {self.base_url}")
        print(f"Goal creation: every {self.cycle_interval}s")
        print(f"Metrics collection: every {self.metrics_interval}s")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        end_time = start_time + (self.cycle_duration_hours * 3600)
        
        last_metrics_time = start_time
        cycle_count = 0
        
        while time.time() < end_time:
            try:
                # Create goals
                await self.run_cycle()
                cycle_count += 1
                
                # Collect metrics periodically
                if time.time() - last_metrics_time >= self.metrics_interval:
                    await self.run_metrics_collection()
                    last_metrics_time = time.time()
                
                # Wait for next cycle
                await asyncio.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                print("\nTest interrupted by user")
                break
            except Exception as e:
                self.errors.append(f"Cycle error: {str(e)}")
                print(f"Error in cycle: {e}")
        
        # Final metrics
        await self.run_metrics_collection()
        
        # Print summary
        self.print_summary()
        
        await self.close()


async def main():
    test = LoadTest24h(base_url="http://localhost:8000")
    await test.run()


if __name__ == "__main__":
    asyncio.run(main())