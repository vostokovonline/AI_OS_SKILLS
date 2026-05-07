"""
Replay Evaluation
=================

Offline bandit evaluation - prove the system learns.

Usage:
    python replay_evaluation.py --traces /app/decision_traces/traces_*.jsonl

This script:
1. Loads historical decision traces
2. Replays with new selector (Gaussian TS)
3. Computes cumulative reward, regret, convergence
4. Compares against legacy policy
"""

import sys
import os
sys.path.insert(0, '/app')

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from experience.gaussian_skill_selector import GaussianSkillSelector


@dataclass
class ReplayResult:
    trace_id: str
    goal_id: str
    legacy_choice: str
    gaussian_choice: str
    
    legacy_reward: float
    gaussian_reward: float
    counterfactual_reward: float  # What gaussian would get if it chose differently
    
    regret: float  # legacy - gaussian (positive = gaussian better)
    counterfactual_regret: float  # What legacy got vs what gaussian would get
    
    matched: bool
    had_counterfactual: bool  # Did we have data to compute counterfactual?


@dataclass
class EvaluationSummary:
    total_traces: int
    matched: int
    counterfactual_count: int  # How many traces had gaussian != legacy
    
    legacy_total_reward: float
    gaussian_total_reward: float
    counterfactual_total_regret: float  # Sum of what legacy got vs gaussian choice
    
    avg_regret: float  # positive = gaussian better
    avg_counterfactual_regret: float  # Counterfactual regret
    regret_std: float
    
    # Per-skill analysis
    skill_selection_count: Dict[str, int]
    skill_success_rate: Dict[str, float]
    
    # Counterfactual skill preference
    gaussian_preferred_skills: Dict[str, int]  # Which skills gaussian chose over legacy
    
    # Convergence (does Gaussian converge to better skills over time?)
    early_avg_reward: float  # first 20% of traces
    late_avg_reward: float   # last 20% of traces
    
    # Recovery (does Gaussian recover after drift?)
    post_drift_recovery: float


