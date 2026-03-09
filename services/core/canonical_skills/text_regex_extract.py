"""
TEXT REGEX EXTRACT SKILL - Extract data using regex patterns
"""
from canonical_skills.base import Skill, SkillResult, Artifact
import re
import json


class TextRegexExtractSkill(Skill):
    """Extract data from text using regular expressions."""

    id = "text_regex_extract"
    version = "1.0.0"
    description = "Extract data from text using regular expression patterns"

    capabilities = ["regex_extract", "text_processing", "data_extraction"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to search"},
            "pattern": {"type": "string", "description": "Regex pattern to match"},
            "flags": {"type": "string", "description": "Regex flags (i, m, s)", "default": ""},
            "group": {"type": "integer", "description": "Capture group to extract (0 for full match)"}
        },
        "required": ["text", "pattern"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "matches": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "DATASET"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Extract data using regex."""
        text = input_data.get("text", "")
        pattern = input_data.get("pattern", "")
        flags_str = input_data.get("flags", "")
        group = input_data.get("group", 0)

        if not text or not pattern:
            return self._error_result("Both text and pattern are required")

        try:
            # Parse flags
            flags = 0
            if 'i' in flags_str:
                flags |= re.IGNORECASE
            if 'm' in flags_str:
                flags |= re.MULTILINE
            if 's' in flags_str:
                flags |= re.DOTALL

            # Find all matches
            matches = re.findall(pattern, text, flags)

            # Extract specific group if requested
            if group != 0 and matches:
                extracted = [m[group] if isinstance(m, tuple) else m for m in matches]
            else:
                # Flatten tuples if groups were captured
                extracted = []
                for m in matches:
                    if isinstance(m, tuple):
                        extracted.extend(m)
                    else:
                        extracted.append(m)

            output = {
                "matches": extracted,
                "count": len(extracted)
            }

            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=f"Extracted {len(extracted)} matches using regex pattern",
                metadata={
                    "pattern": pattern[:100],  # First 100 chars
                    "match_count": len(extracted),
                    "sample_matches": extracted[:5]  # First 5 matches
                }
            )

            return self._success_result(output, [artifact])

        except re.error as e:
            return self._error_result(f"Invalid regex pattern: {str(e)}")
