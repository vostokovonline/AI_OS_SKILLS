"""
CAPABILITY THINKING LAYER - Think → Decide → Expand → Act
========================================================

This layer enables AI-OS to think about capabilities before acting.

Architecture:
    Goal → Decompose → Capability Check → Think → Decision → Expand → Act → Experience

Author: AI-OS System
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExpansionStrategy(Enum):
    """How to expand capabilities when gap detected."""
    EXISTING = "existing"           # Use existing skill
    PIPELINE = "pipeline"           # Compose skills
    MCP_TOOL = "mcp_tool"          # Connect external MCP
    CODE_GENERATE = "code_generate" # Generate new skill
    IMPOSSIBLE = "impossible"       # Cannot solve


@dataclass
class Capability:
    """Represents a single capability."""
    name: str
    category: str
    skills: List[str] = field(default_factory=list)
    mcp_tools: List[str] = field(default_factory=list)
    
    @property
    def has_support(self) -> bool:
        return bool(self.skills or self.mcp_tools)


@dataclass
class TaskCapability:
    """Task mapped to required capabilities."""
    task: str
    required_capabilities: List[str]
    available: List[str]
    missing: List[str]
    strategy: ExpansionStrategy


@dataclass 
class Decision:
    """Decision from Capability Thinking Layer."""
    task: str
    strategy: ExpansionStrategy
    solution: Any  # skill_id, pipeline, mcp_tool, or None
    reasoning: str
    confidence: float


class CapabilityMap:
    """
    Semantic map of what the system can do.
    
    Structure:
        capability category
            └── capability name
                ├── skills (internal)
                └── mcp_tools (external)
    """
    
    def __init__(self):
        self.capabilities: Dict[str, Capability] = {}
        self._init_core_capabilities()
    
    def _init_core_capabilities(self):
        """Initialize core capability categories."""
        
        # Internet/Web capabilities
        self.add_capability("internet", "web_search", ["core.web_research", "core.search"])
        self.add_capability("internet", "web_fetch", ["core.web_research"])
        self.add_capability("internet", "api_call", ["core.run_command"])
        
        # File operations
        self.add_capability("filesystem", "file_read", ["core.file_read"])
        self.add_capability("filesystem", "file_write", ["core.write_file"])
        self.add_capability("filesystem", "file_list", ["core.file_list"])
        self.add_capability("filesystem", "file_search", ["core.file_search"])
        self.add_capability("filesystem", "create_directory", ["core.create_directory"])
        
        # Text processing
        self.add_capability("text", "summarize", ["core.summarize_text"])
        self.add_capability("text", "analyze", ["core.analyze_text"])
        self.add_capability("text", "extract", ["core.web_research"])
        
        # System
        self.add_capability("system", "execute", ["core.run_command"])
        self.add_capability("system", "create_task", ["core.create_directory"])
        
        # Communication
        self.add_capability("communication", "send_message", [])
        self.add_capability("communication", "email", [])
        
        # Development
        self.add_capability("development", "code_write", ["core.write_file"])
        self.add_capability("development", "code_read", ["core.file_read"])
        self.add_capability("development", "test", [])
        self.add_capability("development", "debug", [])
        
        # Data
        self.add_capability("data", "database_query", [])
        self.add_capability("data", "api_integration", [])
        
        logger.info("capability_map_initialized", categories=len(self.capabilities))
    
    def add_capability(self, category: str, name: str, skills: List[str] = None, mcp_tools: List[str] = None):
        """Add a capability to the map."""
        key = f"{category}.{name}"
        if key in self.capabilities:
            cap = self.capabilities[key]
            if skills:
                cap.skills.extend(skills)
            if mcp_tools:
                cap.mcp_tools.extend(mcp_tools)
        else:
            self.capabilities[key] = Capability(
                name=name,
                category=category,
                skills=skills or [],
                mcp_tools=mcp_tools or []
            )
    
    def has_capability(self, capability: str) -> bool:
        """Check if a capability is supported."""
        # Direct match
        if capability in self.capabilities:
            return self.capabilities[capability].has_support
        
        # Check if any capability contains this keyword
        capability_lower = capability.lower()
        for cap in self.capabilities.values():
            if capability_lower in cap.name.lower():
                return cap.has_support
        
        return False
    
    def get_capability(self, capability: str) -> Optional[Capability]:
        """Get capability details."""
        if capability in self.capabilities:
            return self.capabilities[capability]
        
        # Search
        capability_lower = capability.lower()
        for cap in self.capabilities.values():
            if capability_lower in cap.name.lower():
                return cap
        
        return None
    
    def find_missing_capabilities(self, required: List[str]) -> List[str]:
        """Find capabilities that are not available."""
        missing = []
        for cap in required:
            if not self.has_capability(cap):
                missing.append(cap)
        return missing
    
    def get_available_for_task(self, task: str) -> List[str]:
        """Get available capabilities for a task."""
        task_lower = task.lower()
        available = []
        
        keywords = {
            "search": ["internet.web_search"],
            "research": ["internet.web_search", "text.analyze"],
            "read": ["filesystem.file_read"],
            "write": ["filesystem.file_write"],
            "create": ["filesystem.file_write", "filesystem.create_directory"],
            "list": ["filesystem.file_list"],
            "find": ["filesystem.file_search", "internet.web_search"],
            "summarize": ["text.summarize"],
            "analyze": ["text.analyze"],
            "run": ["system.execute"],
            "command": ["system.execute"],
            "api": ["internet.api_call", "data.api_integration"],
            "github": [],
            "database": ["data.database_query"],
            "test": ["development.test"],
            "debug": ["development.debug"],
        }
        
        for keyword, caps in keywords.items():
            if keyword in task_lower:
                available.extend(caps)
        
        # Filter to only available capabilities
        return [c for c in available if self.has_capability(c)]


class CoverageEvaluator:
    """
    Evaluates capability coverage for a task.
    
    Calculates: coverage = available / required
    Decision based on coverage ratio.
    """
    
    def evaluate(
        self, 
        required_capabilities: List[str], 
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate coverage and recommend strategy.
        
        Returns:
            coverage_ratio: 0.0 - 1.0
            strategy: EXISTING | PIPELINE | MCP | CODE | IMPOSSIBLE
            confidence: based on coverage
        """
        if not required_capabilities:
            return {
                "coverage_ratio": 1.0,
                "strategy": ExpansionStrategy.EXISTING,
                "confidence": 1.0,
                "reasoning": "No specific capabilities required"
            }
        
        if not available_capabilities:
            return {
                "coverage_ratio": 0.0,
                "strategy": ExpansionStrategy.CODE_GENERATE,
                "confidence": 0.3,
                "reasoning": "No capabilities available"
            }
        
        # Calculate coverage
        available_set = set(available_capabilities)
        required_set = set(required_capabilities)
        
        covered = available_set.intersection(required_set)
        coverage = len(covered) / len(required_set)
        
        # Decision based on coverage
        if coverage >= 1.0:
            return {
                "coverage_ratio": coverage,
                "strategy": ExpansionStrategy.EXISTING,
                "confidence": 0.9,
                "reasoning": f"Full coverage: {covered}"
            }
        elif coverage >= 0.5:
            return {
                "coverage_ratio": coverage,
                "strategy": ExpansionStrategy.PIPELINE,
                "confidence": 0.7,
                "reasoning": f"Partial coverage {coverage:.0%}: can build pipeline"
            }
        elif coverage > 0:
            return {
                "coverage_ratio": coverage,
                "strategy": ExpansionStrategy.MCP_TOOL,
                "confidence": 0.5,
                "reasoning": f"Low coverage {coverage:.0%}: try MCP tools"
            }
        else:
            return {
                "coverage_ratio": 0.0,
                "strategy": ExpansionStrategy.CODE_GENERATE,
                "confidence": 0.3,
                "reasoning": "No coverage: need code generation"
            }