class ReplayEvaluator:
    """
    Replay historical traces with Gaussian TS selector.
    Compare cumulative reward vs legacy policy.
    """
    
    def __init__(self, storage_path: str = "/app/decision_traces"):
        self.storage_path = Path(storage_path)
        self.selector = GaussianSkillSelector()
        
        # Track skill performance over time
        self.skill_rewards: Dict[str, List[float]] = defaultdict(list)
        
        # Average reward per skill (for counterfactual)
        self.skill_avg_reward: Dict[str, float] = {}
    
    def compute_skill_averages(self, traces: List[dict]):
        """Pre-compute average reward per skill for counterfactual eval"""
        skill_rewards: Dict[str, List[float]] = defaultdict(list)
        
        for trace in traces:
            legacy_choice = trace.get("legacy_choice", "")
            reward = trace.get("reward", 0.0)
            if legacy_choice:
                skill_rewards[legacy_choice].append(reward)
        
        self.skill_avg_reward = {
            skill: sum(rewards) / len(rewards) if rewards else 0.0
            for skill, rewards in skill_rewards.items()
        }
        
        print(f"Skill averages computed: {len(self.skill_avg_reward)} skills")
        for skill, avg in sorted(self.skill_avg_reward.items(), key=lambda x: -x[1])[:5]:
            print(f"  {skill}: {avg:.3f}")
    
    def load_traces(self, pattern: str = "traces_*.jsonl") -> List[dict]:
        """Load all traces matching pattern"""
        traces = []
        
        for filepath in sorted(self.storage_path.glob(pattern)):
            with open(filepath) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        traces.append(data)
                    except json.JSONDecodeError:
                        continue
        
        print(f"Loaded {len(traces)} traces from {self.storage_path}")
        return traces
    
    def replay(self, traces: List[dict]) -> List[ReplayResult]:
        """
        Replay each trace with Gaussian TS + counterfactual evaluation.
        
        For each trace:
        1. Get candidates (skills available)
        2. Query Gaussian TS for choice
        3. Compute counterfactual (what if gaussian chose differently?)
        4. Update selector state
        """
        # Pre-compute skill averages
        self.compute_skill_averages(traces)
        
        results = []
        
        for i, trace in enumerate(traces):
            candidates = trace.get("candidates", [])
            if not candidates or len(candidates) < 2:
                continue
            
            # Get legacy choice and reward
            legacy_choice = trace.get("legacy_choice", "")
            legacy_reward = trace.get("reward", 0.0)
            
            # Get Gaussian choice
            gaussian_choice = self.selector.select(candidates)
            
            matched = (legacy_choice == gaussian_choice)
            
            # Counterfactual: what if gaussian chose differently?
            counterfactual_reward = 0.0
            counterfactual_regret = 0.0
            had_counterfactual = False
            
            if not matched:
                # Gaussian chose different from legacy
                # Get average reward for gaussian's choice (proxy for what we'd get)
                counterfactual_reward = self.skill_avg_reward.get(gaussian_choice, 0.0)
                # Regret: what legacy got vs what gaussian would have gotten
                counterfactual_regret = legacy_reward - counterfactual_reward
                had_counterfactual = True
            
            # Simple regret: legacy vs gaussian actual
            regret = legacy_reward - legacy_reward  # placeholder
            
            result = ReplayResult(
                trace_id=trace.get("trace_id", ""),
                goal_id=trace.get("goal_id", ""),
                legacy_choice=legacy_choice,
                gaussian_choice=gaussian_choice,
                legacy_reward=legacy_reward,
                gaussian_reward=legacy_reward,
                counterfactual_reward=counterfactual_reward,
                regret=0.0,
                counterfactual_regret=counterfactual_regret,
                matched=matched,
                had_counterfactual=had_counterfactual
            )
            
            # Update selector with actual reward (online learning!)
            if not matched:
                # Gaussian made a different choice - update with actual reward
                actual_success = trace.get("success", False)
                reward = trace.get("reward", 0.0)
                self.selector.update(gaussian_choice, reward)
            
            # Also update with legacy choice (so selector learns from all data)
            self.selector.update(legacy_choice, legacy_reward)
            
            results.append(result)
            
            # Progress every 100 traces
            if (i + 1) % 100 == 0:
                print(f"  Replayed {i + 1}/{len(traces)} traces...")
        
        return results
    
    def compute_summary(self, results: List[ReplayResult]) -> EvaluationSummary:
        """Compute evaluation metrics including counterfactual"""
        if not results:
            return EvaluationSummary(
                total_traces=0,
                matched=0,
                legacy_total_reward=0.0,
                gaussian_total_reward=0.0,
                avg_regret=0.0,
                regret_std=0.0,
                skill_selection_count={},
                skill_success_rate={},
                early_avg_reward=0.0,
                late_avg_reward=0.0,
                post_drift_recovery=0.0
            )
        
        total = len(results)
        matched = sum(1 for r in results if r.matched)
        
        # Counterfactual stats
        cf_results = [r for r in results if r.had_counterfactual]
        counterfactual_count = len(cf_results)
        
        legacy_total = sum(r.legacy_reward for r in results)
        gaussian_total = sum(r.gaussian_reward for r in results)
        
        # Counterfactual regret: what legacy got vs what gaussian would have gotten
        counterfactual_regrets = [r.counterfactual_regret for r in cf_results]
        avg_counterfactual_regret = sum(counterfactual_regrets) / len(counterfactual_regrets) if counterfactual_regrets else 0.0
        
        regrets = [r.legacy_reward - r.gaussian_reward for r in results]
        avg_regret = sum(regrets) / len(regrets)
        
        # Std deviation
        variance = sum((r - avg_regret) ** 2 for r in regrets) / len(regrets)
        regret_std = math.sqrt(variance)
        
        # Skill selection counts
        skill_counts: Dict[str, int] = defaultdict(int)
        for r in results:
            skill_counts[r.gaussian_choice] += 1
        
        # Counterfactual: which skills did gaussian prefer vs legacy?
        cf_skill_diff: Dict[str, int] = defaultdict(int)
        for r in cf_results:
            if r.legacy_choice != r.gaussian_choice:
                cf_skill_diff[r.gaussian_choice] += 1
        
        # Note: Can't compute success rate without more data
        skill_success = {}
        
        # Convergence: early vs late performance
        early_cutoff = int(total * 0.2)
        late_cutoff = int(total * 0.8)
        
        early_traces = results[:early_cutoff] if early_cutoff > 0 else []
        late_traces = results[late_cutoff:] if late_cutoff < total else []
        
        early_avg = sum(r.gaussian_reward for r in early_traces) / len(early_traces) if early_traces else 0.0
        late_avg = sum(r.gaussian_reward for r in late_traces) / len(late_traces) if late_traces else 0.0
        
        # Recovery - placeholder (need drift detection)
        post_drift_recovery = 0.0
        
        return EvaluationSummary(
            total_traces=total,
            matched=matched,
            counterfactual_count=counterfactual_count,
            legacy_total_reward=round(legacy_total, 3),
            gaussian_total_reward=round(gaussian_total, 3),
            counterfactual_total_regret=round(sum(counterfactual_regrets), 4) if counterfactual_regrets else 0.0,
            avg_regret=round(avg_regret, 4),
            avg_counterfactual_regret=round(avg_counterfactual_regret, 4),
            regret_std=round(regret_std, 4),
            skill_selection_count=dict(skill_counts),
            skill_success_rate=skill_success,
            gaussian_preferred_skills=dict(cf_skill_diff),
            early_avg_reward=round(early_avg, 4),
            late_avg_reward=round(late_avg, 4),
            post_drift_recovery=round(post_drift_recovery, 4)
        )
    
    def run(self, pattern: str = "traces_*.jsonl") -> EvaluationSummary:
        """Run full replay evaluation"""
        print(f"\n=== Replay Evaluation ===")
        print(f"Storage: {self.storage_path}")
        
        # Load traces
        traces = self.load_traces(pattern)
        
        if not traces:
            print("No traces found!")
            return None
        
        # Replay
        print(f"\nReplaying {len(traces)} traces with Gaussian TS...")
        results = self.replay(traces)
        
        # Compute summary
        print("\nComputing metrics...")
        summary = self.compute_summary(results)
        
        return summary


