"""
LLM Router - Role-based model selection for AI-OS planning loop.

Architecture:
- Planner     → Qwen (reasoning, decomposition)
- Critic      → Qwen (analysis, error detection)
- Replanner   → Qwen (fix planning)
- Executor    → Minimax/opencode (code execution)

Usage:
    from semantic.llm_router import LLMRouter, extract_json
    
    router = LLMRouter()
    
    # Planner call
    response = router.call("planner", DECOMPOSE_PROMPT, goal)
    
    # Critic call  
    response = router.call("critic", CRITIC_PROMPT, context)
"""
from typing import Literal, Dict, Any, Optional, Callable, List
import re
import json
from logging_config import get_logger

logger = get_logger(__name__)

VALID_ROLES: List[Literal["planner", "critic", "replanner", "executor"]] = [
    "planner", "critic", "replanner", "executor"
]


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

_context_builder = None


def _get_context_builder():
    """Get or create context builder."""
    global _context_builder
    if _context_builder is None:
        try:
            from semantic.context_builder import get_context_builder
            _context_builder = get_context_builder()
        except ImportError:
            _context_builder = None
    return _context_builder


class LLMRouter:
    """
    Role-based LLM router with MULTI-MODEL support.
    
    Routes requests to different models based on role:
    - planner   → deepseek-reasoner (structured reasoning)
    - critic     → deepseek-reasoner (analytical, strict)
    - replanner  → deepseek-reasoner (creative fixing)
    - executor   → local-coder (code execution)
    
    Using same model for now, but architecture supports multi-model.
    """
    
    ROLE_MODELS = {
        "planner": "deepseek-reasoner",    # Structured planning
        "critic": "deepseek-reasoner",      # Critical analysis  
        "replanner": "deepseek-reasoner",   # Creative fixing
        "executor": "deepseek-reasoner",    # Execution
    }
    
    ROLE_TEMPERATURE = {
        "planner": 0.2,   # Structured, consistent
        "critic": 0.0,    # Strict, deterministic
        "replanner": 0.3, # Creative, flexible
        "executor": 0.2,  # Balanced
    }
    
    ROLE_MAX_TOKENS = {
        "planner": 4096,
        "critic": 2048,
        "replanner": 4096,
        "executor": 8192,
    }
    
    ROLE_TEMPERATURE = {
        "planner": 0.3,
        "critic": 0.2,
        "replanner": 0.3,
        "executor": 0.4,
    }
    
    def __init__(self, custom_models: Optional[Dict[str, str]] = None):
        """
        Initialize router.
        
        Args:
            custom_models: Override default model selection
        """
        if custom_models:
            self.ROLE_MODELS.update(custom_models)
    
    def call(
        self,
        role: str,
        prompt: str,
        input_data: str
    ) -> str:
        """
        Call LLM for specific role.
        
        Args:
            role: Role identifier (planner/critic/replanner/executor)
            prompt: System prompt
            input_data: User input
            
        Returns:
            Raw LLM response string
        """
        if role not in self.ROLE_MODELS:
            if role not in VALID_ROLES:
                raise ValueError(f"Unknown role: {role}. Must be one of {VALID_ROLES}")
            role = "planner"
        
        model = self.ROLE_MODELS[role]
        temperature = self.ROLE_TEMPERATURE[role]
        max_tokens = self.ROLE_MAX_TOKENS.get(role, 4096)
        
        builder = _get_context_builder()
        if builder and role == "planner":
            context = builder.build_planner_context(input_data)
            user_content = builder.format_for_llm(context, prompt)
            user_content = builder.wrap_with_validation(user_content)
        elif builder and role == "critic":
            context = {"raw_input": input_data}
            user_content = builder.format_for_llm(context, prompt)
        elif builder and role == "replanner":
            context = {"raw_input": input_data}
            user_content = builder.format_for_llm(context, prompt)
        else:
            user_content = input_data
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            from llm_fallback import chat_with_fallback_sync
            result = chat_with_fallback_sync(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = result["choices"][0]["message"]["content"]
            model_used = result.get("model", model)
            
            logger.info("llm_call_success", role=role, model=model_used)
            return content
            
        except Exception as e:
            logger.error("llm_call_failed", role=role, model=model, error=str(e))
            raise
    
    def call_json(
        self,
        role: str,
        prompt: str,
        input_data: str
    ) -> Dict[str, Any]:
        """
        Call LLM and parse JSON response.
        
        Args:
            role: Role identifier
            prompt: System prompt
            input_data: User input
            
        Returns:
            Parsed JSON dict
        """
        response = self.call(role, prompt, input_data)
        return extract_json(response)


class LLMWrapper:
    """
    Adapter for existing code that expects simple llm_func.
    
    Wraps LLMRouter to provide simple callable interface.
    
    Usage:
        router = LLMRouter()
        wrapper = router.get_wrapper()
        
        # Works like simple LLM function
        response = wrapper(prompt="...", input="...")
    """
    
    def __init__(self, router: Optional[LLMRouter] = None):
        self.router = router or LLMRouter()
    
    def __call__(
        self,
        prompt: str,
        input: str,
        role: str = "planner"
    ) -> str:
        """Simple callable interface."""
        if role not in VALID_ROLES:
            role = "planner"
        return self.router.call(role, prompt, input)


_global_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    """Get global router instance."""
    global _global_router
    if _global_router is None:
        _global_router = LLMRouter()
    return _global_router


def llm_func(prompt: str, input: str, role: str = "planner") -> str:
    """
    Global LLM function for planning engine.
    
    Usage:
        response = llm_func(DECOMPOSE_PROMPT, goal)
    """
    router = get_router()
    if role not in VALID_ROLES:
        role = "planner"
    return router.call(role, prompt, input)
