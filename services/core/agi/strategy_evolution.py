"""
Strategy Evolution - Self-Improving Intelligence
================================================

CRITICAL for AGI: Enables system to invent and improve strategies.

Responsibility:
    - Generate new strategies via mutation
    - Evaluate strategy performance
    - Select best strategies (evolutionary)
    - Track strategy population

Author: AI-OS AGI Architecture
Date: 2026-03-10
Phase: AGI Component 3
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import random
import copy

from logging_config import get_logger

logger = get_logger(__name__)


class StrategyType(str, Enum):
    """Types of strategies"""
    ATOMIC_EXECUTION = "atomic_execution"
    COMPLEX_DECOMPOSITION = "complex_decomposition"
    AGENT_GRAPH = "agent_graph"
    HYBRID = "hybrid"
    CUSTOM = "custom"


@dataclass
class Strategy:
    """
    A strategy for achieving goals.

    Defines HOW to execute, not WHAT to execute.
    """
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    strategy_type: StrategyType = StrategyType.ATOMIC_EXECUTION

    # Parameters (what makes this strategy unique)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Constraints (when to use this strategy)
    applicable_goal_types: List[str] = field(default_factory=list)
    applicable_domains: List[str] = field(default_factory=list)
    min_complexity: float = 0.0
    max_complexity: float = 1.0

    # Performance tracking
    usage_count: int = 0
    success_count: int = 0
    total_score: float = 0.0

    # Meta
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: Optional[datetime] = None
    parent_strategy_id: Optional[UUID] = None  # For evolution tracking
    generation: int = 0  # How many evolutions from original?

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.usage_count == 0:
            return 0.5  # Unknown
        return self.success_count / self.usage_count

    @property
    def avg_score(self) -> float:
        """Calculate average score"""
        if self.usage_count == 0:
            return 0.5
        return self.total_score / self.usage_count

    @property
    def fitness(self) -> float:
        """
        Overall fitness score.

        Combines success rate and average score.
        """
        if self.usage_count == 0:
            return 0.5
        return (self.success_rate + self.avg_score) / 2

    def is_applicable(
        self,
        goal_type: str,
        domains: List[str] = None,
        complexity: float = 0.5
    ) -> bool:
        """Check if strategy is applicable to goal"""
        # Check goal type
        if self.applicable_goal_types and goal_type not in self.applicable_goal_types:
            return False

        # Check domains
        if self.applicable_domains and domains:
            if not any(d in self.applicable_domains for d in domains):
                return False

        # Check complexity
        if not (self.min_complexity <= complexity <= self.max_complexity):
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "strategy_type": self.strategy_type.value,
            "parameters": self.parameters,
            "applicable_goal_types": self.applicable_goal_types,
            "applicable_domains": self.applicable_domains,
            "min_complexity": self.min_complexity,
            "max_complexity": self.max_complexity,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 3),
            "avg_score": round(self.avg_score, 3),
            "fitness": round(self.fitness, 3),
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "parent_strategy_id": str(self.parent_strategy_id) if self.parent_strategy_id else None,
            "generation": self.generation
        }


@dataclass
class StrategyEvaluation:
    """Result of evaluating a strategy"""
    strategy_id: UUID
    goal_id: UUID
    success: bool
    score: float  # 0.0 to 1.0
    duration_ms: int
    artifacts_count: int
    error_message: str = ""

    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyEvolution:
    """
    Evolutionary strategy generation and selection.

    Inspired by genetic algorithms:
    - Mutation: Small changes to strategies
    - Crossover: Combine two strategies
    - Selection: Keep best performers
    """

    def __init__(self):
        # Strategy population: id → Strategy
        self._strategies: Dict[UUID, Strategy] = {}

        # History
        self._evaluations: List[StrategyEvaluation] = []

        # Evolution parameters
        self.mutation_rate = 0.2  # Probability of mutation
        self.crossover_rate = 0.3  # Probability of crossover
        self.elitism_count = 2  # Always keep top N strategies

        # Initialize with default strategies
        self._initialize_default_strategies()

    def _initialize_default_strategies(self):
        """Create baseline strategies"""
        # Strategy 1: Simple atomic execution
        atomic = Strategy(
            name="atomic_default",
            description="Direct skill execution for atomic goals",
            strategy_type=StrategyType.ATOMIC_EXECUTION,
            parameters={"timeout_seconds": 300},
            applicable_goal_types=["achievable"],
            min_complexity=0.0,
            max_complexity=0.3
        )
        self._strategies[atomic.id] = atomic

        # Strategy 2: Complex decomposition
        complex_decomp = Strategy(
            name="complex_decomposition",
            description="Decompose complex goals into subgoals",
            strategy_type=StrategyType.COMPLEX_DECOMPOSITION,
            parameters={"max_depth": 2, "max_subgoals": 7},
            applicable_goal_types=["achievable", "exploratory"],
            min_complexity=0.3,
            max_complexity=0.7
        )
        self._strategies[complex_decomp.id] = complex_decomp

        # Strategy 3: Agent graph
        agent_graph = Strategy(
            name="agent_graph_collaboration",
            description="Multi-agent collaboration for complex tasks",
            strategy_type=StrategyType.AGENT_GRAPH,
            parameters={"max_iterations": 25, "timeout_seconds": 600},
            applicable_goal_types=["exploratory", "meta"],
            min_complexity=0.5,
            max_complexity=1.0
        )
        self._strategies[agent_graph.id] = agent_graph

        logger.info(
            "default_strategies_initialized",
            count=len(self._strategies)
        )

    # ========================================================================
    # STRATEGY SELECTION
    # ========================================================================

    async def select_strategy(
        self,
        goal_type: str,
        domains: List[str] = None,
        complexity: float = 0.5,
        use_experience: bool = True
    ) -> Optional[Strategy]:
        """
        Select best strategy for goal.

        Args:
            goal_type: Type of goal
            domains: Domain tags
            complexity: Goal complexity (0.0 to 1.0)
            use_experience: Use past performance if True

        Returns:
            Strategy: Best matching strategy, or None
        """
        # Find applicable strategies
        applicable = [
            s for s in self._strategies.values()
            if s.is_applicable(goal_type, domains, complexity)
        ]

        if not applicable:
            logger.warning(
                "no_applicable_strategies",
                goal_type=goal_type,
                complexity=complexity
            )
            return None

        # Select best based on fitness
        if use_experience:
            # Sort by fitness (best first)
            applicable.sort(key=lambda s: s.fitness, reverse=True)
        else:
            # Random selection (exploration)
            random.shuffle(applicable)

        best = applicable[0]

        logger.debug(
            "strategy_selected",
            strategy=best.name,
            fitness=best.fitness,
            goal_type=goal_type
        )

        return best

    # ========================================================================
    # EVOLUTIONARY OPERATORS
    # ========================================================================

    async def mutate(
        self,
        strategy: Strategy,
        mutation_strength: float = 0.1
    ) -> Strategy:
        """
        Create mutated copy of strategy.

        Mutation types:
        - Parameter adjustment
        - Constraint relaxation
        - Name/description tweak
        """
        # Deep copy to avoid modifying original
        new_strategy = copy.deepcopy(strategy)
        new_strategy.id = uuid4()  # New ID
        new_strategy.parent_strategy_id = strategy.id
        new_strategy.generation = strategy.generation + 1
        new_strategy.name = f"{strategy.name}_mutated"

        # Mutate parameters
        for key, value in new_strategy.parameters.items():
            if isinstance(value, (int, float)):
                # Random adjustment
                adjustment = (random.random() - 0.5) * 2 * mutation_strength
                if isinstance(value, int):
                    new_strategy.parameters[key] = max(0, value + int(adjustment * 10))
                else:
                    new_strategy.parameters[key] = max(0.0, min(1.0, value + adjustment))

        # Mutate constraints (slight relaxation)
        if random.random() < 0.3:
            new_strategy.min_complexity = max(0.0, new_strategy.min_complexity - mutation_strength)
            new_strategy.max_complexity = min(1.0, new_strategy.max_complexity + mutation_strength)

        # Add to population
        self._strategies[new_strategy.id] = new_strategy

        logger.info(
            "strategy_mutated",
            parent=strategy.name,
            child=new_strategy.name,
            generation=new_strategy.generation
        )

        return new_strategy

    async def crossover(
        self,
        parent1: Strategy,
        parent2: Strategy
    ) -> Strategy:
        """
        Combine two strategies into new one.

        Combines parameters and constraints.
        """
        child = Strategy(
            name=f"hybrid_{parent1.name}_{parent2.name}",
            description=f"Hybrid of {parent1.name} and {parent2.name}",
            strategy_type=StrategyType.HYBRID,
            generation=max(parent1.generation, parent2.generation) + 1,
            parent_strategy_id=parent1.id if random.random() < 0.5 else parent2.id
        )

        # Crossover parameters
        all_params = set(parent1.parameters.keys()) | set(parent2.parameters.keys())
        for param in all_params:
            v1 = parent1.parameters.get(param)
            v2 = parent2.parameters.get(param)

            if v1 is not None and v2 is not None:
                # Average or random selection
                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    child.parameters[param] = (v1 + v2) / 2
                else:
                    child.parameters[param] = random.choice([v1, v2])
            elif v1 is not None:
                child.parameters[param] = v1
            else:
                child.parameters[param] = v2

        # Crossover constraints
        child.applicable_goal_types = list(set(
            parent1.applicable_goal_types + parent2.applicable_goal_types
        ))
        child.applicable_domains = list(set(
            parent1.applicable_domains + parent2.applicable_domains
        ))

        # Average complexity ranges
        child.min_complexity = (parent1.min_complexity + parent2.min_complexity) / 2
        child.max_complexity = (parent1.max_complexity + parent2.max_complexity) / 2

        # Add to population
        self._strategies[child.id] = child

        logger.info(
            "strategy_crossover",
            parent1=parent1.name,
            parent2=parent2.name,
            child=child.name
        )

        return child

    # ========================================================================
    # EVALUATION & LEARNING
    # ========================================================================

    async def evaluate(
        self,
        strategy: Strategy,
        goal_id: UUID,
        success: bool,
        score: float,
        duration_ms: int,
        artifacts_count: int,
        error_message: str = ""
    ):
        """
        Record strategy performance.

        Args:
            strategy: Strategy that was used
            goal_id: Goal executed
            success: Did it succeed?
            score: Quality score (0.0 to 1.0)
            duration_ms: Execution time
            artifacts_count: Artifacts produced
            error_message: Error if any
        """
        # Update strategy stats
        strategy.usage_count += 1
        strategy.last_used = datetime.now(timezone.utc)

        if success:
            strategy.success_count += 1

        strategy.total_score += score

        # Record evaluation
        evaluation = StrategyEvaluation(
            strategy_id=strategy.id,
            goal_id=goal_id,
            success=success,
            score=score,
            duration_ms=duration_ms,
            artifacts_count=artifacts_count,
            error_message=error_message
        )

        self._evaluations.append(evaluation)

        logger.info(
            "strategy_evaluated",
            strategy=strategy.name,
            success=success,
            score=score,
            fitness=strategy.fitness
        )

    # ========================================================================
    # EVOLUTION CYCLE
    # ========================================================================

    async def evolve_population(
        self,
        keep_top_n: int = 5,
        mutation_count: int = 3,
        crossover_count: int = 2
    ) -> Dict[str, Any]:
        """
        Run evolution cycle.

        1. Select top performers (elitism)
        2. Mutate top performers
        3. Crossover random pairs
        4. Remove low performers

        Args:
            keep_top_n: Number of top strategies to keep
            mutation_count: Number of mutations to generate
            crossover_count: Number of crossovers to generate

        Returns:
            dict: Evolution statistics
        """
        # Sort by fitness
        sorted_strategies = sorted(
            self._strategies.values(),
            key=lambda s: s.fitness,
            reverse=True
        )

        # Keep top performers (elitism)
        top_strategies = sorted_strategies[:keep_top_n]

        # Generate mutations
        new_mutations = []
        for strategy in top_strategies[:mutation_count]:
            mutated = await self.mutate(strategy)
            new_mutations.append(mutated)

        # Generate crossovers
        new_crossovers = []
        for _ in range(crossover_count):
            if len(top_strategies) >= 2:
                parent1, parent2 = random.sample(top_strategies[:5], 2)
                child = await self.crossover(parent1, parent2)
                new_crossovers.append(child)

        # Remove low performers (keep population manageable)
        max_population = 20
        if len(self._strategies) > max_population:
            # Remove worst performers
            to_remove = sorted_strategies[max_population:]
            for strategy in to_remove:
                if strategy.id in self._strategies:
                    del self._strategies[strategy.id]

        stats = {
            "population_size": len(self._strategies),
            "top_fitness": top_strategies[0].fitness if top_strategies else 0.0,
            "mutations_created": len(new_mutations),
            "crossovers_created": len(new_crossovers),
            "strategies_removed": len(to_remove) if len(self._strategies) > max_population else 0
        }

        logger.info(
            "evolution_cycle_complete",
            stats=stats
        )

        return stats

    def get_population_summary(self) -> Dict[str, Any]:
        """Get summary of strategy population"""
        strategies = list(self._strategies.values())

        if not strategies:
            return {
                "total_strategies": 0,
                "avg_fitness": 0.0,
                "best_strategy": None
            }

        by_type = {}
        for s in strategies:
            stype = s.strategy_type.value
            if stype not in by_type:
                by_type[stype] = []
            by_type[stype].append(s)

        best = max(strategies, key=lambda s: s.fitness)

        return {
            "total_strategies": len(strategies),
            "by_type": {
                stype: len(strats)
                for stype, strats in by_type.items()
            },
            "avg_fitness": sum(s.fitness for s in strategies) / len(strategies),
            "best_strategy": best.to_dict()
        }


# Singleton instance
strategy_evolution = StrategyEvolution()
