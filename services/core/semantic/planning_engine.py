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
import re

logger = get_logger(__name__)


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response."""
    if not text:
        raise ValueError("Empty response from LLM")
    
    text = text.strip()
    
    if text.startswith('{'):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in response: {text[:200]}")
    
    return json.loads(match.group())


@dataclass
class Task:
    """Atomic execution task."""
    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    justification: Optional[str] = field(default=None)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """Execution plan containing tasks."""
    tasks: List[Task] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class PlanValidator:
    """
    Validates plans before execution.
    
    Prevents empty plans, duplicate IDs, cycles, invalid dependencies.
    """
    
    @staticmethod
    def validate(plan: Plan) -> tuple[bool, str]:
        """
        Validate a plan.
        
        Returns:
            (is_valid, error_message)
        """
        if not plan.tasks:
            return False, "Plan is empty - no tasks defined"
        
        task_ids: set = set()
        for task in plan.tasks:
            if not task.id:
                return False, f"Task missing ID"
            
            if task.id in task_ids:
                return False, f"Duplicate task ID: {task.id}"
            task_ids.add(task.id)
            
            if not task.description:
                return False, f"Task {task.id} has empty description"
            
            for dep in task.depends_on:
                if dep not in task_ids and dep not in [t.id for t in plan.tasks]:
                    pass  # Forward reference allowed
        
        if PlanValidator._has_cycle(plan):
            return False, "Plan contains circular dependency"
        
        return True, ""
    
    @staticmethod
    def _has_cycle(plan: Plan) -> bool:
        """Check for cycles using DFS."""
        graph: Dict[str, List[str]] = {t.id: t.depends_on for t in plan.tasks}
        
        visited: set = set()
        rec_stack: set = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for dep in graph.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task in plan.tasks:
            if task.id not in visited:
                if dfs(task.id):
                    return True
        
        return False


class ExecutionValidator:
    """
    Validates execution results.
    
    Ensures all tasks were executed and no critical failures.
    """
    
    @staticmethod
    def validate(plan: Plan, result: ExecutionResult) -> tuple[bool, str]:
        """Validate execution results."""
        if not result.results:
            return False, "No execution results recorded"
        
        executed_ids = set(result.results.keys())
        
        failed = [tid for tid, r in result.results.items() if not r.success]
        
        if len(failed) == len(plan.tasks):
            return False, f"All {len(failed)} tasks failed"
        
        if failed:
            return True, f"Warning: {len(failed)} tasks failed: {failed}"
        
        return True, ""


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
    
    def _get_llm_router(self):
        """Get LLM router for planner role."""
        if self.llm_func:
            return self.llm_func
        try:
            from semantic.llm_router import llm_func as router_func
            return router_func
        except ImportError:
            return None
    
    def create_plan(self, goal: str) -> Plan:
        """
        Create execution plan from goal.
        
        Uses memory-based retrieval if similar plan exists.
        
        Args:
            goal: High-level goal description
            
        Returns:
            Plan with tasks
        """
        logger.info("creating_plan", goal=goal[:50])
        
        memory_hints = None
        hierarchical_result = None
        selected_strategy = None
        
        try:
            from semantic.plan_memory import get_plan_memory
            memory = get_plan_memory()
            memory_result = memory.retrieve(goal, top_k=3)
            
            available_strategies = ["api_fetch", "web_scraping", "database_fetch", "cached_data", "bulk_write"]
            available_strategies = self._enforce_blacklist(goal, available_strategies)
            
            hierarchical_result = memory.hierarchical_select(goal, available_strategies)
            
            if hierarchical_result.get("abstract_strategy"):
                selected_strategy = hierarchical_result["abstract_strategy"]
                if hasattr(selected_strategy, 'abstract_strategy'):
                    selected_strategy = selected_strategy.abstract_strategy
            
            if memory_result and memory_result.get("plans"):
                memory_hints = memory_result
                memory_hints["hierarchical_selection"] = {
                    "abstract_strategy": hierarchical_result.get("abstract_strategy"),
                    "concrete_strategy": hierarchical_result.get("concrete_strategy"),
                    "reasoning": hierarchical_result.get("reasoning", "")
                }
                
                constraints = hierarchical_result.get("constraints", [])
                recommendations = hierarchical_result.get("recommendations", [])
                memory_hints["risk_assessment"] = {
                    "constraints": constraints,
                    "recommendations": recommendations
                }
                
                logger.info("memory_hints_available", 
                           plans=len(memory_result["plans"]),
                           has_constraints=len(constraints) > 0,
                           selected_strategy=selected_strategy,
                           abstract=hierarchical_result.get("abstract_strategy"))
        except ImportError:
            pass
        except Exception as e:
            logger.warning("memory_retrieval_failed", error=str(e))
        
        # LLM-based planning (with memory context)
        llm = self._get_llm_router()
        
        if llm:
            try:
                # Build input with memory hints
                if memory_hints:
                    input_with_memory = self._build_input_with_memory(goal, memory_hints)
                else:
                    input_with_memory = f"Goal: {goal}\n\nOutput JSON:"
                
                response = llm(
                    prompt=DECOMPOSE_PROMPT,
                    input=input_with_memory,
                    role="planner"
                )
                data = extract_json(response)
                tasks = self._parse_tasks(data)
                plan = Plan(tasks=tasks)
                
                is_valid, error = PlanValidator.validate(plan)
                if not is_valid:
                    logger.warning("llm_plan_invalid", error=error)
                    return self._fallback_plan(goal)
                
                risk_assessment = self._assess_risks(plan, goal)
                structural_violations = risk_assessment.get("structural_violations", [])
                
                if structural_violations:
                    logger.warning("plan_has_structural_violations", violations=structural_violations)
                    return self._replan_without_structural_violations(goal, plan, risk_assessment)
                
                scores = risk_assessment.get("strategy_scores", [])
                constraints = risk_assessment.get("constraints", [])
                recommendations = risk_assessment.get("recommendations", [])
                
                if scores:
                    logger.info("strategy_scores", 
                               scores=[{"s": s["strategy"], "ev": s["expected_value"]} for s in scores[:3]])
                
                constraint_valid, constraint_error = self._validate_constraints(plan, constraints)
                if not constraint_valid:
                    logger.warning("plan_violates_constraints", error=constraint_error)
                    
                    if hierarchical_result:
                        logger.info("replanning_with_constraints", 
                                   constraints=len(constraints),
                                   recommendations=recommendations[:3])
                        return self._replan_with_constraints(goal, plan, constraints, recommendations)
                
                strategy_valid, strategy_error = self._validate_strategy_enforcement(plan, selected_strategy)
                if not strategy_valid:
                    logger.warning("plan_violates_strategy", error=strategy_error)
                    if hierarchical_result:
                        logger.info("replanning_for_strategy_violation")
                        return self._replan_with_constraints(goal, plan, constraints, recommendations)
                
                if constraints:
                    logger.info("constraints_passed", 
                               constraints_count=len(constraints),
                               recommendations=recommendations[:3])
                    plan.metadata["constraints_applied"] = True
                    plan.metadata["adaptation_log"] = {
                        "constraints": [c.get("failure_reason") for c in constraints],
                        "mitigations": recommendations
                    }
                    
                    logger.info("adaptation_detected",
                               reason=constraints[0].get("failure_reason") if constraints else None,
                               added=recommendations[0] if recommendations else None)
                
                plan.metadata["risk_penalty"] = risk_assessment.get("penalty", 0)
                plan.metadata["strategy_scores"] = scores
                plan.metadata["hierarchical_info"] = risk_assessment.get("hierarchical_result", {})
                logger.info("plan_created_llm", tasks=len(tasks), memory_used=memory_hints is not None)
                return plan
            except Exception as e:
                logger.warning("llm_planning_failed", error=str(e))
        
        # Fallback: use task graph builder
        return self._fallback_plan(goal)
    
    def _build_input_with_memory(self, goal: str, memory_hints: Dict) -> str:
        """Build input with strategic abstraction memory context and FAILURE CONSTRAINTS."""
        plans_text = ""
        patterns_text = ""
        strategy_text = ""
        
        for i, p in enumerate(memory_hints.get("plans", []), 1):
            tasks = p.get("tasks", [])
            tasks_preview = [t.get("description", t.get("id", "")) for t in tasks[:3]]
            patterns = self._extract_patterns(tasks)
            
            plans_text += f"\n{i}. Goal: {p.get('goal', 'unknown')[:50]}"
            plans_text += f"\n   Tasks: {', '.join(tasks_preview)}"
            plans_text += f"\n   Success rate: {p.get('success_rate', 0):.0%}"
            
            patterns_text += f"\n  - {patterns}"
        
        strategy_scores = memory_hints.get("strategy_scores", [])
        
        constraints_text = ""
        recommendations_text = ""
        hierarchical_info = ""
        
        if strategy_scores:
            strategy_text = "\n\n### STRATEGIC INSIGHTS (from experience)\n"
            
            for item in strategy_scores[:5]:
                insights = item.get("failure_insights", [])
                insight_str = ""
                if insights:
                    insight_str = f" → Risk: {insights[0]['reason']}"
                
                strategy_text += f"\n  {item['strategy']} ({item['abstract']}):\n"
                strategy_text += f"    expected_value={item['expected_value']:.2f}, bayesian_rate={item['bayesian_rate']:.0%}\n"
                strategy_text += f"    attempts={item['attempts']}, uncertainty={item['uncertainty']:.0%}{insight_str}\n"
            
            strategy_text += "\n  → Higher expected_value = better choice for THIS context\n"
            strategy_text += "  → Consider uncertainty when data is limited\n"
        
        risk_data = memory_hints.get("risk_assessment", {})
        constraints = risk_data.get("constraints", [])
        recommendations = risk_data.get("recommendations", [])
        
        if constraints:
            constraints_text = "\n\n### 🚨 KNOWN FAILURE PATTERNS (CRITICAL - MUST ADDRESS)\n"
            for c in constraints[:5]:
                constraints_text += f"\n- If using: {c.get('if_using', 'any strategy')}"
                constraints_text += f"\n  Failure: {c.get('failure_reason', 'unknown')}"
                constraints_text += f"\n  → MUST add: {c.get('mitigation', 'alternative approach')}\n"
        
        if recommendations:
            recommendations_text = "\n\n### ✅ RECOMMENDED MITIGATIONS:\n"
            for r in recommendations[:5]:
                recommendations_text += f"\n- {r}"
        
        hierarchical = memory_hints.get("hierarchical_selection", {})
        strategy_lock = ""
        hierarchical_info = ""
        
        if hierarchical:
            abstract = hierarchical.get("abstract_strategy")
            concrete = hierarchical.get("concrete_strategy")
            reasoning = hierarchical.get("reasoning", "")
            
            if abstract:
                if hasattr(abstract, 'abstract_strategy'):
                    abstract_name = abstract.abstract_strategy
                else:
                    abstract_name = str(abstract)
                
                if concrete:
                    if hasattr(concrete, 'strategy'):
                        concrete_name = concrete.strategy
                    else:
                        concrete_name = str(concrete)
                    concrete_info = f"Concrete implementation: {concrete_name}"
                else:
                    concrete_info = ""
                
                hierarchical_info = f"\n\n### 🎯 SELECTED STRATEGY:\n  Abstract: {abstract_name}\n{concrete_info}\n  Reasoning: {reasoning}\n"
                
                strategy_lock = f"""
