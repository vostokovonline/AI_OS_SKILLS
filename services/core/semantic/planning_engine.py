"""
Planning Engine with Critic + Replanner Loop

Makes the system self-correcting and iterative.

Architecture:
Goal → Planner → Plan → Executor → Results → Critic → Issues?
                                                    ↓
                                              Replanner → New Plan → Loop
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from logging_config import get_logger
import json

logger = get_logger(__name__)


@dataclass
class Task:
    """Atomic execution task."""
    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """Execution plan containing tasks."""
    tasks: List[Task] = field(default_factory=list)


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    output: Any = None
    success: bool = False
    error: str = ""


@dataclass
class ExecutionResult:
    """Result of plan execution."""
    results: Dict[str, TaskResult] = field(default_factory=dict)


@dataclass
class CriticReport:
    """Report from critic."""
    issues: List[str] = field(default_factory=list)
    should_replan: bool = False
    warnings: List[str] = field(default_factory=list)


# LLM Prompts
DECOMPOSE_PROMPT = """You are a task planning engine inside an AI operating system.

Your job is to convert a high-level goal into a structured task graph.

## Rules

1. Decompose the goal into atomic, executable tasks
2. Each task must represent ONE clear action
3. Tasks must have explicit dependencies (depends_on)
4. Use parallelization when possible
5. Avoid unnecessary steps
6. Do NOT invent data — only process or request it
7. Prefer minimal viable plan

## Task Types (use implicitly, do not label them):
- extraction (identify entities, inputs)
- retrieval (get data)
- transformation (clean/normalize)
- analysis (reason, compare, infer)
- generation (produce output)
- aggregation (combine results)

## Output format (STRICT JSON)

{
  "tasks": [
    {
      "id": "task_1",
      "description": "clear action description",
      "depends_on": []
    }
  ]
}

## Example

Goal:
"Analyze 3 competitors and summarize their strengths"

Output:
{
  "tasks": [
    {"id": "task_1", "description": "identify 3 competitors", "depends_on": []},
    {"id": "task_2a", "description": "collect data about competitor A", "depends_on": ["task_1"]},
    {"id": "task_2b", "description": "collect data about competitor B", "depends_on": ["task_1"]},
    {"id": "task_2c", "description": "collect data about competitor C", "depends_on": ["task_1"]},
    {"id": "task_3", "description": "compare competitors", "depends_on": ["task_2a", "task_2b", "task_2c"]},
    {"id": "task_4", "description": "summarize insights", "depends_on": ["task_3"]}
  ]
}

Now process the user goal."""

CRITIC_PROMPT = """You are a plan critic for an AI operating system.

Analyze:
1. Goal
2. Plan (tasks and dependencies)
3. Execution results

Find issues:
- failed tasks
- missing dependencies
- logical errors
- potential improvements

Return JSON:
{
  "issues": ["..."],
  "warnings": ["..."],
  "should_replan": true/false
}"""

REPLAN_PROMPT = """You are a replanning engine.

Given:
- original goal
- previous plan
- execution results
- critic issues

Fix the plan.

Rules:
- keep successful tasks
- replace failed tasks
- add missing steps
- remove redundant tasks
- ensure valid dependencies

