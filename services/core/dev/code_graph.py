"""
Code Graph - Анализ структуры кодовой базы для Dev Orchestrator

Используется для:
1. Context Building - выбор релевантных модулей для LLM
2. Dependency Analysis - понимание связей между модулями
3. Dead Code Detection - поиск неиспользуемого кода
4. Architecture Understanding - структура проекта
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import hashlib


@dataclass
class CodeNode:
    """Узел графа кода"""
    name: str
    type: str  # module, class, function, method
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)


@dataclass  
class CodeEdge:
    """Связь между узлами"""
    from_node: str
    to_node: str
    relation: str  # imports, calls, inherits, depends


class CodeGraph:
    """
    Граф структуры кодовой базы.
    
    Построение:
    1. Парсит Python файлы через AST
    2. Извлекает модули, классы, функции
    3. Строит связи между ними
    """
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.nodes: Dict[str, CodeNode] = {}
        self.edges: List[CodeEdge] = []
        self.modules: Dict[str, str] = {}  # module_name -> file_path
        self._index: Dict[str, List[str]] = defaultdict(list)  # word -> nodes
        
    def build(self, extensions: List[str] = [".py"]) -> Dict[str, Any]:
        """
        Построить граф из файлов проекта.
        
        Returns:
            stats: Количество узлов, связей, модулей
        """
        for ext in extensions:
            for file_path in self.root_path.rglob(f"*{ext}"):
                # Skip hidden, cache, test directories
                if any(x in str(file_path) for x in ['__pycache__', '.git', 'node_modules', 'venv', '.venv', 'test_', '_test.']):
                    continue
                self._process_file(file_path)
        
        self._build_index()
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "modules": len(self.modules),
            "classes": len([n for n in self.nodes.values() if n.type == "class"]),
            "functions": len([n for n in self.nodes.values() if n.type in ["function", "method"]])
        }
    
    def _process_file(self, file_path: Path) -> None:
        """Обработать один файл"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return
        
        module_name = self._get_module_name(file_path)
        self.modules[module_name] = str(file_path)
        
        # Process classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._add_class_node(node, module_name, file_path, content)
            elif isinstance(node, ast.FunctionDef):
                if not self._is_method(node):  # Skip methods (processed with class)
                    self._add_function_node(node, module_name, file_path, content)
        
        # Process imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._add_import(module_name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._add_import(module_name, node.module)
    
    def _get_module_name(self, file_path: Path) -> str:
        """Получить имя модуля из пути к файлу"""
        rel_path = file_path.relative_to(self.root_path)
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)
    
    def _is_method(self, node: ast.FunctionDef) -> bool:
        """Проверить является ли функция методом класса"""
        return isinstance(node.parent, ast.ClassDef)
    
    def _add_class_node(self, node: ast.ClassDef, module: str, file_path: Path, content: str) -> None:
        """Добавить узел класса"""
        node_id = f"{module}.{node.name}"
        
        docstring = ast.get_docstring(node) or ""
        
        # Get decorators
        decorators = [d.id if isinstance(d, ast.Name) else ast.unparse(d) for d in node.decorator_list]
        
        self.nodes[node_id] = CodeNode(
            name=node.name,
            type="class",
            file_path=str(file_path),
            line_start=node.lineno or 0,
            line_end=node.end_lineno or 0,
            docstring=docstring,
            decorators=decorators,
            imports=[]
        )
    
    def _add_function_node(self, node: ast.FunctionDef, module: str, file_path: Path, content: str) -> None:
        """Добавить узел функции"""
        node_id = f"{module}.{node.name}"
        
        docstring = ast.get_docstring(node) or ""
        
        decorators = [d.id if isinstance(d, ast.Name) else ast.unparse(d) for d in node.decorator_list]
        
        self.nodes[node_id] = CodeNode(
            name=node.name,
            type="function",
            file_path=str(file_path),
            line_start=node.lineno or 0,
            line_end=node.end_lineno or 0,
            docstring=docstring,
            decorators=decorators,
            imports=[]
        )
    
    def _add_import(self, from_module: str, import_name: str) -> None:
        """Добавить связь импорта"""
        # Find what module/class is being imported
        for node_id, node in self.nodes.items():
            if node_id.startswith(from_module):
                node.imports.append(import_name)
        
        # Add edge
        to_module = import_name.split('.')[0]
        self.edges.append(CodeEdge(
            from_node=from_module,
            to_node=to_module,
            relation="imports"
        ))
    
    def _build_index(self) -> None:
        """Построить индекс для быстрого поиска"""
        for node_id, node in self.nodes.items():
            # Index by name parts
            for part in node.name.lower().split('_'):
                self._index[part].append(node_id)
            
            # Index by docstring words
            for word in node.docstring.lower().split():
                if len(word) > 3:
                    self._index[word].append(node_id)
    
    def find_related(self, query: str, limit: int = 10) -> List[CodeNode]:
        """
        Найти связанные узлы по запросу.
        
        Args:
            query: Поисковый запрос (ключевое слово)
            limit: Максимум результатов
            
        Returns:
            Список найденных узлов
        """
        query_lower = query.lower()
        candidates = set()
        
        # Search in index
        for word in query_lower.split():
            if word in self._index:
                candidates.update(self._index[word])
        
        # Also search in node names
        for node_id, node in self.nodes.items():
            if query_lower in node.name.lower():
                candidates.add(node_id)
        
        # Return nodes
        result = []
        for node_id in list(candidates)[:limit]:
            if node_id in self.nodes:
                result.append(self.nodes[node_id])
        
        return result
    
    def find_dependencies(self, module_name: str) -> Dict[str, List[str]]:
        """
        Найти зависимости модуля.
        
        Returns:
            {
                "imports": [...],
                "imported_by": [...]
            }
        """
        imports = []
        imported_by = []
        
        # What this module imports
        for edge in self.edges:
            if edge.from_node == module_name:
                imports.append(edge.to_node)
        
        # What imports this module
        for edge in self.edges:
            if edge.to_node == module_name:
                imported_by.append(edge.from_node)
        
        return {
            "imports": imports,
            "imported_by": imported_by
        }
    
    def find_circular_deps(self) -> List[List[str]]:
        """Найти циклические зависимости"""
        # Build adjacency
        adj = defaultdict(list)
        for edge in self.edges:
            if edge.relation == "imports":
                adj[edge.from_node].append(edge.to_node)
        
        # DFS to find cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    cycles.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
            return False
        
        for node in adj:
            if node not in visited:
                dfs(node, [node])
        
        return cycles
    
    def get_module_stats(self, module_name: str) -> Dict[str, Any]:
        """Получить статистику модуля"""
        nodes = [n for n in self.nodes.values() if n.file_path.replace('\\', '/').startswith(self.modules.get(module_name, "").replace('\\', '/').rsplit('/', 1)[0])]
        
        return {
            "total_nodes": len(nodes),
            "classes": len([n for n in nodes if n.type == "class"]),
            "functions": len([n for n in nodes if n.type == "function"]),
            "lines": sum(n.line_end - n.line_start for n in nodes)
        }
    
    def export_json(self) -> Dict[str, Any]:
        """Экспорт графа в JSON для визуализации"""
        return {
            "nodes": [
                {
                    "id": node_id,
                    "name": node.name,
                    "type": node.type,
                    "file": node.file_path,
                    "line_start": node.line_start,
                    "line_end": node.line_end
                }
                for node_id, node in self.nodes.items()
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "relation": edge.relation
                }
                for edge in self.edges
            ],
            "modules": self.modules
        }