=== ⚡ STRATEGY LOCK (MANDATORY) ===

You MUST follow this strategy: {abstract_name}
{concrete_info}

RULES:
1. Do NOT deviate from the selected strategy
2. Do NOT try alternative strategies
3. Execute ONLY within this strategy framework
4. If strategy has limitations, work around them WITHIN the strategy

VIOLATION = PLAN REJECTED"""
        
        return f"""Goal: {goal}

=== MEMORY (MANDATORY ANALYSIS) ===

Analyze past strategic experiences.
Consider ABSTRACT strategy types, not just concrete implementations.

{plans_text}

Extracted Patterns:
{patterns_text}
{strategy_text}
{hierarchical_info}
{constraints_text}
{recommendations_text}
{strategy_lock}

=== STRICT RULES (NON-NEGOTIABLE) ===

1. If failure patterns exist above, you MUST include their mitigations in the plan.
2. You MUST NOT repeat known failure patterns without adding mitigation steps.
3. Tasks using rate_limit-prone strategies MUST include retry_with_backoff.
4. If you ignore recommendations, you MUST justify in "reasoning" field.

=== YOUR RESPONSE ===

Analyze memory:
- What ABSTRACT strategy works best for this type of goal?
- What failures tell us about WHY something didn't work?
- Consider uncertainty when data is limited.

