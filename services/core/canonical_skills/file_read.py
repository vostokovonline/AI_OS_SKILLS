"""
FILE READ SKILL - Read file contents
"""
import os
from pathlib import Path
from canonical_skills.base import Skill, SkillResult, Artifact


class FileReadSkill(Skill):
    """Read contents of a file."""

    id = "core.file_read"
    version = "1.0"
    description = "Read contents of a file"
    
    capabilities = ["file-read", "read", "load"]
    requirements = ["file_path"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to file to read"
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to read (optional)"
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)"
            }
        },
        "required": ["file_path"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "lines": {"type": "integer"},
            "size_bytes": {"type": "integer"}
        }
    }
    
    produces_artifacts = ["FILE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        file_path = input_data.get("file_path")
        max_lines = input_data.get("max_lines")
        encoding = input_data.get("encoding", "utf-8")
        
        if not file_path:
            return self._error_result("No file_path provided")
        
        try:
            path = Path(file_path)
            if not path.exists():
                return self._error_result(f"File not found: {file_path}")
            
            if not path.is_file():
                return self._error_result(f"Not a file: {file_path}")
            
            with open(path, 'r', encoding=encoding) as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                else:
                    content = f.read()
            
            stat = path.stat()
            
            artifact = self._artifact(
                type_="FILE",
                content=content,
                metadata={
                    "source": "FileReadSkill",
                    "file_path": str(path.absolute()),
                    "size_bytes": stat.st_size,
                    "lines": content.count('\n') + 1
                }
            )
            
            output = {
                "content": content,
                "lines": content.count('\n') + 1,
                "size_bytes": stat.st_size
            }
            
            return self._success_result(output, [artifact])
            
        except UnicodeDecodeError as e:
            return self._error_result(f"Encoding error: {str(e)}")
        except Exception as e:
            return self._error_result(f"Read failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        if not result.success:
            return False
        if not result.artifacts:
            return False
        return len(result.artifacts) > 0
