"""
Semantic Pattern Matcher for AI-OS
Uses embeddings to find relevant execution patterns
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
from semantic.embedding_service import embed_text, cosine_similarity, build_embedding_text

logger = get_logger(__name__)


class SemanticMatcher:
    """
    Finds execution patterns using graduated semantic matching.
    
    Three-tier matching:
    1. HIGH confidence (sim > 0.5) → use pattern directly
    2. MEDIUM confidence (0.3 < sim <= 0.5) → suggest pattern, validate with planner
    3. LOW confidence (sim <= 0.3) → use planner
    
    This enables "close enough" matching for similar tasks.
    """
    
    HIGH_CONFIDENCE = 0.5   # Direct use
    MEDIUM_CONFIDENCE = 0.3  # Suggest for validation
    MIN_SCORE_THRESHOLD = 0.3
    MAX_PATTERNS_TO_CHECK = 50
    
    async def find_best_pattern(
        self, 
        goal_title: str, 
        goal_description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching pattern for a goal with graduated confidence.
        
        Returns:
            Dict with pattern info or None
            Includes 'confidence' field: 'high', 'medium', or 'low'
        """
        query_text = build_embedding_text(goal_title, goal_description)
        query_embedding = embed_text(query_text)
        
        if query_embedding is None:
            logger.warning("embedding_failed_for_goal", title=goal_title[:50])
            return None
        
        patterns = await self._get_patterns_from_db()
        
        if not patterns:
            logger.debug("no_patterns_in_db")
            return None
        
        best_pattern = None
        best_score = 0.0
        
        for pattern in patterns:
            pattern_id = pattern["pattern_id"]
            skill_sequence = pattern["skill_sequence"]
            frequency = pattern["frequency"] or 1
            success_rate = pattern["avg_success_rate"] or 0.5
            embedding = pattern.get("embedding")
            
            if not embedding:
                continue
            
            try:
                import json
                pattern_embedding = json.loads(embedding) if isinstance(embedding, str) else embedding
            except:
                continue
            
            semantic_sim = cosine_similarity(query_embedding, pattern_embedding)
            
            frequency_score = min(frequency / 10.0, 1.0)
            score = semantic_sim * 0.7 + success_rate * 0.2 + frequency_score * 0.1
            
            if score > best_score:
                best_score = score
                best_pattern = {
                    "pattern_id": pattern_id,
                    "skill_sequence": skill_sequence,
                    "semantic_similarity": semantic_sim,
                    "success_rate": success_rate,
                    "frequency": frequency,
                    "score": score
                }
        
        if not best_pattern:
            return None
        
        sim = best_pattern["semantic_similarity"]
        
        if sim >= self.HIGH_CONFIDENCE:
            best_pattern["confidence"] = "high"
            logger.info(
                "semantic_pattern_high_confidence",
                pattern_id=best_pattern["pattern_id"],
                score=round(best_score, 2),
                similarity=round(sim, 2)
            )
            return best_pattern
        
        elif sim >= self.MEDIUM_CONFIDENCE:
            best_pattern["confidence"] = "medium"
            logger.info(
                "semantic_pattern_medium_confidence",
                pattern_id=best_pattern["pattern_id"],
                score=round(best_score, 2),
                similarity=round(sim, 2)
            )
            return best_pattern
        
        logger.debug(
            "semantic_pattern_low_confidence",
            pattern_id=best_pattern["pattern_id"],
            similarity=round(sim, 2)
        )
        return None
    
    async def _get_patterns_from_db(self) -> List[Dict[str, Any]]:
        """Get patterns with embeddings from database.
        
        Filters:
        - Only patterns with embeddings
        - Only patterns with success_rate >= 0.6
        - Skip generic echo patterns
        - Order by success rate first (quality), then frequency
        """
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
                    AND avg_success_rate >= 0.6
                    AND pattern_id != 'core.echo'
                    ORDER BY avg_success_rate DESC, frequency DESC
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
semantic_matcher = SemanticMatcher()
