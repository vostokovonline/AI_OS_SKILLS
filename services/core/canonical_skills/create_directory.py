"""
CREATE DIRECTORY SKILL - Create directories
"""
import os
from pathlib import Path
from canonical_skills.base import Skill, SkillResult, Artifact


class CreateDirectorySkill(Skill):
    """Create a directory."""

    id = "core.create_directory"
    version = "1.0"
    description = "Create a directory"
    
    capabilities = ["create-directory", "mkdir", "create-dir"]
    requirements = ["directory_path"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "directory_path": {"type": "string", "description": "Path to create"},
            "parents": {"type": "boolean", "description": "Create parent dirs"}
        },
        "required": ["directory_path"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "created": {"type": "boolean"},
            "path": {"type": "string"}
        }
    }
    
    produces_artifacts = ["FILE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        directory_path = input_data.get("directory_path")
        parents = input_data.get("parents", True)
        
        if not directory_path:
            return self._error_result("No directory_path provided")
        
        try:
            path = Path(directory_path)
            path.mkdir(parents=parents, exist_ok=True)
            
            content = f"Directory created: {path.absolute()}"
            
            artifact = self._artifact(
                type_="FILE",
                content=content,
                metadata={"source": "CreateDirectorySkill", "path": str(path.absolute())}
            )
            
            output = {"created": True, "path": str(path.absolute())}
            return self._success_result(output, [artifact])
            
        except Exception as e:
            return self._error_result(f"Create directory failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        return result.success
