"""
TEXT TOKENIZE SKILL - Tokenize text into words
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class TextTokenizeSkill(Skill):
    """Tokenize text into words and sentences."""

    id = "text_tokenize"
    version = "1.0.0"
    description = "Tokenize text into words and sentences with configurable language support"

    capabilities = ["tokenize", "text_processing"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to tokenize"},
            "language": {"type": "string", "description": "Language code (en, ru, etc.)", "default": "en"},
            "lowercase": {"type": "boolean", "description": "Convert to lowercase", "default": True}
        },
        "required": ["text"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "tokens": {"type": "array", "items": {"type": "string"}},
            "word_count": {"type": "integer"},
            "sentence_count": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Tokenize text into words and sentences."""
        import re

        text = input_data.get("text", "")
        language = input_data.get("language", "en")
        lowercase = input_data.get("lowercase", True)

        if not text:
            return self._error_result("No text provided")

        # Lowercase if requested
        if lowercase:
            text = text.lower()

        # Tokenize into words (handles punctuation)
        words = re.findall(r'\b\w+\b', text)

        # Split into sentences (basic implementation)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Prepare output
        output = {
            "tokens": words,
            "word_count": len(words),
            "sentence_count": len(sentences),
            "language": language
        }

        # Create artifact
        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Tokenized {len(words)} words from {len(sentences)} sentences",
            metadata={
                "word_count": len(words),
                "sentence_count": len(sentences),
                "language": language,
                "sample_tokens": words[:10]  # First 10 tokens as sample
            }
        )

        return self._success_result(output, [artifact])
