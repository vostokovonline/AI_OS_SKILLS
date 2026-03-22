"""
Task Graph Builder - Semantic Task Decomposition for AI-OS

Builds task graphs from goals before capability binding.
Enables proper task decomposition and semantic understanding.

Architecture:
Goal → Task Graph → Capability Binding → Execution DAG
         ↑
    🔥 NEW LAYER
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from logging_config import get_logger
from semantic.embedding_service import embed_text
from semantic.capability_inference import infer_capabilities

logger = get_logger(__name__)


@dataclass
class Task:
    """
    A semantic task decomposed from the goal.
    
    Tasks represent WHAT needs to be done, not HOW.
    """
    id: str
    description: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    parallel_key: Optional[str] = None  # For tasks that can run in parallel


@dataclass
class TaskGraph:
    """Graph of tasks derived from goal."""
    goal_id: str
    tasks: List[Task] = field(default_factory=list)
    
    def get_ready_tasks(self, completed: set) -> List[Task]:
        """Get tasks ready to execute (all dependencies completed)."""
        ready = []
        for task in self.tasks:
            if task.id in completed:
                continue
            if all(dep in completed for dep in task.depends_on):
                ready.append(task)
        return ready
    
    def get_parallel_groups(self, tasks: List[Task]) -> Dict[str, List[Task]]:
        """Group tasks for parallel execution."""
        groups = {}
        for task in tasks:
            key = task.parallel_key or task.id
            if key not in groups:
                groups[key] = []
            groups[key].append(task)
        return groups


class TaskGraphBuilder:
    """
    Builds task graphs from goals using semantic decomposition.
    
    Key insight:
    - Task = semantic unit of work
    - Capability = implementation of task
    - DAG = execution order
    
    This separation enables proper planning.
    """
    
    # Keywords that trigger splitting
    SPLIT_KEYWORDS = ["3", "multiple", "list", "compare", "several", "different", "various", "all", "each"]
    
    # Task templates for common patterns
    TASK_TEMPLATES = {
        "research": [
            {"description": "extract search targets from goal", "outputs": ["targets"]},
            {"description": "retrieve information for each target", "parallel": True, "depends": 0},
            {"description": "aggregate retrieved information", "depends": 1},
        ],
        "analyze": [
            {"description": "extract entities to analyze", "outputs": ["entities"]},
            {"description": "fetch data for each entity", "parallel": True, "depends": 0},
            {"description": "aggregate fetched data", "depends": 1},
            {"description": "analyze aggregated data", "depends": 2},
        ],
        "summarize": [
            {"description": "gather content to summarize", "outputs": ["content"]},
            {"description": "extract key points from content", "depends": 0},
            {"description": "generate summary", "depends": 1},
        ],
        "create": [
            {"description": "determine requirements", "outputs": ["spec"]},
            {"description": "write content based on requirements", "depends": 0},
            {"description": "validate written content", "depends": 1},
        ],
    }
    
    def build(self, goal_title: str, goal_description: str = "") -> TaskGraph:
        """
        Build task graph from goal.
        
        Process:
        1. Analyze goal semantics
        2. Match to task template (or create custom)
        3. Extract entities for splitting
        4. Build task graph
        
        Returns:
            TaskGraph with ordered tasks
        """
        text = f"{goal_title} {goal_description}".lower()
        
        # Step 1: Determine task type
        task_type = self._detect_task_type(text)
        
        # Step 2: Extract entities if splitting needed
        should_split = self._should_split(text)
        entities = self._extract_entities(text) if should_split else []
        
        # Step 3: Build tasks
        if task_type in self.TASK_TEMPLATES:
            tasks = self._build_from_template(task_type, entities)
        else:
            tasks = self._build_custom_tasks(text, task_type)
        
        # Step 4: Create task graph
        graph = TaskGraph(
            goal_id=goal_title[:20],
            tasks=tasks
        )
        
        logger.info(
            "task_graph_built",
            goal=goal_title[:50],
            task_type=task_type,
            tasks=len(tasks),
            entities=entities[:3] if entities else [],
            should_split=should_split
        )
        
        return graph
    
    def _detect_task_type(self, text: str) -> str:
        """Detect the type of task from text."""
        if any(kw in text for kw in ["research", "find", "search", "lookup", "gather"]):
            return "research"
        elif any(kw in text for kw in ["analyze", "analysis", "examine", "investigate", "study"]):
            return "analyze"
        elif any(kw in text for kw in ["summarize", "summary", "condense", "digest"]):
            return "summarize"
        elif any(kw in text for kw in ["write", "create", "generate", "build", "develop"]):
            return "create"
        else:
            return "generic"
    
    def _should_split(self, text: str) -> bool:
        """Check if task needs to be split into parallel subtasks."""
        # Check for number patterns
        import re
        numbers = re.findall(r'\b(\d+)\b', text)
        for num in numbers:
            if int(num) > 1:
                return True
        
        # Check for explicit plural keywords
        if any(kw in text for kw in ["multiple", "several", "various", "different", "all", "each"]):
            return True
        
        return False
    
    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract entities from text for splitting.
        
        Example:
            "analyze 3 competitors" → ["competitor_1", "competitor_2", "competitor_3"]
        """
        import re
        
        entities = []
        
        # Try to find number
        numbers = re.findall(r'\b(\d+)\b', text)
        if numbers:
            count = int(numbers[0])
            # Try to find entity type
            words = text.split()
            entity_type = "item"
            for i, w in enumerate(words):
                if w in ["3", "3"] and i + 1 < len(words):
                    entity_type = words[i + 1]
                    break
            
            for i in range(count):
                entities.append(f"{entity_type}_{i + 1}")
        
        return entities[:10]  # Limit to 10
    
    def _build_from_template(self, task_type: str, entities: List[str]) -> List[Task]:
        """Build tasks from template."""
        template = self.TASK_TEMPLATES[task_type]
        tasks = []
        task_counter = 0
        
        for step in template:
            task = Task(
                id=f"task_{task_counter}",
                description=step["description"],
                outputs=step.get("outputs", []),
                depends_on=[f"task_{step.get('depends', 0)}"] if "depends" in step else [],
                parallel_key=f"parallel_{task_counter}" if step.get("parallel") else None
            )
            tasks.append(task)
            task_counter += 1
        
        # If we have entities and need to expand
        if entities and len(entities) > 1:
            tasks = self._expand_for_entities(tasks, entities)
        
        return tasks
    
    def _expand_for_entities(self, tasks: List[Task], entities: List[str]) -> List[Task]:
        """
        Expand tasks to handle multiple entities in parallel.
        
        Example:
            Input tasks: [fetch_data]
            Entities: ["A", "B", "C"]
            Output: [fetch_A, fetch_B, fetch_C] in parallel
        """
        expanded = []
        task_id_map = {}  # Maps original task_id -> list of expanded task_ids
        
        # First pass: expand parallel tasks
        for task in tasks:
            if task.parallel_key:
                # This task needs to be expanded for each entity
                for entity in entities:
                    entity_task = Task(
                        id=f"{task.id}_{entity}",
                        description=f"{task.description} for {entity}",
                        outputs=[f"{o}_{entity}" for o in task.outputs],
                        depends_on=task.depends_on,  # Will be fixed in second pass
                        parallel_key=task.parallel_key
                    )
                    expanded.append(entity_task)
                    if task.id not in task_id_map:
                        task_id_map[task.id] = []
                    task_id_map[task.id].append(entity_task.id)
            else:
                # Keep non-parallel tasks
                expanded.append(task)
                if task.id not in task_id_map:
                    task_id_map[task.id] = []
                task_id_map[task.id].append(task.id)
        
        # Second pass: fix dependencies to point to expanded tasks
        final_tasks = []
        for task in expanded:
            new_depends = []
            for dep in task.depends_on:
                if dep in task_id_map:
                    # Point to last expanded task of the dependency
                    new_depends.append(task_id_map[dep][-1])
                else:
                    # Keep original dependency (for non-parallel deps)
                    new_depends.append(dep)
            task.depends_on = new_depends
            final_tasks.append(task)
        
        return final_tasks
    
    def _build_custom_tasks(self, text: str, task_type: str) -> List[Task]:
        """Build custom tasks when no template matches."""
        tasks = []
        
        # Simple 3-step default
        tasks.append(Task(
            id="task_0",
            description=f"prepare for {task_type}",
            outputs=["context"]
        ))
        tasks.append(Task(
            id="task_1",
            description=f"execute {task_type}",
            depends_on=["task_0"],
            outputs=["result"]
        ))
        tasks.append(Task(
            id="task_2",
            description=f"finalize {task_type}",
            depends_on=["task_1"],
            outputs=["output"]
        ))
        
        return tasks


