"""
ANALYZE TEXT SKILL - Analyze text for sentiment, length, etc.
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class AnalyzeTextSkill(Skill):
    """Analyze text for various metrics."""

    id = "core.analyze_text"
    version = "1.0"
    description = "Analyze text for sentiment, word count, complexity"
    
    capabilities = ["analyze", "analyze-text", "text-analysis"]
    requirements = ["text"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to analyze"},
            "analysis_type": {
                "type": "string",
                "enum": ["basic", "detailed"],
                "description": "Type of analysis"
            }
        },
        "required": ["text"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "word_count": {"type": "integer"},
            "char_count": {"type": "integer"},
            "line_count": {"type": "integer"},
            "avg_word_length": {"type": "number"}
        }
    }
    
    produces_artifacts = ["KNOWLEDGE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        text = input_data.get("text", "")
        
        if not text:
            return self._error_result("No text provided")
        
        words = text.split()
        lines = text.split('\n')
        
        analysis = {
            "word_count": len(words),
            "char_count": len(text),
            "line_count": len(lines),
            "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
            "unique_words": len(set(w.lower() for w in words))
        }
        
        content = f"Text Analysis:\n"
        content += f"- Words: {analysis['word_count']}\n"
        content += f"- Characters: {analysis['char_count']}\n"
        content += f"- Lines: {analysis['line_count']}\n"
        content += f"- Avg word length: {analysis['avg_word_length']:.1f}\n"
        content += f"- Unique words: {analysis['unique_words']}\n"
        
        artifact = self._artifact(
            type_="KNOWLEDGE",
            content=content,
            metadata={"source": "AnalyzeTextSkill", **analysis}
        )
        
        return self._success_result(analysis, [artifact])
    
    def verify(self, result: SkillResult) -> bool:
        return result.success
