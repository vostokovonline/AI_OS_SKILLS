"""
DAG Planner with Task Graph Integration

Builds execution DAGs from Task Graphs with proper capability binding.

Architecture:
Goal → Task Graph Builder → Task Graph → Capability Binder → Execution DAG
"""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from logging_config import get_logger
from semantic.embedding_service import embed_text
from semantic.capability_inference import infer_capabilities
from semantic.task_graph_builder import TaskGraphBuilder, CapabilityBinder, Task

logger = get_logger(__name__)


@dataclass
class PlanNode:
    """A node in the execution DAG."""
    id: str
    capability: str
    task_description: str = ""
    depends_on: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    parallel_group: Optional[str] = None


@dataclass
class ExecutionDAG:
    """Directed Acyclic Graph for execution."""
    nodes: List[PlanNode] = field(default_factory=list)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    
    def get_ready_nodes(self, completed: Set[str]) -> List[PlanNode]:
        """Get nodes that are ready to execute."""
        ready = []
        for node in self.nodes:
            if node.id in completed:
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(node)
        return ready
    
    def get_parallel_groups(self, nodes: List[PlanNode]) -> Dict[str, List[PlanNode]]:
        """Group nodes by parallel_group for concurrent execution."""
        groups = {}
        standalone = []
        for node in nodes:
            if node.parallel_group:
                if node.parallel_group not in groups:
                    groups[node.parallel_group] = []
                groups[node.parallel_group].append(node)
            else:
                standalone.append(node)
        
        for node in standalone:
            groups[node.id] = [node]
        
        return groups


class DAGPlanner:
    """
    Builds execution DAGs from goals using Task Graph → Capability binding.
    
    Architecture:
    Goal → Task Graph → Capability Binding → Execution DAG
    """
    
    def __init__(self):
        self.task_builder = TaskGraphBuilder()
        self.capability_binder = CapabilityBinder()
    
    def plan(self, goal_title: str, goal_description: str = "") -> Dict[str, Any]:
        """
        Create execution DAG from goal using task graph.
        
        Process:
        1. Build task graph from goal
        2. Bind tasks to capabilities
        3. Build execution DAG
        4. Calculate metrics
        """
        # Step 1: Build task graph
        task_graph = self.task_builder.build(goal_title, goal_description)
        
        if not task_graph.tasks:
            logger.info("no_tasks_built")
            return {"dag": None, "tasks": [], "capabilities": [], "depth": 0}
        
        # Step 2: Bind tasks to capabilities
        bindings = self.capability_binder.bind_graph(task_graph)
        
        # Step 3: Build DAG from bindings
        dag = self._build_dag_from_bindings(bindings, goal_title)
        
        # Step 4: Calculate depth
        depth = self._calculate_depth(dag)
        
        logger.info(
            "dag_planned_from_tasks",
            goal=goal_title[:50],
            tasks=len(task_graph.tasks),
            capabilities=len(set(b["capability"] for b in bindings)),
            depth=depth
        )
        
        return {
            "dag": dag,
            "tasks": task_graph.tasks,
            "bindings": bindings,
            "capabilities": list(set(b["capability"] for b in bindings)),
            "parallel_groups": self._get_parallel_groups(dag),
            "total_nodes": len(dag.nodes),
            "depth": depth
        }
    
    def _build_dag_from_bindings(
        self, 
        bindings: List[Dict[str, Any]],
        goal_title: str
    ) -> ExecutionDAG:
        """Build execution DAG from task-capability bindings."""
        dag = ExecutionDAG()
        
        for binding in bindings:
            node = PlanNode(
                id=binding["task_id"],
                capability=binding["capability"],
                task_description=binding["task_description"],
                depends_on=binding["depends_on"],
                parallel_group=binding.get("parallel_key")
            )
            dag.nodes.append(node)
        
        return dag
    
    def _get_parallel_groups(self, dag: ExecutionDAG) -> List[str]:
        """Get list of parallel execution groups."""
        groups = set()
        for node in dag.nodes:
            if node.parallel_group:
                groups.add(node.parallel_group)
        return list(groups)
    
    def _calculate_depth(self, dag: ExecutionDAG) -> int:
        """Calculate DAG depth (longest path)."""
        if not dag.nodes:
            return 0
        
        depths = {}
        
        def get_depth(node_id: str) -> int:
            if node_id in depths:
                return depths[node_id]
            
            node = next((n for n in dag.nodes if n.id == node_id), None)
            if not node:
                return 0
            
            if not node.depends_on:
                depths[node_id] = 1
                return 1
            
            max_parent_depth = max(get_depth(dep) for dep in node.depends_on)
            depths[node_id] = max_parent_depth + 1
            return depths[node_id]
        
        return max(get_depth(n.id) for n in dag.nodes)
    
    def validate_dag(self, dag: ExecutionDAG) -> Dict[str, Any]:
        """Validate DAG for executability."""
        errors = []
        warnings = []
        
        if self._has_cycle(dag):
            errors.append("DAG contains cycles")
        
        node_ids = {n.id for n in dag.nodes}
        for node in dag.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    errors.append(f"Node {node.id} depends on missing {dep}")
        
        has_summarize = any(n.capability == "summarization" for n in dag.nodes)
        has_retrieval = any(n.capability == "information_retrieval" for n in dag.nodes)
        if has_summarize and not has_retrieval:
            warnings.append("summarization without retrieval may fail")
        
        if not dag.nodes:
            errors.append("DAG has no nodes")
        
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
    
    def _has_cycle(self, dag: ExecutionDAG) -> bool:
        """Check for cycles using DFS."""
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for dep in dag.edges.get(node_id, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node in dag.nodes:
            if node.id not in visited:
                if dfs(node.id):
                    return True
        
        return False


dag_planner = DAGPlanner()
