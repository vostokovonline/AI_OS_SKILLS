"""
FILE LIST SKILL - List files in directory
"""
from pathlib import Path
from canonical_skills.base import Skill, SkillResult, Artifact


class FileListSkill(Skill):
    """List files in a directory."""

    id = "core.file_list"
    version = "1.0"
    description = "List files in a directory"
    
    capabilities = ["file-list", "list", "ls", "directory"]
    requirements = ["directory_path"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "Path to directory"
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g., *.py)"
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively"
            }
        },
        "required": ["directory_path"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "files": {"type": "array"},
            "count": {"type": "integer"}
        }
    }
    
    produces_artifacts = ["FILE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        directory_path = input_data.get("directory_path")
        pattern = input_data.get("pattern", "*")
        recursive = input_data.get("recursive", False)
        
        if not directory_path:
            return self._error_result("No directory_path provided")
        
        try:
            path = Path(directory_path)
            if not path.exists():
                return self._error_result(f"Directory not found: {directory_path}")
            
            if not path.is_dir():
                return self._error_result(f"Not a directory: {directory_path}")
            
            if recursive:
                files = [str(f.relative_to(path)) for f in path.rglob(pattern) if f.is_file()]
            else:
                files = [f.name for f in path.glob(pattern) if f.is_file()]
            
            files.sort()
            
            content = f"Files in {directory_path}:\n" + "\n".join(f"  - {f}" for f in files)
            
            artifact = self._artifact(
                type_="FILE",
                content=content,
                metadata={
                    "source": "FileListSkill",
                    "directory": str(path.absolute()),
                    "count": len(files),
                    "pattern": pattern
                }
            )
            
            output = {
                "files": files,
                "count": len(files)
            }
            
            return self._success_result(output, [artifact])
            
        except Exception as e:
            return self._error_result(f"List failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        if not result.success:
            return False
        return len(result.artifacts) > 0
