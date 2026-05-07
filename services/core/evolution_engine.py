"""
EVOLUTION ENGINE - Self-Evolving AI-OS Core
========================================

This is the final layer that makes AI-OS truly self-evolving:

Goal → Execute → Fail → Gap Detection → Evolution Strategy → Capability Growth

Author: AI-OS System
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EvolutionStrategy(Enum):
    """How to evolve when gap detected."""
    PIPELINE = "pipeline"          # Compose existing skills
    MCP_TOOL = "mcp_tool"         # Connect external MCP
    SKILL_GENERATE = "skill_generate"  # Generate new skill
    IMPROVE = "improve"          # Improve existing skill
    PRUNE = "prune"              # Remove bad skill
    NONE = "none"                # No evolution needed


@dataclass
class GapReport:
    """Report of capability gap."""
    goal_title: str
    failed_task: str
    required_capability: str
    available_skills: List[str]
    missing_skills: List[str]
    failure_reason: str
    confidence: float


@dataclass
class EvolutionAction:
    """Action to take for evolution."""
    strategy: EvolutionStrategy
    target: str  # skill/capability to create/improve
    action: str  # specific action to take
    priority: int  # 1-10
    reasoning: str


class FailureAnalyzer:
    """
    Analyzes why goals/tasks failed.
    
    Returns GapReport with detailed analysis.
    """
    
    def analyze_failure(
        self,
        goal_title: str,
        task: str,
        skill_used: str,
        success: bool,
        error: Optional[str],
        confidence: float,
        evaluation_result: Any = None
    ) -> GapReport:
        """
        Analyze why a task failed.
        
        Returns detailed gap report.
        """
        
        if success:
            return GapReport(
                goal_title=goal_title,
                failed_task=task,
                required_capability="",
                available_skills=[],
                missing_skills=[],
                failure_reason="none",
                confidence=1.0
            )
        
        # Determine failure reason
        if error:
            if "not found" in error.lower() or "404" in error:
                reason = "resource_not_found"
            elif "timeout" in error.lower():
                reason = "timeout"
            elif "permission" in error.lower() or "unauthorized" in error.lower():
                reason = "access_denied"
            elif "invalid" in error.lower():
                reason = "invalid_input"
            else:
                reason = "execution_error"
        elif confidence < 0.5:
            reason = "low_confidence"
        elif evaluation_result and hasattr(evaluation_result, 'passed'):
            if not evaluation_result.passed:
                reason = "evaluation_failed"
            else:
                reason = "unknown"
        else:
            reason = "unknown"
        
        # Determine what was missing
        missing_skills = []
        
        if reason == "resource_not_found":
            # Missing capability to fetch resource
            missing_skills = ["fetch_content", "web_fetch"]
        elif reason == "timeout":
            # Skill too slow
            missing_skills = ["optimize_performance"]
        elif reason == "low_confidence":
            # Skill not capable enough
            missing_skills = ["enhanced_analysis"]
        elif reason == "evaluation_failed":
            # Output didn't meet criteria
            missing_skills = ["validation", "refinement"]
        else:
            # Generic missing capability
            missing_skills = []
        
        return GapReport(
            goal_title=goal_title,
            failed_task=task,
            required_capability=task,
            available_skills=[skill_used] if skill_used else [],
            missing_skills=missing_skills,
            failure_reason=reason,
            confidence=confidence
        )


class CapabilityGapDetector:
    """
    Detects capability gaps and recommends evolution strategies.
    """
    
    def __init__(self):
        self.failed_goals: List[GapReport] = []
        self.capability_demand: Dict[str, int] = {}  # capability -> demand count
    
    def detect_gap(
        self,
        required_capabilities: List[str],
        available_skills: List[str]
    ) -> List[str]:
        """Detect which capabilities are missing."""
        missing = []
        
        for cap in required_capabilities:
            # Check if any available skill can provide this capability
            can_provide = False
            for skill in available_skills:
                if self._skill_provides_capability(skill, cap):
                    can_provide = True
                    break
            
            if not can_provide:
                missing.append(cap)
                # Track demand
                self.capability_demand[cap] = self.capability_demand.get(cap, 0) + 1
        
        return missing
    
    def _skill_provides_capability(self, skill: str, capability: str) -> bool:
        """Check if a skill provides a capability."""
        # Simple keyword matching
        skill_lower = skill.lower()
        cap_lower = capability.lower()
        
        if "search" in cap_lower and "search" in skill_lower:
            return True
        if "fetch" in cap_lower and ("fetch" in skill_lower or "web" in skill_lower):
            return True
        if "read" in cap_lower and "read" in skill_lower:
            return True
        if "write" in cap_lower and "write" in skill_lower:
            return True
        if "analyze" in cap_lower and "analyze" in skill_lower:
            return True
        if "summarize" in cap_lower and "summarize" in skill_lower:
            return True
        
        return False
    
    def record_failure(self, gap_report: GapReport):
        """Record a failure for pattern detection."""
        self.failed_goals.append(gap_report)
        
        # Track missing capabilities
        for missing in gap_report.missing_skills:
            self.capability_demand[missing] = self.capability_demand.get(missing, 0) + 1
    
    def get_high_demand_capabilities(self, min_demand: int = 3) -> List[Dict]:
        """Get capabilities that are frequently missing."""
        high_demand = [
            {"capability": cap, "demand": count}
            for cap, count in self.capability_demand.items()
            if count >= min_demand
        ]
        high_demand.sort(key=lambda x: x["demand"], reverse=True)
        return high_demand


class EvolutionEngine:
    """
    The core of self-evolving AI-OS.
    
    Connects:
    - Failure Analysis
    - Gap Detection
    - Evolution Strategy Selection
    - Action Execution
    """
    
    def __init__(
        self,
        skill_evolution_loop,  # The learning loop we built
        capability_graph      # Capability mapping
    ):
        self.skill_evolution = skill_evolution_loop
        self.capability_graph = capability_graph
        
        self.failure_analyzer = FailureAnalyzer()
        self.gap_detector = CapabilityGapDetector()
        
        self.evolution_history: List[EvolutionAction] = []
        
        logger.info("evolution_engine_initialized")
    
    def process_execution_result(
        self,
        goal_title: str,
        task: str,
        skill_used: str,
        capability_required: str,
        success: bool,
        error: Optional[str],
        confidence: float,
        available_skills: List[str]
    ) -> Optional[EvolutionAction]:
        """
        Process execution result and determine if evolution needed.
        
        This is the main entry point for the evolution loop.
        """
        
        # Step 1: Analyze failure
        gap_report = self.failure_analyzer.analyze_failure(
            goal_title=goal_title,
            task=task,
            skill_used=skill_used,
            success=success,
            error=error,
            confidence=confidence
        )
        
        if success:
            logger.info("execution_successful_no_evolution", task=task)
            return None
        
        # Step 2: Record failure for pattern detection
        self.gap_detector.record_failure(gap_report)
        
        # Step 3: Detect capability gaps
        missing_caps = self.gap_detector.detect_gap(
            required_capabilities=[capability_required],
            available_skills=available_skills
        )
        
        if not missing_caps:
            logger.info("no_capability_gap_detected", task=task)
            return None
        
        # Step 4: Decide evolution strategy
        action = self._decide_evolution_strategy(
            gap_report=gap_report,
            missing_capabilities=missing_caps,
            available_skills=available_skills
        )
        
        if action:
            self.evolution_history.append(action)
            
            logger.info(
                "evolution_triggered",
                strategy=action.strategy.value,
                target=action.target,
                reasoning=action.reasoning
            )
        
        return action
    
    def _decide_evolution_strategy(
        self,
        gap_report: GapReport,
        missing_capabilities: List[str],
        available_skills: List[str]
    ) -> Optional[EvolutionAction]:
        """Decide how to evolve based on gap."""
        
        missing = missing_capabilities[0] if missing_capabilities else ""
        
        # Strategy 1: Can we build a pipeline?
        # Check if we have partial capabilities
        partial_available = [
            s for s in available_skills 
            if s != gap_report.failed_task
        ]
        
        if partial_available:
            return EvolutionAction(
                strategy=EvolutionStrategy.PIPELINE,
                target=missing,
                action=f"build_pipeline:{gap_report.failed_task}→{missing}",
                priority=7,
                reasoning=f"Can compose pipeline using {partial_available[0]}"
            )
        
        # Strategy 2: Is there an MCP tool available?
        if self._check_mcp_availability(missing):
            return EvolutionAction(
                strategy=EvolutionStrategy.MCP_TOOL,
                target=missing,
                action=f"connect_mcp:{missing}",
                priority=6,
                reasoning="MCP tool available for this capability"
            )
        
        # Strategy 3: Generate new skill (last resort)
        demand = self.gap_detector.capability_demand.get(missing, 0)
        
        if demand >= 2:  # Only generate if frequently needed
            return EvolutionAction(
                strategy=EvolutionStrategy.SKILL_GENERATE,
                target=missing,
                action=f"generate_skill:{missing}",
                priority=4,
                reasoning=f"Capability in high demand ({demand} requests)"
            )
        
        # No evolution needed
        return None
    
    def _check_mcp_availability(self, capability: str) -> bool:
        """Check if MCP tool available for capability."""
        # TODO: Integrate with MCP registry
        # For now, return False
        common_mcp_capabilities = {
            "github": True,
            "database": True,
            "browser": True,
            "email": True,
        }
        
        for key in common_mcp_capabilities:
            if key in capability.lower():
                return common_mcp_capabilities[key]
        
        return False
    
    def get_evolution_recommendations(self) -> Dict[str, Any]:
        """Get evolution recommendations."""
        
        # Get high-demand capabilities
        high_demand = self.gap_detector.get_high_demand_capabilities(min_demand=2)
        
        # Get skills needing improvement
        skills_for_improvement = (
            self.skill_evolution.get_skills_for_improvement()
            if self.skill_evolution else []
        )
        
        # Get composable skills
        composable = (
            self.skill_evolution.detect_composable_skills()
            if self.skill_evolution else []
        )
        
        return {
            "high_demand_capabilities": high_demand,
            "skills_for_improvement": skills_for_improvement,
            "composable_skills": composable,
            "evolution_ready": len(high_demand) > 0 or len(composable) > 0,
            "total_evolutions": len(self.evolution_history)
        }


class SelfEvolvingAIOS:
    """
    Complete Self-Evolving AI-OS System.
    
    This integrates all layers:
    1. Goal → Task Graph
    2. Capability Analysis
    3. Skill Selection (with learning)
    4. Execution
    5. Experience Recording
    6. Failure Analysis
    7. Gap Detection
    8. Evolution Engine
    """
    
    def __init__(
        self,
        skill_evolution_loop,
        capability_graph,
        mcp_system=None
    ):
        self.skill_evolution = skill_evolution_loop
        self.capability_graph = capability_graph
        self.mcp_system = mcp_system
        
        # Evolution components
        self.failure_analyzer = FailureAnalyzer()
        self.gap_detector = CapabilityGapDetector()
        self.evolution_engine = EvolutionEngine(
            skill_evolution_loop=skill_evolution_loop,
            capability_graph=capability_graph
        )
        
        logger.info("self_evolving_ai_os_complete_initialized")
    
    def execute_with_evolution(
        self,
        goal_title: str,
        task: str,
        capability_required: str,
        available_skills: List[str],
        execute_fn  # Function to execute skill
    ) -> Dict[str, Any]:
        """
        Execute task with full evolution loop.
        
        This is the main integration point.
        """
        
        # 1. Select skill (using learning)
        selected_skill = None
        
        if self.skill_evolution:
            selected_skill = self.skill_evolution.select_skill(
                capability=capability_required,
                available_skills=available_skills
            )
        
        if not selected_skill and available_skills:
            selected_skill = available_skills[0]
        
        # 2. Execute
        import time
        start = time.time()
        
        try:
            result = execute_fn(selected_skill)
            success = result.get("success", False)
            error = result.get("error")
            duration_ms = int((time.time() - start) * 1000)
            confidence = result.get("confidence", 0.5)
        except Exception as e:
            success = False
            error = str(e)
            duration_ms = int((time.time() - start) * 1000)
            confidence = 0.0
        
        # 3. Record experience
        if self.skill_evolution:
            self.skill_evolution.record_execution(
                goal_id="",
                goal_title=goal_title,
                task=task,
                skill_id=selected_skill or "unknown",
                capability=capability_required,
                success=success,
                duration_ms=duration_ms,
                confidence=confidence
            )
        
        # 4. Process result for evolution
        action = self.evolution_engine.process_execution_result(
            goal_title=goal_title,
            task=task,
            skill_used=selected_skill or "unknown",
            capability_required=capability_required,
            success=success,
            error=error,
            confidence=confidence,
            available_skills=available_skills
        )
        
        return {
            "selected_skill": selected_skill,
            "success": success,
            "duration_ms": duration_ms,
            "evolution_action": action
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        
        evolution_status = self.evolution_engine.get_evolution_recommendations()
        
        intelligence = (
            self.skill_evolution.get_system_intelligence()
            if self.skill_evolution else {}
        )
        
        return {
            "evolution": evolution_status,
            "intelligence": intelligence,
            "ready_for_evolution": evolution_status.get("evolution_ready", False)
        }


# Global instance
_evolution_engine = None


def get_evolution_engine() -> EvolutionEngine:
    """Get global evolution engine."""
    global _evolution_engine
    if _evolution_engine is None:
        from skill_evolution_loop import get_skill_evolution_loop
        from self_evolving_ai_os import get_self_evolving_ai_os
        
        ai_os = get_self_evolving_ai_os()
        
        _evolution_engine = EvolutionEngine(
            skill_evolution_loop=get_skill_evolution_loop(),
            capability_graph=ai_os.capability_graph
        )
    
    return _evolution_engine