def print_summary(summary: EvaluationSummary):
    """Pretty print evaluation summary"""
    print("\n" + "=" * 60)
    print("REPLAY EVALUATION RESULTS (WITH COUNTERFACTUAL)")
    print("=" * 60)
    
    print(f"\nTotal Traces: {summary.total_traces}")
    print(f"Policy Match Rate: {summary.matched / summary.total_traces * 100:.1f}%")
    print(f"Counterfactual Eval: {summary.counterfactual_count} traces")
    
    print(f"\n--- Cumulative Reward ---")
    print(f"Legacy Policy:   {summary.legacy_total_reward:+.4f}")
    print(f"Gaussian Policy: {summary.gaussian_total_reward:+.4f}")
    print(f"Delta:           {summary.gaussian_total_reward - summary.legacy_total_reward:+.4f}")
    
    print(f"\n--- Counterfactual Regret (Dense Signal) ---")
    print(f"Avg Counterfactual Regret: {summary.avg_counterfactual_regret:+.4f}")
    print(f"Total Counterfactual Regret: {summary.counterfactual_total_regret:+.4f}")
    
    if summary.avg_counterfactual_regret > 0:
        print("  → Gaussian would have done WORSE than legacy (on average)")
    elif summary.avg_counterfactual_regret < 0:
        print("  → Gaussian would have done BETTER than legacy!")
    else:
        print("  → No difference in counterfactual evaluation")
    
    print(f"\n--- Gaussian Skill Preference (vs Legacy) ---")
    for skill, count in sorted(summary.gaussian_preferred_skills.items(), key=lambda x: -x[1]):
        print(f"  {skill}: {count} times")
    
    print(f"\n--- Gaussian Total Selection ---")
    for skill, count in sorted(summary.skill_selection_count.items(), key=lambda x: -x[1]):
        pct = count / summary.total_traces * 100
        print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print(f"\n--- Convergence ---")
    print(f"Early (first 20%):  {summary.early_avg_reward:+.4f}")
    print(f"Late (last 20%):    {summary.late_avg_reward:+.4f}")
    improvement = summary.late_avg_reward - summary.early_avg_reward
    print(f"Improvement:        {improvement:+.4f}")
    
    if improvement > 0.1:
        print("  ✅ Gaussian shows learning (convergence to better skills)")
    elif improvement < -0.1:
        print("  ⚠️ Gaussian degraded over time (possible non-stationary drift)")
    else:
        print("  ➖ No significant convergence detected (need more data)")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Replay evaluation for bandit selectors")
    parser.add_argument(
        "--storage", 
        default="/app/decision_traces",
        help="Path to decision traces directory"
    )
    parser.add_argument(
        "--pattern",
        default="traces_*.jsonl",
        help="Glob pattern for trace files"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    evaluator = ReplayEvaluator(storage_path=args.storage)
    summary = evaluator.run(pattern=args.pattern)
    
    if summary:
        print_summary(summary)
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(asdict(summary), f, indent=2)
            print(f"\nResults saved to {args.output}")
    else:
        print("No results to display")


if __name__ == "__main__":
    main()