def load_or_build_graph(root_path: str, cache_file: Optional[str] = None) -> CodeGraph:
    """
    Загрузить граф из кэша или построить новый.
    
    Args:
        root_path: Путь к корню проекта
        cache_file: Путь к файлу кэша (опционально)
        
    Returns:
        CodeGraph объект
    """
    import json
    
    graph = CodeGraph(root_path)
    
    if cache_file and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Restore nodes
            for node_data in data.get("nodes", []):
                graph.nodes[node_data["id"]] = CodeNode(
                    name=node_data["name"],
                    type=node_data["type"],
                    file_path=node_data["file"],
                    line_start=node_data["line_start"],
                    line_end=node_data["line_end"]
                )
            
            # Restore modules
            graph.modules = data.get("modules", {})
            
            print(f"Loaded graph from cache: {len(graph.nodes)} nodes")
            return graph
        except Exception as e:
            print(f"Failed to load cache: {e}")
    
    # Build new graph
    stats = graph.build()
    print(f"Built graph: {stats}")
    
    # Save to cache if specified
    if cache_file:
        try:
            with open(cache_file, 'w') as f:
                json.dump(graph.export_json(), f)
            print(f"Saved graph to cache: {cache_file}")
        except Exception as e:
            print(f"Failed to save cache: {e}")
    
    return graph
