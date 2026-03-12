"""
Dev Orchestrator - Управление разработкой через CLI

Роли:
- Qwen CLI: architecture, analysis, review
- OpenCode CLI: implementation, boilerplate, experiments

Pipeline:
1. development_goal
2. context_builder (using code_graph)
3. task_router (select CLI)
4. cli_runner
5. patch_manager
6. review (manual or auto)
"""
import os
import subprocess
import json
import tempfile
import hashlib
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CLIModel(Enum):
    """Доступные CLI модели"""
    QWEN = "qwen"
    OPENCODE = "opencode"
    CLAUDE = "claude"


@dataclass
class DevelopmentGoal:
    """Цель разработки"""
    goal_type: str  # refactor, implement, analyze, review
    target: str  # module, class, function name
    description: str
    requirements: List[str]
    priority: int = 1


@dataclass
class CodePatch:
    """Патч кода"""
    model: CLIModel
    file_path: str
    diff: str
    original_content: str
    new_content: str
    confidence: float = 0.5


@dataclass
class DevelopmentResult:
    """Результат разработки"""
    success: bool
    patches: List[CodePatch]
    review_result: Optional[str] = None
    applied: bool = False
    error: Optional[str] = None


class TaskRouter:
    """Роутинг задач на модели"""
    
    ROUTES = {
        # Qwen - для анализа и архитектуры
        "analyze": CLIModel.QWEN,
        "architecture": CLIModel.QWEN,
        "review": CLIModel.QWEN,
        "refactor": CLIModel.QWEN,
        "design": CLIModel.QWEN,
        "planning": CLIModel.QWEN,
        
        # OpenCode - для реализации
        "implement": CLIModel.OPENCODE,
        "create": CLIModel.OPENCODE,
        "generate": CLIModel.OPENCODE,
        "boilerplate": CLIModel.OPENCODE,
        "experiment": CLIModel.OPENCODE,
        "fix": CLIModel.OPENCODE,
        "debug": CLIModel.OPENCODE,
    }
    
    @classmethod
    def route(cls, goal: DevelopmentGoal) -> CLIModel:
        """Определить модель для задачи"""
        # Match by goal_type
        if goal.goal_type in cls.ROUTES:
            return cls.ROUTES[goal.goal_type]
        
        # Match by keywords in description
        desc_lower = goal.description.lower()
        for keyword, model in cls.ROUTES.items():
            if keyword in desc_lower:
                return model
        
        # Default to OpenCode for implementation tasks
        return CLIModel.OPENCODE


class ContextBuilder:
    """Построение контекста для LLM - использует ContextSelector"""
    
    def __init__(self, code_graph=None, root_path: str = None):
        self.code_graph = code_graph
        self.root_path = root_path
        self._selector = None
        
    def _get_selector(self):
        """Lazy load context selector"""
        if self._selector is None:
            try:
                from dev.context_selector import ContextSelector
                self._selector = ContextSelector(self.code_graph, self.root_path)
            except ImportError:
                self._selector = None
        return self._selector
        
    def build(self, goal: DevelopmentGoal) -> str:
        """Построить контекст для задачи"""
        context_parts = []
        
        # Add goal description
        context_parts.append(f"# Development Goal\n{goal.description}")
        
        # Try using ContextSelector for smart context building
        selector = self._get_selector()
        if selector and goal.target:
            try:
                pack = selector.select(
                    target=goal.target,
                    task_type=goal.goal_type,
                    model="qwen"
                )
                # Use smart context
                return selector.export_for_llm(pack)
            except Exception as e:
                # Fallback to simple context
                pass
        
        # Fallback: simple context building
        context_parts.append(f"# Target: {goal.target}")
            
            if related_nodes:
                context_parts.append(f"\n# Related Code\n")
                for node in related_nodes:
                    context_parts.append(f"## {node.name} ({node.type})")
                    if node.docstring:
                        context_parts.append(f"```\n{node.docstring}\n```")
        
        # Add requirements
        if goal.requirements:
            context_parts.append(f"\n# Requirements\n")
            for req in goal.requirements:
                context_parts.append(f"- {req}")
        
        return "\n\n".join(context_parts)


