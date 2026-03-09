"""
TEXT COUNT WORDS SKILL - Count words, characters, and sentences
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class TextCountWordsSkill(Skill):
    """Count words, characters, sentences, and paragraphs in text."""

    id = "text_count_words"
    version = "1.0.0"
    description = "Count words, characters, sentences, and paragraphs in text"

    capabilities = ["count_words", "text_analysis", "statistics"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to analyze"},
            "include_spaces": {"type": "boolean", "description": "Include spaces in char count", "default": False}
        },
        "required": ["text"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "words": {"type": "integer"},
            "characters": {"type": "integer"},
            "sentences": {"type": "integer"},
            "paragraphs": {"type": "integer"},
            "avg_word_length": {"type": "number"}
        }
    }

    produces_artifacts = ["KNOWLEDGE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Count text statistics."""
        import re

        text = input_data.get("text", "")
        include_spaces = input_data.get("include_spaces", False)

        if not text:
            return self._error_result("No text provided")

        # Count words
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)

        # Count characters
        if include_spaces:
            char_count = len(text)
        else:
            char_count = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))

        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])

        # Count paragraphs (separated by blank lines)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraph_count = len([p for p in paragraphs if p.strip()])

        # Calculate average word length
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0

        output = {
            "words": word_count,
            "characters": char_count,
            "sentences": sentence_count,
            "paragraphs": paragraph_count,
            "avg_word_length": round(avg_word_length, 2)
        }

        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Text statistics: {word_count} words, {char_count} characters, {sentence_count} sentences",
            metadata=output
        )

        return self._success_result(output, [artifact])
