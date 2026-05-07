"""
Skill Router for AI-OS Control Plane
Dynamic routing с интеграцией в Control Plane
"""

import json
import os
from typing import Callable, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class Skill:
    name: str
    description: str
    goal_type: str
    model_preferences: List[str]
    max_tokens: int = 512
    timeout_sec: int = 10
    routing_mode: str = "dynamic"
    static_model: Optional[str] = None
    pre_checks: List[Callable] = field(default_factory=list)
    post_checks: List[Callable] = field(default_factory=list)
    enabled: bool = True

    def validate_input(self, input_data) -> bool:
        for check in self.pre_checks:
            if not check(input_data):
                raise ValueError(f"Pre-check failed for skill '{self.name}'")
        return True

    def validate_output(self, output_data) -> bool:
        for check in self.post_checks:
            if not check(output_data):
                raise ValueError(f"Post-check failed for skill '{self.name}'")
        return True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "goal_type": self.goal_type,
            "model_preferences": self.model_preferences,
            "max_tokens": self.max_tokens,
            "timeout_sec": self.timeout_sec,
            "routing_mode": self.routing_mode,
            "static_model": self.static_model,
            "enabled": self.enabled,
            "pre_checks_count": len(self.pre_checks),
            "post_checks_count": len(self.post_checks)
        }


SKILL_REGISTRY: dict[str, Skill] = {}
SKILL_API_BASE = os.getenv("CONTROL_PLANE_URL", "http://ns_core:8000")


def register_skill(skill: Skill) -> None:
    if skill.name in SKILL_REGISTRY:
        print(f"[*] Skill '{skill.name}' already registered, skipping")
        return
    SKILL_REGISTRY[skill.name] = skill
    print(f"[+] Registered skill: {skill.name} (routing={skill.routing_mode})")


def get_skill(name: str) -> Optional[Skill]:
    return SKILL_REGISTRY.get(name)


def list_skills() -> List[str]:
    return list(SKILL_REGISTRY.keys())


def get_recommended_model(goal_type: str) -> Optional[str]:
    if not HTTPX_AVAILABLE:
        print("[!] httpx not available, using default model")
        return "local-coder"

def get_recommended_model(goal_type: str) -> Optional[str]:
    if not HTTPX_AVAILABLE:
        print("[!] httpx not available, using default model")
        return "local-coder"

    # Goal type to model mapping (direct LiteLLM model names)
    GOAL_TYPE_MODEL = {
        "precise_reasoning": "local-coder",
        "creative_writing": "deepseek-reasoner",
        "cheap_generation": "local-coder",
        "long_context": "deepseek-reasoner",
    }
    
    # Return direct LiteLLM model based on goal type
    model = GOAL_TYPE_MODEL.get(goal_type, "local-coder")
    print(f"[!] Using direct model for {goal_type}: {model}")
    return model


def log_decision_trace(skill: Skill, model: str, goal_type: str) -> None:
    if not HTTPX_AVAILABLE:
        return

    try:
        url = f"{SKILL_API_BASE}/llm/control/decision/trace"
        data = {
            "skill_name": skill.name,
            "goal_type": goal_type,
            "selected_model": model,
            "routing_mode": skill.routing_mode,
            "timestamp": datetime.utcnow().isoformat()
        }
        httpx.post(url, json=data, timeout=5.0)
    except Exception as e:
        print(f"[!] Failed to log decision trace: {e}")


def create_skill(
    name: str,
    description: str,
    goal_type: str,
    preferred_models: List[str],
    max_tokens: int = 512,
    timeout_sec: int = 10,
    routing_mode: str = "dynamic",
    static_model: Optional[str] = None,
    pre_checks: List[Callable] = None,
    post_checks: List[Callable] = None,
    auto_register: bool = True
) -> Skill:
    if routing_mode == "static" and not static_model:
        raise ValueError("static_model required when routing_mode='static'")

    def default_non_empty(data):
        return bool(data and str(data).strip())

    skill = Skill(
        name=name,
        description=description,
        goal_type=goal_type,
        model_preferences=preferred_models,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        routing_mode=routing_mode,
        static_model=static_model,
        pre_checks=pre_checks or [default_non_empty],
        post_checks=post_checks or [default_non_empty]
    )

    if auto_register:
        register_skill(skill)

    return skill


