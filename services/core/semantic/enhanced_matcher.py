"""
Enhanced Semantic Pattern Matcher with Capability Inference

Two-stage matching:
1. Goal → Capabilities (what does the goal need?)
2. Capabilities → Patterns (which patterns provide these capabilities?)

This enables generalization - different goals can map to same patterns.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
from semantic.embedding_service import embed_text, cosine_similarity, build_embedding_text
from semantic.capability_inference import infer_capabilities

logger = get_logger(__name__)


# Capability → Skill mapping (what skills provide each capability)
CAPABILITY_SKILL_MAP = {
    "information_retrieval": ["core.web_research", "core.file_search"],
    "summarization": ["core.summarize_text", "core.text_merge"],
    "analysis": ["core.analyze_text", "core.text_extract_keywords"],
    "code_generation": ["core.write_file", "core.create_directory"],
    "data_processing": ["core.text_parse_csv", "core.text_parse_json", "core.text_regex_extract"],
    "writing": ["core.write_file"],
    "computation": ["core.echo"],  # Placeholder
    "decision_making": ["core.echo"],  # Placeholder
}


class EnhancedMatcher:
    """
    Two-stage semantic matcher with capability inference.
    
    Stage 1: Infer capabilities from goal
    Stage 2: Find patterns that provide those capabilities
    
    Benefits:
    - Generalization: "research ML papers" and "find AI articles" → same capabilities
    - Abstraction: Pattern selection based on capabilities, not exact match
    """
    
    HIGH_CONFIDENCE = 0.5
    MEDIUM_CONFIDENCE = 0.3
    MIN_SCORE_THRESHOLD = 0.25
    MAX_PATTERNS_TO_CHECK = 50
    CAPABILITY_WEIGHT = 0.6
    SEMANTIC_WEIGHT = 0.4
    
    async def find_best_pattern(
        self, 
        goal_title: str, 
        goal_description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Two-stage pattern matching with capability inference.
        
        Args:
            goal_title: Goal title
            goal_description: Goal description
            
        Returns:
            Dict with pattern info, capabilities, and confidence
        """
        # Stage 1: Infer capabilities
        capabilities = infer_capabilities(goal_title, goal_description)
        logger.info("capabilities_inferred", goal=goal_title[:50], capabilities=[c["name"] for c in capabilities])
        
        if not capabilities:
            logger.debug("no_capabilities_inferred")
            # Fall back to pure semantic matching
            return await self._semantic_match_only(goal_title, goal_description)
        
        # Stage 2: Find patterns matching capabilities
        pattern = await self._capability_based_match(goal_title, goal_description, capabilities)
        
        if pattern:
            pattern["capabilities"] = [c["name"] for c in capabilities]
            return pattern
        
        return None
    
    async def _capability_based_match(
        self, 
        goal_title: str, 
        goal_description: str,
        capabilities: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Match patterns based on inferred capabilities.
        
        For each capability, find patterns that provide it.
        Combine scores with semantic similarity.
        """
        patterns = await self._get_all_patterns()
        
        if not patterns:
            return None
        
        best_pattern = None
        best_score = 0.0
        
        top_capabilities = capabilities[:3]  # Top 3 capabilities
        
        for pattern in patterns:
            pattern_id = pattern["pattern_id"]
            skill_sequence = pattern["skill_sequence"]
            frequency = pattern.get("frequency", 1) or 1
            success_rate = pattern.get("avg_success_rate", 0.5) or 0.5
            embedding = pattern.get("embedding")
            
            # Calculate capability match score
            capability_score = self._calculate_capability_score(skill_sequence, top_capabilities)
            
            # Calculate semantic similarity
            semantic_sim = 0.0
            if embedding:
                query_text = build_embedding_text(goal_title, goal_description, skill_sequence)
                query_emb = embed_text(query_text)
                if query_emb:
                    try:
                        import json
                        pattern_emb = json.loads(embedding) if isinstance(embedding, str) else embedding
                        semantic_sim = cosine_similarity(query_emb, pattern_emb)
                    except:
                        semantic_sim = 0.0
            
            # Combined score
            frequency_score = min(frequency / 10.0, 1.0)
            score = (
                capability_score * self.CAPABILITY_WEIGHT +
                semantic_sim * self.SEMANTIC_WEIGHT +
                success_rate * 0.1
            )
            
            if score > best_score:
                best_score = score
                best_pattern = {
                    "pattern_id": pattern_id,
                    "skill_sequence": skill_sequence,
                    "semantic_similarity": semantic_sim,
                    "capability_score": capability_score,
                    "success_rate": success_rate,
                    "frequency": frequency,
                    "score": score
                }
        
        if not best_pattern:
            return None
        
        # Determine confidence level
        total_capability = sum(c["confidence"] for c in top_capabilities)
        avg_capability = total_capability / len(top_capabilities)
        
        if avg_capability >= self.HIGH_CONFIDENCE:
            best_pattern["confidence"] = "high"
        elif avg_capability >= self.MEDIUM_CONFIDENCE:
            best_pattern["confidence"] = "medium"
        else:
            best_pattern["confidence"] = "low"
            return None
        
        logger.info(
            "capability_pattern_matched",
            pattern_id=best_pattern["pattern_id"],
            capabilities=[c["name"] for c in top_capabilities],
            score=round(best_score, 2),
            confidence=best_pattern["confidence"]
        )
        
        return best_pattern
    
    def _calculate_capability_score(
        self, 
        skill_sequence: List[str], 
        capabilities: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate how well a pattern's skills match required capabilities.
        
        Uses fuzzy matching - doesn't require exact match.
        """
        if not skill_sequence or not capabilities:
            return 0.0
        
        score = 0.0
        
        for cap in capabilities:
            cap_name = cap["name"]
            cap_conf = cap["confidence"]
            
            # Check if any skill in sequence provides this capability
            for skill_id in skill_sequence:
                skill_id_lower = skill_id.lower()
                
                # Direct capability → skill mapping
                if cap_name in CAPABILITY_SKILL_MAP:
                    required_skills = CAPABILITY_SKILL_MAP[cap_name]
                    for req_skill in required_skills:
                        if req_skill in skill_id_lower or skill_id_lower in req_skill:
                            score += cap_conf * 0.5
                            break
                
                # Fuzzy keyword matching
                cap_keywords = cap_name.replace("_", " ").split()
                skill_words = skill_id_lower.replace("core.", "").replace("_", " ").split()
                
                overlap = set(cap_keywords) & set(skill_words)
                if overlap:
                    score += cap_conf * 0.3 * len(overlap) / len(cap_keywords)
        
        return min(score, 1.0)
    
    async def _semantic_match_only(
        self, 
        goal_title: str, 
        goal_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback: pure semantic matching without capability inference.
        """
        query_text = build_embedding_text(goal_title, goal_description)
        query_embedding = embed_text(query_text)
        
        if not query_embedding:
            return None
        
        patterns = await self._get_all_patterns()
        
        best_pattern = None
        best_score = 0.0
        
        for pattern in patterns:
            embedding = pattern.get("embedding")
            if not embedding:
                continue
            
            try:
                import json
                pattern_emb = json.loads(embedding) if isinstance(embedding, str) else embedding
                semantic_sim = cosine_similarity(query_embedding, pattern_emb)
            except:
                continue
            
            if semantic_sim < self.MEDIUM_CONFIDENCE:
                continue
            
            frequency = pattern.get("frequency", 1) or 1
            success_rate = pattern.get("avg_success_rate", 0.5) or 0.5
            frequency_score = min(frequency / 10.0, 1.0)
            
            score = semantic_sim * 0.7 + success_rate * 0.2 + frequency_score * 0.1
            
            if score > best_score:
                best_score = score
                best_pattern = {
                    "pattern_id": pattern["pattern_id"],
                    "skill_sequence": pattern["skill_sequence"],
                    "semantic_similarity": semantic_sim,
                    "success_rate": success_rate,
                    "frequency": frequency,
                    "score": score,
                    "confidence": "medium"
                }
        
        return best_pattern
    
    async def _get_all_patterns(self) -> List[Dict[str, Any]]:
        """Get all patterns with embeddings."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT 
                        pattern_id,
                        skill_sequence,
                        frequency,
                        avg_success_rate,
                        embedding
                    FROM skill_patterns
                    WHERE embedding IS NOT NULL
                    AND avg_success_rate >= 0.5
                    AND pattern_id != 'core.echo'
                    ORDER BY avg_success_rate DESC
                    LIMIT :limit
                """)
                
                result = await session.execute(query, {"limit": self.MAX_PATTERNS_TO_CHECK})
                rows = result.fetchall()
                
                patterns = []
                for row in rows:
                    patterns.append({
                        "pattern_id": row[0],
                        "skill_sequence": row[1],
                        "frequency": row[2],
                        "avg_success_rate": row[3],
                        "embedding": row[4]
                    })
                
                return patterns
                
        except Exception as e:
            logger.error("failed_to_get_patterns", error=str(e))
            return []


# Global instance
enhanced_matcher = EnhancedMatcher()
