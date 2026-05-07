"""
Skill Evolution Loop - Pattern Extraction Engine

Анализирует execution traces и обнаруживает повторяющиеся паттерны skill chains.

Usage:
    from skill_evolution import PatternExtractor

    extractor = PatternExtractor()

    # Discover patterns from last N executions
    patterns = await extractor.discover_patterns(
        lookback_executions=100,
        min_frequency=5,
        min_success_rate=0.8
    )

    for pattern in patterns:
        print(f"{pattern['pattern_id']}: {pattern['frequency']} times, "
              f"{pattern['avg_success_rate']:.2%} success")
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from execution_models import GoalExecution
from skill_evolution_models import SkillPattern, SkillGraphNode, SkillGraphEdge
from logging_config import get_logger

logger = get_logger(__name__)


class PatternExtractor:
    """
    Извлекает паттерны из execution traces.

    Алгоритм:
    1. Собрать execution chains за последние N executions
    2. Сгруппировать по skill sequences
    3. Вычислить metrics (frequency, success_rate, avg_latency)
    4. Отфильтровать по thresholds
    5. Сохранить в skill_patterns
    """

    async def discover_patterns(
        self,
        lookback_executions: int = 100,
        min_frequency: int = 5,
        min_success_rate: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Discover patterns from recent executions.

        Args:
            lookback_executions: How many recent executions to analyze
            min_frequency: Minimum times pattern must appear
            min_success_rate: Minimum success rate for pattern

        Returns:
            List of discovered patterns with metrics
        """
        logger.info(
            "pattern_discovery_started",
            lookback=lookback_executions,
            min_frequency=min_frequency,
            min_success_rate=min_success_rate
        )

        # Step 1: Gather execution data
        async with AsyncSessionLocal() as session:
            # Get recent executions
            stmt = (
                select(GoalExecution)
                .order_by(desc(GoalExecution.started_at))
                .limit(lookback_executions)
            )
            result = await session.execute(stmt)
            executions = result.scalars().all()

            logger.debug("gathered_executions", count=len(executions))

            if len(executions) < min_frequency:
                logger.warning(
                    "insufficient_executions",
                    total=len(executions),
                    required=min_frequency
                )
                return []

            # Step 2: Extract skill sequences
            sequences = self._extract_sequences(executions)

            logger.debug("extracted_sequences", unique_sequences=len(sequences))

            # Step 3: Calculate metrics per sequence
            pattern_metrics = self._calculate_sequence_metrics(executions, sequences)

            # Step 4: Filter by thresholds
            candidate_patterns = [
                p for p in pattern_metrics
                if p['frequency'] >= min_frequency
                and p['avg_success_rate'] >= min_success_rate
            ]

            logger.info(
                "pattern_candidates_found",
                total= len(pattern_metrics),
                candidates= len(candidate_patterns)
            )

            # Step 5: Save to database
            saved_patterns = []
            for pattern_data in candidate_patterns:
                pattern = await self._save_or_update_pattern(session, pattern_data)
                saved_patterns.append(pattern.to_dict())

            await session.commit()

            # Step 6: Update skill graph
            await self._update_skill_graph(session, candidate_patterns)

            await session.commit()

            logger.info(
                "pattern_discovery_completed",
                patterns_saved=len(saved_patterns)
            )

            return saved_patterns

    def _extract_sequences(self, executions: List[GoalExecution]) -> List[Tuple[str, ...]]:
        """
        Extract unique skill sequences from executions.

        Args:
            executions: List of GoalExecution records

        Returns:
            List of unique skill sequences (as tuples)
        """
        sequences = []

        for execution in executions:
            # For atomic goals, we have single skill
            # For composite goals, we'd need to parse execution_trace
            skill_id = execution.skill_id

            # Single skill sequence (atomic goals)
            sequences.append((skill_id,))

        # Get unique sequences
        unique_sequences = list(set(sequences))

        return unique_sequences

    def _calculate_sequence_metrics(
        self,
        executions: List[GoalExecution],
        sequences: List[Tuple[str, ...]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate metrics for each sequence.

        Args:
            executions: All executions
            sequences: Unique sequences to calculate metrics for

        Returns:
            List of pattern metrics dicts
        """
        pattern_metrics = []

        # Group executions by sequence
        executions_by_sequence = defaultdict(list)
        for execution in executions:
            sequence = (execution.skill_id,)
            executions_by_sequence[sequence].append(execution)

        # Calculate metrics per sequence
        for sequence in sequences:
            seq_executions = executions_by_sequence.get(sequence, [])

            if not seq_executions:
                continue

            # Calculate metrics
            frequency = len(seq_executions)
            successful = sum(1 for e in seq_executions if e.success)
            avg_success_rate = successful / frequency if frequency > 0 else 0

            durations = [e.duration_ms for e in seq_executions if e.duration_ms is not None]
            avg_duration_ms = sum(durations) / len(durations) if durations else None

            confidences = [e.confidence for e in seq_executions if e.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None

            # Generate pattern_id from sequence
            pattern_id = "_".join(sequence)

            pattern_metrics.append({
                "pattern_id": pattern_id,
                "skill_sequence": list(sequence),
                "frequency": frequency,
                "avg_success_rate": avg_success_rate,
                "avg_duration_ms": avg_duration_ms,
                "avg_confidence": avg_confidence,
                "common_artifact_types": []  # TODO: Extract from artifacts
            })

        # Sort by score (frequency * success_rate)
        pattern_metrics.sort(
            key=lambda p: p['frequency'] * p['avg_success_rate'],
            reverse=True
        )

        return pattern_metrics

    async def _save_or_update_pattern(
        self,
        session: AsyncSession,
        pattern_data: Dict[str, Any]
    ) -> SkillPattern:
        """
        Save new pattern or update existing.

        Args:
            session: Database session
            pattern_data: Pattern metrics

        Returns:
            Saved SkillPattern instance
        """
        # Check if pattern exists
        stmt = select(SkillPattern).where(
            SkillPattern.pattern_id == pattern_data['pattern_id']
        )
        result = await session.execute(stmt)
        existing_pattern = result.scalar_one_or_none()

        if existing_pattern:
            # Update existing
            existing_pattern.frequency = pattern_data['frequency']
            existing_pattern.avg_success_rate = pattern_data['avg_success_rate']
            existing_pattern.avg_duration_ms = pattern_data['avg_duration_ms']
            existing_pattern.avg_confidence = pattern_data['avg_confidence']
            existing_pattern.last_seen_at = datetime.utcnow()

            logger.debug(
                "pattern_updated",
                pattern_id=pattern_data['pattern_id'],
                frequency=pattern_data['frequency']
            )

            return existing_pattern
        else:
            # Create new
            pattern = SkillPattern(
                pattern_id=pattern_data['pattern_id'],
                skill_sequence=pattern_data['skill_sequence'],
                frequency=pattern_data['frequency'],
                avg_success_rate=pattern_data['avg_success_rate'],
                avg_duration_ms=pattern_data['avg_duration_ms'],
                avg_confidence=pattern_data['avg_confidence'],
                common_artifact_types=pattern_data['common_artifact_types']
            )
            session.add(pattern)

            logger.info(
                "pattern_discovered",
                pattern_id=pattern_data['pattern_id'],
                frequency=pattern_data['frequency'],
                success_rate=f"{pattern_data['avg_success_rate']:.2%}"
            )

            return pattern

    async def _update_skill_graph(
        self,
        session: AsyncSession,
        patterns: List[Dict[str, Any]]
    ):
        """
        Update skill graph nodes and edges from patterns.

        Args:
            session: Database session
            patterns: Discovered patterns
        """
        for pattern in patterns:
            sequence = pattern['skill_sequence']

            # Create nodes for each skill
            for skill_id in sequence:
                await self._ensure_node_exists(session, skill_id)

            # Create edges for sequence transitions
            for i in range(len(sequence) - 1):
                from_skill = sequence[i]
                to_skill = sequence[i + 1]
                await self._update_edge(
                    session,
                    from_skill,
                    to_skill,
                    pattern['frequency'],
                    pattern['avg_success_rate'],
                    pattern['avg_duration_ms']
                )

    async def _ensure_node_exists(self, session: AsyncSession, skill_id: str):
        """Ensure skill graph node exists for skill."""
        stmt = select(SkillGraphNode).where(
            SkillGraphNode.skill_id == skill_id
        )
        result = await session.execute(stmt)
        node = result.scalar_one_or_none()

        if not node:
            node = SkillGraphNode(
                skill_id=skill_id,
                node_type="primitive",  # TODO: Determine from skill registry
                depth_level=0  # TODO: Calculate from dependencies
            )
            session.add(node)

    async def _update_edge(
        self,
        session: AsyncSession,
        from_skill: str,
        to_skill: str,
        frequency: int,
        success_rate: float,
        avg_latency: Optional[float]
    ):
        """Update skill graph edge."""
        stmt = select(SkillGraphEdge).where(
            and_(
                SkillGraphEdge.from_skill == from_skill,
                SkillGraphEdge.to_skill == to_skill
            )
        )
        result = await session.execute(stmt)
        edge = result.scalar_one_or_none()

        if edge:
            # Update existing edge
            edge.transition_count += frequency
            # Recalculate weighted average
            edge.success_rate = (edge.success_rate * 0.9 + success_rate * 0.1)
            edge.avg_latency_ms = (
                (edge.avg_latency_ms * 0.9 + avg_latency * 0.1)
                if avg_latency and edge.avg_latency_ms
                else avg_latency or edge.avg_latency_ms
            )
            # Weight = transition probability
            total_outgoing = await self._count_outgoing_transitions(session, from_skill)
            edge.weight = edge.transition_count / total_outgoing if total_outgoing > 0 else 0
        else:
            # Create new edge
            edge = SkillGraphEdge(
                from_skill=from_skill,
                to_skill=to_skill,
                transition_count=frequency,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
                weight=1.0  # Will be recalculated
            )
            session.add(edge)

    async def _count_outgoing_transitions(self, session: AsyncSession, from_skill: str) -> int:
        """Count total outgoing transitions from skill."""
        stmt = select(func.sum(SkillGraphEdge.transition_count)).where(
            SkillGraphEdge.from_skill == from_skill
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


class CompositeSkillGenerator:
    """
    Генерирует composite skills на основе паттернов.

    Args:
        pattern: Pattern from PatternExtractor
    """

    def generate_from_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate composite skill from pattern.

        Args:
            pattern: Pattern data from PatternExtractor

        Returns:
            Composite skill definition
        """
        sequence = pattern['skill_sequence']

        # Determine execution strategy
        if len(sequence) == 1:
            strategy = "sequential"  # Single skill
        elif pattern.get('avg_duration_ms', 0) > 10000:
            strategy = "parallel"  # Long chains → parallelize if possible
        else:
            strategy = "sequential"

        # Generate skill ID
        skill_id = f"{'_'.join(sequence)}_v1"

        composite_skill = {
            "skill_id": skill_id,
            "version": 1,
            "component_skills": sequence,
            "execution_strategy": strategy,
            "status": "candidate",
            "estimated_success_rate": pattern['avg_success_rate'],
            "estimated_latency_ms": pattern['avg_duration_ms'],
            "parent_pattern_id": pattern.get('pattern_id'),
            "metadata": {
                "generated_from": "pattern_extraction",
                "pattern_frequency": pattern['frequency']
            }
        }

        logger.info(
            "composite_skill_generated",
            skill_id=skill_id,
            components=len(sequence),
            strategy=strategy
        )

        return composite_skill


# Singleton instances
pattern_extractor = PatternExtractor()
composite_generator = CompositeSkillGenerator()


async def run_evolution_cycle():
    """
    Run complete evolution cycle.

    Called periodically (e.g., every 24 hours or every 100 executions).
    """
    logger.info("evolution_cycle_started")

    try:
        # Step 1: Pattern Discovery
        patterns = await pattern_extractor.discover_patterns(
            lookback_executions=100,
            min_frequency=5,
            min_success_rate=0.8
        )

        logger.info("evolution_cycle_patterns_discovered", count=len(patterns))

        # Step 2: Generate Composite Skills
        composite_skills = []
        for pattern in patterns:
            if len(pattern['skill_sequence']) > 1:  # Only multi-skill patterns
                composite = composite_generator.generate_from_pattern(pattern)
                composite_skills.append(composite)

        logger.info(
            "evolution_cycle_composites_generated",
            count=len(composite_skills)
        )

        # Step 3: Save composites to database
        async with AsyncSessionLocal() as session:
            for composite_data in composite_skills:
                from skill_evolution_models import CompositeSkill

                composite = CompositeSkill(
                    skill_id=composite_data['skill_id'],
                    version=composite_data['version'],
                    component_skills=composite_data['component_skills'],
                    execution_strategy=composite_data['execution_strategy'],
                    status=composite_data['status'],
                    metadata=composite_data.get('metadata')
                )
                session.add(composite)

            await session.commit()

        logger.info(
            "evolution_cycle_completed",
            patterns=len(patterns),
            composites=len(composite_skills)
        )

        return {
            "patterns_discovered": len(patterns),
            "composites_generated": len(composite_skills)
        }

    except Exception as e:
        logger.error(
            "evolution_cycle_failed",
            error=str(e)
        )
        raise
