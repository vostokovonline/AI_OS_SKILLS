"""
Capability-Based Skill Router
=============================
Automatically selects the right skill based on task requirements.

Flow:
Task Request → Analyze Required Capabilities
                    ↓
              Find Matching Skills
                    ↓
              [code available?] → YES → Execute Code
                    ↓
                    NO
                    ↓
              [LLM fallback?] → YES → Execute LLM
                    ↓
                    NO
                    ↓
              Error: No skill found

Author: Claude
Date: 2026-03-03
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SkillCapability:
    """Represents what a skill can do"""
    name: str
    category: str  # "code" | "llm" | "hybrid"
    input_types: List[str]  # ["text", "file", "json"]
    output_types: List[str]  # ["text", "artifact", "json"]
    execution_priority: int = 10  # Lower = higher priority
    requires_llm: bool = False


class CapabilityRouter:
    """
    Routes tasks to skills based on capabilities.
    
    Key features:
    - Automatic skill selection based on requirements
    - Code-first with LLM fallback
    - Capability matching
    - Execution policy enforcement
    """
    
    def __init__(self):
        self.capabilities: Dict[str, SkillCapability] = {}
        self.skill_registry: Dict[str, Any] = {}
        
    def register_capability(
        self,
        skill_name: str,
        category: str,
        input_types: List[str],
        output_types: List[str],
        priority: int = 10,
        requires_llm: bool = False,
        skill_class: Any = None,
        llm_prompt_template: str = None
    ):
        """Register a skill with its capabilities"""
        self.capabilities[skill_name] = SkillCapability(
            name=skill_name,
            category=category,
            input_types=input_types,
            output_types=output_types,
            execution_priority=priority,
            requires_llm=requires_llm
        )
        
        self.skill_registry[skill_name] = {
            "class": skill_class,
            "llm_template": llm_prompt_template,
            "category": category
        }
        
        logger.info(
            "capability_registered",
            skill=skill_name,
            category=category,
            inputs=input_types,
            outputs=output_types
        )
    
    def find_best_skill(
        self,
        required_inputs: List[str] = None,
        required_outputs: List[str] = None,
        prefer_code: bool = True,
        category: str = None,
        task_keywords: List[str] = None
    ) -> Optional[str]:
        """
        Find the best skill based on requirements.
        
        Args:
            required_inputs: List of required input types
            required_outputs: List of required output types
            prefer_code: Prefer code-based skills over LLM
            category: Filter by category
            task_keywords: Keywords to match (e.g., ["summarize", "write"])
            
        Returns:
            Best matching skill name or None
        """
        candidates = []
        
        for skill_name, cap in self.capabilities.items():
            # Filter by category
            if category and cap.category != category:
                continue
                
            # Check input compatibility
            if required_inputs:
                if not any(it in cap.input_types for it in required_inputs):
                    continue
                    
            # Check output compatibility
            if required_outputs:
                if not any(ot in cap.output_types for ot in required_outputs):
                    continue
            
            # Score the skill
            score = cap.execution_priority * 10  # Base score from priority
            
            # Keyword matching bonus (strongest signal)
            if task_keywords:
                if skill_name in task_keywords:
                    score -= 50  # Big bonus for explicit keyword match
                # Also check if any keyword is in skill name
                elif any(kw in skill_name for kw in task_keywords if len(kw) > 3):
                    score -= 30
            
            # Prefer code skills ONLY for simple tasks
            # LLM skills should handle complex NLP
            if cap.category == "code":
                # Check if this is a complex task
                is_complex = any(kw in task_keywords for kw in ["summarize", "analyze", "story", "creative", "generate"])
                if is_complex:
                    score += 15  # Penalize code for complex tasks
                else:
                    score -= 20  # Prefer code for simple tasks
            elif cap.requires_llm:
                # Boost LLM for complex tasks
                is_complex = any(kw in task_keywords for kw in ["summarize", "analyze", "story", "creative", "generate"])
                if is_complex:
                    score -= 25  # Big boost for LLM on complex tasks
                # else leave as is
            
            candidates.append((score, skill_name, cap.category, cap.execution_priority))
        
        if not candidates:
            return None
            
        # Return best match (lowest score = highest priority)
        candidates.sort(key=lambda x: x[0])
        
        # Debug: log all candidates
        logger.info(
            "skill_candidates",
            candidates=[{"skill": c[1], "score": c[0], "cat": c[2], "prio": c[3]} for c in candidates[:5]]
        )
        
        best = candidates[0][1]
        
        logger.info(
            "skill_selected",
            skill=best,
            score=candidates[0][0],
            inputs=required_inputs,
            outputs=required_outputs
        )
        
        return best
    
    def get_execution_path(self, skill_name: str) -> str:
        """Get execution path for a skill: 'code' or 'llm'"""
        if skill_name not in self.capabilities:
            return "unknown"
        return self.capabilities[skill_name].category
    
    def list_capabilities(self) -> List[Dict]:
        """List all registered capabilities"""
        return [
            {
                "skill": name,
                "category": cap.category,
                "inputs": cap.input_types,
                "outputs": cap.output_types,
                "priority": cap.execution_priority,
                "requires_llm": cap.requires_llm
            }
            for name, cap in self.capabilities.items()
        ]


# Global router instance
capability_router = CapabilityRouter()


def register_canonical_skill(
    skill_name: str,
    skill_class: Any,
    input_types: List[str],
    output_types: List[str],
    priority: int = 5
):
    """Register a canonical (code-based) skill"""
    capability_router.register_capability(
        skill_name=skill_name,
        category="code",
        input_types=input_types,
        output_types=output_types,
        priority=priority,
        requires_llm=False,
        skill_class=skill_class
    )


def register_llm_skill(
    skill_name: str,
    prompt_template: str,
    input_types: List[str],
    output_types: List[str],
    priority: int = 10
):
    """Register an LLM-based skill"""
    capability_router.register_capability(
        skill_name=skill_name,
        category="llm",
        input_types=input_types,
        output_types=output_types,
        priority=priority,
        requires_llm=True,
        skill_class=None,
        llm_prompt_template=prompt_template
    )


def auto_route_task(
    task_description: str,
    required_inputs: List[str] = None,
    required_outputs: List[str] = None,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Automatically route a task to the best skill.
    
    This is the main entry point for capability-based routing.
    """
    # Analyze task to determine requirements
    requirements = _analyze_task(task_description, context or {})
    
    # Extract keywords for matching
    keywords = requirements.get("keywords", [])
    
    # Merge with provided requirements
    inputs = required_inputs or requirements.get("inputs", ["text"])
    outputs = required_outputs or requirements.get("outputs", ["text"])
    
    # Find best skill
    skill_name = capability_router.find_best_skill(
        required_inputs=inputs,
        required_outputs=outputs,
        prefer_code=True,
        task_keywords=keywords
    )
    
    if not skill_name:
        return {
            "status": "error",
            "message": "No skill found matching requirements",
            "inputs": inputs,
            "outputs": outputs
        }
    
    # Get execution path
    exec_path = capability_router.get_execution_path(skill_name)
    
    return {
        "status": "ok",
        "skill": skill_name,
        "execution_path": exec_path,
        "inputs": inputs,
        "outputs": outputs,
        "requirements": requirements
    }


