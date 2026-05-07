"""
Planner - LLM generates action plan based on goal + strategies
This is where strategies start to actually influence behavior
"""
import json
from typing import List, Dict, Any, Optional
from llm.direct_router import DirectLLMRouter
from learning.strategy_store import StrategyStore


class ActionStep:
    """Single action in a plan"""
    def __init__(self, action: str, skill: str = None, params: dict = None):
        self.action = action
        self.skill = skill
        self.params = params or {}
    
    def to_dict(self) -> dict:
        return {"action": self.action, "skill": self.skill, "params": self.params}


class Planner:
    """
    Generates structured action plans using LLM + strategies
    This is the key point where learning starts to affect behavior
    """
    
    def __init__(self):
        self.router = DirectLLMRouter()
        self.store = StrategyStore()
    
    async def generate_plan(self, goal_title: str, goal_description: str = None, task_type: str = None) -> List[ActionStep]:
        """
        Generate action plan with strategies as input
        """
        # Get relevant strategies (with timeout to avoid blocking)
        strategies = []
        try:
            import asyncio
            strategies = await asyncio.wait_for(
                self.store.get_best(limit=2, task_type=task_type),
                timeout=3.0
            )
        except:
            pass  # Skip strategies if slow
        
        # Build strategy context for prompt
        strategy_context = ""
        if strategies:
            strategy_context = "\n\nPROVEN STRATEGIES (use if relevant):\n"
            for s in strategies:
                strategy_context += f"- {s['name']}: {s['pattern']}\n"
        
        prompt = f"""You are a planning system. Generate a simple action plan.

Goal: {goal_title}
Description: {goal_description or 'none'}
Task type: {task_type or 'general'}

{strategy_context}

Output a JSON array with steps. Each step has:
- action: what to do
- skill: skill ID like 'core.write_file', 'core.echo', etc. (or null if not applicable)
- params: parameters for the action

Format:
[
  {{"action": "prepare_inputs", "skill": "core.write_file", "params": {{"filename": "test.txt"}}}},
  {{"action": "execute_skill", "skill": null, "params": {{}}}},
  {{"action": "validate_result", "skill": null, "params": {{}}}}
]

IMPORTANT: Put skill ID in the 'skill' field for EVERY step that needs a skill.
Do NOT leave skill as null if a skill is needed.

Return ONLY JSON array:"""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = await self.router.call_with_fallback(messages, max_tokens=200, timeout=20.0)
            
            if not result.get("success"):
                return self._default_plan()
            
            content = result.get("content", "")
            
            # Parse JSON from response
            if "[" in content:
                start = content.find("[")
                end = content.rfind("]") + 1
                json_str = content[start:end]
                steps_data = json.loads(json_str)
                
                plan = []
                for step in steps_data:
                    # Try multiple keys for skill
                    skill = (
                        step.get("skill") or 
                        step.get("skill_id") or 
                        step.get("skill_name") or
                        step.get("skill_id")
                    )
                    plan.append(ActionStep(
                        action=step.get("action", "unknown"),
                        skill=skill,
                        params=step.get("params", {})
                    ))
                
                logger.info("plan_parsed", 
                    steps=len(plan),
                    skills=[p.skill for p in plan]
                )
                
                return plan[:5]  # Limit to 5 steps
            
            return self._default_plan()
            
        except Exception:
            return self._default_plan()
    
    def _default_plan(self) -> List[ActionStep]:
        """Fallback plan if LLM fails - with default skill"""
        return [
            ActionStep("parse_requirements", None, {}),
            ActionStep("execute_skill", "core.write_file", {"filename": "output.txt", "text": "Default content"}),
            ActionStep("validate_result", None, {}),
        ]

    async def generate_plan_with_context(
        self, 
        goal_title: str, 
        goal_description: str = None, 
        task_type: str = None,
        failure_context: dict = None
    ) -> List[ActionStep]:
        """
        Generate plan with failure context for replanning.
        This enables the agent to learn from mistakes and try different approaches.
        """
        # Build failure context prompt
        failure_info = ""
        if failure_context:
            failed_skill = failure_context.get("failed_skill", "unknown")
            error = failure_context.get("error", "unknown")
            prev_steps = failure_context.get("previous_steps", [])
            
            failure_info = f"""
FAILURE CONTEXT (learn from this):
- Failed skill: {failed_skill}
- Error: {error}
- What was tried: {prev_steps}

The previous plan failed. Generate a NEW plan that:
1. Uses a DIFFERENT skill or approach
2. Handles the error that occurred
3. Has different step structure if needed
"""
        
        prompt = f"""You are a replanning system. A previous plan failed - you need to generate a NEW plan.

Goal: {goal_title}
Description: {goal_description or 'none'}
Task type: {task_type or 'general'}

{failure_info}

Output a JSON array with steps. Each step has:
- action: what to do
- skill: skill ID like 'core.write_file', 'core.echo', etc.
- params: parameters

IMPORTANT: Make the plan DIFFERENT from what failed before!
Use different skills or different parameters.

Format:
[
  {{"action": "execute_skill", "skill": "core.write_file", "params": {{"filename": "output.txt"}}}},
  {{"action": "validate_result", "skill": null, "params": {{}}}}
]

Return ONLY JSON array:"""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = await self.router.call_with_fallback(messages, max_tokens=200, timeout=20.0)
            
            if not result.get("success"):
                return self._default_plan()
            
            content = result.get("content", "")
            
            # Parse JSON
            if "[" in content:
                start = content.find("[")
                end = content.rfind("]") + 1
                json_str = content[start:end]
                steps_data = json.loads(json_str)
                
                plan = []
                for step in steps_data:
                    skill = step.get("skill") or step.get("skill_id")
                    plan.append(ActionStep(
                        action=step.get("action", "unknown"),
                        skill=skill,
                        params=step.get("params", {})
                    ))
                
                return plan[:5]
            
            return self._default_plan()
            
        except Exception:
            return self._default_plan()


class PolicyLayer:
    """
    Bandit-based strategy selection
    Balances exploration vs exploitation
    """
    
    async def select_strategy(self, task_type: str = None) -> Optional[Dict]:
        """
        ε-greedy selection: 20% explore, 80% exploit
        """
        import random
        
        strategies = await self.store.get_best(limit=10, task_type=task_type)
        
        if not strategies:
            return None
        
        # ε-greedy: 20% exploration
        if random.random() < 0.2:
            # Explore: random selection
            return random.choice(strategies)
        else:
            # Exploit: best by success_rate
            return max(strategies, key=lambda s: s['success_rate'])


__all__ = ["Planner", "ActionStep", "PolicyLayer"]