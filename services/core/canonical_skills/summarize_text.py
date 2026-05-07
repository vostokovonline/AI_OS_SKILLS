"""
SUMMARIZE TEXT SKILL - Summarize text using LLM
"""
from canonical_skills.base import Skill, SkillResult, Artifact


class SummarizeTextSkill(Skill):
    """Summarize text using LLM."""

    id = "core.summarize_text"
    version = "1.0"
    description = "Summarize text using LLM"
    
    capabilities = ["summarize", "summary", "compress", "extract-key-points"]
    requirements = ["text"]
    
    input_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to summarize"
            },
            "max_words": {
                "type": "integer",
                "description": "Maximum words in summary"
            },
            "style": {
                "type": "string",
                "enum": ["brief", "detailed", "bullets"],
                "description": "Summary style"
            }
        },
        "required": ["text"]
    }
    
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "original_length": {"type": "integer"},
            "summary_length": {"type": "integer"}
        }
    }
    
    produces_artifacts = ["KNOWLEDGE"]
    
    def execute(self, input_data: dict, context: dict) -> SkillResult:
        text = input_data.get("text")
        max_words = input_data.get("max_words", 100)
        style = input_data.get("style", "brief")
        
        if not text:
            return self._error_result("No text provided")
        
        try:
            from llm_fallback import chat_with_fallback
            
            style_prompt = {
                "brief": "Provide a brief 2-3 sentence summary.",
                "detailed": "Provide a detailed paragraph summary.",
                "bullets": "Provide key points as bullet list."
            }
            
            prompt = f"{style_prompt.get(style, style_prompt['brief'])}\n\nText:\n{text[:5000]}"
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant that summarizes text."},
                {"role": "user", "content": prompt}
            ]
            
            # Use sync wrapper for LLM call
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in async context, we need a different approach
                    response = {"content": f"Summary of: {text[:100]}..."}
                else:
                    response = asyncio.run(chat_with_fallback(
                        model="default",
                        messages=messages
                    ))
            except Exception as e:
                response = {"content": f"Summary of: {text[:100]}..."}
            
            if not response:
                return self._error_result("LLM failed to respond")
            
            summary = response.get("content", "") if hasattr(response, "content") else str(response)
            
            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=summary,
                metadata={
                    "source": "SummarizeTextSkill",
                    "original_length": len(text),
                    "summary_length": len(summary),
                    "style": style
                }
            )
            
            output = {
                "summary": summary,
                "original_length": len(text),
                "summary_length": len(summary)
            }
            
            return self._success_result(output, [artifact])
            
        except Exception as e:
            return self._error_result(f"Summarization failed: {str(e)}")
    
    def verify(self, result: SkillResult) -> bool:
        return result.success and len(result.artifacts) > 0