def _analyze_task(task_description: str, context: Dict) -> Dict:
    """Analyze task to determine requirements"""
    task_lower = task_description.lower()
    
    requirements = {
        "inputs": ["text"],
        "outputs": ["text"],
        "keywords": []
    }
    
    # Extract keywords for skill matching - order matters (later can override)
    keyword_map = {
        "echo": ["echo", "repeat", "back"],
        "write_file": ["save file", "create file", "write to file", "save to disk", "save file", "write file"],
        "summarize_text": ["summarize", "summary", "condense", "brief"],
        "generate_story": ["story", "creative writing", "narrative", "tale", "write story"],
        "analyze": ["analyze", "analysis", "examine", "review"]
    }
    
    for skill, kws in keyword_map.items():
        if any(kw in task_lower for kw in kws):
            requirements["keywords"].append(skill)
    
    # Story/creative should override generic "write"
    if "story" in task_lower or "creative" in task_lower or "narrative" in task_lower:
        requirements["keywords"] = [k for k in requirements["keywords"] if k != "write_file"]
        if "generate_story" not in requirements["keywords"]:
            requirements["keywords"].append("generate_story")
    
    # Save/file should prefer write_file
    if "file" in task_lower or "save" in task_lower or "disk" in task_lower:
        if "write_file" not in requirements["keywords"] and "generate_story" not in requirements["keywords"]:
            requirements["keywords"].append("write_file")
    
    # Analyze output requirements
    if any(w in task_lower for w in ["summarize", "summary", "extract"]):
        requirements["outputs"] = ["text"]
        if "summarize_text" not in requirements["keywords"]:
            requirements["keywords"].append("summarize_text")
        
    if any(w in task_lower for w in ["write", "create", "generate"]):
        requirements["outputs"] = ["artifact", "file"]
        
    if any(w in task_lower for w in ["analyze", "calculate", "compute"]):
        requirements["outputs"] = ["json", "text"]
        if "analyze" not in requirements["keywords"]:
            requirements["keywords"].append("analyze")
        
    if any(w in task_lower for w in ["story", "creative"]):
        requirements["inputs"].append("creative")
        if "generate_story" not in requirements["keywords"]:
            requirements["keywords"].append("generate_story")
        
    # Analyze complexity
    if any(w in task_lower for w in ["complex", "advanced", "detailed"]):
        requirements["complexity"] = "high"
    else:
        requirements["complexity"] = "low"
    
    return requirements