class TaskDecomposer:
    """
    Decomposes goal into task graph.
    
    Goal: "Analyze GitHub repository"
        ↓
    Tasks:
        clone_repo
        list_files
        read_files
        analyze_code
    """
    
    def decompose(self, goal_title: str, goal_description: str = "") -> List[Dict]:
        """
        Decompose goal into atomic tasks.
        
        Returns:
            List of tasks with dependencies
        """
        text = f"{goal_title} {goal_description}".lower()
        tasks = []
        
        # Common task patterns
        task_templates = {
            "research": [
                {"task": "search_web", "capability": "internet.web_search"},
                {"task": "fetch_content", "capability": "internet.web_fetch"},
                {"task": "extract_info", "capability": "text.extract"},
                {"task": "summarize", "capability": "text.summarize"},
            ],
            "analyze": [
                {"task": "collect_data", "capability": "filesystem.file_read"},
                {"task": "process_data", "capability": "text.analyze"},
                {"task": "generate_report", "capability": "text.summarize"},
            ],
            "create": [
                {"task": "prepare_content", "capability": "text.analyze"},
                {"task": "write_file", "capability": "filesystem.file_write"},
            ],
            "build": [
                {"task": "create_structure", "capability": "filesystem.create_directory"},
                {"task": "write_code", "capability": "filesystem.file_write"},
                {"task": "test", "capability": "system.execute"},
            ],
        }
        
        # Match goal to task template
        for pattern, task_list in task_templates.items():
            if pattern in text:
                tasks.extend(task_list)
        
        # If no match, create generic task
        if not tasks:
            tasks.append({
                "task": "process_request",
                "capability": "system.execute"
            })
        
        # Add dependencies (each task depends on previous)
        for i, task in enumerate(tasks):
            task["depends_on"] = tasks[i-1]["task"] if i > 0 else None
            task["order"] = i
        
        return tasks


