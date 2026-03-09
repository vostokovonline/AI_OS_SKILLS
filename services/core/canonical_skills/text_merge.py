"""
TEXT MERGE SKILL - Merge multiple texts
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class TextMergeSkill(Skill):
    """Merge multiple text strings into one."""

    id = "text_merge"
    version = "1.0.0"
    description = "Merge multiple text strings with custom separators"

    capabilities = ["merge_text", "text_processing", "text_combination"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "texts": {"type": "array", "items": {"type": "string"}, "description": "Texts to merge"},
            "separator": {"type": "string", "description": "Separator between texts", "default": " "},
            "add_newlines": {"type": "boolean", "description": "Add newlines between texts", "default": False}
        },
        "required": ["texts"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "merged": {"type": "string"},
            "text_count": {"type": "integer"},
            "total_length": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "FILE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Merge texts."""
        texts = input_data.get("texts", [])
        separator = input_data.get("separator", " ")
        add_newlines = input_data.get("add_newlines", False)

        if not texts:
            return self._error_result("No texts provided")

        # Build separator
        if add_newlines:
            separator = "\n\n" + separator + "\n\n"

        # Merge texts
        merged = separator.join(texts)

        output = {
            "merged": merged,
            "text_count": len(texts),
            "total_length": len(merged),
            "separator": separator[:20]  # First 20 chars of separator
        }

        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Merged {len(texts)} texts into one ({len(merged)} chars)",
            metadata={
                "text_count": len(texts),
                "total_length": len(merged),
                "avg_text_length": round(len(merged) / len(texts), 2)
            }
        )

        return self._success_result(output, [artifact])
