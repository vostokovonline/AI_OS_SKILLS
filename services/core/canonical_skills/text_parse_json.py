"""
TEXT PARSE JSON SKILL - Parse and validate JSON data
"""
from canonical_skills.base import Skill, SkillResult, Artifact
import json


class TextParseJsonSkill(Skill):
    """Parse and validate JSON strings."""

    id = "text_parse_json"
    version = "1.0.0"
    description = "Parse and validate JSON strings with error reporting"

    capabilities = ["parse_json", "json_processing", "data_validation"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "json_string": {"type": "string", "description": "JSON string to parse"},
            "output_format": {"type": "string", "description": "Output format (dict, string)", "default": "dict"}
        },
        "required": ["json_string"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "parsed": {"type": "object"},
            "is_valid": {"type": "boolean"},
            "error": {"type": "string"}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "DATASET"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Parse JSON string."""
        json_string = input_data.get("json_string", "")
        output_format = input_data.get("output_format", "dict")

        if not json_string:
            return self._error_result("No JSON string provided")

        try:
            # Parse JSON
            parsed = json.loads(json_string)

            # Format output
            if output_format == "string":
                output_json = json.dumps(parsed, indent=2)
            else:
                output_json = parsed

            output = {
                "parsed": output_json,
                "is_valid": True,
                "type": type(parsed).__name__,
                "size": len(json_string)
            }

            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=f"Successfully parsed JSON ({type(parsed).__name__})",
                metadata={
                    "type": type(parsed).__name__,
                    "size": len(json_string),
                    "valid": True
                }
            )

            return self._success_result(output, [artifact])

        except json.JSONDecodeError as e:
            output = {
                "parsed": None,
                "is_valid": False,
                "error": str(e),
                "line": e.lineno,
                "column": e.colno
            }

            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=f"JSON parsing failed: {str(e)}",
                metadata={
                    "valid": False,
                    "error": str(e),
                    "line": e.lineno
                }
            )

            return self._success_result(output, [artifact])
