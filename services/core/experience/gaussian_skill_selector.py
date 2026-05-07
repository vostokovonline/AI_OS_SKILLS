"""
Gaussian Skill Selector - Production-Ready
==========================================
Windowed Gaussian Thompson Sampling with tanh reward normalization

Key properties:
- Non-stationary: sliding window for memory
- Exploration: natural through variance, no magic numbers
- Stable: tanh normalization prevents variance explosion
- Principled: no override, no audit, no hard thresholds
"""

import math
import random
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

WINDOW_SIZE = 50  # Environment timescale - how fast things change
REWARD_SCALE = 1.5  # Tanh normalization scale


@dataclass
class SkillResult:
    success: bool
    latency: float


class GaussianTracker:
    """Gaussian Thompson Sampling with sliding window"""
    
    def __init__(self, skill_id: str, window_size: int = WINDOW_SIZE):
        self.skill_id = skill_id
        self.history: deque = deque(maxlen=window_size)
        self.total_selections = 0
    
    @property
    def n(self) -> int:
        return len(self.history)
    
    @property
    def mean(self) -> float:
        if self.n == 0:
            return 0.0
        return sum(self.history) / self.n
    
    @property
    def variance(self) -> float:
        if self.n < 2:
            return 1.0
        m = self.mean
        return sum((x - m) ** 2 for x in self.history) / self.n
    
    @property
    def std(self) -> float:
        return max(math.sqrt(self.variance), 0.1)
    
    def sample(self) -> float:
        """Thompson Sampling - exploration through variance"""
        if self.n == 0:
            return random.gauss(0.0, 1.0)
        return random.gauss(self.mean, self.std)
    
    def update(self, reward: float):
        self.history.append(reward)
        self.total_selections += 1


class GaussianSkillSelector:
    """
    Production-ready skill selector with exploration budget.
    
    Selection formula:
        score = sample_from_N(mean, std) + exploration_bonus
    
    Exploration mechanisms:
        - epsilon_floor: minimum random exploration probability
        - entropy_bonus: boost under-explored skills
        - uncertainty_trigger: extra exploration when variance is high
    """
    
    WINDOW = WINDOW_SIZE
    SCALE = REWARD_SCALE
    
    # Exploration params
    EPSILON_FLOOR = 0.05  # 5% random exploration always
    ENTROPY_FLOOR = 0.02  # Small boost for under-explored
    UNCERTAINTY_THRESHOLD = 0.5  # Std threshold for extra exploration
    
    def __init__(
        self, 
        window_size: int = WINDOW_SIZE, 
        scale: float = REWARD_SCALE,
        temperature: float = 1.0,
        epsilon_floor: float = 0.05
    ):
        self.window_size = window_size
        self.scale = scale
        self.temperature = temperature
        self.epsilon_floor = epsilon_floor
        self.trackers: Dict[str, GaussianTracker] = {}
        self.total_steps = 0
        self.exploration_count = 0
    
    def _get_tracker(self, skill_id: str) -> GaussianTracker:
        if skill_id not in self.trackers:
            self.trackers[skill_id] = GaussianTracker(skill_id, self.window_size)
        return self.trackers[skill_id]
    
    def _raw_reward(self, result: SkillResult) -> float:
        """Raw reward before normalization"""
        if not result.success:
            return -2.0
        return 1.0 - min(result.latency * 0.3, 0.3)
    
    def reward(self, result: SkillResult) -> float:
        """
        Normalized reward using tanh.
        
        Maps:
            -2.0 -> -0.87  (extreme failure compressed)
            +0.9 -> +0.54  (success)
            +1.0 -> +0.58  (max reward)
        
        This prevents variance explosion from extreme negative rewards.
        """
        raw = self._raw_reward(result)
        return math.tanh(raw / self.scale)
    
    def select(self, skill_ids: List[str]) -> Tuple[str, str]:
        """
        Select skill using Thompson Sampling with exploration budget.
        
        Returns:
            (selected_skill, exploration_mode) where mode is "explore" or "exploit"
        """
        self.total_steps += 1
        
        if not skill_ids:
            raise ValueError("No skills to select from")
        
        # Exploration check: epsilon-flip for guaranteed minimum exploration
        if random.random() < self.epsilon_floor:
            selected = random.choice(skill_ids)
            self.exploration_count += 1
            return selected, "explore"
        
        # Thompson Sampling: sample from each and pick max
        scores = {sid: self._get_tracker(sid).sample() for sid in skill_ids}
        
        # Check uncertainty: if top skills have high variance, add exploration bonus
        top_skills = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        if len(top_skills) >= 2:
            top_std = self._get_tracker(top_skills[0][0]).std
            second_std = self._get_tracker(top_skills[1][0]).std
            avg_std = (top_std + second_std) / 2
            if avg_std > self.UNCERTAINTY_THRESHOLD:
                # High uncertainty - add random boost to exploration
                for sid in skill_ids:
                    scores[sid] += random.uniform(0, self.ENTROPY_FLOOR)
                self.exploration_count += 1
        
        selected = max(scores, key=scores.get)
        
        return selected, "balanced" if self.exploration_count > 0 else "exploit"
    
    def update(self, skill_id: str, reward: float):
        """Update tracker with normalized reward"""
        self._get_tracker(skill_id).update(reward)
    
    def get_selection_probability(self, candidates: List[str], chosen: str) -> float:
        """
        Compute P(chosen | candidates) under current Thompson sampling policy.
        
        This is used as propensity score for IPS/Doubly Robust evaluation.
        
        Approximation: Use softmax over sampled scores.
        """
        if not candidates or chosen not in candidates:
            return 0.0
        
        # Get samples
        scores = {sid: self._get_tracker(sid).sample() for sid in candidates}
        
        # Softmax over scores (temperature-scaled)
        exp_scores = {sid: math.exp(scores[sid] / self.temperature) for sid in candidates}
        total = sum(exp_scores.values())
        
        if total == 0:
            return 1.0 / len(candidates)  # Uniform if no info
        
        return exp_scores.get(chosen, 0) / total
    
    def stats(self) -> Dict:
        """Return selector statistics for monitoring"""
        return {
            "total_steps": self.total_steps,
            "skills": {
                sid: {
                    "n": t.n,
                    "mean": round(t.mean, 3),
                    "std": round(t.std, 3),
                    "selections": t.total_selections
                }
                for sid, t in self.trackers.items()
            }
        }


def example_usage():
    """Example of how to integrate into AI-OS"""
    selector = GaussianSkillSelector()
    
    # In goal execution:
    skill_ids = ["echo", "write_file", "web_research"]
    
    # Select skill
    chosen = selector.select(skill_ids)
    print(f"Selected: {chosen}")
    
    # After execution:
    result = SkillResult(success=True, latency=0.1)
    selector.update(chosen, result)
    
    # Monitor
    print(selector.stats())


if __name__ == "__main__":
    example_usage()