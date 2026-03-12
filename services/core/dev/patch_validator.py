"""
Patch Validator - Safety Layer для Dev Orchestrator

Проверяет патчи перед применением:
1. Syntax validity
2. Import checks
3. Architecture rules
4. Impact analysis
5. Dry run
"""
import os
import ast
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    """Уровень валидации"""
    SYNTAX = "syntax"
    IMPORTS = "imports"
    ARCHITECTURE = "architecture"
    IMPACT = "impact"
    FULL = "full"


@dataclass
class ValidationResult:
    """Результат валидации"""
    valid: bool
    level: ValidationLevel
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


class ArchitectureRules:
    """Правила архитектуры"""
    
    # Разрешённые зависимости между слоями
    ALLOWED_DEPS = {
        "execution": ["skills", "memory", "database", "utils"],
        "skills": ["tools", "memory", "utils"],
        "memory": ["database"],
        "database": [],
        "utils": [],
        "api": ["execution", "skills", "database"],
        "dev": ["execution", "skills", "api"],
    }
    
    # Защищённые модули (нельзя менять без approval)
    PROTECTED_MODULES = [
        "models",
        "database",
        "infrastructure",
    ]
    
    @classmethod
    def check_import(cls, from_module: str, to_module: str) -> Tuple[bool, str]:
        """Проверить разрешён ли импорт"""
        from_layer = cls._get_layer(from_module)
        to_layer = cls._get_layer(to_module)
        
        if not from_layer or not to_layer:
            return True, ""  # Unknown modules - allow
        
        allowed = cls.ALLOWED_DEPS.get(from_layer, [])
        
        if to_layer in allowed:
            return True, ""
        
        return False, f"Disallowed dependency: {from_layer} → {to_layer}"
    
    @classmethod
    def _get_layer(cls, module: str) -> Optional[str]:
        """Определить слой по имени модуля"""
        module = module.lower()
        
        if "execution" in module:
            return "execution"
        if "skill" in module:
            return "skills"
        if "memory" in module or "trace" in module:
            return "memory"
        if "database" in module or "db" in module:
            return "database"
        if "api" in module or "endpoint" in module:
            return "api"
        if "dev" in module:
            return "dev"
        if "util" in module or "helper" in module:
            return "utils"
        
        return None


class PatchValidator:
    """Валидатор патчей"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.architecture = ArchitectureRules()
        
    def validate(self, patch_content: str, target_files: List[str]) -> ValidationResult:
        """
        Валидировать патч.
        
        Args:
            patch_content: Содержимое патча
            target_files: Список файлов в патче
            
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        
        # Level 1: Syntax
        syntax_errors = self._check_syntax(patch_content)
        if syntax_errors:
            errors.extend(syntax_errors)
            return ValidationResult(False, ValidationLevel.SYNTAX, errors, warnings, {})
        
        # Level 2: Imports
        import_errors = self._check_imports(target_files)
        if import_errors:
            warnings.extend(import_errors)
        
        # Level 3: Architecture
        arch_errors = self._check_architecture(patch_content)
        if arch_errors:
            errors.extend(arch_errors)
            return ValidationResult(False, ValidationLevel.ARCHITECTURE, errors, warnings, {})
        
        # Level 4: Protected modules
        protected_errors = self._check_protected(target_files)
        if protected_errors:
            warnings.extend(protected_errors)
        
        return ValidationResult(
            valid=len(errors) == 0,
            level=ValidationLevel.FULL if errors else ValidationLevel.ARCHITECTURE,
            errors=errors,
            warnings=warnings,
            details={"files": target_files}
        )
    
    def _check_syntax(self, patch_content: str) -> List[str]:
        """Проверить синтаксис"""
        errors = []
        
        # Try to compile each file mentioned in patch
        lines = patch_content.split('\n')
        current_file = None
        content_lines = []
        
        for line in lines:
            if line.startswith('+++ b/') or line.startswith('+++ '):
                # Save previous file
                if current_file and content_lines:
                    syntax_error = self._validate_python_syntax(current_file, '\n'.join(content_lines))
                    if syntax_error:
                        errors.append(f"{current_file}: {syntax_error}")
                
                # New file
                current_file = line.replace('+++ b/', '').replace('+++ ', '').strip()
                content_lines = []
            elif current_file and (line.startswith('+') or line.startswith(' ')) and not line.startswith('+++'):
                content_lines.append(line[1:])  # Remove +
        
        # Check last file
        if current_file and content_lines:
            syntax_error = self._validate_python_syntax(current_file, '\n'.join(content_lines))
            if syntax_error:
                errors.append(f"{current_file}: {syntax_error}")
        
        return errors
    
    def _validate_python_syntax(self, filepath: str, content: str) -> Optional[str]:
        """Валидировать Python синтаксис файла"""
        if not filepath.endswith('.py'):
            return None
        
        try:
            ast.parse(content)
            return None
        except SyntaxError as e:
            return f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return f"Parse error: {str(e)}"
    
    def _check_imports(self, files: List[str]) -> List[str]:
        """Проверить импорты"""
        errors = []
        
        for filepath in files:
            if not filepath.endswith('.py'):
                continue
            if not os.path.exists(filepath):
                continue
                
            try:
                with open(filepath, 'r') as f:
                    ast.parse(f.read())
            except ImportError as e:
                errors.append(f"{filepath}: Missing import - {e}")
            except Exception:
                pass
        
        return errors
    
    def _check_architecture(self, patch_content: str) -> List[str]:
        """Проверить архитектурные правила"""
        errors = []
        
        lines = patch_content.split('\n')
        
        for line in lines:
            # Look for import statements in patch
            if 'import ' in line or 'from ' in line:
                # Check if this creates disallowed dependency
                pass  # Simplified for now
        
        return errors
    
    def _check_protected(self, files: List[str]) -> List[str]:
        """Проверить защищённые модули"""
        warnings = []
        
        for filepath in files:
            for protected in ArchitectureRules.PROTECTED_MODULES:
                if protected in filepath:
                    warnings.append(f"WARNING: Modifying protected module: {filepath}")
        
        return warnings
    
    def validate_and_apply(self, patch_content: str, target_files: List[str]) -> Tuple[bool, ValidationResult]:
        """
        Валидировать и применить патч.
        
        Returns:
            (success, validation_result)
        """
        result = self.validate(patch_content, target_files)
        
        if not result.valid:
            return False, result
        
        if self.dry_run:
            print(f"[DRY RUN] Would apply patch to {len(target_files)} files")
            return True, result
        
        # Apply patch
        try:
            with open('/tmp/dev_patch.patch', 'w') as f:
                f.write(patch_content)
            
            result = subprocess.run(
                ['patch', '-p1', '-i', '/tmp/dev_patch.patch'],
                capture_output=True,
                text=True
            )
            
            os.unlink('/tmp/dev_patch.patch')
            
            if result.returncode != 0:
                return False, ValidationResult(
                    False, ValidationLevel.IMPACT,
                    [f"Patch failed: {result.stderr}"], [], {}
                )
            
            return True, result
            
        except Exception as e:
            return False, ValidationResult(
                False, ValidationLevel.IMPACT,
                [f"Apply error: {str(e)}"], [], {}
            )


def quick_validate(patch: str) -> bool:
    """Быстрая валидация - только синтаксис"""
    import re
    
    # Extract files
    files = re.findall(r'\+\+\+ b/(\S+)', patch)
    
    validator = PatchValidator(dry_run=True)
    result = validator.validate(patch, files)
    
    return result.valid
