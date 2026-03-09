"""
TEXT CLEAN SKILL - Clean and normalize text
"""
from canonical_skills.base import Skill, SkillResult, Artifact
import re


class TextCleanSkill(Skill):
    """Clean and normalize text by removing noise."""

    id = "text_clean"
    version = "1.0.0"
    description = "Clean text by removing extra whitespace, special characters, and normalizing"

    capabilities = ["clean_text", "text_normalization", "text_preprocessing"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to clean"},
            "remove_extra_whitespace": {"type": "boolean", "default": True},
            "remove_special_chars": {"type": "boolean", "default": False},
            "lowercase": {"type": "boolean", "default": False},
            "remove_numbers": {"type": "boolean", "default": False}
        },
        "required": ["text"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "cleaned": {"type": "string"},
            "original_length": {"type": "integer"},
            "cleaned_length": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Clean text."""
        text = input_data.get("text", "")
        remove_extra_whitespace = input_data.get("remove_extra_whitespace", True)
        remove_special_chars = input_data.get("remove_special_chars", False)
        lowercase = input_data.get("lowercase", False)
        remove_numbers = input_data.get("remove_numbers", False)

        if not text:
            return self._error_result("No text provided")

        original_length = len(text)
        cleaned = text

        # Remove extra whitespace
        if remove_extra_whitespace:
            cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
            cleaned = cleaned.strip()

        # Remove special characters
        if remove_special_chars:
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned)

        # Remove numbers
        if remove_numbers:
            cleaned = re.sub(r'\d+', '', cleaned)

        # Convert to lowercase
        if lowercase:
            cleaned = cleaned.lower()

        output = {
            "cleaned": cleaned,
            "original_length": original_length,
            "cleaned_length": len(cleaned),
            "reduction": original_length - len(cleaned)
        }

        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Cleaned text: {original_length} → {len(cleaned)} chars",
            metadata={
                "original_length": original_length,
                "cleaned_length": len(cleaned),
                "reduction_pct": round((1 - len(cleaned) / original_length) * 100, 2) if original_length > 0 else 0
            }
        )

        return self._success_result(output, [artifact])