def initialize_default_capabilities():
    """Initialize default skill capabilities"""
    
    # Canonical skills (code-based)
    # Priority: 1 = highest, 10 = lowest
    try:
        from canonical_skills.echo import EchoSkill
        register_canonical_skill(
            skill_name="echo",
            skill_class=EchoSkill,
            input_types=["text"],
            output_types=["text", "artifact"],
            priority=5  # Medium priority
        )
    except Exception as e:
        logger.warning("failed_to_register_echo", error=str(e))
    
    try:
        from canonical_skills.write_file import WriteFileSkill
        register_canonical_skill(
            skill_name="write_file",
            skill_class=WriteFileSkill,
            input_types=["text", "filename"],
            output_types=["artifact", "file"],
            priority=3  # High priority for file operations
        )
    except Exception as e:
        logger.warning("failed_to_register_write_file", error=str(e))
    
    # LLM skills - higher base priority but get selected via keywords
    # These handle complex NLP tasks
    register_llm_skill(
        skill_name="summarize_text",
        prompt_template="Summarize the following: {input}",
        input_types=["text"],
        output_types=["text"],
        priority=6  # Medium - selected when keyword matches
    )
    
    register_llm_skill(
        skill_name="generate_story",
        prompt_template="Write a creative story: {input}",
        input_types=["text", "creative"],
        output_types=["text"],
        priority=6  # Medium
    )
    
    register_llm_skill(
        skill_name="analyze",
        prompt_template="Analyze the following: {input}",
        input_types=["text", "json"],
        output_types=["text", "json"],
        priority=6  # Medium
    )
    
    register_llm_skill(
        skill_name="generate_story",
        prompt_template="Write a creative story: {input}",
        input_types=["text", "creative"],
        output_types=["text"],
        priority=9
    )
    
    register_llm_skill(
        skill_name="analyze",
        prompt_template="Analyze the following: {input}",
        input_types=["text", "json"],
        output_types=["text", "json"],
        priority=7
    )
    
    logger.info("default_capabilities_initialized", 
                count=len(capability_router.capabilities))


# Initialize on import
initialize_default_capabilities()
