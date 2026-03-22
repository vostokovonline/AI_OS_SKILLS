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
    """
    Extract JSON from LLM response.
    
    LLM often returns text with JSON embedded. This extracts it reliably.
    
    Args:
        text: Raw LLM response
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If no JSON found
    """
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
    
    json_str = match.group()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error("json_parse_failed", error=str(e), json_snippet=json_str[:100])
        raise ValueError(f"Invalid JSON: {e}")


class LLMRouter:
    """
    Role-based LLM router for planning loop.
    
    Routes requests to appropriate models based on role:
    - planner   → deepseek-reasoner (ollama/deepseek-v3.1)
    - critic    → deepseek-reasoner (ollama/deepseek-v3.1)
    - replanner → deepseek-reasoner (ollama/deepseek-v3.1)
    - executor  → deepseek-reasoner (ollama/deepseek-v3.1)
    
    Note: Uses LiteLLM model names (defined in litellm_config.yaml)
    """
    
    ROLE_MODELS = {
        "planner": "deepseek-reasoner",
        "critic": "deepseek-reasoner", 
        "replanner": "deepseek-reasoner",
        "executor": "deepseek-reasoner",
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
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_data}
        ]
        
        try:
            from llm_fallback import chat_with_fallback_sync
            result = chat_with_fallback_sync(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096
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