Strategy types (use as guidance):
- structured_data_acquisition: APIs, databases (predictable, reliable)
- unstructured_data_acquisition: web scraping (flexible but risky)
- cached_data_retrieval: cached sources (fast but may be stale)

Output your plan in STRICT JSON format:
{{
  "reasoning": "why this plan is correct, including how failures are avoided",
  "tasks": [
    {{
      "id": "task_1",
      "description": "clear actionable step",
      "depends_on": []
    }}
  ]
}}

Constraints:
- Max 7 tasks
- No cycles
- Each task must be executable"""

    def _extract_patterns(self, tasks: List[Dict]) -> str:
        """Extract actionable patterns from tasks."""
        if not tasks:
            return "no-pattern"
        
        verbs = {"identify", "collect", "fetch", "retrieve", "analyze", 
                 "compare", "generate", "summarize", "extract", "create"}
        
        patterns = []
        for t in tasks:
            desc = t.get("description", "").lower()
            words = desc.split()
            action = next((w for w in words if w in verbs), words[0] if words else "unknown")
            patterns.append(action)
        
        return " → ".join(patterns)
    
    def _assess_risks(self, plan: Plan, goal: str = "") -> Dict[str, Any]:
        """
        Assess plan risks using hierarchical bandit scoring.
        
        Returns:
            {
                "can_proceed": bool,
                "penalty": float,
                "strategy_scores": [...],
                "constraints": [...],
                "recommendations": [...]
            }
        """
        try:
            from semantic.plan_memory import get_plan_memory
            memory = get_plan_memory()
            
            task_strategies = [memory._extract_strategy({"description": t.description}) for t in plan.tasks]
            unique_strategies = list(set(task_strategies))
            
            result = memory.select_best_strategy(goal, unique_strategies)
            
            constraints = result.get("constraints", [])
            recommendations = result.get("recommendations", [])
            
            abstract_score = result.get("abstract_strategy")
            concrete_score = result.get("concrete_strategy")
            
            strategy_scores = []
            if abstract_score:
                strategy_scores.append({
                    "strategy": abstract_score.abstract_strategy,
                    "abstract": abstract_score.abstract_strategy,
                    "expected_value": abstract_score.expected_value,
                    "bayesian_rate": abstract_score.bayesian_success_rate,
                    "uncertainty": abstract_score.uncertainty,
                    "attempts": abstract_score.attempts,
                    "failure_insights": abstract_score.failure_insights
                })
            
            return {
                "can_proceed": True,
                "risks": [],
                "penalty": 0.0,
                "strategy_scores": strategy_scores,
                "constraints": constraints,
                "recommendations": recommendations,
                "hierarchical_result": {
                    "abstract": abstract_score.abstract_strategy if abstract_score else None,
                    "concrete": concrete_score.strategy if concrete_score else None,
                    "reasoning": result.get("reasoning", "")
                }
            }
        except ImportError:
            return {"can_proceed": True, "risks": [], "penalty": 0.0, "strategy_scores": [], "constraints": [], "recommendations": []}
        except Exception as e:
            logger.warning("risk_assessment_failed", error=str(e))
            return {"can_proceed": True, "risks": [], "penalty": 0.0, "strategy_scores": [], "constraints": [], "recommendations": []}
    
    def _validate_constraints(self, plan: Plan, constraints: List[Dict]) -> tuple[bool, str]:
        """
        HARD Validate that plan includes required mitigations for known failures.
        
        This is the ENFORCEMENT layer - not suggestions, but requirements.
        
        Returns:
            (is_valid, error_message)
        """
        if not constraints:
            return True, ""
        
        violations = []
        task_descriptions = " ".join(t.description.lower() for t in plan.tasks)
        
        for constraint in constraints:
            failure_reason = constraint.get("failure_reason", "")
            mitigation = constraint.get("mitigation", "")
            
            if failure_reason == "rate_limit":
                has_retry = any(w in task_descriptions for w in ["retry", "backoff", "delay", "wait", "attempt"])
                if not has_retry:
                    violations.append(f"VIOLATION: Missing retry/backoff for rate_limit. Required: {mitigation}")
            
            elif failure_reason == "timeout":
                has_retry = any(w in task_descriptions for w in ["retry", "async", "timeout"])
                if not has_retry:
                    violations.append(f"VIOLATION: Missing retry/async for timeout. Required: {mitigation}")
            
            elif failure_reason == "authentication":
                has_auth = any(w in task_descriptions for w in ["token", "auth", "refresh", "credential", "bearer"])
                if not has_auth:
                    violations.append(f"VIOLATION: Missing token refresh for authentication. Required: {mitigation}")
        
        if violations:
            return False, "; ".join(violations)
        
        return True, ""
    
    def _validate_strategy_enforcement(
        self, 
        plan: Plan, 
        selected_strategy: Optional[str]
    ) -> tuple[bool, str]:
        """
        HARD Validate that plan follows the selected strategy.
        
        This rejects plans that deviate from the strategy selected by the scoring system.
        
        Returns:
            (is_valid, error_message)
        """
        if not selected_strategy:
            return True, ""
        
        task_descriptions = " ".join(t.description.lower() for t in plan.tasks)
        
        forbidden_patterns = {
            "structured_data_acquisition": ["scrape", "crawl", "beautifulsoup", "selenium", "playwright"],
            "unstructured_data_acquisition": ["api", "database", "sql", "query endpoint"],
            "cached_data_retrieval": [],
            "bulk_data_operation": [],
        }
        
        if selected_strategy in forbidden_patterns:
            forbidden = forbidden_patterns[selected_strategy]
            violations = []
            
            for pattern in forbidden:
                if pattern in task_descriptions:
                    violations.append(f"VIOLATION: Using {pattern} but selected strategy is {selected_strategy}")
            
            if violations:
                return False, "; ".join(violations)
        
        return True, ""
    
    def _enforce_blacklist(
        self, 
        goal: str, 
        available_strategies: List[str]
    ) -> List[str]:
        """
        Score-based selection with blacklist as SOFT constraint.
        
        - High uncertainty strategies get exploration bonus
        - Even blacklisted strategies can be tried if uncertainty is high enough
        - After success, strategy is removed from blacklist
        
        Returns:
            Sorted list of strategies (best first)
        """
        try:
            from semantic.plan_memory import get_plan_memory
            memory = get_plan_memory()
            
            blacklisted = memory.get_blacklisted_strategies(goal)
            
            blacklist_strategies = set()
            if blacklisted:
                for key in blacklisted.keys():
                    if ":" in key:
                        strategy_part = key.split(":", 1)[1]
                        blacklist_strategies.add(strategy_part)
                    else:
                        blacklist_strategies.add(key)
                
                logger.warning("blacklisted_strategies_present", 
                             goal=goal[:30], 
                             blacklisted=list(blacklist_strategies))
            
            mode = memory.get_mode()
            locked = memory.get_locked_strategy()
            
            logger.info("strategy_selection_mode",
                       goal=goal[:30],
                       mode=mode,
                       locked_strategy=locked)
            
            selected = memory.select_strategy(available_strategies)
            
            logger.info("strategy_selected",
                       goal=goal[:30],
                       selected=selected,
                       mode=mode)
            
            return [selected] + [s for s in available_strategies if s != selected]
            
        except Exception:
            pass
        
        return available_strategies
    
    def _replan_with_constraints(self, goal: str, plan: Plan, constraints: List[Dict], recommendations: List[str]) -> Plan:
        """
        Regenerate plan WITH constraints - adds required mitigations.
        """
        logger.info("replan_with_constraints", constraints_count=len(constraints))
        
        constraints_str = "\n".join([f"- {c.get('mitigation')}" for c in constraints[:3]])
        
        llm = self._get_llm_router()
        if llm:
            try:
                prompt = f"""Goal: {goal}