class CLIRunner:
    """Запуск CLI команд"""
    
    def __init__(self):
        self.available_models = self._check_available()
        
    def _check_available(self) -> Dict[CLIModel, bool]:
        """Проверить доступность CLI"""
        models = {
            CLIModel.QWEN: self._check_cli("qwen-code"),
            CLIModel.OPENCODE: self._check_cli("opencode"),
            CLIModel.CLAUDE: self._check_cli("claude"),
        }
        return models
    
    def _check_cli(self, cmd: str) -> bool:
        """Проверить доступность команды"""
        try:
            result = subprocess.run(
                ["which", cmd],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def run(self, model: CLIModel, prompt: str, context: str = "") -> str:
        """Запустить CLI с промптом"""
        if not self.available_models.get(model, False):
            return f"Error: {model.value} CLI not available"
        
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        try:
            # Different CLI interfaces
            if model == CLIModel.OPENCODE:
                result = subprocess.run(
                    ["opencode", full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            elif model == CLIModel.QWEN:
                # Qwen可能有不同的接口
                result = subprocess.run(
                    ["qwen-code", "-p", full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            elif model == CLIModel.CLAUDE:
                result = subprocess.run(
                    ["claude", "-p", full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                return f"Unknown model: {model}"
            
            return result.stdout if result.returncode == 0 else result.stderr
            
        except subprocess.TimeoutExpired:
            return "Error: CLI timeout"
        except Exception as e:
            return f"Error: {str(e)}"


class PatchManager:
    """Управление патчами"""
    
    @staticmethod
    def parse_patch(output: str) -> List[CodePatch]:
        """Парсить patch из вывода CLI"""
        patches = []
        
        # Simple diff parsing - look for file paths and diffs
        lines = output.split('\n')
        current_file = None
        current_diff = []
        
        for line in lines:
            # Detect file in diff
            if line.startswith('--- ') or line.startswith('+++ '):
                if current_file and current_diff:
                    patches.append(CodePatch(
                        model=CLIModel.OPENCODE,  # Will be set by caller
                        file_path=current_file,
                        diff='\n'.join(current_diff),
                        original_content="",
                        new_content=""
                    ))
                current_file = line.replace('--- ', '').replace('+++ ', '').strip()
                current_diff = [line]
            elif current_file:
                current_diff.append(line)
        
        # Add last patch
        if current_file and current_diff:
            patches.append(CodePatch(
                model=CLIModel.OPENCODE,
                file_path=current_file,
                diff='\n'.join(current_diff),
                original_content="",
                new_content=""
            ))
        
        return patches
    
    @staticmethod
    def apply_patch(patch: CodePatch, dry_run: bool = True) -> bool:
        """Применить патч"""
        if dry_run:
            print(f"[DRY RUN] Would apply patch to {patch.file_path}")
            print(patch.diff)
            return True
        
        try:
            # Write to temp file and apply
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(patch.diff)
                patch_file = f.name
            
            result = subprocess.run(
                ["patch", "-p1", "-i", patch_file],
                capture_output=True,
                text=True
            )
            
            os.unlink(patch_file)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Failed to apply patch: {e}")
            return False
    
    @staticmethod
    def resolve(patches: List[CodePatch], strategy: str = "longest") -> CodePatch:
        """Выбрать лучший патч из нескольких"""
        if not patches:
            raise ValueError("No patches to resolve")
        
        if len(patches) == 1:
            return patches[0]
        
        if strategy == "longest":
            return max(patches, key=lambda p: len(p.diff))
        elif strategy == "first":
            return patches[0]
        else:
            return patches[0]


class DevOrchestrator:
    """
    Главный оркестратор разработки.
    
    Pipeline:
    1. Receive development goal
    2. Build context using code graph
    3. Route to appropriate CLI
    4. Generate patch
    5. (Optional) Review
    6. Apply or show for manual approval
    """
    
    def __init__(self, code_graph=None, root_path: str = None):
        self.router = TaskRouter()
        self.context_builder = ContextBuilder(code_graph, root_path)
        self.cli_runner = CLIRunner()
        self.patch_manager = PatchManager()
        
    def execute(
        self, 
        goal: DevelopmentGoal,
        auto_apply: bool = False,
        review_callback: Optional[Callable[[CodePatch], str]] = None
    ) -> DevelopmentResult:
        """
        Выполнить задачу разработки.
        
        Args:
            goal: Цель разработки
            auto_apply: Автоматически применять патчи
            review_callback: Функция для review патча
            
        Returns:
            DevelopmentResult с патчами
        """
        try:
            # Step 1: Route to model
            model = self.router.route(goal)
            
            # Step 2: Build context
            context = self.context_builder.build(goal)
            
            # Step 3: Generate prompt
            prompt = self._build_prompt(goal)
            
            # Step 4: Run CLI
            output = self.cli_runner.run(model, prompt, context)
            
            # Step 5: Parse patches
            patches = self.patch_manager.parse_patch(output)
            
            if not patches:
                return DevelopmentResult(
                    success=False,
                    patches=[],
                    error="No patches generated"
                )
            
            # Step 6: Review
            selected_patch = self.patch_manager.resolve(patches)
            selected_patch.model = model
            
            review_result = None
            if review_callback:
                review_result = review_callback(selected_patch)
            
            # Step 7: Apply or show
            applied = False
            if auto_apply and (not review_result or review_result == "approve"):
                applied = self.patch_manager.apply_patch(selected_patch, dry_run=False)
            
            return DevelopmentResult(
                success=True,
                patches=patches,
                review_result=review_result,
                applied=applied
            )
            
        except Exception as e:
            return DevelopmentResult(
                success=False,
                patches=[],
                error=str(e)
            )
    
    def _build_prompt(self, goal: DevelopmentGoal) -> str:
        """Построить промпт для CLI"""
        prompts = {
            "refactor": f"""Refactor the code at {goal.target}.

Requirements:
{chr(10).join(f"- {r}" for r in goal.requirements)}

Output:
- Show the diff
- Explain what changed and why""",
            
            "implement": f"""Implement new functionality at {goal.target}.

Requirements:
{chr(10).join(f"- {r}" for r in goal.requirements)}

Output:
- Show the implementation
- Include necessary imports""",
            
            "analyze": f"""Analyze the code at {goal.target}.

Requirements:
{chr(10).join(f"- {r}" for r in goal.requirements)}

Output:
- Current structure
- Issues found
- Recommendations""",
            
            "review": f"""Review the code at {goal.target}.

Requirements:
{chr(10).join(f"- {r}" for r in goal.requirements)}

Output:
- Code quality assessment
- Potential issues
- Suggestions for improvement"""
        }
        
        base_prompt = prompts.get(goal.goal_type, goal.description)
        return base_prompt


# Example usage
if __name__ == "__main__":
    # Initialize
    orchestrator = DevOrchestrator()
    
    # Create goal
    goal = DevelopmentGoal(
        goal_type="analyze",
        target="trace_mining_engine",
        description="Analyze trace_mining_engine for improvements",
        requirements=["Find performance bottlenecks", "Suggest optimizations"]
    )
    
    # Execute
    result = orchestrator.execute(goal, auto_apply=False)
    
    print(f"Success: {result.success}")
    print(f"Patches: {len(result.patches)}")
    print(f"Applied: {result.applied}")
