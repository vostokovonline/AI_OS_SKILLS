"""
Dev Task Types - Типы задач разработки

Разделение по CLI:
- QwenCode CLI: analysis, architecture, reasoning
- OpenCode CLI: patch generation, refactor, editing
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class DevTaskType(Enum):
    """Типы задач разработки"""
    
    # Analysis tasks - QwenCode CLI
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    DEAD_CODE_DETECTION = "dead_code_detection"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    CODE_UNDERSTANDING = "code_understanding"
    PLANNING = "planning"
    
    # Implementation tasks - OpenCode CLI
    PATCH_GENERATION = "patch_generation"
    REFACTOR = "refactor"
    CODE_EDIT = "code_edit"
    BUG_FIX = "bug_fix"
    TEST_GENERATION = "test_generation"
    SKILL_GENERATION = "skill_generation"
    
    # Composite tasks - 2-stage
    FULL_REFACTOR = "full_refactor"  # QwenCode → OpenCode
    MODULE_SPLIT = "module_split"   # QwenCode → OpenCode


class TaskComplexity(Enum):
    """Сложность задачи"""
    SIMPLE = 1      # One file, clear goal
    MEDIUM = 2      # Few files, standard task
    COMPLEX = 3     # Multiple files, architecture change
    CRITICAL = 4    # Core system changes


@dataclass
class DevTask:
    """Задача разработки"""
    task_type: DevTaskType
    target: str  # file, module, function
    description: str
    requirements: List[str]
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    max_files: int = 5  # Max files in patch
    
    @property
    def needs_analysis(self) -> bool:
        """Нужен ли анализ перед реализацией"""
        return self.task_type in [
            DevTaskType.FULL_REFACTOR,
            DevTaskType.MODULE_SPLIT,
            DevTaskType.REFACTOR,
            DevTaskType.COMPLEX,
        ]
    
    @property
    def is_safe(self) -> bool:
        """Безопасная ли задача"""
        return self.task_type in [
            DevTaskType.CODE_UNDERSTANDING,
            DevTaskType.PLANNING,
            DevTaskType.DEAD_CODE_DETECTION,
        ]


# Routing rules
CLI_ROUTES = {
    # QwenCode CLI - analysis and planning
    DevTaskType.ARCHITECTURE_ANALYSIS: "qwencode",
    DevTaskType.DEAD_CODE_DETECTION: "qwencode",
    DevTaskType.DEPENDENCY_ANALYSIS: "qwencode",
    DevTaskType.CODE_UNDERSTANDING: "qwencode",
    DevTaskType.PLANNING: "qwencode",
    
    # OpenCode CLI - implementation
    DevTaskType.PATCH_GENERATION: "opencode",
    DevTaskType.REFACTOR: "opencode",
    DevTaskType.CODE_EDIT: "opencode",
    DevTaskType.BUG_FIX: "opencode",
    DevTaskType.TEST_GENERATION: "opencode",
    DevTaskType.SKILL_GENERATION: "opencode",
    
    # Composite - 2 stage
    DevTaskType.FULL_REFACTOR: "both",  # qwencode → opencode
    DevTaskType.MODULE_SPLIT: "both",
}


def route_task(task: DevTask) -> str:
    """Определить CLI для задачи"""
    return CLI_ROUTES.get(task.task_type, "opencode")


def is_2_stage_task(task: DevTask) -> bool:
    """Нужна ли 2-стадийная обработка"""
    return CLI_ROUTES.get(task.task_type) == "both"


# Quick constructors
def analyze_dead_code(target: str) -> DevTask:
    """Создать задачу анализа dead code"""
    return DevTask(
        task_type=DevTaskType.DEAD_CODE_DETECTION,
        target=target,
        description=f"Find dead code in {target}",
        requirements=["List unreachable functions", "Identify unused imports"],
        complexity=TaskComplexity.MEDIUM
    )


def full_refactor(target: str, requirements: List[str]) -> DevTask:
    """Создать задачу полного рефакторинга"""
    return DevTask(
        task_type=DevTaskType.FULL_REFACTOR,
        target=target,
        description=f"Refactor {target}",
        requirements=requirements,
        complexity=TaskComplexity.COMPLEX,
        max_files=10
    )


def generate_patch(target: str, requirements: List[str]) -> DevTask:
    """Создать задачу генерации патча"""
    return DevTask(
        task_type=DevTaskType.PATCH_GENERATION,
        target=target,
        description=f"Generate patch for {target}",
        requirements=requirements,
        complexity=TaskComplexity.MEDIUM
    )
