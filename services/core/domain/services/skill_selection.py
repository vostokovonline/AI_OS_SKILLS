"""
Domain Services - Skill Selection Engine
=========================================
Выбор оптимального навыка на основе capability graph и метрик.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import math

from domain.models.capability import (
    Skill, SkillMetrics, CapabilityGraph, Capability, SkillStatus
)


@dataclass
class SkillSelectionCriteria:
    """Критерии выбора навыка"""
    capability: str
    prefer_speed: bool = False      # Минимизировать latency
    prefer_quality: bool = False    # Максимизировать quality
    prefer_reliability: bool = True # Минимизировать failures
    prefer_cost: bool = False        # Минимизировать cost
    
    # Constraints
    min_success_rate: float = 0.0
    max_latency_seconds: float = float('inf')
    max_cost: float = float('inf')


@dataclass
class SkillSelectionResult:
    """Результат выбора навыка"""
    selected_skill: Optional[Skill]
    candidates: List[Skill]
    scores: Dict[str, float]  # skill_id -> score
    reasoning: str


class SkillSelectionService:
    """
    Доменный сервис для выбора оптимального навыка.
    
    Алгоритм:
    1. Найти все навыки с заданной capability
    2. Отфильтровать по constraints
    3. Ранжировать по weighted score
    4. Вернуть лучший
    
    Score formula:
    score = (success_rate * w_reliability) + 
            (quality * w_quality) + 
            (speed_score * w_speed) +
            (cost_score * w_cost)
    """
    
    # Веса по умолчанию
    DEFAULT_WEIGHTS = {
        "reliability": 0.4,
        "quality": 0.3,
        "speed": 0.2,
        "cost": 0.1,
    }
    
    def __init__(self, capability_graph: CapabilityGraph):
        self.capability_graph = capability_graph
    
    def select_skill(
        self,
        skills: List[Skill],
        criteria: SkillSelectionCriteria
    ) -> SkillSelectionResult:
        """
        Выбрать оптимальный навык.
        """
        # Step 1: Find skills with required capability
        candidates = self._find_candidates(skills, criteria.capability)
        
        if not candidates:
            return SkillSelectionResult(
                selected_skill=None,
                candidates=[],
                scores={},
                reasoning=f"No skills found for capability: {criteria.capability}"
            )
        
        # Step 2: Filter by constraints
        filtered = self._filter_by_constraints(candidates, criteria)
        
        if not filtered:
            # Fallback to unfiltered candidates if all filtered out
            filtered = candidates
            reasoning = f"No skills passed constraints, using all {len(candidates)} candidates"
        else:
            reasoning = f"Filtered to {len(filtered)} candidates"
        
        # Step 3: Rank by score
        scored = self._rank_skills(filtered, criteria)
        
        selected = scored[0][0] if scored else None
        
        return SkillSelectionResult(
            selected_skill=selected,
            candidates=[s for s, _ in scored],
            scores={s.manifest.id: score for s, score in scored},
            reasoning=reasoning
        )
    
    def _find_candidates(self, skills: List[Skill], capability: str) -> List[Skill]:
        """Найти все навыки реализующие capability (включая дочерние)"""
        # Get capability and its children
        cap = self.capability_graph.get_capability(capability)
        if not cap:
            # Fallback: search by manifest directly
            return [s for s in skills if capability in s.manifest.capabilities]
        
        # Include capability and all children
        relevant_capabilities = {cap.id}
        for child in cap.child_capabilities:
            relevant_capabilities.add(child)
        
        # Also include ancestors for fallback
        for ancestor in self.capability_graph.get_all_ancestors(cap.id):
            relevant_capabilities.add(ancestor.id)
        
        # Filter skills
        candidates = []
        for skill in skills:
            if skill.status == SkillStatus.DEPRECATED:
                continue
            if any(c in relevant_capabilities for c in skill.manifest.capabilities):
                candidates.append(skill)
        
        return candidates
    
    def _filter_by_constraints(
        self,
        skills: List[Skill],
        criteria: SkillSelectionCriteria
    ) -> List[Skill]:
        """Фильтрация по hard constraints"""
        filtered = []
        
        for skill in skills:
            metrics = skill.metrics
            
            # Success rate constraint
            if metrics.success_rate < criteria.min_success_rate:
                continue
            
            # Latency constraint
            if criteria.max_latency_seconds < float('inf'):
                if metrics.avg_latency_seconds > criteria.max_latency_seconds:
                    continue
            
            # Cost constraint
            if criteria.max_cost < float('inf'):
                if metrics.avg_cost > criteria.max_cost:
                    continue
            
            filtered.append(skill)
        
        return filtered
    
    def _rank_skills(
        self,
        skills: List[Skill],
        criteria: SkillSelectionCriteria
    ) -> List[tuple]:
        """Ранжирование навыков по weighted score"""
        scored = []
        
        for skill in skills:
            score = self._calculate_score(skill, criteria)
            scored.append((skill, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored
    
    def _calculate_score(self, skill: Skill, criteria: SkillSelectionCriteria) -> float:
        """Вычислить weighted score для навыка"""
        metrics = skill.metrics
        
        # Determine weights based on criteria
        w_rel = 0.4
        w_qual = 0.3
        w_speed = 0.2
        w_cost = 0.1
        
        if criteria.prefer_speed:
            w_speed, w_qual = 0.5, 0.1
        elif criteria.prefer_quality:
            w_qual, w_speed = 0.5, 0.1
        elif criteria.prefer_cost:
            w_cost, w_rel = 0.4, 0.2
        
        # Calculate component scores
        # Success rate (0-1)
        success_score = metrics.success_rate
        
        # Quality (0-1)
        quality_score = min(metrics.avg_quality_score, 1.0)
        
        # Speed score (inverse of latency, normalized)
        if metrics.avg_latency_seconds > 0:
            # Lower latency = higher score
            speed_score = 1.0 / (1.0 + metrics.avg_latency_seconds)
        else:
            speed_score = 1.0
        
        # Cost score (inverse of cost, normalized)
        if metrics.avg_cost > 0:
            cost_score = 1.0 / (1.0 + metrics.avg_cost)
        else:
            cost_score = 1.0
        
        # Apply confidence penalty (if few samples)
        if metrics.sample_count < 10:
            confidence_penalty = metrics.sample_count / 10
            success_score *= confidence_penalty
            quality_score *= confidence_penalty
        
        # Weighted sum
        total_score = (
            success_score * w_rel +
            quality_score * w_qual +
            speed_score * w_speed +
            cost_score * w_cost
        )
        
        return total_score
    
    def get_best_alternative(
        self,
        skills: List[Skill],
        failed_skill_id: str,
        criteria: SkillSelectionCriteria
    ) -> Optional[Skill]:
        """
        Получить лучшую альтернативу если основной навык не работает.
        """
        candidates = [
            s for s in skills 
            if s.manifest.id != failed_skill_id 
            and s.status != SkillStatus.DEPRECATED
        ]
        
        result = self.select_skill(candidates, criteria)
        return result.selected_skill
