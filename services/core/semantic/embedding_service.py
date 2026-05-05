"""
Semantic Embedding Service for AI-OS
Uses bge-m3 for multilingual semantic search
"""
import numpy as np
from typing import Optional, List
from logging_config import get_logger

logger = get_logger(__name__)

# Global model instance (lazy loaded)
_model = None
_embedding_dimension = 384  # all-MiniLM-L6-v2 dimension


def get_embedding_model():
    """Lazy load the embedding model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("embedding_model_loaded", model="all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence_transformers_not_installed")
            return None
        except Exception as e:
            logger.error("embedding_model_load_failed", error=str(e))
            return None
    return _model


def embed_text(text: str) -> Optional[List[float]]:
    """
    Generate embedding for text.
    
    Returns:
        List of floats (embedding) or None if failed
    """
    model = get_embedding_model()
    if model is None:
        return _simple_hash_embedding(text)
    
    try:
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.warning("embedding_generation_failed", error=str(e))
        return _simple_hash_embedding(text)


def _simple_hash_embedding(text: str, dim: int = 384) -> Optional[List[float]]:
    """
    Simple fallback: deterministic hash-based embedding for testing.
    Used when sentence_transformers is not available.
    """
    import hashlib
    h = hashlib.sha256(text.encode()).digest()
    
    vec = [0.0] * dim
    for i, byte in enumerate(h):
        vec[i % dim] += (byte - 128) / 128.0
    
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    
    return vec


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two embeddings."""
    try:
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr))
    except Exception:
        return 0.0


def build_embedding_text(goal_title: str, goal_description: str = "", skill_sequence: List[str] = None) -> str:
    """
    Build semantic embedding text from actual meaning, not templates.
    
    Transforms skills to natural language for better semantic understanding.
    """
    parts = []
    
    if goal_title:
        parts.append(goal_title)
    
    if goal_description:
        parts.append(goal_description)
    
    if skill_sequence:
        skill_text = " then ".join([
            s.replace("core.", "").replace("_", " ")
            for s in skill_sequence
        ])
        parts.append(f"Steps: {skill_text}")
        
        if "web research" in skill_text.lower() or "research" in skill_text.lower():
            parts.append("This task involves finding information")
        
        if "summarize" in skill_text.lower():
            parts.append("This task involves condensing information")
        
        if "write" in skill_text.lower() or "file" in skill_text.lower():
            parts.append("This task involves creating content")
        
        if "analyze" in skill_text.lower():
            parts.append("This task involves analysis")
    
    return ". ".join(parts)


def build_intent_embedding_text(goal_title: str, goal_description: str = "") -> str:
    """Build embedding focused on intent only."""
    parts = []
    if goal_title:
        parts.append(goal_title)
    if goal_description:
        parts.append(goal_description)
    return ". ".join(parts)


def build_execution_embedding_text(skill_sequence: List[str]) -> str:
    """Build embedding focused on execution flow."""
    if not skill_sequence:
        return "unknown execution"
    
    parts = []
    skill_text = " then ".join([
        s.replace("core.", "").replace("_", " ")
        for s in skill_sequence
    ])
    parts.append(f"Steps: {skill_text}")
    
    if "web research" in skill_text.lower() or "research" in skill_text.lower():
        parts.append("finding information")
    if "summarize" in skill_text.lower():
        parts.append("condensing information")
    if "write" in skill_text.lower():
        parts.append("creating content")
    if "analyze" in skill_text.lower():
        parts.append("analysis")
    
    return ". ".join(parts)


def get_embedding_dimension() -> int:
    """Return the embedding dimension for the model."""
    return _embedding_dimension
