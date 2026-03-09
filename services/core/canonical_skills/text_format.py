"""
TEXT FORMAT SKILL - Format text with templates
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class TextFormatSkill(Skill):
    """Format text using templates and variable substitution."""

    id = "text_format"
    version = "1.0.0"
    description = "Format text using templates with variable substitution"

    capabilities = ["format_text", "text_processing", "templating"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "template": {"type": "string", "description": "Text template with {variable} placeholders"},
            "variables": {"type": "object", "description": "Variables to substitute"}
        },
        "required": ["template"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "formatted": {"type": "string"},
            "variables_used": {"type": "array", "items": {"type": "string"}}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "FILE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Format text template."""
        template = input_data.get("template", "")
        variables = input_data.get("variables", {})

        if not template:
            return self._error_result("No template provided")

        try:
            # Format using string format method
            formatted = template.format(**variables)

            # Extract used variables
            import re
            variables_used = re.findall(r'\{(\w+)\}', template)

            output = {
                "formatted": formatted,
                "variables_used": variables_used,
                "length": len(formatted)
            }

            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=formatted,
                metadata={
                    "variables_count": len(variables_used),
                    "template_length": len(template)
                }
            )

            return self._success_result(output, [artifact])

        except KeyError as e:
            return self._error_result(f"Missing variable: {str(e)}")
        except Exception as e:
            return self._error_result(f"Formatting failed: {str(e)}")
