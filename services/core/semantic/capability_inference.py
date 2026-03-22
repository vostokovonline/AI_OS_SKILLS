"""
Capability Inference Layer for AI-OS

Infers required capabilities from goal descriptions.
Enables generalization - different goals can map to same capabilities.
"""
from typing import List, Dict, Any, Optional
from semantic.embedding_service import embed_text, cosine_similarity


# Core capabilities that map to skill families
CAPABILITIES = {
    "information_retrieval": {
        "keywords": ["search", "find", "research", "collect", "gather", "lookup", "retrieve", "explore", "discover"],
        "description": "Finding and collecting information from various sources"
    },
    "summarization": {
        "keywords": ["summarize", "summary", "condense", "digest", "overview", "brief", "recap", "tldr"],
        "description": "Condensing information into concise form"
    },
    "analysis": {
        "keywords": ["analyze", "analysis", "examine", "evaluate", "assess", "compare", "investigate", "study"],
        "description": "Breaking down information to understand patterns"
    },
    "code_generation": {
        "keywords": ["write", "code", "program", "script", "implement", "build", "create", "develop"],
        "description": "Writing or generating code"
    },
    "data_processing": {
        "keywords": ["process", "parse", "extract", "transform", "convert", "format", "clean", "normalize"],
        "description": "Manipulating and transforming data"
    },
    "writing": {
        "keywords": ["write", "compose", "draft", "author", "craft", "produce", "generate text"],
        "description": "Creating written content"
    },
    "computation": {
        "keywords": ["calculate", "compute", "math", "count", "sum", "formula", "algorithm"],
        "description": "Mathematical or algorithmic computation"
    },
    "decision_making": {
        "keywords": ["decide", "choose", "select", "pick", "recommend", "suggest", "prioritize"],
        "description": "Making choices or recommendations"
    }
}


def infer_capabilities(goal_title: str, goal_description: str = "") -> List[Dict[str, Any]]:
    """
    Infer required capabilities from goal.
    
    Uses keyword matching + semantic similarity to capabilities.
    
    Args:
        goal_title: Goal title
        goal_description: Goal description
        
    Returns:
        List of (capability_name, confidence) tuples sorted by confidence
    """
    text = f"{goal_title} {goal_description}".lower()
    words = set(text.split())
    
    scores = {}
    
    for cap_name, cap_info in CAPABILITIES.items():
        score = 0.0
        
        # Keyword matching
        keyword_matches = sum(1 for kw in cap_info["keywords"] if kw in text)
        if keyword_matches > 0:
            score += keyword_matches * 0.3
        
        # Word overlap with description
        desc_words = set(cap_info["description"].lower().split())
        overlap = words & desc_words
        score += len(overlap) * 0.1
        
        # Semantic similarity to capability description
        cap_text = f"{cap_name.replace('_', ' ')}: {cap_info['description']}"
        goal_text = f"{goal_title} {goal_description}"
        
        cap_emb = embed_text(cap_text)
        goal_emb = embed_text(goal_text)
        
        if cap_emb and goal_emb:
            sim = cosine_similarity(cap_emb, goal_emb)
            score += sim * 0.5
        
        if score > 0.1:
            scores[cap_name] = min(score, 1.0)
    
    # Sort by score descending
    sorted_caps = sorted(scores.items(), key=lambda x: -x[1])
    
    return [
        {"name": name, "confidence": conf, "description": CAPABILITIES[name]["description"]}
        for name, conf in sorted_caps
    ]


def get_capability_embeddings() -> Dict[str, List[float]]:
    """Pre-compute embeddings for all capabilities."""
    embeddings = {}
    for cap_name, cap_info in CAPABILITIES.items():
        cap_text = f"{cap_name.replace('_', ' ')}: {cap_info['description']}"
        emb = embed_text(cap_text)
        if emb:
            embeddings[cap_name] = emb
    return embeddings


def infer_capabilities_batch(goals: List[Dict[str, str]]) -> List[List[Dict[str, Any]]]:
    """Infer capabilities for multiple goals efficiently."""
    # Pre-compute capability embeddings
    cap_embeddings = get_capability_embeddings()
    
    results = []
    for goal in goals:
        title = goal.get("title", "")
        desc = goal.get("description", "")
        
        # Embed goal
        goal_text = f"{title} {desc}"
        goal_emb = embed_text(goal_text)
        
        if not goal_emb:
            results.append([])
            continue
        
        # Score against each capability
        scores = []
        for cap_name, cap_emb in cap_embeddings.items():
            sim = cosine_similarity(goal_emb, cap_emb)
            if sim > 0.1:
                scores.append({
                    "name": cap_name,
                    "confidence": sim,
                    "description": CAPABILITIES[cap_name]["description"]
                })
        
        # Sort by confidence
        scores.sort(key=lambda x: -x["confidence"])
        results.append(scores)
    
    return results
