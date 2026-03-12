"""
Trace Mining Engine - Анализи traces и извлекает паттерны

Основные функции:
1. Skill Success Rate - лучший skill для типа задачи
2. Pattern Detection - цепочки действий
3. Strategy Extraction - оптимальные стратегии
4. Cognitive Cache - быстрые решения без LLM
"""
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import asyncio


class TraceMiningEngine:
    """
    Анализирует execution traces и извлекает паттерны для обучения системы.
    """
    
    def __init__(self, trace_store):
        self.trace_store = trace_store
        self._cognitive_cache: Dict[str, Dict[str, Any]] = {}
        self._compiled_strategies: Dict[str, List[str]] = {}
        
    async def analyze_all(self) -> Dict[str, Any]:
        """Полный анализ всех traces"""
        traces = await self.trace_store.get_all_traces(limit=1000)
        
        return {
            "skill_success_rate": await self.analyze_skill_success_rate(traces),
            "skill_usage": await self.analyze_skill_usage(traces),
            "patterns": await self.detect_patterns(traces),
            "strategies": await self.extract_strategies(traces),
            "cognitive_cache": self._cognitive_cache,
            "compiled_strategies": self._compiled_strategies
        }
    
    async def analyze_skill_success_rate(self, traces: List[dict]) -> Dict[str, float]:
        """Подсчитать success rate для каждого skill"""
        skill_results: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
        
        for trace in traces:
            status = trace.get("status")
            if not status:
                continue
            
            # Extract goal title for context
            goal_title = ""
            for event in trace.get("events", []):
                if event["type"] == "GoalExecutionStarted":
                    goal_title = event["data"].get("goal_title", "")
                    
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    skill = event["data"].get("skill_name", "unknown")
                    
                    # Create key with goal context
                    key = f"{skill}"
                    skill_results[key]["total"] += 1
                    
                    if status == "completed":
                        skill_results[key]["success"] += 1
        
        # Calculate rates
        rates = {}
        for skill, stats in skill_results.items():
            if stats["total"] > 0:
                rates[skill] = {
                    "success_rate": stats["success"] / stats["total"],
                    "total": stats["total"],
                    "successes": stats["success"]
                }
            else:
                rates[skill] = {"success_rate": 0.0, "total": 0, "successes": 0}
        
        return rates
    
    async def analyze_skill_usage(self, traces: List[dict]) -> Dict[str, int]:
        """Подсчитать использование каждого skill"""
        usage = defaultdict(int)
        
        for trace in traces:
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    skill = event["data"].get("skill_name", "unknown")
                    usage[skill] += 1
        
        return dict(usage)
    
    async def detect_patterns(self, traces: List[dict]) -> Dict[str, Any]:
        """Обнаружить паттерны - цепочки действий"""
        patterns: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
        
        for trace in traces:
            status = trace.get("status")
            
            # Extract skill chain
            chain = []
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    chain.append(event["data"].get("skill_name", "unknown"))
            
            if chain:
                chain_key = tuple(chain)
                patterns[chain_key]["total"] += 1
                if status == "completed":
                    patterns[chain_key]["success"] += 1
        
        # Convert to sorted list
        pattern_list = []
        for chain, stats in patterns.items():
            rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            pattern_list.append({
                "chain": list(chain),
                "success_rate": rate,
                "total": stats["total"],
                "successes": stats["success"]
            })
        
        # Sort by success rate
        pattern_list.sort(key=lambda x: (x["success_rate"], x["total"]), reverse=True)
        
        return {
            "patterns": pattern_list[:20],  # Top 20
            "total_patterns": len(pattern_list)
        }
    
    async def extract_strategies(self, traces: List[dict]) -> Dict[str, List[str]]:
        """Извлечь оптимальные стратегии - лучшие цепочки для типов задач"""
        strategies = {}
        
        # Group by goal title keywords
        goal_strategies: Dict[str, List[Tuple[List[str], float, int]]] = defaultdict(list)
        
        for trace in traces:
            status = trace.get("status")
            goal_title = ""
            
            for event in trace.get("events", []):
                if event["type"] == "GoalExecutionStarted":
                    goal_title = event["data"].get("goal_title", "")
            
            if not goal_title:
                continue
            
            # Extract skill chain
            chain = []
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    chain.append(event["data"].get("skill_name", "unknown"))
            
            if not chain:
                continue
            
            # Categorize by keywords
            goal_lower = goal_title.lower()
            
            if "summarize" in goal_lower or "summary" in goal_lower:
                key = "summarize"
            elif "research" in goal_lower or "search" in goal_lower:
                key = "research"
            elif "write" in goal_lower or "create" in goal_lower:
                key = "write"
            elif "analyze" in goal_lower:
                key = "analyze"
            else:
                key = "general"
            
            success = 1.0 if status == "completed" else 0.0
            goal_strategies[key].append((chain, success, 1))
        
        # Find best strategy for each category
        for key, chains in goal_strategies.items():
            if not chains:
                continue
                
            # Aggregate
            chain_scores: Dict[Tuple[str, ...], List[float]] = defaultdict(list)
            for chain, success, _ in chains:
                chain_scores[tuple(chain)].append(success)
            
            # Find best
            best_chain = None
            best_rate = 0.0
            for chain, successes in chain_scores.items():
                rate = sum(successes) / len(successes)
                if rate > best_rate:
                    best_rate = rate
                    best_chain = chain
            
            if best_chain:
                strategies[key] = {
                    "chain": list(best_chain),
                    "success_rate": best_rate
                }
        
        return strategies
    
    async def build_cognitive_cache(self) -> Dict[str, Dict[str, Any]]:
        """Построить Cognitive Cache - быстрые решения без LLM по goal_type"""
        traces = await self.trace_store.get_all_traces(limit=500)
        
        goal_type_skills: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        for trace in traces:
            goal_type = trace.get("goal_type", "")
            if not goal_type:
                continue
            
            skill_name = trace.get("skill_name", "")
            status = trace.get("status", "")
            
            if goal_type not in goal_type_skills:
                goal_type_skills[goal_type] = {}
            
            if skill_name:
                if skill_name not in goal_type_skills[goal_type]:
                    goal_type_skills[goal_type][skill_name] = {"success": 0, "total": 0}
                
                goal_type_skills[goal_type][skill_name]["total"] += 1
                if status == "completed":
                    goal_type_skills[goal_type][skill_name]["success"] += 1
        
        cache = {}
        for goal_type, skills in goal_type_skills.items():
            best_skill = None
            best_rate = 0.0
            best_count = 0
            
            for skill, stats in skills.items():
                rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0.0
                if stats["total"] >= 1 and (rate > best_rate or (rate == best_rate and stats["total"] > best_count)):
                    best_rate = rate
                    best_count = stats["total"]
                    best_skill = skill
            
            if best_skill:
                cache[goal_type] = {
                    "skill": best_skill,
                    "confidence": best_rate,
                    "usage_count": best_count
                }
        
        self._cognitive_cache = cache
        return cache
    
    async def get_best_skill(self, goal_title: str = "", goal_type: str = "") -> Optional[str]:
        """Получить лучший skill для goal без LLM
        
        Args:
            goal_title: Title of the goal (for fallback keyword matching)
            goal_type: Type of the goal (achievable, continuous, directional, exploratory, meta)
        """
        if not self._cognitive_cache:
            await self.build_cognitive_cache()
        
        if not self._cognitive_cache:
            return None
        
        if goal_type and goal_type in self._cognitive_cache:
            return self._cognitive_cache[goal_type]["skill"]
        
        if goal_title:
            goal_lower = goal_title.lower()
            
            for cached_type, info in self._cognitive_cache.items():
                if cached_type.lower() in goal_lower or goal_lower in cached_type.lower():
                    return info["skill"]
            
            best = max(self._cognitive_cache.items(), 
                      key=lambda x: (x[1]["confidence"], x[1]["usage_count"]))
            return best[1]["skill"]
        
        return None
    
    async def get_best_skill_by_type(self, goal_type: str) -> Optional[Dict[str, Any]]:
        """Получить лучший skill для конкретного goal_type"""
        if not self._cognitive_cache:
            await self.build_cognitive_cache()
        
        return self._cognitive_cache.get(goal_type)
    
    async def compile_strategies(self) -> Dict[str, List[str]]:
        """Скомпилировать стратегии для быстрого выполнения"""
        traces = await self.trace_store.get_all_traces(limit=500)
        
        # Extract strategies
        strategies = await self.extract_strategies(traces)
        
        # Store compiled
        compiled = {}
        for key, info in strategies.items():
            compiled[key] = info.get("chain", [])
        
        self._compiled_strategies = compiled
        return compiled
    
    async def get_recommendation(self, goal_title: str) -> Dict[str, Any]:
        """Получить рекомендацию для goal - skill + стратегия"""
        # Try cached skill
        best_skill = await self.get_best_skill(goal_title)
        
        # Try compiled strategy
        goal_lower = goal_title.lower()
        strategy = None
        
        for key, chain in self._compiled_strategies.items():
            if key in goal_lower:
                strategy = chain
                break
        
        return {
            "goal_title": goal_title,
            "recommended_skill": best_skill,
            "compiled_strategy": strategy,
            "source": "trace_mining"
        }


# Global instance
_mining_engine = None


def get_mining_engine(trace_store=None) -> TraceMiningEngine:
    """Get or create mining engine"""
    global _mining_engine
    if _mining_engine is None:
        if trace_store is None:
            from trace_store import get_trace_store
            trace_store = get_trace_store()
        _mining_engine = TraceMiningEngine(trace_store)
    return _mining_engine
