"""
SKILL EVOLUTION LOOP - Self-Improving AI-OS
=========================================

This layer connects:
Execution → Experience → Stats → Selection → Graph → Composition → Evolution

Author: AI-OS System
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionExperience:
    """Single execution experience."""
    goal_id: str
    goal_title: str
    task: str
    skill_id: str
    capability: str
    success: bool
    duration_ms: int
    confidence: float
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class SkillStats:
    """Aggregated skill statistics."""
    skill_id: str
    capability: str
    usage_count: int = 0
    success_count: int = 0
    total_duration_ms: int = 0
    failure_count: int = 0
    last_used: datetime = None
    
    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    @property
    def avg_duration_ms(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.total_duration_ms / self.usage_count


@dataclass
class SkillTransition:
    """Transition between skills in execution."""
    from_skill: str
    to_skill: str
    count: int = 0
    success_count: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.count == 0:
            return 0.0
        return self.success_count / self.count


class SkillEvolutionLoop:
    """
    Complete Skill Evolution Loop.
    
    Pipeline:
    Execution → Experience → Stats → Selection → Graph → Composition → Evolution
    """
    
    def __init__(self):
        # In-memory storage (would be DB in production)
        self.experiences: List[ExecutionExperience] = []
        self.skill_stats: Dict[str, SkillStats] = {}
        self.transitions: Dict[str, SkillTransition] = {}
        self.capability_skills: Dict[str, List[str]] = defaultdict(list)
        
        logger.info("skill_evolution_loop_initialized")
    
    # =========================================================================
    # LAYER 1: Experience Recording
    # =========================================================================
    
    def record_execution(
        self,
        goal_id: str,
        goal_title: str,
        task: str,
        skill_id: str,
        capability: str,
        success: bool,
        duration_ms: int,
        confidence: float,
        error: Optional[str] = None
    ):
        """Record an execution experience."""
        
        experience = ExecutionExperience(
            goal_id=goal_id,
            goal_title=goal_title,
            task=task,
            skill_id=skill_id,
            capability=capability,
            success=success,
            duration_ms=duration_ms,
            confidence=confidence,
            error=error
        )
        
        self.experiences.append(experience)
        
        # Update stats
        self._update_skill_stats(
            skill_id=skill_id,
            capability=capability,
            success=success,
            duration_ms=duration_ms
        )
        
        logger.info(
            "experience_recorded",
            skill_id=skill_id,
            capability=capability,
            success=success,
            total_experiences=len(self.experiences)
        )
        
        return len(self.experiences)
    
    # =========================================================================
    # LAYER 2: Skill Statistics Engine
    # =========================================================================
    
    def _update_skill_stats(
        self,
        skill_id: str,
        capability: str,
        success: bool,
        duration_ms: int
    ):
        """Update skill statistics."""
        
        if skill_id not in self.skill_stats:
            self.skill_stats[skill_id] = SkillStats(
                skill_id=skill_id,
                capability=capability
            )
        
        stats = self.skill_stats[skill_id]
        stats.usage_count += 1
        stats.total_duration_ms += duration_ms
        
        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1
        
        stats.last_used = datetime.utcnow()
        
        # Track capability -> skill mapping
        if capability not in self.capability_skills[capability]:
            self.capability_skills[capability].append(skill_id)
    
    def get_skill_score(self, skill_id: str) -> float:
        """
        Calculate skill score for selection.
        
        score = success_rate * 0.5 + speed_score * 0.2 + recency * 0.2 + exploration * 0.1
        """
        if skill_id not in self.skill_stats:
            return 0.5  # Default for unknown skills
        
        stats = self.skill_stats[skill_id]
        
        # Success rate (0-1)
        success_score = stats.success_rate
        
        # Speed score (0-1, faster = higher)
        if stats.avg_duration_ms > 0:
            speed_score = min(1.0, 5000 / stats.avg_duration_ms)
        else:
            speed_score = 0.5
        
        # Recency score (0-1, more recent = higher)
        if stats.last_used:
            hours_since = (datetime.utcnow() - stats.last_used).total_seconds() / 3600
            recency_score = max(0, 1 - hours_since / 24)  # Decay over 24 hours
        else:
            recency_score = 0
        
        # Exploration bonus (0-1, less used = higher)
        if stats.usage_count < 5:
            exploration_score = 1.0
        elif stats.usage_count < 20:
            exploration_score = 0.5
        else:
            exploration_score = 0.1
        
        # Weighted score
        score = (
            success_score * 0.5 +
            speed_score * 0.2 +
            recency_score * 0.2 +
            exploration_score * 0.1
        )
        
        return score
    
    def get_best_skill_for_capability(self, capability: str) -> Optional[str]:
        """Get best skill for a capability based on score."""
        skills = self.capability_skills.get(capability, [])
        
        if not skills:
            return None
        
        scored_skills = [
            (skill, self.get_skill_score(skill))
            for skill in skills
        ]
        
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        
        return scored_skills[0][0] if scored_skills else None
    
    # =========================================================================
    # LAYER 3: Skill Selection (Uses Stats)
    # =========================================================================
    
    def select_skill(
        self,
        capability: str,
        available_skills: List[str]
    ) -> Optional[str]:
        """
        Select best skill using learned scores.
        
        This is the key function that makes the system self-improving.
        """
        if not available_skills:
            return None
        
        # Score each available skill
        scored = []
        for skill in available_skills:
            score = self.get_skill_score(skill)
            scored.append((skill, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        best_skill = scored[0][0]
        
        logger.info(
            "skill_selected_with_learning",
            capability=capability,
            selected=best_skill,
            score=scored[0][1],
            alternatives=[s[0] for s in scored[1:3]]
        )
        
        return best_skill
    
    # =========================================================================
    # LAYER 4: Skill Graph (Transitions)
    # =========================================================================
    
    def record_transition(self, from_skill: str, to_skill: str, success: bool):
        """Record skill transition."""
        key = f"{from_skill}→{to_skill}"
        
        if key not in self.transitions:
            self.transitions[key] = SkillTransition(from_skill, to_skill)
        
        trans = self.transitions[key]
        trans.count += 1
        if success:
            trans.success_count += 1
    
    def get_skill_chain_patterns(self) -> List[Dict]:
        """Find common skill chain patterns."""
        patterns = []
        
        for key, trans in self.transitions.items():
            if trans.count >= 3 and trans.success_rate > 0.5:
                patterns.append({
                    "chain": [trans.from_skill, trans.to_skill],
                    "count": trans.count,
                    "success_rate": trans.success_rate
                })
        
        # Sort by count
        patterns.sort(key=lambda x: x["count"], reverse=True)
        
        return patterns[:10]
    
    # =========================================================================
    # LAYER 5: Skill Composition (New Skills from Patterns)
    # =========================================================================
    
    def detect_composable_skills(self) -> List[Dict]:
        """
        Detect skills that can be composed into new ones.
        
        Example:
            web_search → scrape → summarize
            Can become: research_topic
        """
        patterns = self.get_skill_chain_patterns()
        
        composable = []
        for pattern in patterns:
            chain = pattern["chain"]
            
            # Check if it's a common pattern
            if pattern["count"] >= 5:
                composable.append({
                    "composed_skill_name": f"composed_{chain[0].split('.')[-1]}_{chain[-1].split('.')[-1]}",
                    "component_skills": chain,
                    "usage_count": pattern["count"],
                    "success_rate": pattern["success_rate"]
                })
        
        return composable
    
    # =========================================================================
    # LAYER 6: Skill Evolution (Improve/Create/Prune)
    # =========================================================================
    
    def get_skills_for_improvement(self) -> List[Dict]:
        """Get skills that need improvement."""
        improvements = []
        
        for skill_id, stats in self.skill_stats.items():
            if stats.usage_count >= 3:
                # Low success rate
                if stats.success_rate < 0.4:
                    improvements.append({
                        "skill_id": skill_id,
                        "reason": "low_success_rate",
                        "success_rate": stats.success_rate,
                        "usage_count": stats.usage_count,
                        "action": "improve"
                    })
                
                # High latency
                elif stats.avg_duration_ms > 10000:  # >10s
                    improvements.append({
                        "skill_id": skill_id,
                        "reason": "high_latency",
                        "avg_duration": stats.avg_duration_ms,
                        "usage_count": stats.usage_count,
                        "action": "optimize"
                    })
        
        return improvements
    
    def get_skills_for_pruning(self) -> List[Dict]:
        """Get skills that should be pruned."""
        prunable = []
        
        for skill_id, stats in self.skill_stats.items():
            if stats.usage_count >= 5:
                # Low success rate after enough usage
                if stats.success_rate < 0.2:
                    prunable.append({
                        "skill_id": skill_id,
                        "reason": "consistently_failing",
                        "success_rate": stats.success_rate,
                        "usage_count": stats.usage_count,
                        "action": "prune"
                    })
        
        return prunable
    
    # =========================================================================
    # Analytics
    # =========================================================================
    
    def get_system_intelligence(self) -> Dict:
        """Get overall system intelligence metrics."""
        total_experiences = len(self.experiences)
        
        if total_experiences == 0:
            return {
                "total_experiences": 0,
                "unique_skills": 0,
                "avg_success_rate": 0,
                "chain_patterns": 0,
                "composable_skills": 0,
                "skills_for_improvement": 0,
                "evolution_ready": False
            }
        
        # Calculate average success rate
        success_count = sum(1 for e in self.experiences if e.success)
        avg_success = success_count / total_experiences
        
        # Get stats
        chain_patterns = self.get_skill_chain_patterns()
        composable = self.detect_composable_skills()
        improvements = self.get_skills_for_improvement()
        
        return {
            "total_experiences": total_experiences,
            "unique_skills": len(self.skill_stats),
            "avg_success_rate": avg_success,
            "chain_patterns": len(chain_patterns),
            "composable_skills": len(composable),
            "skills_for_improvement": len(improvements),
            "evolution_ready": total_experiences >= 50
        }


# Global instance
_skill_evolution_loop = None


def get_skill_evolution_loop() -> SkillEvolutionLoop:
    """Get global skill evolution loop."""
    global _skill_evolution_loop
    if _skill_evolution_loop is None:
        _skill_evolution_loop = SkillEvolutionLoop()
    return _skill_evolution_loop
