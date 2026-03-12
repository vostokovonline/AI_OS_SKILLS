"""
Context Selector - Умный выбор контекста для LLM

Принцип работы:
1. Получить задачу (target)
2. Найти связанные модули через code_graph
3. Выбрать релевантные файлы
4. Собрать контекст (interfaces, deps, tests)
5. Сформировать context pack для LLM
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dev.code_graph import CodeGraph, load_or_build_graph


@dataclass
class ContextPack:
    """Контекст-пак для LLM"""
    target: str
    files: List[Dict[str, Any]]  # path, content, relevance
    imports: List[str]  # Что нужно импортировать
    interfaces: List[Dict]  # Сигнатуры функций/классов
    total_tokens: int
    summary: str


class ContextSelector:
    """
    Выбирает релевантный контекст для LLM.
    
    Алгоритм:
    1. Query code_graph для связанных узлов
    2. Expand до файлов
    3. Extract interfaces
    4. Limit по tokens
    """
    
    # Max tokens для разных моделей
    TOKEN_LIMITS = {
        "qwen": 32000,
        "opencode": 4000,
        "claude": 100000,
        "gpt4": 8000,
    }
    
    def __init__(self, code_graph: CodeGraph = None, root_path: str = None):
        self.graph = code_graph
        self.root_path = root_path
        
    def select(
        self,
        target: str,
        task_type: str = "implement",
        model: str = "qwen",
        max_tokens: int = None
    ) -> ContextPack:
        """
        Выбрать контекст для задачи.
        
        Args:
            target: Цель (файл, класс, функция)
            task_type: Тип задачи (implement, analyze, refactor, review)
            model: Модель LLM
            max_tokens: Лимит токенов (опционально)
            
        Returns:
            ContextPack с подобранным контекстом
        """
        if max_tokens is None:
            max_tokens = self.TOKEN_LIMITS.get(model, 8000)
        
        # Step 1: Найти связанные узлы
        related_nodes = self._find_related_nodes(target)
        
        # Step 2: Определить файлы для включения
        files_to_include = self._select_files(related_nodes, task_type)
        
        # Step 3: Прочитать содержимое
        file_contents = self._read_files(files_to_include, max_tokens)
        
        # Step 4: Extract interfaces
        interfaces = self._extract_interfaces(related_nodes)
        
        # Step 5: Найти imports
        imports = self._find_required_imports(related_nodes)
        
        # Step 6: Build summary
        summary = self._build_summary(target, task_type, related_nodes)
        
        total_tokens = sum(len(content) // 4 for _, content in file_contents)
        
        return ContextPack(
            target=target,
            files=file_contents,
            imports=imports,
            interfaces=interfaces,
            total_tokens=total_tokens,
            summary=summary
        )
    
    def _find_related_nodes(self, target: str) -> List[Any]:
        """Найти связанные узлы через code_graph"""
        if not self.graph:
            return []
        
        # Direct lookup
        if target in self.graph.nodes:
            nodes = [self.graph.nodes[target]]
        else:
            nodes = self.graph.find_related(target, limit=20)
        
        # Expand: добавить зависимости
        expanded = set()
        expanded.update(n.node_id if hasattr(n, 'node_id') else n for n in nodes)
        
        for node in nodes:
            if hasattr(node, 'file_path'):
                # Add nodes from same file
                for n in self.graph.nodes.values():
                    if n.file_path == node.file_path:
                        expanded.add(n.node_id if hasattr(n, 'node_id') else n)
        
        # Convert back to nodes
        result = []
        for node_id in expanded:
            if isinstance(node_id, str) and node_id in self.graph.nodes:
                result.append(self.graph.nodes[node_id])
        
        return result
    
    def _select_files(self, nodes: List[Any], task_type: str) -> Set[str]:
        """Выбрать файлы для включения"""
        files = set()
        
        # Always include target file
        for node in nodes:
            if hasattr(node, 'file_path') and node.file_path:
                files.add(node.file_path)
        
        # Add related based on task type
        if task_type == "refactor":
            # Для рефакторинга - включить все зависимости
            for node in nodes:
                if hasattr(node, 'imports'):
                    for imp in node.imports[:5]:  # Top 5 imports
                        files.add(imp)
        
        elif task_type == "analyze":
            # Для анализа - включить тесты
            for f in list(files):
                files.add(f.replace('.py', '_test.py'))
        
        elif task_type == "implement":
            # Для реализации - включить интерфейсы
            pass  # Just target file
        
        return files
    
    def _read_files(self, files: Set[str], max_tokens: int) -> List[tuple]:
        """Прочитать файлы с ограничением по токенам"""
        result = []
        current_tokens = 0
        
        for file_path in sorted(files):
            if not os.path.exists(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                file_tokens = len(content) // 4
                
                if current_tokens + file_tokens > max_tokens:
                    # Truncate
                    available = max_tokens - current_tokens
                    if available < 100:
                        break
                    content = content[:available * 4]
                    current_tokens = max_tokens
                else:
                    current_tokens += file_tokens
                
                result.append((file_path, content))
                
                if current_tokens >= max_tokens:
                    break
                    
            except Exception:
                continue
        
        return result
    
    def _extract_interfaces(self, nodes: List[Any]) -> List[Dict]:
        """Извлечь сигнатуры функций/классов"""
        interfaces = []
        
        for node in nodes:
            if not hasattr(node, 'type'):
                continue
                
            if node.type == "function":
                interfaces.append({
                    "type": "function",
                    "name": node.name,
                    "params": getattr(node, 'params', []),
                    "returns": getattr(node, 'returns', ''),
                    "doc": node.docstring[:100] if node.docstring else ''
                })
                
            elif node.type == "class":
                methods = []
                # Find methods (simplified)
                interfaces.append({
                    "type": "class",
                    "name": node.name,
                    "doc": node.docstring[:100] if node.docstring else ''
                })
        
        return interfaces[:20]  # Limit
    
    def _find_required_imports(self, nodes: List[Any]) -> List[str]:
        """Найти необходимые импорты"""
        imports = set()
        
        for node in nodes:
            if hasattr(node, 'imports'):
                for imp in node.imports[:5]:
                    imports.add(imp)
        
        return sorted(list(imports))[:10]
    
    def _build_summary(self, target: str, task_type: str, nodes: List[Any]) -> str:
        """Построить summary"""
        parts = [f"Task: {task_type}", f"Target: {target}"]
        
        # Count types
        classes = sum(1 for n in nodes if hasattr(n, 'type') and n.type == "class")
        functions = sum(1 for n in nodes if hasattr(n, 'type') and n.type in ["function", "method"])
        
        parts.append(f"Related: {classes} classes, {functions} functions")
        
        return " | ".join(parts)
    
    def export_for_llm(self, pack: ContextPack) -> str:
        """Экспортировать pack в формат для LLM"""
        output = []
        
        # Header
        output.append(f"# Context for: {pack.target}")
        output.append(f"# {pack.summary}")
        output.append(f"# Tokens: {pack.total_tokens}")
        output.append("")
        
        # Required imports
        if pack.imports:
            output.append("# Required imports:")
            for imp in pack.imports:
                output.append(f"#   - {imp}")
            output.append("")
        
        # Interfaces
        if pack.interfaces:
            output.append("# Interfaces:")
            for iface in pack.interfaces[:10]:
                if iface['type'] == 'function':
                    params = ', '.join(iface.get('params', []))
                    output.append(f"# {iface['name']}({params})")
                else:
                    output.append(f"# class {iface['name']}")
            output.append("")
        
        # Files
        for path, content in pack.files:
            output.append(f"\n# ===== {path} =====")
            output.append(content)
        
        return "\n".join(output)


def main():
    """Пример использования"""
    import json
    
    # Build graph
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    graph = load_or_build_graph(root, "/tmp/codebase_map.json")
    
    # Create selector
    selector = ContextSelector(graph, root)
    
    # Select context
    target = sys.argv[2] if len(sys.argv) > 2 else "goal_executor_v2"
    
    print(f"Selecting context for: {target}")
    
    pack = selector.select(
        target=target,
        task_type="implement",
        model="qwen"
    )
    
    print(f"\nSummary: {pack.summary}")
    print(f"Files: {len(pack.files)}")
    print(f"Tokens: {pack.total_tokens}")
    print(f"\n--- Context Preview ---\n")
    
    # Export preview
    preview = selector.export_for_llm(pack)
    print(preview[:2000])
    print("\n... [truncated]")


if __name__ == "__main__":
    main()