Return updated plan in JSON format."""


class Planner:
    """
    Creates plans from goals using LLM.
    
    Uses the DECOMPOSE_PROMPT to generate structured task graphs.
    """
    
    def __init__(self, llm_func: Optional[Callable] = None):
        """
        Args:
            llm_func: Optional LLM function. If None, uses fallback.
        """
        self.llm_func = llm_func
    
    def create_plan(self, goal: str) -> Plan:
        """
        Create execution plan from goal.
        
        Args:
            goal: High-level goal description
            
        Returns:
            Plan with tasks
        """
        logger.info("creating_plan", goal=goal[:50])
        
        if self.llm_func:
            try:
                response = self.llm_func(
                    prompt=DECOMPOSE_PROMPT,
                    input=f"Goal: {goal}\n\nOutput JSON:"
                )
                data = json.loads(response)
                tasks = self._parse_tasks(data)
                plan = Plan(tasks=tasks)
                logger.info("plan_created_llm", tasks=len(tasks))
                return plan
            except Exception as e:
                logger.warning("llm_planning_failed", error=str(e))
        
        # Fallback: use task graph builder
        return self._fallback_plan(goal)
    
    def _parse_tasks(self, data: Dict) -> List[Task]:
        """Parse tasks from LLM response."""
        tasks = []
        for t in data.get("tasks", []):
            tasks.append(Task(
                id=t["id"],
                description=t["description"],
                depends_on=t.get("depends_on", [])
            ))
        return tasks
    
    def _fallback_plan(self, goal: str) -> Plan:
        """Fallback plan creation using task graph builder."""
        from semantic.dag_planner import dag_planner
        
        result = dag_planner.plan(goal)
        bindings = result.get("bindings", [])
        
        tasks = []
        for b in bindings:
            tasks.append(Task(
                id=b["task_id"],
                description=b["task_description"],
                depends_on=b.get("depends_on", [])
            ))
        
        return Plan(tasks=tasks)


class RuleBasedCritic:
    """
    Rule-based critic for quick validation.
    
    Checks:
    - Dependency validity
    - Cycle detection
    - Failed tasks
    """
    
    def evaluate(self, plan: Plan, result: ExecutionResult) -> CriticReport:
        """
        Evaluate plan execution.
        
        Returns:
            CriticReport with issues
        """
        issues = []
        warnings = []
        
        # 1. Check for failed tasks
        for task_id, task_result in result.results.items():
            if not task_result.success:
                issues.append(f"Task {task_id} failed: {task_result.error}")
        
        # 2. Check dependency validity
        task_ids = {t.id for t in plan.tasks}
        for task in plan.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    issues.append(f"Invalid dependency: {dep} not in plan")
        
        # 3. Check for cycles (simple DFS)
        if self._has_cycle(plan):
            issues.append("Plan contains cycles")
        
        # 4. Check for empty results
        if not result.results:
            warnings.append("No task results recorded")
        
        # 5. Check for orphaned tasks
        task_ids_with_results = set(result.results.keys())
        for task in plan.tasks:
            if task.id not in task_ids_with_results:
                warnings.append(f"Task {task.id} has no result")
        
        should_replan = len(issues) > 0
        
        return CriticReport(
            issues=issues,
            warnings=warnings,
            should_replan=should_replan
        )
    
    def _has_cycle(self, plan: Plan) -> bool:
        """Check for cycles using DFS."""
        visited = set()
        rec_stack = set()
        
        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = next((t for t in plan.tasks if t.id == task_id), None)
            if not task:
                rec_stack.remove(task_id)
                return False
            
            for dep in task.depends_on:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(task_id)
            return False
        
        for task in plan.tasks:
            if task.id not in visited:
                if dfs(task.id):
                    return True
        
        return False


class LLMCritic:
    """
    LLM-based critic for deeper analysis.
    
    Can find semantic issues that rule-based misses.
    """
    
    def __init__(self, llm_func: Optional[Callable] = None):
        self.llm_func = llm_func
    
    def evaluate(self, goal: str, plan: Plan, result: ExecutionResult) -> CriticReport:
        """
        Evaluate using LLM.
        
        Falls back to rule-based if LLM unavailable.
        """
        if not self.llm_func:
            critic = RuleBasedCritic()
            return critic.evaluate(plan, result)
        
        try:
            payload = {
                "goal": goal,
                "plan": [
                    {"id": t.id, "description": t.description, "depends_on": t.depends_on}
                    for t in plan.tasks
                ],
                "results": {
                    k: {"success": v.success, "error": v.error}
                    for k, v in result.results.items()
                }
            }
            
            response = self.llm_func(
                prompt=CRITIC_PROMPT,
                input=json.dumps(payload, indent=2)
            )
            
            data = json.loads(response)
            
            return CriticReport(
                issues=data.get("issues", []),
                warnings=data.get("warnings", []),
                should_replan=data.get("should_replan", False)
            )
            
        except Exception as e:
            logger.warning("llm_critic_failed", error=str(e))
            critic = RuleBasedCritic()
            return critic.evaluate(plan, result)


class Replanner:
    """
    Replans based on critic feedback.
    
    Uses LLM to fix issues or falls back to rule-based repair.
    """
    
    def __init__(self, llm_func: Optional[Callable] = None):
        self.llm_func = llm_func
    
    def replan(
        self, 
        goal: str, 
        plan: Plan, 
        result: ExecutionResult,
        report: CriticReport
    ) -> Plan:
        """
        Create new plan fixing issues.
        
        Args:
            goal: Original goal
            plan: Previous plan
            result: Execution results
            report: Critic report with issues
            
        Returns:
            New plan
        """
        logger.info("replanning", issues=len(report.issues))
        
        if self.llm_func:
            try:
                payload = {
                    "goal": goal,
                    "plan": [
                        {
                            "id": t.id, 
                            "description": t.description, 
                            "depends_on": t.depends_on
                        }
                        for t in plan.tasks
                    ],
                    "results": {
                        k: {"success": v.success, "error": v.error, "output": str(v.output)[:100]}
                        for k, v in result.results.items()
                    },
                    "issues": report.issues,
                    "warnings": report.warnings
                }
                
                response = self.llm_func(
                    prompt=REPLAN_PROMPT,
                    input=json.dumps(payload, indent=2)
                )
                
                data = json.loads(response)
                tasks = [
                    Task(
                        id=t["id"],
                        description=t["description"],
                        depends_on=t.get("depends_on", [])
                    )
                    for t in data.get("tasks", [])
                ]
                
                logger.info("replan_created_llm", tasks=len(tasks))
                return Plan(tasks=tasks)
                
            except Exception as e:
                logger.warning("llm_replan_failed", error=str(e))
        
        # Fallback: rule-based repair
        return self._rule_based_replan(goal, plan, result, report)
    
    def _rule_based_replan(
        self, 
        goal: str, 
        plan: Plan, 
        result: ExecutionResult,
        report: CriticReport
    ) -> Plan:
        """
        Rule-based plan repair.
        
        Removes failed tasks and retries.
        """
        logger.info("rule_based_replan")
        
        new_tasks = []
        for task in plan.tasks:
            task_result = result.results.get(task.id)
            
            if task_result and not task_result.success:
                # Skip failed task but keep it as comment
                logger.info("skipping_failed_task", task_id=task.id, error=task_result.error)
                continue
            
            new_tasks.append(task)
        
        # If all tasks failed, create simple fallback
        if not new_tasks:
            new_tasks = [Task(
                id="task_1",
                description=f"execute: {goal[:100]}",
                depends_on=[]
            )]
        
        return Plan(tasks=new_tasks)


class Executor:
    """
    Executes plans using capability runner.
    
    Supports parallel execution of independent tasks.
    """
    
    def __init__(self, capability_runner: Optional[Callable] = None):
        """
        Args:
            capability_runner: Function to run capabilities. 
                             Signature: (task_description) -> result
        """
        self.capability_runner = capability_runner
    
    def execute(self, plan: Plan) -> ExecutionResult:
        """
        Execute plan.
        
        Args:
            plan: Plan to execute
            
        Returns:
            ExecutionResult with all task results
        """
        results = {}
        completed = set()
        
        max_iterations = len(plan.tasks) * 2  # Safety limit
        iterations = 0
        
        while len(completed) < len(plan.tasks) and iterations < max_iterations:
            iterations += 1
            
            # Find ready tasks (all dependencies completed)
            ready_tasks = [
                t for t in plan.tasks
                if t.id not in completed
                and all(dep in completed for dep in t.depends_on)
            ]
            
            if not ready_tasks:
                # Check for blocked tasks
                remaining = [t for t in plan.tasks if t.id not in completed]
                if remaining:
                    # Find which dependency is missing
                    for task in remaining:
                        missing_deps = [d for d in task.depends_on if d not in completed]
                        if missing_deps:
                            logger.warning("missing_dependency", task=task.id, deps=missing_deps)
                break
            
            # Execute ready tasks
            for task in ready_tasks:
                try:
                    if self.capability_runner:
                        output = self.capability_runner(task.description)
                    else:
                        output = self._mock_execute(task.description)
                    
                    results[task.id] = TaskResult(
                        task_id=task.id,
                        output=output,
                        success=True
                    )
                except Exception as e:
                    logger.error("task_execution_failed", task_id=task.id, error=str(e))
                    results[task.id] = TaskResult(
                        task_id=task.id,
                        success=False,
                        error=str(e)
                    )
                
                completed.add(task.id)
        
        logger.info("plan_executed", completed=len(completed), total=len(plan.tasks))
        
        return ExecutionResult(results=results)
    
    def _mock_execute(self, description: str) -> str:
        """Mock execution for testing."""
        return f"executed: {description[:50]}"


class PlanningEngine:
    """
    Main orchestrator with critic + replan loop.
    
    Architecture:
    Goal → Planner → Plan → Executor → Results → Critic
                                                       ↓
                                                  Issues?
                                                 ↓        ↓
                                               NO       YES
                                                 ↓        ↓
                                               Done    Replanner
                                                         ↓
                                                      New Plan
    """
    
    def __init__(
        self,
        llm_func: Optional[Callable] = None,
        capability_runner: Optional[Callable] = None,
        max_iterations: int = 3
    ):
        """
        Args:
            llm_func: LLM function for planning/critic
            capability_runner: Function to execute capabilities
            max_iterations: Maximum replan iterations
        """
        self.planner = Planner(llm_func)
        self.executor = Executor(capability_runner)
        self.rule_critic = RuleBasedCritic()
        self.llm_critic = LLMCritic(llm_func)
        self.replanner = Replanner(llm_func)
        self.max_iterations = max_iterations
    
    def run(self, goal: str, use_llm_critic: bool = False) -> ExecutionResult:
        """
        Execute goal with planning loop.
        
        Args:
            goal: Goal to achieve
            use_llm_critic: Use LLM for deeper critique
            
        Returns:
            Final execution result
        """
        logger.info("planning_engine_start", goal=goal[:50])
        
        # Create initial plan
        plan = self.planner.create_plan(goal)
        
        for iteration in range(self.max_iterations):
            logger.info("iteration_start", iteration=iteration + 1, tasks=len(plan.tasks))
            
            # Execute plan
            result = self.executor.execute(plan)
            
            # Critic evaluation
            if use_llm_critic:
                report = self.llm_critic.evaluate(goal, plan, result)
            else:
                report = self.rule_critic.evaluate(plan, result)
            
            if not report.should_replan:
                logger.info("iteration_success", iteration=iteration + 1)
                return result
            
            logger.info(
                "iteration_issues",
                iteration=iteration + 1,
                issues=report.issues[:3]
            )
            
            # Replan
            plan = self.replanner.replan(goal, plan, result, report)
        
        logger.warning("max_iterations_reached", iterations=self.max_iterations)
        return result
    
    def get_plan(self, goal: str) -> Plan:
        """Get plan without executing."""
        return self.planner.create_plan(goal)


# Global instance (for convenience)
planning_engine = PlanningEngine()
