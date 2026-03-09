"""
TEXT EXTRACT KEYWORDS SKILL - Extract important keywords from text
"""
from canonical_skills.base import Skill, SkillResult, Artifact
import re
from collections import Counter


class TextExtractKeywordsSkill(Skill):
    """Extract important keywords using frequency analysis."""

    id = "text_extract_keywords"
    version = "1.0.0"
    description = "Extract important keywords from text using frequency analysis"

    capabilities = ["extract_keywords", "text_analysis", "nlp"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to analyze"},
            "max_keywords": {"type": "integer", "description": "Maximum keywords to return", "default": 10},
            "min_length": {"type": "integer", "description": "Minimum word length", "default": 3}
        },
        "required": ["text"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "frequencies": {"type": "object"}
        }
    }

    produces_artifacts = ["KNOWLEDGE"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Extract keywords from text."""
        text = input_data.get("text", "")
        max_keywords = input_data.get("max_keywords", 10)
        min_length = input_data.get("min_length", 3)

        if not text:
            return self._error_result("No text provided")

        # Common stop words to filter out
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how'
        }

        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter stop words and short words
        filtered_words = [w for w in words if w not in stop_words and len(w) >= min_length]

        # Count frequency
        word_freq = Counter(filtered_words)

        # Get top keywords
        top_keywords = word_freq.most_common(max_keywords)
        keywords = [kw for kw, count in top_keywords]
        frequencies = dict(top_keywords)

        output = {
            "keywords": keywords,
            "frequencies": frequencies,
            "total_unique_words": len(word_freq)
        }

        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Extracted {len(keywords)} keywords from text",
            metadata={
                "keywords": keywords[:5],  # Top 5 as sample
                "top_frequency": frequencies[keywords[0]] if keywords else 0
            }
        )

        return self._success_result(output, [artifact])