class CapabilityBinder:
    """
    Binds tasks to capabilities.
    
    Task → Capability mapping based on task semantics.
    """
    
    TASK_CAPABILITY_MAP = {
        "retrieve": "information_retrieval",
        "fetch": "information_retrieval",
        "search": "information_retrieval",
        "gather": "information_retrieval",
        "extract": "information_retrieval",
        "summarize": "summarization",
        "summary": "summarization",
        "condense": "summarization",
        "digest": "summarization",
        "analyze": "analysis",
        "examine": "analysis",
        "evaluate": "analysis",
        "compare": "analysis",
        "process": "data_processing",
        "normalize": "data_processing",
        "transform": "data_processing",
        "write": "writing",
        "create": "code_generation",
        "generate content": "code_generation",
        "generate": "code_generation",
        "build": "code_generation",
        "determine": "task_decomposition",
        "execute": "code_execution",
        "run": "code_execution",
        "validate": "analysis",
        "aggregate": "aggregation",
        "combine": "aggregation",
        "merge": "aggregation",
        "decompose": "task_decomposition",
        "split": "task_decomposition",
        "prepare": "task_decomposition",
    }
    
    def bind(self, task: Task) -> str:
        """Bind task to capability based on description."""
        desc_lower = task.description.lower()
        
        # Special case: generate summary → summarization
        if "generate" in desc_lower and "summary" in desc_lower:
            return "summarization"
        
        # Check longer phrases first
        phrases = ["generate content"]
        for phrase in phrases:
            if phrase in desc_lower:
                return self.TASK_CAPABILITY_MAP[phrase]
        
        # Check single keywords
        for keyword, capability in self.TASK_CAPABILITY_MAP.items():
            if keyword in desc_lower and keyword not in ["generate"]:
                return capability
        
        return "information_retrieval"
    
    def bind_graph(self, task_graph: TaskGraph) -> List[Dict[str, Any]]:
        """Bind all tasks in graph to capabilities."""
        bindings = []
        
        for task in task_graph.tasks:
            capability = self.bind(task)
            bindings.append({
                "task_id": task.id,
                "task_description": task.description,
                "capability": capability,
                "inputs": task.inputs,
                "outputs": task.outputs,
                "depends_on": task.depends_on,
                "parallel_key": task.parallel_key
            })
        
        return bindings


# Global instances
task_graph_builder = TaskGraphBuilder()
capability_binder = CapabilityBinder()
