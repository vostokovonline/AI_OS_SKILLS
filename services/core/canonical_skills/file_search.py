"""
FILE SEARCH SKILL - Search files by content
"""
import os
from pathlib import Path
from canonical_skills.base import Skill, SkillResult, Artifact


class FileSearchSkill(Skill):
    """Search for text in files."""

    id = "core.file_search"
    version = "1.0"
    description = "Search for text in files"
    
    capabilities = ["file-search", "search", "grep", "find"]
    requirements = ["query", "directory"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "directory": {
                "type": "string",
                "description": "Directory to search in"
            },
            "file_pattern": {
                "type": "string",
                "description": "File pattern (e.g., *.py)"
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case sensitive search"
            }
        },
        "required": ["query", "directory"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "matches": {"type": "array"},
            "files_found": {"type": "integer"}
        }
    }
    
    produces_artifacts = ["FILE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        query = input_data.get("query")
        directory = input_data.get("directory")
        file_pattern = input_data.get("file_pattern", "*")
        case_sensitive = input_data.get("case_sensitive", True)
        
        if not query or not directory:
            return self._error_result("Missing query or directory")
        
        try:
            path = Path(directory)
            if not path.exists():
                return self._error_result(f"Directory not found: {directory}")
            
            matches = []
            search_term = query if case_sensitive else query.lower()
            
            for file_path in path.rglob(file_pattern):
                if not file_path.is_file():
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            search_line = line if case_sensitive else line.lower()
                            if search_term in search_line:
                                matches.append({
                                    "file": str(file_path.relative_to(path)),
                                    "line": line_num,
                                    "content": line.strip()[:100]
                                })
                except Exception:
                    continue
            
            content = f"Search results for '{query}' in {directory}:\n"
            content += f"Found {len(matches)} matches in {len(set(m.get('file') for m in matches))} files\n\n"
            for m in matches[:50]:
                content += f"{m['file']}:{m['line']}: {m['content']}\n"
            
            artifact = self._artifact(
                type_="FILE",
                content=content,
                metadata={
                    "source": "FileSearchSkill",
                    "query": query,
                    "matches": len(matches)
                }
            )
            
            output = {
                "matches": matches[:100],
                "files_found": len(set(m.get('file') for m in matches))
            }
            
            return self._success_result(output, [artifact])
            
        except Exception as e:
            return self._error_result(f"Search failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        return result.success