You must add MITIGATIONS to your plan based on past failures:

REQUIRED MITIGATIONS (MUST include):
{constraints_str}

Previous plan tasks:
{chr(10).join([f"- {t.description}" for t in plan.tasks[:5]])}

Return updated plan that INCLUDES these mitigations:
{{
  "reasoning": "why this plan addresses past failures",
  "tasks": [
    {{"id": "task_1", "description": "action with mitigation", "depends_on": []}}
  ]
}}"""
                
                response = llm(prompt=DECOMPOSE_PROMPT, input=prompt, role="planner")
                data = extract_json(response)
                tasks = self._parse_tasks(data)
                new_plan = Plan(tasks=tasks)
                
                is_valid, _ = PlanValidator.validate(new_plan)
                if is_valid:
                    logger.info("replan_with_constraints_success", tasks=len(tasks))
                    return new_plan
            except Exception as e:
                logger.warning("replan_with_constraints_failed", error=str(e))
        
        return plan
    
    def _replan_without_structural_violations(self, goal: str, plan: Plan, risks: Dict) -> Plan:
        """
        Regenerate plan avoiding structural risk patterns.
        """
        structural = risks.get("structural_violations", [])
        violated_strategies = [v["strategy"] for v in structural]
        
        logger.info("replan_without_structural_violations", violations=violated_strategies)
        
        llm = self._get_llm_router()
        if llm:
            try:
                prompt = f"""Goal: {goal}

