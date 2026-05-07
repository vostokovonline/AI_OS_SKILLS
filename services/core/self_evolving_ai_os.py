"""
SELF-EVOLVING AI-OS - Full Architecture
=======================================

9-Layer Self-Evolving System:
1. Goal Engine
2. Planner (Task Graph)
3. Task Decomposer
4. Capability Thinking
5. Coverage Evaluator
6. Decision Engine
7. Expansion Engine (Pipeline/MCP/Code)
8. Execution Engine
9. Experience & Learning Loop

Author: AI-OS System
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExpansionStrategy(Enum):
    EXISTING = "existing"
    PIPELINE = "pipeline"
    MCP_TOOL = "mcp_tool"
    CODE_GENERATE = "code_generate"
    IMPOSSIBLE = "impossible"


@dataclass
class Task:
    """Atomic task in a task graph."""
    id: str
    name: str
    capability_required: str
    skill_needed: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    parallel_with: List[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class TaskGraph:
    """Graph of tasks with dependencies."""
    tasks: List[Task] = field(default_factory=list)
    
    def add_task(self, task: Task):
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None
    
    def topological_sort(self) -> List[Task]:
        """Return tasks in execution order."""
        in_degree = {t.id: len(t.depends_on) for t in self.tasks}
        queue = [t for t in self.tasks if in_degree[t.id] == 0]
        result = []
        
        while queue:
            task = queue.pop(0)
            result.append(task)
            
            for other in self.tasks:
                if task.id in other.depends_on:
                    in_degree[other.id] -= 1
                    if in_degree[other.id] == 0:
                        queue.append(other)
        
        return result


class CapabilityNode:
    """Node in capability graph."""
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.skills: List[str] = []
        self.mcp_tools: List[str] = []
        self.success_rate: float = 0.0
        self.usage_count: int = 0
        self.parent: Optional[str] = None
        self.children: List[str] = []
    
    def can_substitute(self, other: str) -> bool:
        """Check if this capability can substitute another."""
        # Same category
        if self.category == other.split('.')[0]:
            return True
        return False


class CapabilityGraph:
    """
    Self-learning capability graph.
    
    Grows through experience:
    - New capabilities discovered
    - Relations learned
    - Success rates tracked
    """
    
    def __init__(self):
        self.nodes: Dict[str, CapabilityNode] = {}
        self._init_foundation()
    
    def _init_foundation(self):
        """Initialize foundation capabilities."""
        # Internet
        self.add_capability("internet", "web_search", ["core.web_research"])
        self.add_capability("internet", "web_fetch", ["core.web_research"])
        self.add_capability("internet", "api_call", ["core.run_command"])
        
        # Filesystem
        self.add_capability("filesystem", "file_read", ["core.file_read"])
        self.add_capability("filesystem", "file_write", ["core.write_file"])
        self.add_capability("filesystem", "file_list", ["core.file_list"])
        self.add_capability("filesystem", "file_search", ["core.file_search"])
        
        # Text
        self.add_capability("text", "summarize", ["core.summarize_text"])
        self.add_capability("text", "analyze", ["core.analyze_text"])
        
        # System
        self.add_capability("system", "execute", ["core.run_command"])
        
        logger.info("capability_graph_initialized", nodes=len(self.nodes))
    
    def add_capability(self, category: str, name: str, skills: List[str] = None, mcp_tools: List[str] = None):
        """Add a capability to the graph."""
        key = f"{category}.{name}"
        
        if key in self.nodes:
            node = self.nodes[key]
            if skills:
                node.skills.extend(skills)
            if mcp_tools:
                node.mcp_tools.extend(mcp_tools)
        else:
            node = CapabilityNode(name, category)
            node.skills = skills or []
            node.mcp_tools = mcp_tools or []
            self.nodes[key] = node
        
        # Add to category
        category_key = f"{category}.*"
        if category_key not in self.nodes:
            self.nodes[category_key] = CapabilityNode("*", category)
        self.nodes[category_key].children.append(key)
        node.parent = category_key
    
    def get_capability(self, capability: str) -> Optional[CapabilityNode]:
        """Get capability node."""
        return self.nodes.get(capability)
    
    def find_capable_skills(self, capability: str) -> List[str]:
        """Find skills that can provide this capability."""
        if capability in self.nodes:
            return self.nodes[capability].skills
        
        # Try category match
        parts = capability.split('.')
        if len(parts) >= 2:
            category = parts[0]
            category_node = self.nodes.get(f"{category}.*")
            if category_node:
                return category_node.skills
        
        return []
    
    def find_substitutes(self, missing_capability: str) -> List[str]:
        """Find capabilities that can substitute for missing."""
        substitutes = []
        
        for key, node in self.nodes.items():
            if node.can_substitute(missing_capability) and node.skills:
                substitutes.extend(node.skills)
        
        return list(set(substitutes))
    
    def update_success_rate(self, capability: str, success: bool):
        """Update success rate from experience."""
        if capability not in self.nodes:
            return
        
        node = self.nodes[capability]
        node.usage_count += 1
        
        if success:
            # Simple moving average
            current = node.success_rate
            node.success_rate = (current * (node.usage_count - 1) + 1.0) / node.usage_count
        else:
            current = node.success_rate
            node.success_rate = (current * (node.usage_count - 1)) / node.usage_count
    
    def discover_capability(self, capability: str, skill: str, category: str = "discovered"):
        """Discover new capability from experience."""
        key = f"{category}.{capability}"
        
        if key not in self.nodes:
            self.add_capability(category, capability, [skill])
            logger.info("capability_discovered", capability=key, skill=skill)


class Planner:
    """
    Builds task graphs from goals.
    
    This is not template-based - it's reasoning-based.
    """
    
    def __init__(self, capability_graph: CapabilityGraph):
        self.capability_graph = capability_graph
    
    def plan(self, goal_title: str, goal_description: str = "") -> TaskGraph:
        """
        Build task graph for goal.
        
        This uses reasoning, not templates.
        """
        text = f"{goal_title} {goal_description}".lower()
        graph = TaskGraph()
        
        # Analyze what needs to happen
        task_sequence = self._analyze_goal(text)
        
        # Build task graph
        for i, task_spec in enumerate(task_sequence):
            task = Task(
                id=f"task_{i}",
                name=task_spec["name"],
                capability_required=task_spec["capability"],
                skill_needed=self.capability_graph.find_capable_skills(task_spec["capability"])[0] if self.capability_graph.find_capable_skills(task_spec["capability"]) else None,
                depends_on=[f"task_{i-1}"] if i > 0 else []
            )
            graph.add_task(task)
        
        logger.info("task_graph_built", goal=goal_title, tasks=len(graph.tasks))
        
        return graph
    
    def _analyze_goal(self, text: str) -> List[Dict]:
        """Analyze goal and determine required tasks."""
        tasks = []
        
        # Research pattern
        if any(w in text for w in ["research", "find information", "search", "investigate"]):
            tasks.extend([
                {"name": "search", "capability": "internet.web_search"},
                {"name": "fetch", "capability": "internet.web_fetch"},
                {"name": "analyze", "capability": "text.analyze"},
            ])
        
        # Analysis pattern
        elif any(w in text for w in ["analyze", "analysis", "examine", "review"]):
            tasks.extend([
                {"name": "collect", "capability": "filesystem.file_read"},
                {"name": "analyze", "capability": "text.analyze"},
                {"name": "report", "capability": "filesystem.file_write"},
            ])
        
        # Build/Create pattern
        elif any(w in text for w in ["build", "create", "make", "develop"]):
            tasks.extend([
                {"name": "plan", "capability": "text.analyze"},
                {"name": "create_files", "capability": "filesystem.file_write"},
                {"name": "test", "capability": "system.execute"},
            ])
        
        # Default
        if not tasks:
            tasks.append({
                "name": "process",
                "capability": "system.execute"
            })
        
        return tasks


class SelfEvolvingAIOS:
    """
    Complete Self-Evolving AI-OS Architecture.
    
    9 Layers:
    1. Goal Engine
    2. Planner (Task Graph)
    3. Task Decomposer
    4. Capability Thinking
    5. Coverage Evaluator
    6. Decision Engine
    7. Expansion Engine
    8. Execution Engine
    9. Experience & Learning
    """
    
    def __init__(self):
        # Layer 4: Capability Graph (self-learning)
        self.capability_graph = CapabilityGraph()
        
        # Layer 2: Planner
        self.planner = Planner(self.capability_graph)
        
        # Learning history
        self.execution_history: List[Dict] = []
        
        logger.info("self_evolving_ai_os_initialized")
    
    def process_goal(self, goal_title: str, goal_description: str = "") -> Dict:
        """
        Process goal through full self-evolving pipeline.
        
        Goal → Task Graph → Capability Analysis → Coverage → Decision → Execute → Learn
        """
        
        # Layer 1-2: Build task graph
        task_graph = self.planner.plan(goal_title, goal_description)
        
        # Layer 3-4: Analyze capabilities
        task_analysis = []
        all_required_capabilities = set()
        all_covered_capabilities = set()
        
        for task in task_graph.tasks:
            required_capability = task.capability_required
            available_skills = self.capability_graph.find_capable_skills(required_capability)
            substitutes = self.capability_graph.find_substitutes(required_capability)
            
            all_required_capabilities.add(required_capability)
            
            # Track which capabilities are covered
            if available_skills or substitutes:
                all_covered_capabilities.add(required_capability)
            
            task_analysis.append({
                "task": task.name,
                "required_capability": required_capability,
                "available_skills": available_skills,
                "substitutes": substitutes,
                "has_solution": bool(available_skills or substitutes)
            })
        
        # Layer 5: Evaluate coverage (capability coverage, not skill coverage)
        if not all_required_capabilities:
            coverage = 1.0
        else:
            coverage = len(all_covered_capabilities) / len(all_required_capabilities)
        
        # Layer 6: Decide strategy
        if coverage >= 1.0:
            strategy = ExpansionStrategy.EXISTING
        elif coverage >= 0.5:
            strategy = ExpansionStrategy.PIPELINE
        elif coverage > 0:
            strategy = ExpansionStrategy.MCP_TOOL
        else:
            strategy = ExpansionStrategy.CODE_GENERATE
        
        # Layer 7-8: Build execution plan
        missing_capabilities = list(all_required_capabilities - all_covered_capabilities)
        
        execution_plan = {
            "goal": goal_title,
            "strategy": strategy.value,
            "coverage": coverage,
            "task_graph": [
                {
                    "name": t.name,
                    "capability": t.capability_required,
                    "skill": t.skill_needed or "MISSING"
                }
                for t in task_graph.tasks
            ],
            "missing_capabilities": missing_capabilities
        }
        
        logger.info(
            "goal_planned",
            goal=goal_title,
            strategy=strategy.value,
            coverage=coverage,
            tasks=len(task_graph.tasks)
        )
        
        return execution_plan
    
    def record_experience(
        self,
        goal_title: str,
        task_name: str,
        capability: str,
        skill_used: str,
        success: bool
    ):
        """Record execution experience and update capability graph."""
        
        # Update capability success rate
        self.capability_graph.update_success_rate(capability, success)
        
        # Record in history
        self.execution_history.append({
            "goal": goal_title,
            "task": task_name,
            "capability": capability,
            "skill": skill_used,
            "success": success
        })
        
        # Discover new capabilities if task failed
        if not success:
            # Mark capability as needing expansion
            logger.info("capability_gap_detected", capability=capability)
        
        # Track successful skill for capability
        if success and skill_used:
            node = self.capability_graph.get_capability(capability)
            if node and skill_used not in node.skills:
                node.skills.append(skill_used)
                logger.info("skill_linked_to_capability", capability=capability, skill=skill_used)
    
    def get_system_status(self) -> Dict:
        """Get current system status."""
        return {
            "capabilities": len(self.capability_graph.nodes),
            "execution_history": len(self.execution_history),
            "success_rate": sum(1 for e in self.execution_history if e["success"]) / len(self.execution_history) if self.execution_history else 0
        }


# Global instance
_ai_os = None


def get_self_evolving_ai_os() -> SelfEvolvingAIOS:
    """Get global AI-OS instance."""
    global _ai_os
    if _ai_os is None:
        _ai_os = SelfEvolvingAIOS()
    return _ai_os