def create_skill_interactive() -> Skill:
    print("\n" + "="*50)
    print("=== AI-OS Skill Router Generator ===")
    print("="*50)
    
    name = input("Skill name: ").strip()
    description = input("Description: ").strip()
    goal_type = input("Goal type (precise_reasoning, creative_writing, cheap_generation, long_context): ").strip()
    
    models_input = input("Preferred models (comma separated, empty for dynamic): ").strip()
    if models_input:
        preferred_models = [m.strip() for m in models_input.split(",")]
    else:
        preferred_models = []
    
    max_tokens = int(input("Max tokens (default 512): ") or 512)
    timeout_sec = int(input("Timeout seconds (default 10): ") or 10)
    
    routing_mode = input("Routing mode (dynamic/static, default dynamic): ").strip() or "dynamic"
    static_model = None
    if routing_mode == "static":
        static_model = input("Static model name: ").strip()

    skill = create_skill(
        name=name,
        description=description,
        goal_type=goal_type,
        preferred_models=preferred_models,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        routing_mode=routing_mode,
        static_model=static_model
    )

    return skill


def export_skills_to_json(path: str = "skills_registry.json") -> None:
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "skills_count": len(SKILL_REGISTRY),
        "skills": {name: skill.to_dict() for name, skill in SKILL_REGISTRY.items()}
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[+] Skills exported to {path}")


def load_skills_from_json(path: str) -> int:
    with open(path, "r") as f:
        data = json.load(f)

    count = 0
    for name, spec in data.get("skills", {}).items():
        create_skill(
            name=name,
            description=spec.get("description", ""),
            goal_type=spec.get("goal_type", "precise_reasoning"),
            preferred_models=spec.get("model_preferences", []),
            max_tokens=spec.get("max_tokens", 512),
            timeout_sec=spec.get("timeout_sec", 10),
            routing_mode=spec.get("routing_mode", "dynamic"),
            static_model=spec.get("static_model"),
            auto_register=True
        )
        count += 1

    print(f"[+] Loaded {count} skills from {path}")
    return count


def run_cli():
    print("\n=== AI-OS Skill Router CLI ===")
    print("Commands: new, list, info <name>, export, import <path>, quit")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "new":
                create_skill_interactive()
                
            elif cmd == "list":
                if not SKILL_REGISTRY:
                    print("No skills registered")
                else:
                    for name, skill in SKILL_REGISTRY.items():
                        print(f"  {name}: {skill.goal_type} ({skill.routing_mode})")
                        
            elif cmd.startswith("info "):
                name = cmd[5:].strip()
                skill = get_skill(name)
                if skill:
                    print(json.dumps(skill.to_dict(), indent=2))
                else:
                    print(f"Skill '{name}' not found")
                    
            elif cmd == "export":
                export_skills_to_json()
                
            elif cmd.startswith("import "):
                path = cmd[7:].strip()
                load_skills_from_json(path)
                
            elif cmd in ("quit", "exit", "q"):
                print("Bye!")
                break
                
            else:
                print("Unknown command. Available: new, list, info, export, import, quit")
                
        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    run_cli()


# =============================================================================
# Auto-loaded Sample Skills
# =============================================================================

def _load_sample_skills():
    """Load sample skills at module import time"""
    create_skill(
        name="summarize_text",
        description="Creates a summary of the input text",
        goal_type="precise_reasoning",
        preferred_models=["local-coder", "deepseek-reasoner"],
        max_tokens=300,
        timeout_sec=15,
        routing_mode="dynamic",
        auto_register=True
    )
    
    create_skill(
        name="echo_text",
        description="Returns the text as-is",
        goal_type="cheap_generation",
        preferred_models=["local-coder"],
        max_tokens=100,
        timeout_sec=5,
        routing_mode="static",
        static_model="local-coder",
        auto_register=True
    )
    
    create_skill(
        name="generate_story",
        description="Generates a creative story",
        goal_type="creative_writing",
        preferred_models=["deepseek-reasoner", "local-coder"],
        max_tokens=2000,
        timeout_sec=30,
        routing_mode="dynamic",
        auto_register=True
    )
    
    create_skill(
        name="write_code",
        description="Writes code based on requirements",
        goal_type="precise_reasoning",
        preferred_models=["local-coder", "deepseek-reasoner"],
        max_tokens=4000,
        timeout_sec=20,
        routing_mode="dynamic",
        auto_register=True
    )


# Load sample skills on module import
_load_sample_skills()
