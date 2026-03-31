"""
Plan Memory v7 - Hierarchical Multi-Armed Bandit

Key fixes over v6:
1. Two-level selection: abstract_strategy → concrete_strategy
2. Bayesian calculated once per strategy (not per-experience)
3. Confidence BONUS instead of penalty (exploitation = good)
4. Failure insights → planner constraints (adaptive replanning)
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from typing import Dict as TypeDict
from dataclasses import dataclass, field
import time
import re
import math
import random


PATTERN_TYPES = {
    "structural_failures": {
        "infinite_loop",
        "cyclic_dependency",
        "no_validation",
        "missing_error_handling",
        "memory_leak",
        "deadlock",
    },
}

FAILURE_CATEGORIES = {
    "rate_limit": ["429", "rate limit", "too many requests", "throttl"],
    "timeout": ["timeout", "timed out", "connection reset", "too slow"],
    "authentication": ["401", "403", "auth", "token", "unauthorized", "forbidden"],
    "not_found": ["404", "not found", "does not exist", "missing"],
    "server_error": ["500", "502", "503", "server error", "internal error"],
    "network": ["connection", "network", "dns", "refused"],
    "parse_error": ["parse", "json error", "cannot decode", "invalid format"],
    "quota": ["quota", "limit exceeded", "daily limit"],
}

FAILURE_SEVERITY = {
    "rate_limit": "recoverable",
    "timeout": "recoverable",
    "not_found": "recoverable",
    "quota": "recoverable",
    "network": "recoverable",
    "server_error": "recoverable",
    "parse_error": "recoverable",
    "authentication": "fatal",
    "permission_denied": "fatal",
}

RECOVERABLE_PENALTY_FACTOR = 0.3
FATAL_PENALTY_FACTOR = 0.8

FAILURE_PENALTY_EXPONENT = 1.5
DECAY_HALF_LIFE_HOURS = 24

DECAY_TAU_ITERATIONS = 10  # Time constant for decay (in iterations)
# weight = exp(-age / tau), so after tau iterations weight = 0.36, after 3*tau = 0.05

BLACKLIST_THRESHOLD = 2
BLACKLIST_COOLDOWN_HOURS = 24


STRATEGY_ABSTRACTION = {
    "web_scraping": "unstructured_data_acquisition",
    "web_crawling": "unstructured_data_acquisition",
    "regex_html_parsing": "unstructured_data_acquisition",
    "html_parsing": "unstructured_data_acquisition",
    "api_fetch": "structured_data_acquisition",
    "external_api_call": "structured_data_acquisition",
    "database_fetch": "structured_data_acquisition",
    "cached_data": "cached_data_retrieval",
    "bulk_write": "bulk_data_operation",
    "parallelism": "concurrent_execution",
    "uncontrolled_parallelism": "concurrent_execution",
    "synchronous_blocking": "synchronous_execution",
    "single_threaded_execution": "sequential_execution",
    "unreliable_pattern": "fault_tolerant_execution",
}


FAILURE_MITIGATIONS = {
    "rate_limit": "add retry_with_backoff OR use rate_limited alternative",
    "authentication": "refresh token OR use service_account",
    "timeout": "add async/retry OR increase timeout",
    "anti_bot": "use official API OR add proxy rotation",
    "data_quality": "add validation OR use alternative source",
    "availability": "add fallback_source OR use cached_data",
    "parse_error": "improve parser OR use structured format",
    "resource_exhaustion": "add resource limits OR batch processing",
}


FAILURE_REASON_PATTERNS = {
    "rate_limit": [r"rate.?limit", r"429", r"too.?many.?requests", r"throttl"],
    "authentication": [r"auth", r"401", r"403", r"token.?expired", r"unauthorized"],
    "timeout": [r"timeout", r"timed.?out", r"connection.?reset", r"too.?slow"],
    "anti_bot": [r"captcha", r"blocked", r"403", r"robot", r"denied"],
    "data_quality": [r"invalid", r"malformed", r"corrupt", r"empty.?response"],
    "availability": [r"503", r"unavailable", r"down", r"not.?found", r"404"],
    "parse_error": [r"parse", r"json.?error", r"xml.?error", r"cannot.?decode"],
    "resource_exhaustion": [r"memory", r"cpu", r"disk.?full", r"out.?of.?memory"],
}


@dataclass
class FailureReason:
    """Why a strategy failed in this context."""
    reason: str
    frequency: int
    examples: List[str] = field(default_factory=list)


@dataclass
class PatternExperience:
    """Single experience with a strategy in a context."""
    strategy: str
    abstract_strategy: str
    success: bool
    goal_embedding: List[float]
    goal_context: str
    timestamp: float
    failure_reasons: List[FailureReason] = field(default_factory=list)


@dataclass
class StoredPlan:
    """Plan with accumulated experiences."""
    goal: str
    embedding: List[float]
    tasks: List[Dict]
    patterns: List[str] = field(default_factory=list)
    experiences: List[PatternExperience] = field(default_factory=list)
    last_used: float = field(default_factory=lambda: time.time())
    created_at: float = field(default_factory=lambda: time.time())
    metadata: TypeDict[str, Any] = field(default_factory=dict)


@dataclass
class AbstractStrategyScore:
    """Score for an abstract strategy type."""
    abstract_strategy: str
    expected_value: float
    bayesian_success_rate: float
    uncertainty: float
    attempts: int
    is_structural: bool
    failure_insights: List[Dict]
    failure_penalty: float = 0.0


@dataclass
class ConcreteStrategyScore:
    """Score for a concrete implementation."""
    strategy: str
    abstract_strategy: str
    expected_value: float
    bayesian_success_rate: float
    uncertainty: float
    attempts: int
    failure_insights: List[Dict]
    mitigations: List[str]
    failure_penalty: float = 0.0


@dataclass
class MemoryHint:
    goal: str
    tasks: List[Dict]
    score: float
    success_rate: float


class PlanMemory:
    """
    Hierarchical Multi-Armed Bandit Memory.
    
    Key concepts:
    1. Two-level selection: abstract → concrete
    2. Bayesian estimated once per strategy
    3. Confidence bonus (exploitation reward)
    4. Failure insights → mitigations for planner
    """
    
    STRONG_CONFIDENCE = 0.8
    MEDIUM_CONFIDENCE = 0.5
    RECENCY_DECAY = 0.1
    MIN_SIMILARITY = 0.3
    BAYESIAN_PRIOR = 1.0
    
    EXPLORATION_RATE = 0.1
    FAILURE_DECAY = 0.95
    UNCERTAINTY_BONUS = 0.4
    UCB_EXPLORATION_CONST = 1.4
    
    # Mode control (explore/probe/exploit)
    DECAY_HISTORY = 5
    DECAY_THRESHOLD = 0.6
    PROBE_ATTEMPTS = 3
    
    # Thompson Sampling parameters
    DECAY_TAU_ITERATIONS = 10  # Time constant for decay
    RECENCY_WEIGHT = 0.3  # Weight for recency in final score
    
    # Forced re-exploration (coverage guarantee)
    REEXPLORE_ITERATIONS = 20  # Force re-check strategy after N iterations (reduced for testing)
    REEXPLORE_PROBABILITY = 0.3  # Probability to recheck if overdue
    
    # Artifact system
    ARTIFACT_TTL_SECONDS = 300  # 5 minutes TTL
    ARTIFACT_MAX_SIZE = 1000  # Max artifacts in store
    ARTIFACT_MIN_SUCCESS_RATE = 0.5  # Only cache if success rate > 50%
    
    def __init__(self, storage_path: str = "/app/plan_memory.json"):
        self.plans: List[StoredPlan] = []
        self._embed_func = None
        self._cache: Dict[str, List[float]] = {}
        self._storage_path = storage_path
        self._strategy_scores: Dict[str, Dict[str, Any]] = {}
        
        self._mode = "explore"
        self._probe_candidate: Optional[str] = None
        self._probe_successes = 0
        self._probe_attempts = 0
        self._locked_strategy: Optional[str] = None
        
        self._exploit_history: List[bool] = []
        self._iteration_count = 0
        self._total_experience_cache: int = 0
        
        # Context bandit: track last seen iteration per (goal_type, strategy)
        self._last_seen: Dict[Tuple[str, str], int] = {}
        
        # Artifact system
        self._artifacts: Dict[str, Dict[str, Any] ] = {}  # key -> {value, strategy, timestamp, success, usage_count}
        
        self._load()
        self._load_blacklist()
    
    def _get_recent_success_rate(self) -> float:
        """Calculate success rate over last k attempts"""
        if not self._exploit_history:
            return 1.0
        recent = self._exploit_history[-self.DECAY_HISTORY:]
        if not recent:
            return 1.0
        return sum(recent) / len(recent)
    
    def get_mode(self) -> str:
        return self._mode
    
    def get_locked_strategy(self) -> Optional[str]:
        return self._locked_strategy
    
    def _update_mode(self, strategy: str, success: bool) -> None:
        # Clock is already incremented in select_strategy
        # Do NOT increment here - causes double tick
        
        if self._mode == "exploit" and strategy == self._locked_strategy:
            self._exploit_history.append(success)
            if len(self._exploit_history) > 20:
                self._exploit_history = self._exploit_history[-20:]
            
            recent_rate = self._get_recent_success_rate()
            if recent_rate < self.DECAY_THRESHOLD:
                print(f"[DECAY] Success rate {recent_rate:.2f} < {self.DECAY_THRESHOLD}, returning to explore")
                self._mode = "explore"
                self._locked_strategy = None
                self._exploit_history = []
                return
        
        if self._mode == "explore":
            if success:
                self._mode = "probe"
                self._probe_candidate = strategy
                self._probe_successes = 1
                self._probe_attempts = 1
                self._probe_just_started = True
                self._locked_strategy = None  # Clear locked when starting new probe
                print(f"[PROBE] Started probing: {strategy}")
        
        elif self._mode == "probe":
            if strategy == self._probe_candidate:
                self._probe_attempts += 1
                if success:
                    self._probe_successes += 1
                
                if self._probe_attempts >= self.PROBE_ATTEMPTS:
                    if self._probe_successes >= 2:
                        self._mode = "exploit"
                        self._locked_strategy = self._probe_candidate
                        print(f"[EXPLOIT] Locked to: {self._locked_strategy}")
                    else:
                        self._mode = "explore"
                        print(f"[PROBE] Failed, back to explore")
                        self._probe_candidate = None
            # PROBE IS LOCKED - no switching candidates
            # Even if different strategy was executed, we ignore it
        
        elif self._mode == "exploit":
            if strategy == self._locked_strategy:
                if not success:
                    print(f"[EXPLOIT] Locked strategy failed, returning to explore")
                    self._mode = "explore"
                    self._locked_strategy = None
            else:
                if success:
                    print(f"[EXPLOIT] ε-exploration found better option: {strategy}")
                    self._mode = "probe"
                    self._probe_candidate = strategy
                    self._probe_successes = 1
                    self._probe_attempts = 1
                    self._probe_just_started = True
                    self._locked_strategy = None  # Clear locked when switching to better option
                    print(f"[PROBE] Started probing: {strategy}")
    
    EPSILON = 0.25  # 25% exploration in exploit mode
    RECOVERY_BOOST = 0.3  # Boost for strategies that previously failed but might recover

    def select_strategy(self, strategies: List[str]) -> str:
        # Thompson Sampling core: tick clock once per selection
        self._iteration_count += 1
        
        # PROBE MODE: Locked to single candidate - NO exploration allowed
        if self._mode == "probe" and self._probe_candidate:
            print(f"[PROBE] Probing: {self._probe_candidate}")
            return self._probe_candidate
        
        # EXPLOIT MODE: Use Thompson Sampling (natural exploration via distribution)
        if self._mode == "exploit" and self._locked_strategy:
            if self._locked_strategy in strategies:
                print(f"[EXPLOIT] Using locked: {self._locked_strategy}")
                return self._locked_strategy
            else:
                print(f"[EXPLOIT] Strategy not available, explore mode")
                self._mode = "explore"
                self._locked_strategy = None
        
        # Thompson Sampling with Recency + Forced Re-exploration
        import random
        best_strategy = strategies[0] if strategies else "unknown"
        best_score = -1.0
        
        for s in strategies:
            # FORCED RE-EXPLORATION: Check if strategy needs re-check
            if self._should_force_rexplore(s):
                print(f"[REXPLORE] Forcing re-check of {s}")
                return s
            
            # Get Thompson sample
            ts_sample = self._get_thompson_sample(s)
            
            # RECENCY BOOST: Give slight boost to recent strategies
            key = ("default", s)
            last_seen = self._last_seen.get(key, 0)
            recency = 1.0 + self.RECENCY_WEIGHT * (1.0 - min(1.0, (self._iteration_count - last_seen) / 50))
            
            final_score = ts_sample * recency
            
            if final_score > best_score:
                best_score = final_score
                best_strategy = s
        
        # Track selection for re-exploration tracking
        self._last_seen[("default", best_strategy)] = self._iteration_count
        
        return best_strategy
    
    def _get_thompson_sample(self, strategy: str) -> float:
        """Pure Thompson Sampling: sample from Beta distribution"""
        import random
        
        if strategy not in self._strategy_scores:
            # New strategy: uniform prior - will explore naturally
            return random.betavariate(1.0, 1.0)
        
        weighted_s, weighted_f, total_trials = self._get_weighted_counts(strategy)
        
        # Prior that fades with experience
        prior_scale = 2.0 / (2.0 + total_trials)
        
        alpha = weighted_s + prior_scale
        beta = weighted_f + prior_scale
        
        try:
            return random.betavariate(alpha, beta)
        except (ValueError, ZeroDivisionError):
            return 0.5
    
    def get_strategy_score(self, strategy: str) -> float:
        """Calculate score using weighted Beta distribution with time decay"""
        if strategy not in self._strategy_scores:
            self._strategy_scores[strategy] = {"success_times": [], "fail_times": []}
        
        # Use weighted counts (returns 3-tuple now)
        weighted_s, weighted_f, _ = self._get_weighted_counts(strategy)
        
        # Beta distribution with Laplace smoothing
        score = (weighted_s + 1) / (weighted_s + weighted_f + 2)
        return score
    
    def get_total_trials(self) -> int:
        """Get total trials across all strategies"""
        total = 0
        for stats in self._strategy_scores.values():
            total += stats["success"] + stats["fail"]
        return total
    
    # Old UCB methods removed - using pure Thompson Sampling now
    # See _get_thompson_sample() for the sampling logic
    
    def _get_weighted_counts(self, strategy: str) -> tuple:
        """
        Calculate commitment multiplier based on recent success rate.
        
        commitment = 1 + bonus * recent_success_rate
        bonus = 0.3 (max 30% boost)
        
        This helps system "lock in" to good strategies instead of constantly exploring.
        """
        if strategy not in self._strategy_scores:
            return 1.0
        
        stats = self._strategy_scores[strategy]
        success_times = stats.get("success_times", [])
        fail_times = stats.get("fail_times", [])
        
        # Need at least 3 trials for meaningful commitment
        total = len(success_times) + len(fail_times)
        if total < 3:
            return 1.0
        
        # Calculate recent success rate (last 5 trials)
        recent_k = 5
        recent_successes = 0
        recent_total = 0
        
        # Check recent successes (last K from combined history)
        all_recent = []
        for s in success_times[-recent_k:]:
            all_recent.append((s, True))
        for f in fail_times[-recent_k:]:
            all_recent.append((f, False))
        
        all_recent.sort(reverse=True)  # Most recent first
        
        for _, is_success in all_recent:
            recent_total += 1
            if is_success:
                recent_successes += 1
        
        if recent_total == 0:
            return 1.0
        
        recent_rate = recent_successes / recent_total
        
        # Max 30% bonus when recent success rate is high
        COMMITMENT_BONUS = 0.3
        multiplier = 1.0 + COMMITMENT_BONUS * recent_rate
        
        return multiplier
    
    MAX_HISTORY_SIZE = 50  # Bounded memory - only keep last 50 events for decay calculation
    
    def _get_weighted_counts(self, strategy: str) -> tuple:
        """
        Calculate weighted success/fail counts with ITERATION-BASED decay.
        
        Returns:
            (weighted_success, weighted_fail, total_trials)
            
        Key insight:
        - weighted counts: iteration-based decay for consistent behavior
        - total_trials: NEVER truncated, for stable exploration term
        - priors: prevent complete weight loss for old good strategies
        """
        import math
        
        if strategy not in self._strategy_scores:
            return 0.0, 0.0, 0
        
        stats = self._strategy_scores[strategy]
        tau = self.DECAY_TAU_ITERATIONS  # Logical clock (iterations)
        
        # total_trials - NEVER truncated (stores true experience)
        total_trials = stats.get("total_trials", 0)
        
        # Get bounded iteration counts for decay calculation
        success_iterations = stats.get("success_times", [])[-self.MAX_HISTORY_SIZE:]
        fail_iterations = stats.get("fail_times", [])[-self.MAX_HISTORY_SIZE:]
        
        weighted_success = 0.0
        weighted_fail = 0.0
        
        # LOGICAL-CLOCK decay (iterations)
        # This ensures consistent behavior in tests and production
        current_clock = getattr(self, '_iteration_count', 0)
        
        for it in success_iterations:
            age = current_clock - it  # Logical age in iterations
            weight = math.exp(-age / tau) if tau > 0 else 1.0
            weighted_success += weight
        
        for it in fail_iterations:
            age = current_clock - it
            weight = math.exp(-age / tau) if tau > 0 else 1.0
            weighted_fail += weight
        
        # Scale priors by experience: strong at first, fading with trials
        # This prevents priors from dominating after many trials
        prior_scale = 1.0 / (1.0 + total_trials)
        weighted_success += prior_scale
        weighted_fail += prior_scale
        
        return weighted_success, weighted_fail, total_trials
    
    def get_strategy_uncertainty(self, strategy: str) -> float:
        """Uncertainty decreases with total_trials (NOT bounded history)"""
        if strategy not in self._strategy_scores:
            return 1.0
        
        total_trials = self._strategy_scores[strategy].get("total_trials", 0)
        
        return 1.0 / (total_trials + 1)
    
    def record_strategy_success(self, strategy: str) -> None:
        """Record successful execution of strategy (logical clock already incremented in select)"""
        if strategy not in self._strategy_scores:
            self._strategy_scores[strategy] = {"success_times": [], "fail_times": [], "total_trials": 0}
        
        # Increment total_trials and cache (O(1))
        self._strategy_scores[strategy]["total_trials"] = \
            self._strategy_scores[strategy].get("total_trials", 0) + 1
        self._total_experience_cache += 1
        
        # Store CURRENT iteration (clock already ticked in select_strategy)
        self._strategy_scores[strategy]["success_times"].append(self._iteration_count)
        
        # Keep only last MAX_HISTORY_SIZE for decay calculation
        if len(self._strategy_scores[strategy]["success_times"]) > self.MAX_HISTORY_SIZE:
            self._strategy_scores[strategy]["success_times"] = \
                self._strategy_scores[strategy]["success_times"][-self.MAX_HISTORY_SIZE:]
    
    def record_strategy_failure(self, strategy: str) -> None:
        """Record failed execution of strategy (logical clock already incremented in select)"""
        if strategy not in self._strategy_scores:
            self._strategy_scores[strategy] = {"success_times": [], "fail_times": [], "total_trials": 0}
        
        # Increment total_trials and cache (O(1))
        self._strategy_scores[strategy]["total_trials"] = \
            self._strategy_scores[strategy].get("total_trials", 0) + 1
        self._total_experience_cache += 1
        
        # Store CURRENT iteration (clock already ticked in select_strategy)
        self._strategy_scores[strategy]["fail_times"].append(self._iteration_count)
        
        # Track last seen for forced re-exploration
        self._last_seen[(strategy, strategy)] = self._iteration_count
        
        # Keep only last MAX_HISTORY_SIZE for decay calculation
        if len(self._strategy_scores[strategy]["fail_times"]) > self.MAX_HISTORY_SIZE:
            self._strategy_scores[strategy]["fail_times"] = \
                self._strategy_scores[strategy]["fail_times"][-self.MAX_HISTORY_SIZE:]
    
    # ========================================================================
    # FORCED RE-EXPLORATION (Coverage Guarantee)
    # ========================================================================
    
    def _should_force_rexplore(self, strategy: str) -> bool:
        """Check if strategy should be forced re-explored due to age"""
        key = ("default", strategy)  # Using "default" as goal_type for now
        last_seen = self._last_seen.get(key, 0)
        age = self._iteration_count - last_seen
        
        if age > self.REEXPLORE_ITERATIONS:
            return random.random() < self.REEXPLORE_PROBABILITY
        return False
    
    # ========================================================================
    # ARTIFACT SYSTEM
    # ========================================================================
    
    def get_artifact(self, goal_type: str, input_key: str) -> Optional[Dict]:
        """Get cached artifact if valid"""
        key = f"{goal_type}:{input_key}"
        artifact = self._artifacts.get(key)
        
        if not artifact:
            return None
        
        import time
        age = time.time() - artifact.get("timestamp", 0)
        
        # Check TTL
        if age > self.ARTIFACT_TTL_SECONDS:
            del self._artifacts[key]
            return None
        
        # Check success rate
        if artifact.get("success_count", 0) / max(artifact.get("usage_count", 1), 1) < self.ARTIFACT_MIN_SUCCESS_RATE:
            return None
        
        artifact["usage_count"] = artifact.get("usage_count", 0) + 1
        return artifact
    
    def store_artifact(self, goal_type: str, input_key: str, result: Any, strategy: str, success: bool) -> None:
        """Store result as artifact if worth caching"""
        if not success:
            return  # Don't cache failures
        
        key = f"{goal_type}:{input_key}"
        
        # Initialize or update
        if key not in self._artifacts:
            self._artifacts[key] = {
                "value": result,
                "strategy": strategy,
                "timestamp": 0,
                "success_count": 0,
                "usage_count": 0
            }
        
        artifact = self._artifacts[key]
        import time
        artifact["timestamp"] = time.time()
        artifact["strategy"] = strategy
        artifact["success_count"] = artifact.get("success_count", 0) + 1
        artifact["value"] = result
        
        # Enforce max size (LRU-like eviction)
        if len(self._artifacts) > self.ARTIFACT_MAX_SIZE:
            # Remove oldest
            oldest_key = min(self._artifacts.keys(), 
                           key=lambda k: self._artifacts[k].get("timestamp", 0))
            del self._artifacts[oldest_key]
    
    def get_strategy_stats(self, strategy: str) -> Dict[str, int]:
        """Get success/fail counts for strategy"""
        return self._strategy_scores.get(strategy, {"success": 0, "fail": 0})
    
    def _load(self):
        """Load plans from disk."""
        import os
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, "r") as f:
                import json
                data = json.load(f)
                self.plans = []
                for p in data:
                    experiences = []
                    for e in p.get("experiences", []):
                        failure_reasons = [
                            FailureReason(
                                reason=fr["reason"],
                                frequency=fr["frequency"],
                                examples=fr.get("examples", [])
                            )
                            for fr in e.get("failure_reasons", [])
                        ]
                        experiences.append(PatternExperience(
                            strategy=e["strategy"],
                            abstract_strategy=e.get("abstract_strategy", ""),
                            success=e["success"],
                            goal_embedding=e["goal_embedding"],
                            goal_context=e.get("goal_context", ""),
                            timestamp=e.get("timestamp", time.time()),
                            failure_reasons=failure_reasons
                        ))
                    plan = StoredPlan(
                        goal=p["goal"],
                        embedding=p["embedding"],
                        tasks=p["tasks"],
                        patterns=p.get("patterns", []),
                        experiences=experiences,
                        last_used=p.get("last_used", time.time()),
                        created_at=p.get("created_at", time.time()),
                        metadata=p.get("metadata", {})
                    )
                    self.plans.append(plan)
        except Exception as e:
            print(f"Memory load failed: {e}")
    
    def _save(self):
        """Save plans to disk."""
        try:
            import json
            data = [
                {
                    "goal": p.goal,
                    "embedding": p.embedding,
                    "tasks": p.tasks,
                    "patterns": p.patterns,
                    "experiences": [
                        {
                            "strategy": e.strategy,
                            "abstract_strategy": e.abstract_strategy,
                            "success": e.success,
                            "goal_embedding": e.goal_embedding,
                            "goal_context": e.goal_context,
                            "timestamp": e.timestamp,
                            "failure_reasons": [
                                {
                                    "reason": fr.reason,
                                    "frequency": fr.frequency,
                                    "examples": fr.examples
                                }
                                for fr in e.failure_reasons
                            ]
                        }
                        for e in p.experiences
                    ],
                    "last_used": p.last_used,
                    "created_at": p.created_at,
                    "metadata": p.metadata
                }
                for p in self.plans
            ]
            with open(self._storage_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Memory save failed: {e}")
    
    def _get_embed(self):
        if self._embed_func is None:
            try:
                from semantic.embedding_service import embed_text
                self._embed_func = embed_text
            except ImportError:
                self._embed_func = lambda x: None
        return self._embed_func
    
    def _embed(self, text: str) -> Optional[List[float]]:
        if text in self._cache:
            return self._cache[text]
        func = self._get_embed()
        vec = func(text)
        if vec is not None and len(self._cache) < 100:
            self._cache[text] = vec
        return vec
    
    def _cosine(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
    
    def _get_abstract_strategy(self, concrete: str) -> str:
        """Map concrete strategy to abstract type."""
        return STRATEGY_ABSTRACTION.get(concrete.lower(), "general_strategy")
    
    def _extract_failure_reasons(self, error_message: str) -> List[FailureReason]:
        """Extract WHY the strategy failed."""
        error_lower = error_message.lower()
        reasons: List[FailureReason] = []
        
        for reason_name, patterns in FAILURE_REASON_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_lower):
                    reasons.append(FailureReason(
                        reason=reason_name,
                        frequency=1,
                        examples=[error_message[:100]]
                    ))
                    break
        
        if not reasons:
            reasons.append(FailureReason(
                reason="unknown",
                frequency=1,
                examples=[error_message[:100]]
            ))
        
        return reasons
    
    def _get_pattern_type(self, pattern: str) -> str:
        """Determine if pattern is structural (hard) or contextual."""
        pattern_lower = pattern.lower()
        if pattern_lower in PATTERN_TYPES.get("structural_failures", set()):
            return "structural_failures"
        return "contextual_failures"
    
    def _extract_strategy(self, task: Dict) -> str:
        """Extract the CONCRETE strategy from a task."""
        desc = task.get("description", "").lower()
        
        strategy_patterns = [
            (r'web\s*scrap', 'web_scraping'),
            (r'crawl', 'web_crawling'),
            (r'regex.*html', 'regex_html_parsing'),
            (r'html\s*pars', 'html_parsing'),
            (r'api\s*call|external\s*api', 'external_api_call'),
            (r'without\s*(retry|cache|fallback)', 'unreliable_pattern'),
            (r'parallel.*all', 'uncontrolled_parallelism'),
            (r'bulk\s*insert', 'bulk_write'),
            (r'sync.*call', 'synchronous_blocking'),
            (r'single\s*thread', 'single_threaded_execution'),
            (r'without\s*validation', 'no_validation'),
            (r'memory.*intensive', 'memory_inefficient'),
            (r'nested.*loop', 'nested_loop_inefficiency'),
            (r'infinite\s*loop', 'infinite_loop'),
            (r'cyclic.*depend', 'cyclic_dependency'),
            (r'missing.*error', 'missing_error_handling'),
            (r'fetch.*api|api.*fetch', 'api_fetch'),
            (r'fetch.*db|database.*fetch', 'database_fetch'),
            (r'cache|cached', 'cached_data'),
            (r'fetch.*from.*file', 'file_fetch'),
            (r'retry', 'retry_strategy'),
            (r'fallback', 'fallback_strategy'),
        ]
        
        for pattern, strategy in strategy_patterns:
            if re.search(pattern, desc):
                return strategy
        
        words = desc.split()
        if len(words) <= 3:
            return '_'.join(words)
        
        return '_'.join(words[:3])
    
    def _recency_weight(self, timestamp: float) -> float:
        """Calculate recency weight with exponential decay."""
        age_hours = (time.time() - timestamp) / 3600
        return math.exp(-self.RECENCY_DECAY * age_hours)
    
    def _categorize_failure(self, error_message: str) -> str:
        """Categorize error for generalization (works without embeddings)."""
        error_lower = error_message.lower()
        
        for category, patterns in FAILURE_CATEGORIES.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return category
        
        return "unknown"
    
    def _calculate_failure_penalty(
        self, 
        experiences: List[PatternExperience]
    ) -> float:
        """
        Calculate NON-LINEAR penalty for recent failures.
        
        - Recoverable failures (rate_limit, timeout): moderate penalty
        - Fatal failures (auth): severe penalty
        - Multiple failures: exponential increase
        """
        if not experiences:
            return 0.0
        
        recent_failures = {
            "recoverable": 0,
            "fatal": 0,
            "total": 0
        }
        
        now = time.time()
        for exp in experiences:
            age_hours = (now - exp.timestamp) / 3600
            if age_hours < 24:
                recent_failures["total"] += 1
                if not exp.success:
                    for fr in exp.failure_reasons:
                        severity = FAILURE_SEVERITY.get(fr.reason, "recoverable")
                        recent_failures[severity] += 1
        
        if recent_failures["total"] == 0:
            return 0.0
        
        recoverable_rate = recent_failures["recoverable"] / recent_failures["total"]
        fatal_rate = recent_failures["fatal"] / recent_failures["total"]
        
        recoverable_penalty = (recoverable_rate ** FAILURE_PENALTY_EXPONENT) * RECOVERABLE_PENALTY_FACTOR
        fatal_penalty = (fatal_rate ** FAILURE_PENALTY_EXPONENT) * FATAL_PENALTY_FACTOR
        
        penalty = recoverable_penalty + fatal_penalty
        
        return min(0.9, penalty)
    
    def _aggregate_strategy_stats(
        self,
        experiences: List[PatternExperience],
        goal_embedding: List[float]
    ) -> tuple[int, int, float, float]:
        """
        Aggregate statistics ONCE per strategy (not per-experience).
        
        NOW includes:
        - Weight decay (recent experiences matter more)
        - Failure penalty (recent failures reduce score)
        
        Returns:
            (successes, attempts, weighted_success_rate, weighted_uncertainty)
        """
        if not experiences:
            return 0, 0, 0.0, 1.0
        
        successes = sum(1 for e in experiences if e.success)
        attempts = len(experiences)
        
        total_weight = 0.0
        weighted_success = 0.0
        
        for exp in experiences:
            similarity = self._cosine(goal_embedding, exp.goal_embedding)
            recency = self._recency_weight(exp.timestamp)
            weight = similarity * recency
            
            if similarity >= self.MIN_SIMILARITY:
                total_weight += weight
                weighted_success += (1.0 if exp.success else 0.0) * weight
        
        if total_weight == 0:
            return successes, attempts, 0.0, 1.0
        
        weighted_success_rate = weighted_success / total_weight
        
        alpha = successes + self.BAYESIAN_PRIOR
        beta = (attempts - successes) + self.BAYESIAN_PRIOR
        uncertainty = math.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1))) if (alpha + beta) > 0 else 1.0
        
        return successes, attempts, weighted_success_rate, uncertainty
    
    def _get_failure_insights(
        self,
        experiences: List[PatternExperience]
    ) -> List[Dict]:
        """Aggregate failure reasons across experiences."""
        insights: Dict[str, Dict] = {}
        
        for exp in experiences:
            if exp.success:
                continue
            for fr in exp.failure_reasons:
                if fr.reason == "unknown":
                    continue
                if fr.reason not in insights:
                    insights[fr.reason] = {
                        "reason": fr.reason,
                        "count": 0,
                        "mitigation": FAILURE_MITIGATIONS.get(fr.reason, "use alternative approach")
                    }
                insights[fr.reason]["count"] += fr.frequency
        
        result = sorted(insights.values(), key=lambda x: x["count"], reverse=True)
        return [{"reason": i["reason"], "count": i["count"], "mitigation": i["mitigation"]} for i in result]
    
    def store(
        self, 
        goal: str, 
        tasks: List[Dict], 
        success: bool,
        failed_task_ids: Optional[List[str]] = None,
        failure_errors: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store experience with strategy abstraction and failure reasoning."""
        vec = self._embed(goal)
        if vec is None:
            return False
        
        patterns = [self._extract_strategy(t) for t in tasks]
        
        task_map = {t.get("id"): t for t in tasks}
        failed_strategies: Dict[str, List[str]] = {}
        successful_strategies: Set[str] = set()
        
        if failed_task_ids and failure_errors:
            for task_id in failed_task_ids:
                if task_id in task_map:
                    strategy = self._extract_strategy(task_map[task_id])
                    if strategy not in failed_strategies:
                        failed_strategies[strategy] = []
                    failed_strategies[strategy].append(failure_errors.get(task_id, "unknown"))
        elif not success:
            for task in tasks:
                strategy = self._extract_strategy(task)
                if strategy not in failed_strategies:
                    failed_strategies[strategy] = ["unknown"]
        
        if success:
            for task in tasks:
                successful_strategies.add(self._extract_strategy(task))
        
        for p in self.plans:
            if p.goal.lower() == goal.lower():
                p.last_used = time.time()
                
                for strategy, errors in failed_strategies.items():
                    failure_reasons = []
                    for error in errors:
                        reasons = self._extract_failure_reasons(error)
                        for r in reasons:
                            existing = next((fr for fr in failure_reasons if fr.reason == r.reason), None)
                            if existing:
                                existing.frequency += r.frequency
                            else:
                                failure_reasons.append(r)
                    
                    p.experiences.append(PatternExperience(
                        strategy=strategy,
                        abstract_strategy=self._get_abstract_strategy(strategy),
                        success=False,
                        goal_embedding=vec,
                        goal_context=goal,
                        timestamp=time.time(),
                        failure_reasons=failure_reasons
                    ))
                
                for strategy in successful_strategies:
                    p.experiences.append(PatternExperience(
                        strategy=strategy,
                        abstract_strategy=self._get_abstract_strategy(strategy),
                        success=True,
                        goal_embedding=vec,
                        goal_context=goal,
                        timestamp=time.time(),
                        failure_reasons=[]
                    ))
                
                if metadata:
                    p.metadata.update(metadata)
                
                self._save()
                return True
        
        experiences = []
        for strategy, errors in failed_strategies.items():
            failure_reasons = []
            for error in errors:
                reasons = self._extract_failure_reasons(error)
                for r in reasons:
                    existing = next((fr for fr in failure_reasons if fr.reason == r.reason), None)
                    if existing:
                        existing.frequency += r.frequency
                    else:
                        failure_reasons.append(r)
            
            experiences.append(PatternExperience(
                strategy=strategy,
                abstract_strategy=self._get_abstract_strategy(strategy),
                success=False,
                goal_embedding=vec,
                goal_context=goal,
                timestamp=time.time(),
                failure_reasons=failure_reasons
            ))
        
        for strategy in successful_strategies:
            experiences.append(PatternExperience(
                strategy=strategy,
                abstract_strategy=self._get_abstract_strategy(strategy),
                success=True,
                goal_embedding=vec,
                goal_context=goal,
                timestamp=time.time(),
                failure_reasons=[]
            ))
        
        plan = StoredPlan(
            goal=goal,
            embedding=vec,
            tasks=tasks,
            patterns=patterns,
            experiences=experiences,
            metadata=metadata or {}
        )
        self.plans.append(plan)
        
        self._save()
        return True
    
    def get_available_strategies(self, candidate_strategies: List[str]) -> Dict[str, List[str]]:
        """Group concrete strategies by abstract type."""
        abstract_map: Dict[str, List[str]] = {}
        for s in candidate_strategies:
            abstract = self._get_abstract_strategy(s)
            if abstract not in abstract_map:
                abstract_map[abstract] = []
            abstract_map[abstract].append(s)
        return abstract_map
    
    def select_abstract_strategy(self, goal: str) -> List[AbstractStrategyScore]:
        """
        Level 1: Select best ABSTRACT strategy type.
        
        This is where abstraction really matters - system learns which TYPE of
        strategy works best, not just which implementation.
        """
        vec = self._embed(goal)
        if vec is None:
            return []
        
        abstract_experiences: Dict[str, List[PatternExperience]] = {}
        
        for p in self.plans:
            sim = self._cosine(vec, p.embedding)
            if sim < self.MIN_SIMILARITY:
                continue
            
            for exp in p.experiences:
                abstract = exp.abstract_strategy
                if abstract not in abstract_experiences:
                    abstract_experiences[abstract] = []
                abstract_experiences[abstract].append(exp)
        
        scored: List[AbstractStrategyScore] = []
        
        for abstract, experiences in abstract_experiences.items():
            successes, attempts, weighted_rate, uncertainty = self._aggregate_strategy_stats(
                experiences, vec
            )
            
            if attempts == 0:
                continue
            
            is_structural = self._get_pattern_type(abstract) == "structural_failures"
            failure_insights = self._get_failure_insights(experiences)
            
            failure_penalty = self._calculate_failure_penalty(experiences)
            confidence_bonus = 0.15 if uncertainty < 0.3 else 0.0
            exploration_penalty = 0.1 if attempts < 3 else 0.0
            
            expected_value = (
                weighted_rate * 0.6 + 
                confidence_bonus - 
                exploration_penalty - 
                failure_penalty
            )
            
            scored.append(AbstractStrategyScore(
                abstract_strategy=abstract,
                expected_value=expected_value,
                bayesian_success_rate=weighted_rate,
                uncertainty=uncertainty,
                attempts=attempts,
                is_structural=is_structural,
                failure_insights=failure_insights,
                failure_penalty=failure_penalty
            ))
        
        scored.sort(key=lambda x: x.expected_value, reverse=True)
        return scored
    
    def select_concrete_strategy(
        self,
        goal: str,
        abstract: str,
        concrete_options: List[str]
    ) -> List[ConcreteStrategyScore]:
        """
        Level 2: Select best CONCRETE implementation within abstract type.
        
        Compare implementations like api_fetch vs database_fetch.
        """
        vec = self._embed(goal)
        if vec is None:
            return []
        
        concrete_experiences: Dict[str, List[PatternExperience]] = {}
        
        for p in self.plans:
            sim = self._cosine(vec, p.embedding)
            if sim < self.MIN_SIMILARITY:
                continue
            
            for exp in p.experiences:
                if exp.abstract_strategy == abstract and exp.strategy in concrete_options:
                    if exp.strategy not in concrete_experiences:
                        concrete_experiences[exp.strategy] = []
                    concrete_experiences[exp.strategy].append(exp)
        
        scored: List[ConcreteStrategyScore] = []
        
        for strategy in concrete_options:
            experiences = concrete_experiences.get(strategy, [])
            successes, attempts, weighted_rate, uncertainty = self._aggregate_strategy_stats(
                experiences, vec
            )
            
            failure_insights = self._get_failure_insights(experiences)
            mitigations = [f["mitigation"] for f in failure_insights[:3]]
            
            failure_penalty = self._calculate_failure_penalty(experiences)
            confidence_bonus = 0.15 if uncertainty < 0.3 else 0.0
            exploration_penalty = 0.1 if attempts < 3 else 0.0
            
            expected_value = (
                weighted_rate * 0.6 + 
                confidence_bonus - 
                exploration_penalty - 
                failure_penalty
            )
            
            scored.append(ConcreteStrategyScore(
                strategy=strategy,
                abstract_strategy=abstract,
                expected_value=expected_value,
                bayesian_success_rate=weighted_rate,
                uncertainty=uncertainty,
                attempts=attempts,
                failure_insights=failure_insights,
                mitigations=mitigations,
                failure_penalty=failure_penalty
            ))
        
        scored.sort(key=lambda x: x.expected_value, reverse=True)
        return scored
    
    def hierarchical_select(
        self,
        goal: str,
        available_strategies: List[str]
    ) -> Dict[str, Any]:
        """
        Two-level hierarchical selection: abstract → concrete.
        
        Returns:
            {
                "abstract_strategy": {...},
                "concrete_strategy": {...},
                "reasoning": "..."
            }
        """
        abstract_map = self.get_available_strategies(available_strategies)
        
        abstract_scores = self.select_abstract_strategy(goal)
        
        if not abstract_scores:
            concrete_scores = self.select_concrete_strategy(
                goal, 
                list(abstract_map.keys())[0] if abstract_map else "general_strategy",
                available_strategies
            )
            return {
                "abstract_strategy": None,
                "concrete_strategy": concrete_scores[0] if concrete_scores else None,
                "reasoning": "No abstract data, selecting best concrete"
            }
        
        selected_abstract = abstract_scores[0]
        
        concrete_options = abstract_map.get(selected_abstract.abstract_strategy, [])
        if not concrete_options:
            concrete_options = available_strategies
        
        concrete_scores = self.select_concrete_strategy(
            goal,
            selected_abstract.abstract_strategy,
            concrete_options
        )
        
        selected_concrete = concrete_scores[0] if concrete_scores else None
        
        reasoning = f"Abstract: {selected_abstract.abstract_strategy} (EV={selected_abstract.expected_value:.2f})"
        if selected_concrete:
            reasoning += f" → Concrete: {selected_concrete.strategy} (EV={selected_concrete.expected_value:.2f})"
        
        return {
            "abstract_strategy": selected_abstract,
            "concrete_strategy": selected_concrete,
            "reasoning": reasoning,
            "all_abstract_options": [
                {"abstract": a.abstract_strategy, "ev": a.expected_value}
                for a in abstract_scores[:3]
            ]
        }
    
    def get_planner_constraints(self, goal: str, strategy: str) -> Dict[str, Any]:
        """
        Get constraints for planner based on failure history.
        
        This is the key integration: failure_insights → planner rules.
        """
        vec = self._embed(goal)
        if vec is None:
            return {"constraints": [], "recommendations": []}
        
        relevant_exp: List[PatternExperience] = []
        
        for p in self.plans:
            sim = self._cosine(vec, p.embedding)
            if sim < self.MIN_SIMILARITY:
                continue
            for exp in p.experiences:
                if exp.strategy == strategy or exp.abstract_strategy == strategy:
                    relevant_exp.append(exp)
        
        constraints = []
        recommendations = []
        
        failure_insights = self._get_failure_insights(relevant_exp)
        
        for insight in failure_insights[:3]:
            constraints.append({
                "if_using": strategy,
                "failure_reason": insight["reason"],
                "mitigation": insight["mitigation"]
            })
            recommendations.append(insight["mitigation"])
        
        return {
            "constraints": constraints,
            "recommendations": recommendations
        }
    
    def retrieve(self, goal: str, top_k: int = 3) -> Optional[Dict]:
        """Retrieve TOP-K similar plans as memory hints."""
        vec = self._embed(goal)
        if vec is None:
            return None
        
        scored = []
        for p in self.plans:
            if not p.experiences:
                continue
            sim = self._cosine(vec, p.embedding)
            successes, attempts, weighted_rate, _ = self._aggregate_strategy_stats(
                p.experiences, vec
            )
            recency = self._recency_weight(p.last_used)
            score = sim * 0.6 + weighted_rate * 0.3 + recency * 0.1
            scored.append((score, p))
        
        if not scored:
            return None
        
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        
        hints = []
        for s, p in top:
            successes, attempts, weighted_rate, _ = self._aggregate_strategy_stats(
                p.experiences, vec
            )
            hints.append(MemoryHint(
                goal=p.goal,
                tasks=p.tasks,
                score=s,
                success_rate=weighted_rate
            ))
        
        abstract_scores = self.select_abstract_strategy(goal)
        
        return {
            "type": "memory_hint",
            "mandatory_analysis": True,
            "plans": [
                {
                    "goal": h.goal, 
                    "tasks": h.tasks, 
                    "patterns": p.patterns,
                    "confidence": h.score,
                    "success_rate": h.success_rate
                }
                for h, p in zip(hints, [scored[i][1] for i in range(len(top))])
            ],
            "abstract_strategy_recommendation": {
                "strategy": abstract_scores[0].abstract_strategy if abstract_scores else None,
                "expected_value": abstract_scores[0].expected_value if abstract_scores else 0,
                "bayesian_rate": abstract_scores[0].bayesian_success_rate if abstract_scores else 0,
                "uncertainty": abstract_scores[0].uncertainty if abstract_scores else 1.0,
                "failure_insights": abstract_scores[0].failure_insights[:3] if abstract_scores else []
            } if abstract_scores else None,
            "all_abstract_options": [
                {
                    "abstract": a.abstract_strategy,
                    "ev": round(a.expected_value, 2),
                    "attempts": a.attempts
                }
                for a in abstract_scores[:5]
            ]
        }
    
    def select_best_strategy(
        self, 
        goal: str, 
        available_strategies: List[str],
        justification: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: hierarchical selection with full reasoning.
        """
        result = self.hierarchical_select(goal, available_strategies)
        
        if result["concrete_strategy"]:
            constraints = self.get_planner_constraints(goal, result["concrete_strategy"].strategy)
            result["constraints"] = constraints["constraints"]
            result["recommendations"] = constraints["recommendations"]
        
        return result
    
    def get_blacklisted_strategies(self, goal: str, allow_exploration: bool = True) -> Dict[str, float]:
        """
        Get strategies that should be blacklisted for this goal.
        
        Args:
            goal: The goal context
            allow_exploration: If True, occasionally allow exploration by returning None
                             even if strategy is blacklisted (to re-test failed strategies)
        
        Returns:
            Dict[str, float] - strategy -> cooldown_until timestamp
            OR None if exploration triggered (meaning: don't filter, try anything)
        """
        if not hasattr(self, '_blacklist'):
            self._blacklist: Dict[str, float] = {}
            self._failure_counts: Dict[str, int] = {}
        
        now = time.time()
        
        expired_keys = []
        for key in list(self._blacklist.keys()):
            if now > self._blacklist[key]:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._blacklist[key]
            if key in self._failure_counts:
                del self._failure_counts[key]
        
        if expired_keys:
            self._save_blacklist()
        
        if not self._blacklist:
            return {}
        
        if allow_exploration and random.random() < self.EXPLORATION_RATE:
            exploration_key = random.choice(list(self._blacklist.keys()))
            if ":" in exploration_key:
                strategy = exploration_key.split(":", 1)[1]
            else:
                strategy = exploration_key
                print(f"[EXPLORATION] Trying blacklisted strategy: {strategy}")
            return {}
        
        # Filter blacklist by goal and return strategy->cooldown mapping
        blacklisted = {}
        for key, cooldown_until in self._blacklist.items():
            # Key format is "goal:strategy"
            if key.startswith(goal + ":"):
                strategy = key[len(goal) + 1:]  # Extract strategy name
                if now <= cooldown_until:
                    blacklisted[strategy] = cooldown_until
        
        return blacklisted
    
    def record_failure(self, goal: str, strategy: str, failure_reason: str) -> bool:
        """
        Record a failure and apply blacklist if threshold exceeded.
        
        Returns:
            True if strategy was blacklisted
        """
        if not hasattr(self, '_blacklist'):
            self._blacklist = {}
            self._failure_counts = {}
        
        key = f"{goal}:{strategy}"
        
        if key not in self._failure_counts:
            self._failure_counts[key] = 0
        
        severity = FAILURE_SEVERITY.get(failure_reason, "recoverable")
        
        if severity == "fatal":
            self._failure_counts[key] += 2
        else:
            self._failure_counts[key] += 1
        
        if self._failure_counts[key] >= BLACKLIST_THRESHOLD:
            cooldown = time.time() + (BLACKLIST_COOLDOWN_HOURS * 3600)
            self._blacklist[key] = cooldown
            self._save_blacklist()
            return True
        
        return False
    
    def _save_blacklist(self):
        try:
            import json
            blacklist_path = "/app/plan_blacklist.json"
            data = {
                "blacklist": getattr(self, '_blacklist', {}),
                "failure_counts": getattr(self, '_failure_counts', {})
            }
            with open(blacklist_path, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass
    
    def _load_blacklist(self):
        try:
            import json
            blacklist_path = "/app/plan_blacklist.json"
            with open(blacklist_path, 'r') as f:
                data = json.load(f)
                self._blacklist = data.get("blacklist", {})
                self._failure_counts = data.get("failure_counts", {})
        except Exception:
            self._blacklist = {}
            self._failure_counts = {}
    
    def stats(self) -> Dict:
        if not self.plans:
            return {"total": 0, "avg_success": 0.0}
        
        total_exp = sum(len(p.experiences) for p in self.plans)
        total_success = sum(sum(1 for e in p.experiences if e.success) for p in self.plans)
        
        return {
            "total": len(self.plans),
            "total_experiences": total_exp,
            "avg_success": total_success / total_exp if total_exp > 0 else 0.0,
            "cache_size": len(self._cache)
        }


plan_memory = PlanMemory()


def get_plan_memory() -> PlanMemory:
    return plan_memory