You must create a plan that AVOIDS these failed strategies:
{', '.join(violated_strategies)}

These patterns led to failures in previous attempts.

Return JSON plan that does NOT use any of these strategies:
{{
  "tasks": [
    {{"id": "task_1", "description": "alternative approach", "depends_on": []}}
  ]
}}"""
                
                response = llm(prompt=DECOMPOSE_PROMPT, input=prompt, role="planner")
                data = extract_json(response)
                tasks = self._parse_tasks(data)
                new_plan = Plan(tasks=tasks)
                
                is_valid, _ = PlanValidator.validate(new_plan)
                if is_valid:
                    return new_plan
            except Exception as e:
                logger.warning("replan_without_violations_failed", error=str(e))
        
        return self._fallback_plan(goal)
    
    def _parse_tasks(self, data: Dict) -> List[Task]:
        """Parse tasks from LLM response."""
        tasks = []
        for t in data.get("tasks", []):
            tasks.append(Task(
                id=t["id"],
                description=t["description"],
                depends_on=t.get("depends_on", []),
                justification=t.get("justification")
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
                    input=json.dumps(payload, indent=2),
                    role="replanner"
                )
                
                data = extract_json(response)
                tasks = [
                    Task(
                        id=t["id"],
                        description=t["description"],
                        depends_on=t.get("depends_on", [])
                    )
                    for t in data.get("tasks", [])
                ]
                
                new_plan = Plan(tasks=tasks)
                
                is_valid, error = PlanValidator.validate(new_plan)
                if not is_valid:
                    logger.warning("replan_invalid", error=error, keeping_old=True)
                    return plan
                
                logger.info("replan_created_llm", tasks=len(tasks))
                return new_plan
                
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
        max_iterations: int = 3,
        max_replans: int = 3,
        degradation_replans: int = 5
    ):
        """
        Args:
            llm_func: LLM function for planning/critic
            capability_runner: Function to execute capabilities
            max_iterations: Maximum execution iterations per plan
            max_replans: Maximum replan attempts before forcing degraded plan
            degradation_replans: After this many replans, use fallback strategy
        """
        self.planner = Planner(llm_func)
        self.executor = Executor(capability_runner)
        self.rule_critic = RuleBasedCritic()
        self.llm_critic = LLMCritic(llm_func)
        self.replanner = Replanner(llm_func)
        self.max_iterations = max_iterations
        self.max_replans = max_replans
        self.degradation_replans = degradation_replans
        
        self._replan_count = 0
        self._last_plan_hash = ""
        self._consecutive_violations = 0
        
        self._execution_policy_manager = None
        try:
            from semantic.execution_policy import get_execution_policy_manager
            self._execution_policy_manager = get_execution_policy_manager()
        except ImportError:
            pass
    
    def run(self, goal: str, use_llm_critic: bool = False) -> ExecutionResult:
        """
        Execute goal with planning loop.
        
        Includes ANTI-LOOP protection:
        - Track replan count
        - Force degraded plan after max_replans
        - Track similar failures to prevent infinite loops
        
        Args:
            goal: Goal to achieve
            use_llm_critic: Use LLM for deeper critique
            
        Returns:
            Final execution result
        """
        logger.info("planning_engine_start", goal=goal[:50])
        
        self._replan_count = 0
        self._consecutive_violations = 0
        
        plan = self.planner.create_plan(goal)
        plan_hash = self._hash_plan(plan)
        self._last_plan_hash = plan_hash
        
        result = ExecutionResult(results={})
        
        for iteration in range(self.max_iterations):
            logger.info("iteration_start", iteration=iteration + 1, tasks=len(plan.tasks))
            
            # ANTI-LOOP: Check if we're stuck
            if self._replan_count >= self.max_replans:
                logger.warning("anti_loop_triggered", 
                             replans=self._replan_count,
                             strategy="degraded_plan")
                plan = self._create_degraded_plan(goal)
            
            # Execute plan
            result = self.executor.execute(plan)
            
            # Critic evaluation
            if use_llm_critic:
                report = self.llm_critic.evaluate(goal, plan, result)
            else:
                report = self.rule_critic.evaluate(plan, result)
            
            if not report.should_replan:
                logger.info("iteration_success", iteration=iteration + 1)
                self._store_execution_in_memory(goal, plan, result, success=True)
                self._reset_anti_loop()
                return result
            
            logger.info(
                "iteration_issues",
                iteration=iteration + 1,
                issues=report.issues[:3]
            )
            
            self._store_execution_in_memory(goal, plan, result, success=False)
            
            failed_task_ids = [tid for tid, tres in result.results.items() if not tres.success]
            failed_errors = {tid: result.results[tid].error for tid in failed_task_ids}
            plan.metadata["last_errors"] = failed_errors
            
            # ANTI-LOOP: Check for repeated same plan
            new_plan = self.get_plan_with_failure_context(goal, failed_errors, plan)
            new_hash = self._hash_plan(new_plan)
            
            if new_hash == self._last_plan_hash:
                self._consecutive_violations += 1
                logger.warning("same_plan_repeated", 
                             violations=self._consecutive_violations)
                
                if self._consecutive_violations >= 2:
                    logger.warning("forcing_strategy_switch")
                    new_plan = self._create_degraded_plan(goal)
            
            self._last_plan_hash = new_hash
            plan = new_plan
            self._replan_count += 1
        
        logger.warning("max_iterations_reached", iterations=self.max_iterations)
        self._store_execution_in_memory(goal, plan, result, success=False)
        
        return result
    
    def _hash_plan(self, plan: Plan) -> str:
        """Create hash of plan for anti-loop detection."""
        import hashlib
        content = "|".join([
            f"{t.id}:{t.description}" 
            for t in sorted(plan.tasks, key=lambda x: x.id)
        ])
        return hashlib.md5(content.encode()).hexdigest()
    
    def _create_degraded_plan(self, goal: str) -> Plan:
        """
        Create a degraded fallback plan when normal planning fails.
        
        This is the last resort - simple, guaranteed to work.
        """
        logger.warning("creating_degraded_plan", reason="max_replans_exceeded")
        
        return self.planner._fallback_plan(goal)
    
    def _reset_anti_loop(self):
        """Reset anti-loop counters after success."""
        self._replan_count = 0
        self._consecutive_violations = 0
    
    def get_plan(self, goal: str) -> Plan:
        """Get plan without executing."""
        return self.planner.create_plan(goal)
    
    def get_plan_with_failure_context(
        self, 
        goal: str, 
        failed_tasks: Dict[str, str],
        previous_plan: Plan
    ) -> Plan:
        """
        Create plan with explicit failure context.
        
        This is the self-repair mechanism:
        - Takes failed tasks and their errors
        - Forces planner to use constraints
        - Returns plan with mitigations
        """
        try:
            from semantic.plan_memory import get_plan_memory
            memory = get_plan_memory()
            
            available_strategies = ["api_fetch", "web_scraping", "database_fetch", "cached_data"]
            selection = memory.select_best_strategy(goal, available_strategies)
            
            constraints = selection.get("constraints", [])
            recommendations = selection.get("recommendations", [])
            
            if constraints:
                logger.info("self_repair_with_constraints",
                           goal=goal[:30],
                           constraints=[c.get("failure_reason") for c in constraints],
                           recommendations=recommendations[:3])
                
                return self._create_constrained_plan(
                    goal, constraints, recommendations, previous_plan
                )
            
        except Exception as e:
            logger.warning("self_repair_failed", error=str(e))
        
        return self.planner.create_plan(goal)
    
    def _create_constrained_plan(
        self,
        goal: str,
        constraints: List[Dict],
        recommendations: List[str],
        previous_plan: Plan
    ) -> Plan:
        """Create plan with forced constraints from failures."""
        llm = self.planner._get_llm_router()
        
        if not llm:
            return previous_plan
        
        try:
            constraints_str = "\n".join([
                f"- {c.get('mitigation', c.get('failure_reason', 'unknown'))}"
                for c in constraints[:3]
            ])
            
            failed_tasks_str = "\n".join([
                f"- {tid}: {err[:100]}"
                for tid, err in previous_plan.metadata.get("last_errors", {}).items()
            ])
            
            prompt = f"""Goal: {goal}