class CapabilityThinkingLayer:
    """
    Think → Decide → Expand → Act cycle.
    
    Before execution, the system thinks about:
    1. What capabilities are needed?
    2. Which are available?
    3. What's missing?
    4. How to fill the gap?
    """
    
    def __init__(self):
        self.capability_map = CapabilityMap()
        self.coverage_evaluator = CoverageEvaluator()
        self.task_decomposer = TaskDecomposer()
        self.decision_history: List[Decision] = []
    
    def think_about_goal(self, goal_title: str, goal_description: str = "") -> Dict[str, Any]:
        """
        Think about a goal (high-level) and plan execution.
        
        This is the main entry point that:
        1. Decomposes goal into tasks
        2. Analyzes each task's capabilities
        3. Evaluates coverage
        4. Makes decision
        
        Args:
            goal_title: The goal title
            goal_description: Optional description
            
        Returns:
            Full plan with tasks, capabilities, and strategy
        """
        # Step 1: Decompose goal into tasks
        tasks = self.task_decomposer.decompose(goal_title, goal_description)
        
        # Step 2: Analyze each task
        task_analysis = []
        all_required = []
        all_available = []
        
        for task in tasks:
            required = self._identify_capabilities(task["task"])
            available = self.capability_map.get_available_for_task(task["task"])
            missing = self.capability_map.find_missing_capabilities(required)
            
            # Evaluate coverage for this task
            coverage = self.coverage_evaluator.evaluate(required, available)
            
            task_analysis.append({
                "task": task["task"],
                "capability": task.get("capability"),
                "depends_on": task.get("depends_on"),
                "required": required,
                "available": available,
                "missing": missing,
                "coverage": coverage
            })
            
            all_required.extend(required)
            all_available.extend(available)
        
        # Step 3: Evaluate overall coverage
        overall_coverage = self.coverage_evaluator.evaluate(
            list(set(all_required)), 
            list(set(all_available))
        )
        
        # Step 4: Decide strategy
        strategy = overall_coverage["strategy"]
        
        # Build solution based on strategy
        if strategy == ExpansionStrategy.EXISTING:
            solution = self._build_existing_solution(task_analysis)
        elif strategy == ExpansionStrategy.PIPELINE:
            solution = self._build_pipeline_solution(task_analysis)
        elif strategy == ExpansionStrategy.MCP_TOOL:
            solution = self._build_mcp_solution(task_analysis)
        else:
            solution = None
        
        return {
            "goal_title": goal_title,
            "tasks": task_analysis,
            "overall_coverage": overall_coverage["coverage_ratio"],
            "strategy": strategy.value,
            "solution": solution,
            "confidence": overall_coverage["confidence"],
            "reasoning": overall_coverage["reasoning"]
        }
    
    def _build_existing_solution(self, task_analysis: List[Dict]) -> List[str]:
        """Build solution using existing skills."""
        skills = []
        for task in task_analysis:
            if task["available"]:
                skills.append(task["available"][0])
        return skills
    
    def _build_pipeline_solution(self, task_analysis: List[Dict]) -> Dict:
        """Build pipeline solution."""
        return {
            "type": "pipeline",
            "tasks": [t["task"] for t in task_analysis],
            "missing": list(set([m for t in task_analysis for m in t["missing"]]))
        }
    
    def _build_mcp_solution(self, task_analysis: List[Dict]) -> Dict:
        """Build MCP solution."""
        return {
            "type": "mcp",
            "missing_capabilities": list(set([m for t in task_analysis for m in t["missing"]]))
        }
    
    def think_about_task(self, task: str) -> Decision:
        """
        Think about a single task and decide how to handle it.
        
        Args:
            task: The task to analyze
            
        Returns:
            Decision with strategy and solution
        """
        # Step 1: Identify required capabilities
        required = self._identify_capabilities(task)
        
        # Step 2: Check what's available
        available = self.capability_map.get_available_for_task(task)
        
        # Step 3: Use coverage evaluator
        coverage = self.coverage_evaluator.evaluate(required, available)
        
        # Step 4: Make decision based on coverage
        strategy = coverage["strategy"]
        solution = available[0] if available and strategy == ExpansionStrategy.EXISTING else None
        
        decision = Decision(
            task=task,
            strategy=strategy,
            solution=solution,
            reasoning=coverage["reasoning"],
            confidence=coverage["confidence"]
        )
        
        # Log decision
        logger.info(
            "capability_thinking",
            task=task,
            required=required,
            available=available,
            missing=missing,
            strategy=decision.strategy.value,
            solution=decision.solution
        )
        
        self.decision_history.append(decision)
        
        return decision
    
    def _identify_capabilities(self, task: str) -> List[str]:
        """Identify required capabilities for a task."""
        task_lower = task.lower()
        capabilities = []
        
        # Keyword to capability mapping
        capability_keywords = {
            "search": "internet.web_search",
            "research": "internet.web_search",
            "find information": "internet.web_search",
            "browse": "internet.web_fetch",
            "fetch": "internet.web_fetch",
            "read": "filesystem.file_read",
            "write": "filesystem.file_write",
            "create": "filesystem.file_write",
            "list": "filesystem.file_list",
            "summarize": "text.summarize",
            "summary": "text.summarize",
            "analyze": "text.analyze",
            "analysis": "text.analyze",
            "run": "system.execute",
            "execute": "system.execute",
            "command": "system.execute",
            "test": "development.test",
            "debug": "development.debug",
            "query": "data.database_query",
            "api": "internet.api_call",
            "github": "development.code_read",
            "email": "communication.email",
            "send": "communication.send_message",
        }
        
        for keyword, capability in capability_keywords.items():
            if keyword in task_lower:
                if capability not in capabilities:
                    capabilities.append(capability)
        
        return capabilities
    
    def _decide(
        self, 
        task: str, 
        required: List[str],
        available: List[str],
        missing: List[str]
    ) -> Decision:
        """
        Decide on expansion strategy.
        
        Priority:
        1. Use existing skill (EXISTING)
        2. Build pipeline (PIPELINE) 
        3. Connect MCP (MCP_TOOL)
        4. Generate code (CODE_GENERATE)
        5. Cannot solve (IMPOSSIBLE)
        """
        
        # If we have capabilities, use existing
        if available:
            # Pick best skill (first available)
            best_skill = self._get_best_skill(available)
            
            return Decision(
                task=task,
                strategy=ExpansionStrategy.EXISTING,
                solution=best_skill,
                reasoning=f"Capability available: {available[0]}",
                confidence=0.9
            )
        
        # Check if we can build a pipeline
        if missing and self._can_build_pipeline(missing):
            pipeline = self._build_pipeline_suggestion(missing)
            
            return Decision(
                task=task,
                strategy=ExpansionStrategy.PIPELINE,
                solution=pipeline,
                reasoning=f"Can build pipeline from: {pipeline}",
                confidence=0.7
            )
        
        # Check if MCP tool available
        if missing and self._has_mcp_tool(missing):
            mcp_tool = self._get_mcp_tool(missing)
            
            return Decision(
                task=task,
                strategy=ExpansionStrategy.MCP_TOOL,
                solution=mcp_tool,
                reasoning=f"MCP tool available: {mcp_tool}",
                confidence=0.6
            )
        
        # Could generate code but risky
        if missing:
            return Decision(
                task=task,
                strategy=ExpansionStrategy.CODE_GENERATE,
                solution=None,
                reasoning=f"Missing capabilities: {missing}. Code generation risky.",
                confidence=0.3
            )
        
        # Cannot solve
        return Decision(
            task=task,
            strategy=ExpansionStrategy.IMPOSSIBLE,
            solution=None,
            reasoning="No solution available",
            confidence=0.0
        )
    
    def _get_best_skill(self, capabilities: List[str]) -> Optional[str]:
        """Get best skill for capability."""
        for cap in capabilities:
            capability = self.capability_map.get_capability(cap)
            if capability and capability.skills:
                return capability.skills[0]
        return None
    
    def _can_build_pipeline(self, missing: List[str]) -> bool:
        """Check if we can build a pipeline from partial capabilities."""
        # For now, always return True if there are missing
        # In future, check if we have partial coverage
        return len(missing) > 0
    
    def _build_pipeline_suggestion(self, missing: List[str]) -> List[str]:
        """Build a pipeline suggestion."""
        # Simple heuristic: just return the missing capabilities
        # In future, this will use skill graph
        return missing
    
    def _has_mcp_tool(self, missing: List[str]) -> bool:
        """Check if MCP tool exists for missing capability."""
        # TODO: Integrate with MCP registry
        return False
    
    def _get_mcp_tool(self, missing: List[str]) -> Optional[str]:
        """Get MCP tool for missing capability."""
        # TODO: Query MCP registry
        return None
    
    def analyze_goal(self, goal_title: str, goal_description: str = "") -> Dict[str, Any]:
        """
        Analyze a goal and return capability requirements.
        
        This now uses task decomposition + coverage evaluation.
        
        Args:
            goal_title: Goal title
            goal_description: Goal description
            
        Returns:
            Dict with task decomposition, coverage, and strategy
        """
        # Use the new think_about_goal which includes:
        # 1. Task decomposition
        # 2. Capability analysis per task
        # 3. Coverage evaluation
        # 4. Strategy decision
        return self.think_about_goal(goal_title, goal_description)


# Global instance
_capability_layer = None


def get_capability_layer() -> CapabilityThinkingLayer:
    """Get global capability thinking layer."""
    global _capability_layer
    if _capability_layer is None:
        _capability_layer = CapabilityThinkingLayer()
    return _capability_layer


# Convenience function
def analyze_goal_capabilities(goal_title: str, goal_description: str = "") -> Dict[str, Any]:
    """Analyze goal capabilities."""
    layer = get_capability_layer()
    return layer.analyze_goal(goal_title, goal_description)
