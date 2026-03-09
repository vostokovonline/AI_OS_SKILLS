"""
TEXT SPLIT SKILL - Split text into chunks
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class TextSplitSkill(Skill):
    """Split text into chunks by size, delimiter, or sentences."""

    id = "text_split"
    version = "1.0.0"
    description = "Split text into chunks by size, delimiter, or sentences"

    capabilities = ["split_text", "text_processing", "chunking"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to split"},
            "mode": {"type": "string", "enum": ["chars", "words", "lines", "sentences"], "description": "Split mode"},
            "chunk_size": {"type": "integer", "description": "Size of each chunk"},
            "delimiter": {"type": "string", "description": "Custom delimiter"}
        },
        "required": ["text", "mode"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "chunks": {"type": "array", "items": {"type": "string"}},
            "chunk_count": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "DATASET"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Split text into chunks."""
        text = input_data.get("text", "")
        mode = input_data.get("mode", "words")
        chunk_size = input_data.get("chunk_size", 100)
        delimiter = input_data.get("delimiter", None)

        if not text:
            return self._error_result("No text provided")

        chunks = []

        if delimiter:
            # Split by custom delimiter
            chunks = text.split(delimiter)
        elif mode == "chars":
            # Split by character count
            for i in range(0, len(text), chunk_size):
                chunks.append(text[i:i + chunk_size])
        elif mode == "words":
            # Split by word count
            words = text.split()
            for i in range(0, len(words), chunk_size):
                chunk = ' '.join(words[i:i + chunk_size])
                chunks.append(chunk)
        elif mode == "lines":
            # Split by lines
            chunks = text.split('\n')
        elif mode == "sentences":
            # Split by sentences
            import re
            chunks = re.split(r'[.!?]+', text)
            chunks = [s.strip() for s in chunks if s.strip()]

        output = {
            "chunks": chunks,
            "chunk_count": len(chunks),
            "mode": mode
        }

        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=f"Split text into {len(chunks)} chunks ({mode} mode)",
            metadata={
                "chunk_count": len(chunks),
                "mode": mode,
                "avg_chunk_size": round(sum(len(c) for c in chunks) / len(chunks), 2) if chunks else 0
            }
        )

        return self._success_result(output, [artifact])
