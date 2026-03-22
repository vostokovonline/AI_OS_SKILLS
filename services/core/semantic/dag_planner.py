"""
DAG Planner - Parallel Execution Planning for AI-OS

Builds execution DAGs instead of linear chains.
Enables parallel task execution and proper dependency management.

Architecture:
Goal → Capabilities → DAG Construction → Parallel Execution
"""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from logging_config import get_logger
from semantic.embedding_service import embed_text
from semantic.capability_inference import infer_capabilities

logger = get_logger(__name__)


@dataclass
class PlanNode:
    """A node in the execution DAG."""
    id: str
    capability: str
    depends_on: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    parallel_group: Optional[str] = None  # For nodes that can run in parallel


@dataclass
class ExecutionDAG:
    """Directed Acyclic Graph for execution."""
    nodes: List[PlanNode] = field(default_factory=list)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # node_id -> [dependent_ids]
    
    def get_ready_nodes(self, completed: Set[str]) -> List[PlanNode]:
        """Get nodes that are ready to execute (all dependencies met)."""
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
        
        # Add standalone nodes as individual groups
        for node in standalone:
            groups[node.id] = [node]
        
        return groups


class DAGPlanner:
    """
    Builds and executes DAGs for parallel task planning.
    
    Key improvements over linear planner:
    - Parallel execution paths
    - Split/merge capabilities
    - DAG validation
    - Fan-out / fan-in support
    """
    
    # Split keywords - tasks containing these should be split
    SPLIT_KEYWORDS = ["multiple", "list of", "compare", "several", "different", "various", "all"]
    
    # Capabilities that support parallel execution
    PARALLELIZABLE = {
        "information_retrieval",
        "data_processing",
        "analysis",
    }
    
    def plan(self, goal_title: str, goal_description: str = "") -> Dict[str, Any]:
        """
        Create execution DAG from goal.
        
        Returns:
            Dict with:
            - dag: ExecutionDAG
            - capabilities: inferred capabilities
            - parallel_groups: list of parallel execution groups
            - total_nodes: total execution nodes
            - estimated_depth: DAG depth (critical path)
        """
        # Step 1: Infer capabilities
        capabilities = infer_capabilities(goal_title, goal_description)
        
        if not capabilities:
            logger.info("no_capabilities_inferred_dag")
            return {"dag": None, "capabilities": [], "parallel_groups": [], "depth": 0}
        
        # Step 2: Check for split requirement
        should_split = self._should_split(goal_title, goal_description)
        
        # Step 3: Build DAG
        dag = self._build_dag(capabilities, should_split, goal_title)
        
        # Step 4: Calculate parallel groups
        all_ready = dag.get_ready_nodes(set())
        parallel_groups = dag.get_parallel_groups(all_ready)
        
        # Step 5: Calculate depth (longest path)
        depth = self._calculate_depth(dag)
        
        logger.info(
            "dag_planned",
            goal=goal_title[:50],
            nodes=len(dag.nodes),
            parallel_groups=len(parallel_groups),
            depth=depth
        )
        
        return {
            "dag": dag,
            "capabilities": [c["name"] for c in capabilities],
            "primary": [c["name"] for c in capabilities if c["confidence"] >= 0.6],
            "parallel_groups": list(parallel_groups.keys()),
            "total_nodes": len(dag.nodes),
            "depth": depth,
            "should_split": should_split
        }
    
    def _should_split(self, title: str, description: str) -> bool:
        """Check if goal requires splitting into parallel subtasks."""
        text = f"{title} {description}".lower()
        return any(kw in text for kw in self.SPLIT_KEYWORDS)
    
    def _build_dag(
        self, 
        capabilities: List[Dict[str, Any]], 
        should_split: bool,
        goal_title: str
    ) -> ExecutionDAG:
        """Build DAG from capabilities."""
        dag = ExecutionDAG()
        
        # Separate primary and secondary
        primary = [c for c in capabilities if c["confidence"] >= 0.6]
        secondary = [c for c in capabilities if 0.3 <= c["confidence"] < 0.6]
        
        # If needs split and has analysis capability, force parallel
        if should_split and any(c["name"] == "analysis" for c in capabilities):
            # Add information_retrieval as dependency
            retrieval_cap = {"name": "information_retrieval", "confidence": 0.8}
            caps = [retrieval_cap] + capabilities
            return self._build_parallel_dag(caps, goal_title)
        
        all_caps = primary + secondary
        
        if should_split and len(all_caps) >= 2:
            # Create parallel execution for multiple capabilities
            dag = self._build_parallel_dag(all_caps, goal_title)
        else:
            # Create linear/sequential DAG
            dag = self._build_linear_dag(all_caps)
        
        return dag
    
    def _build_linear_dag(self, capabilities: List[Dict[str, Any]]) -> ExecutionDAG:
        """Build linear DAG with dependencies."""
        dag = ExecutionDAG()
        node_counter = 0
        prev_node_id = None
        
        for cap in capabilities:
            cap_name = cap["name"]
            
            # Get dependencies from capability graph
            depends_on = self._get_capability_dependencies(cap_name)
            
            # Filter dependencies to only include caps we're using
            existing_deps = []
            cap_ids = {c["name"] for c in capabilities}
            for dep in depends_on:
                if dep in cap_ids or dep == "information_retrieval":
                    existing_deps.append(f"node_{node_counter - 1}") if prev_node_id else None
            
            node = PlanNode(
                id=f"node_{node_counter}",
                capability=cap_name,
                depends_on=[prev_node_id] if prev_node_id and cap_name != "information_retrieval" else []
            )
            
            dag.nodes.append(node)
            prev_node_id = node.id
            node_counter += 1
        
        return dag
    
    def _build_parallel_dag(
        self, 
        capabilities: List[Dict[str, Any]], 
        goal_title: str
    ) -> ExecutionDAG:
        """
        Build DAG with parallel execution paths.
        
        Example:
            Goal: "analyze 3 competitors"
            
            DAG:
            [retrieval_A] ─┐
            [retrieval_B] ─┼─▶ [aggregation] ─▶ [analysis]
            [retrieval_C] ─┘
        """
        dag = ExecutionDAG()
        node_counter = 0
        group_id = f"parallel_{goal_title[:10]}"
        
        # Check if we need fan-out for retrieval
        needs_fan_out = any(
            c["name"] == "information_retrieval" 
            for c in capabilities
        )
        
        if needs_fan_out and len(capabilities) > 1:
            # Create fan-out structure
            fan_out_node = PlanNode(
                id=f"node_{node_counter}",
                capability="task_decomposition",
                depends_on=[],
                parallel_group=group_id,
                params={"splits": len(capabilities)}
            )
            dag.nodes.append(fan_out_node)
            node_counter += 1
            
            # Create parallel retrieval nodes
            retrieval_node = PlanNode(
                id=f"node_{node_counter}",
                capability="information_retrieval",
                depends_on=[fan_out_node.id],
                parallel_group=group_id,
                params={"parallel_tasks": len(capabilities)}
            )
            dag.nodes.append(retrieval_node)
            fan_out_node = retrieval_node  # Next nodes depend on this
            node_counter += 1
            
            # Add other capabilities after merge
            for cap in capabilities:
                if cap["name"] == "information_retrieval":
                    continue
                    
                depends = self._get_capability_dependencies(cap["name"])
                needed_deps = [fan_out_node.id]
                
                if "analysis" in cap["name"] or "summarization" in cap["name"]:
                    # These need aggregation
                    merge_node = PlanNode(
                        id=f"node_{node_counter}",
                        capability="aggregation",
                        depends_on=[fan_out_node.id]
                    )
                    dag.nodes.append(merge_node)
                    needed_deps = [merge_node.id]
                    node_counter += 1
                
                node = PlanNode(
                    id=f"node_{node_counter}",
                    capability=cap["name"],
                    depends_on=needed_deps
                )
                dag.nodes.append(node)
                node_counter += 1
        else:
            # Simple parallel - all capabilities run in parallel
            for cap in capabilities:
                node = PlanNode(
                    id=f"node_{node_counter}",
                    capability=cap["name"],
                    depends_on=[],
                    parallel_group=group_id
                )
                dag.nodes.append(node)
                node_counter += 1
            
            # Merge node if multiple capabilities
            if len(capabilities) > 1:
                merge_node = PlanNode(
                    id=f"node_{node_counter}",
                    capability="aggregation",
                    depends_on=[n.id for n in dag.nodes]
                )
                dag.nodes.append(merge_node)
        
        return dag
    
    def _get_capability_dependencies(self, cap_name: str) -> List[str]:
        """Get dependencies for a capability from the graph."""
        dep_graph = {
            "summarization": ["information_retrieval"],
            "analysis": ["information_retrieval"],
            "code_execution": ["code_generation"],
            "decision_making": ["analysis"],
            "aggregation": ["information_retrieval"],
            "task_decomposition": [],
        }
        return dep_graph.get(cap_name, [])
    
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
        """
        Validate DAG for executability.
        
        Returns:
            Dict with:
            - valid: bool
            - errors: list of issues
            - warnings: list of concerns
        """
        errors = []
        warnings = []
        
        # Check for cycles
        if self._has_cycle(dag):
            errors.append("DAG contains cycles")
        
        # Check for missing dependencies
        node_ids = {n.id for n in dag.nodes}
        for node in dag.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    errors.append(f"Node {node.id} depends on missing node {dep}")
        
        # Check for summarization without retrieval
        has_summarize = any(n.capability == "summarization" for n in dag.nodes)
        has_retrieval = any(n.capability == "information_retrieval" for n in dag.nodes)
        if has_summarize and not has_retrieval:
            warnings.append("summarization without information_retrieval may fail")
        
        # Check for empty DAG
        if not dag.nodes:
            errors.append("DAG has no nodes")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _has_cycle(self, dag: ExecutionDAG) -> bool:
        """Check if DAG has cycles using DFS."""
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


# Global instance
dag_planner = DAGPlanner()
