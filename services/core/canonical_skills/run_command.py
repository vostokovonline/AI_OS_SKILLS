"""
RUN COMMAND SKILL - Execute shell commands
"""
import subprocess
from canonical_skills.base import Skill, SkillResult, Artifact


class RunCommandSkill(Skill):
    """Execute shell command."""

    id = "core.run_command"
    version = "1.0"
    description = "Execute a shell command"
    
    capabilities = ["run-command", "execute", "bash", "shell", "command"]
    requirements = ["command"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds"
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory"
            },
            "shell": {
                "type": "boolean",
                "description": "Use shell"
            }
        },
        "required": ["command"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "return_code": {"type": "integer"}
        }
    }
    
    produces_artifacts = ["EXECUTION_LOG"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        command = input_data.get("command")
        timeout = input_data.get("timeout", 60)
        working_dir = input_data.get("working_directory")
        use_shell = input_data.get("shell", True)
        
        if not command:
            return self._error_result("No command provided")
        
        try:
            result = subprocess.run(
                command,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir
            )
            
            output = {
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "return_code": result.returncode
            }
            
            content = f"Command: {command}\n"
            content += f"Return code: {result.returncode}\n\n"
            content += f"STDOUT:\n{result.stdout[:5000]}\n"
            if result.stderr:
                content += f"\nSTDERR:\n{result.stderr[:2000]}"
            
            artifact = self._artifact(
                type_="EXECUTION_LOG",
                content=content,
                metadata={
                    "source": "RunCommandSkill",
                    "command": command,
                    "return_code": result.returncode,
                    "timeout": timeout
                }
            )
            
            success = result.returncode == 0
            
            return self._success_result(output, [artifact])
            
        except subprocess.TimeoutExpired:
            return self._error_result(f"Command timed out after {timeout}s")
        except Exception as e:
            return self._error_result(f"Execution failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        return result.success
