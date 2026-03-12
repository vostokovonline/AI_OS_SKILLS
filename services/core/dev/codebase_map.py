"""
Codebase Map - Анализ всей кодовой базы

Создает полную карту системы:
- Модули и их зависимости
- Самые большие модули
- Часто вызываемые функции
- Dead code
- Архитектурные проблемы
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
import json

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dev.code_graph import CodeGraph, load_or_build_graph


class CodebaseMap:
    """
    Полная карта кодовой базы.
    
    Анализирует:
    - Структуру модулей
    - Зависимости
    - Размеры
    - Вызовы
    - Dead code
    """
    
    def __init__(self, root_path: str, cache_file: Optional[str] = None):
        self.root_path = root_path
        self.cache_file = cache_file
        self.graph: Optional[CodeGraph] = None
        self.stats: Dict[str, Any] = {}
        
    def build(self) -> Dict[str, Any]:
        """Построить карту кодовой базы"""
        print(f"Building codebase map for: {self.root_path}")
        
        self.graph = load_or_build_graph(self.root_path, self.cache_file)
        
        # Build stats
        self.stats = {
            "overview": self._get_overview(),
            "modules": self._get_module_stats(),
            "dependencies": self._get_dependency_stats(),
            "largest_modules": self._get_largest_modules(20),
            "most_called": self._get_most_called_functions(20),
            "circular_deps": self.graph.find_circular_deps() if self.graph else [],
            "entry_points": self._find_entry_points(),
            "architecture": self._analyze_architecture()
        }
        
        return self.stats
    
    def _get_overview(self) -> Dict[str, Any]:
        """Общая статистика"""
        if not self.graph:
            return {}
        
        nodes = list(self.graph.nodes.values())
        
        return {
            "total_nodes": len(nodes),
            "modules": len(self.graph.modules),
            "classes": len([n for n in nodes if n.type == "class"]),
            "functions": len([n for n in nodes if n.type == "function"]),
            "methods": len([n for n in nodes if n.type == "method"]),
            "total_lines": sum(n.line_end - n.line_start for n in nodes)
        }
    
    def _get_module_stats(self) -> Dict[str, Any]:
        """Статистика по модулям"""
        if not self.graph:
            return {}
        
        module_stats = {}
        
        for module_name, file_path in self.graph.modules.items():
            nodes = [n for n in self.graph.nodes.values() 
                    if n.file_path.replace('\\', '/').startswith(file_path.replace('\\', '/').rsplit('/', 1)[0])]
            
            classes = [n for n in nodes if n.type == "class"]
            funcs = [n for n in nodes if n.type == "function"]
            methods = [n for n in nodes if n.type == "method"]
            
            total_lines = sum(n.line_end - n.line_start for n in nodes)
            
            module_stats[module_name] = {
                "file": file_path,
                "classes": len(classes),
                "functions": len(funcs),
                "methods": len(methods),
                "total_nodes": len(nodes),
                "lines": total_lines
            }
        
        return module_stats
    
    def _get_dependency_stats(self) -> Dict[str, Any]:
        """Статистика зависимостей"""
        if not self.graph:
            return {}
        
        # Count imports
        import_counts = Counter()
        imported_by = defaultdict(list)
        
        for edge in self.graph.edges:
            if edge.relation == "imports":
                import_counts[edge.to_node] += 1
                imported_by[edge.to_node].append(edge.from_node)
        
        return {
            "most_imported": dict(import_counts.most_common(20)),
            "most_used": dict(Counter(
                node for edge in self.graph.edges 
                if edge.relation == "calls" 
                for node in [edge.to_node]
            ).most_common(20)),
            "orphaned_modules": self._find_orphaned_modules()
        }
    
    def _get_largest_modules(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Самые большие модули по строкам"""
        if not self.graph:
            return []
        
        module_lines = defaultdict(int)
        
        for node in self.graph.nodes.values():
            lines = node.line_end - node.line_start
            # Group by module
            parts = node.file_path.replace('\\', '/').split('/')
            if len(parts) >= 2:
                module = parts[-2]
                module_lines[module] += lines
        
        sorted_modules = sorted(module_lines.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"module": m, "lines": l}
            for m, l in sorted_modules[:limit]
        ]
    
    def _get_most_called_functions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Самые часто вызываемые функции"""
        if not self.graph:
            return []
        
        call_counts = Counter()
        
        for node_id, node in self.graph.nodes.items():
            for call in node.calls:
                call_counts[call] += 1
        
        return [
            {"function": f, "calls": c}
            for f, c in call_counts.most_common(limit)
        ]
    
    def _find_entry_points(self) -> List[Dict[str, Any]]:
        """Найти точки входа (main, app, run)"""
        if not self.graph:
            return []
        
        entry_points = []
        
        keywords = ["main", "app", "run", "serve", "start", "create_app", "make_app"]
        
        for node_id, node in self.graph.nodes.items():
            if node.type in ["function", "method"]:
                if any(kw in node.name.lower() for kw in keywords):
                    entry_points.append({
                        "name": node.name,
                        "type": node.type,
                        "file": node.file_path,
                        "line": node.line_start,
                        "decorators": node.decorators
                    })
        
        return entry_points[:20]
    
    def _find_orphaned_modules(self) -> List[str]:
        """Найти модули которые ничего не импортируют и не импортируются"""
        if not self.graph:
            return []
        
        all_modules = set(self.graph.modules.keys())
        
        # Find imported modules
        imported = set()
        importers = set()
        
        for edge in self.graph.edges:
            if edge.relation == "imports":
                imported.add(edge.to_node)
                importers.add(edge.from_node)
        
        # Orphaned = not imported by anyone
        orphaned = all_modules - imported
        
        return list(orphaned)[:20]
    
    def _analyze_architecture(self) -> Dict[str, Any]:
        """Анализ архитектуры"""
        if not self.graph:
            return {}
        
        # Find patterns
        patterns = {
            "has_api": False,
            "has_models": False,
            "has_database": False,
            "has_utils": False,
            "has_tests": False
        }
        
        for module_name in self.graph.modules:
            name_lower = module_name.lower()
            if "api" in name_lower or "endpoint" in name_lower:
                patterns["has_api"] = True
            if "model" in name_lower:
                patterns["has_models"] = True
            if "db" in name_lower or "database" in name_lower or "repo" in name_lower:
                patterns["has_database"] = True
            if "util" in name_lower or "helper" in name_lower:
                patterns["has_utils"] = True
            if "test" in name_lower:
                patterns["has_tests"] = True
        
        return patterns
    
    def get_impact_analysis(self, target: str) -> Dict[str, Any]:
        """Анализ влияния - что сломается если изменить target"""
        if not self.graph:
            return {}
        
        affected = []
        
        # Find what calls this
        for edge in self.graph.edges:
            if edge.to_node == target:
                affected.append({
                    "type": "calls",
                    "source": edge.from_node
                })
        
        # Find what inherits this
        for node_id, node in self.graph.nodes.items():
            if target in node.inherits:
                affected.append({
                    "type": "inherits",
                    "source": node_id
                })
        
        return {
            "target": target,
            "affected_count": len(affected),
            "affected": affected
        }
    
    def export_json(self, output_file: str) -> None:
        """Экспорт карты в JSON"""
        with open(output_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Exported codebase map to: {output_file}")


def main():
    """Пример использования"""
    import sys
    
    root = sys.argv[1] if len(sys.argv) > 1 else "services/core"
    cache = "/tmp/codebase_map.json"
    
    print(f"Analyzing codebase: {root}")
    
    mapper = CodebaseMap(root, cache)
    stats = mapper.build()
    
    # Print summary
    print("\n" + "="*50)
    print("CODEBASE MAP SUMMARY")
    print("="*50)
    
    overview = stats.get("overview", {})
    print(f"\nTotal: {overview.get('modules', 0)} modules, "
          f"{overview.get('classes', 0)} classes, "
          f"{overview.get('functions', 0)} functions")
    
    print("\n📦 Largest Modules:")
    for m in stats.get("largest_modules", [])[:10]:
        print(f"  {m['module']}: {m['lines']} lines")
    
    print("\n🔗 Most Called Functions:")
    for f in stats.get("most_called", [])[:10]:
        print(f"  {f['function']}: {f['calls']} calls")
    
    print("\n⚠️ Circular Dependencies:")
    for cycle in stats.get("circular_deps", [])[:5]:
        print(f"  {' -> '.join(cycle[:5])}")
    
    arch = stats.get("architecture", {})
    print("\n🏗️ Architecture:")
    for k, v in arch.items():
        print(f"  {k}: {v}")
    
    # Export
    mapper.export_json("/tmp/codebase_map.json")
    print("\nFull map exported to: /tmp/codebase_map.json")


if __name__ == "__main__":
    main()