Your previous plan FAILED. You MUST create a new plan that addresses the failures.

FAILED TASKS FROM PREVIOUS ATTEMPT:
{failed_tasks_str}

REQUIRED MITIGATIONS (MUST include in plan):
{constraints_str}

STRICT RULES:
1. If using API calls → MUST include retry with exponential backoff
2. If previous task failed → fix it, don't repeat
3. Each mitigation must be a separate task

Return plan in JSON:
{{
  "reasoning": "how this plan fixes the failures",
  "tasks": [
    {{"id": "task_1", "description": "mitigation step", "depends_on": []}}
  ]
}}"""
            
            response = llm(prompt=DECOMPOSE_PROMPT, input=prompt, role="planner")
            data = extract_json(response)
            tasks = self.planner._parse_tasks(data)
            new_plan = Plan(tasks=tasks)
            
            is_valid, _ = PlanValidator.validate(new_plan)
            if is_valid:
                logger.info("self_repair_success", tasks=len(tasks))
                return new_plan
                
        except Exception as e:
            logger.warning("constrained_plan_failed", error=str(e))
        
        return previous_plan
    
    def _store_execution_in_memory(
        self, 
        goal: str, 
        plan: Plan, 
        result: ExecutionResult,
        success: bool
    ) -> None:
        """
        Store execution result in memory for learning.
        
        This is the CRITICAL feedback loop:
        - Success → strategy reinforced
        - Failure → strategy penalized + blacklist + constraints generated
        """
        try:
            from semantic.plan_memory import get_plan_memory
            memory = get_plan_memory()
            
            tasks_data = [
                {"id": t.id, "description": t.description, "depends_on": t.depends_on}
                for t in plan.tasks
            ]
            
            if success:
                memory.store(goal, tasks_data, success=True)
                logger.info("learning_signal_success", goal=goal[:30])
            else:
                failed_task_ids = []
                failure_errors = {}
                failure_reasons = []
                
                for tid, tres in result.results.items():
                    if not tres.success:
                        failed_task_ids.append(tid)
                        error_msg = tres.error or "unknown"
                        failure_errors[tid] = error_msg
                        
                        reason = memory._categorize_failure(error_msg)
                        failure_reasons.append(reason)
                
                memory.store(
                    goal, 
                    tasks_data, 
                    success=False,
                    failed_task_ids=failed_task_ids,
                    failure_errors=failure_errors
                )
                
                strategy = memory._extract_strategy(tasks_data[0]) if tasks_data else "unknown"
                
                any_blacklisted = False
                for reason in failure_reasons:
                    blacklisted = memory.record_failure(goal, strategy, reason)
                    if blacklisted:
                        any_blacklisted = True
                        logger.warning("strategy_blacklisted", 
                                     goal=goal[:30], 
                                     strategy=strategy,
                                     reason=reason)
                
                logger.info(
                    "learning_signal_failure",
                    goal=goal[:30],
                    failed_count=len(failed_task_ids),
                    reasons=[e[:50] for e in failure_errors.values()],
                    blacklisted=any_blacklisted
                )
                
        except ImportError:
            pass
        except Exception as e:
            logger.warning("learning_signal_failed", error=str(e))


# Global instance (for convenience)
planning_engine = PlanningEngine()


def create_llm_engine(
    capability_runner: Optional[Callable] = None,
    max_iterations: int = 3
) -> PlanningEngine:
    """
    Create planning engine with LLM integration.
    
    Usage:
        from semantic.planning_engine import create_llm_engine
        
        engine = create_llm_engine(capability_runner=my_runner)
        result = engine.run("analyze 3 competitors")
    """
    return PlanningEngine(
        llm_func=None,
        capability_runner=capability_runner,
        max_iterations=max_iterations
    )
