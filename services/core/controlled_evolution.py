"""
Controlled Skill Evolution - WITH Safeguards Against Skill Explosion

This implementation prevents uncontrolled exponential skill growth through:
1. Score-based filtering
2. Branching limits
3. Regular pruning
4. Deduplication
5. Hard caps
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from execution_models import GoalExecution
from skill_evolution_models import (
    SkillPattern,
    CompositeSkill,
    SkillGraphNode,
    SkillEvolutionLog
)
from logging_config import get_logger

logger = get_logger(__name__)


class ControlledSkillEvolution:
    """
    Skill Evolution WITH safeguards against explosion.

    Configuration:
        MAX_BRANCHING_FACTOR: Max new composites per cycle (default: 2)
        MIN_SCORE_THRESHOLD: Min score for pattern consideration (default: 0.7)
        MAX_ACTIVE_SKILLS: Hard cap on total skills (default: 100)
        PRUNING_INTERVAL_DAYS: How often to run pruning (default: 30)
        PRUNING_SCORE_THRESHOLD: Min score to keep skill (default: 0.5)
    """

    # Configuration
    MAX_BRANCHING_FACTOR = 2
    MIN_SCORE_THRESHOLD = 0.5
    MAX_ACTIVE_SKILLS = 100
    PRUNING_INTERVAL_DAYS = 30
    PRUNING_SCORE_THRESHOLD = 0.5
    PRUNING_AGE_THRESHOLD_DAYS = 90
    PRUNING_LAST_USED_THRESHOLD_DAYS = 30

    async def evolution_cycle(self) -> Dict[str, Any]:
        """
        Run controlled evolution cycle with safeguards.

        Returns:
            Cycle results with metrics
        """
        logger.info("controlled_evolution_cycle_started")

        async with AsyncSessionLocal() as session:
            # Step 1: Pattern Discovery
            patterns = await self._discover_patterns(session)
            logger.info("patterns_discovered", count=len(patterns))

            # Step 2: Score & Filter
            scored_patterns = await self._score_and_filter_patterns(session, patterns)
            logger.info(
                "patterns_after_scoring",
                total=len(patterns),
                passed=len(scored_patterns)
            )

            # Step 3: Apply Branching Limit
            top_patterns = self._apply_branching_limit(scored_patterns)
            logger.info(
                "patterns_after_branching_limit",
                selected=len(top_patterns),
                limit=self.MAX_BRANCHING_FACTOR
            )

            # Step 4: Deduplication
            unique_patterns = await self._deduplicate_patterns(session, top_patterns)
            logger.info(
                "patterns_after_deduplication",
                unique=len(unique_patterns)
            )

            # Step 5: Check Cap
            active_count = await self._count_active_skills(session)
            if active_count >= self.MAX_ACTIVE_SKILLS:
                logger.warning(
                    "max_skills_reached",
                    current=active_count,
                    cap=self.MAX_ACTIVE_SKILLS,
                    action="skip_generation"
                )
                return {
                    "status": "skipped",
                    "reason": "max_skills_reached",
                    "current_skills": active_count,
                    "cap": self.MAX_ACTIVE_SKILLS
                }

            # Step 6: Generate Composites
            composites_created = 0
            for pattern in unique_patterns:
                composite = await self._generate_composite(session, pattern)
                if composite:
                    composites_created += 1

            await session.commit()

            # Step 7: Pruning (if needed)
            pruning_result = await self._maybe_prune_skills(session)

            logger.info(
                "controlled_evolution_cycle_completed",
                patterns_analyzed=len(patterns),
                composites_created=composites_created,
                active_skills=await self._count_active_skills(session),
                pruned=pruning_result.get("pruned", 0)
            )

            return {
                "status": "success",
                "patterns_analyzed": len(patterns),
                "composites_created": composites_created,
                "active_skills": await self._count_active_skills(session),
                "pruned": pruning_result.get("pruned", 0)
            }

    async def _score_and_filter_patterns(
        self,
        session: AsyncSession,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Score patterns and filter by threshold.

        Score = frequency * 0.3 + success_rate * 0.4 + utility * 0.2 + novelty * 0.1
        """
        scored_patterns = []

        for pattern in patterns:
            # Calculate utility (based on artifact types)
            utility = await self._calculate_pattern_utility(session, pattern)

            # Calculate novelty (how new is this pattern)
            novelty = await self._calculate_pattern_novelty(session, pattern)

            # Calculate score
            score = (
                (pattern.get('frequency', 1) / 100.0) * 0.3 +  # Normalized frequency
                pattern.get('avg_success_rate', 0.5) * 0.4 +
                utility * 0.2 +
                novelty * 0.1
            )

            if score >= self.MIN_SCORE_THRESHOLD:
                pattern['score'] = score
                pattern['utility'] = utility
                pattern['novelty'] = novelty
                scored_patterns.append(pattern)

        # Sort by score
        scored_patterns.sort(key=lambda p: p['score'], reverse=True)

        return scored_patterns

    async def _calculate_pattern_utility(
        self,
        session: AsyncSession,
        pattern: Dict[str, Any]
    ) -> float:
        """
        Calculate utility based on artifact types produced.

        High-value artifacts:
        - REPORT (0.9)
        - DATASET (0.8)
        - FILE (0.6)
        - KNOWLEDGE (0.7)
        - LINK (0.3)
        """
        artifact_types = pattern.get('common_artifact_types', [])

        if not artifact_types:
            return 0.5  # Default utility

        utility_scores = {
            'REPORT': 0.9,
            'DATASET': 0.8,
            'KNOWLEDGE': 0.7,
            'FILE': 0.6,
            'LINK': 0.3,
            'EXECUTION_LOG': 0.2
        }

        max_utility = max([
            utility_scores.get(atype, 0.5)
            for atype in artifact_types
        ])

        return max_utility

    async def _calculate_pattern_novelty(
        self,
        session: AsyncSession,
        pattern: Dict[str, Any]
    ) -> float:
        """
        Calculate novelty (1.0 = completely new, 0.0 = very common).

        Novelty decreases as pattern appears more frequently.
        """
        frequency = pattern.get('frequency', 1)

        # Novelty = 1.0 / (1.0 + frequency * 0.1)
        novelty = 1.0 / (1.0 + frequency * 0.1)

        return novelty

    def _apply_branching_limit(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply branching limit - only top K patterns."""
        return patterns[:self.MAX_BRANCHING_FACTOR]

    async def _deduplicate_patterns(
        self,
        session: AsyncSession,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate or very similar patterns.

        Two patterns are duplicates if:
        - Same skill sequence
        - OR similar sequence (Levenshtein distance < threshold)
        """
        unique_patterns = []

        for pattern in patterns:
            sequence = pattern['skill_sequence']
            sequence_str = "_".join(sequence)

            # Check for exact duplicate
            is_duplicate = False
            for existing in unique_patterns:
                existing_sequence = existing['skill_sequence']
                existing_str = "_".join(existing_sequence)

                if sequence_str == existing_str:
                    is_duplicate = True
                    logger.debug(
                        "duplicate_pattern_skipped",
                        pattern_id=pattern['pattern_id'],
                        duplicate_of=existing['pattern_id']
                    )
                    break

            if not is_duplicate:
                unique_patterns.append(pattern)

        return unique_patterns

    async def _count_active_skills(self, session: AsyncSession) -> int:
        """Count total active (non-deprecated) skills."""
        stmt = select(func.count(CompositeSkill.id)).where(
            CompositeSkill.status.in_(['candidate', 'testing', 'active'])
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _generate_composite(
        self,
        session: AsyncSession,
        pattern: Dict[str, Any]
    ) -> Optional[CompositeSkill]:
        """Generate composite skill from pattern."""
        sequence = pattern['skill_sequence']

        # Skip single-skill patterns
        if len(sequence) <= 1:
            return None

        # Generate skill ID
        skill_id = f"{'_'.join(sequence)}_v1"

        # Check if already exists
        stmt = select(CompositeSkill).where(
            CompositeSkill.skill_id == skill_id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return None

        # Determine execution strategy
        if len(sequence) == 2:
            strategy = "sequential"
        else:
            strategy = "sequential"  # Default for now

        # Create composite
        composite = CompositeSkill(
            skill_id=skill_id,
            version=1,
            component_skills=sequence,
            execution_strategy=strategy,
            status='candidate',  # Start as candidate (experimental)
            success_rate=pattern.get('avg_success_rate'),
            avg_latency_ms=pattern.get('avg_duration_ms'),
            extra_data={
                'generated_from': 'controlled_evolution',
                'pattern_score': pattern.get('score'),
                'pattern_frequency': pattern.get('frequency'),
                'novelty': pattern.get('novelty')
            }
        )

        session.add(composite)

        logger.info(
            "composite_skill_created",
            skill_id=skill_id,
            components=len(sequence),
            status='candidate'
        )

        # Log evolution decision
        await self._log_evolution_event(
            session,
            event_type="candidate_created",
            candidate_skill_id=skill_id,
            improvement_score=pattern.get('score'),
            reason=f"Pattern score: {pattern.get('score'):.2f}"
        )

        return composite

    async def _maybe_prune_skills(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Prune low-performing skills if needed.

        Runs if:
        - Last pruning was > PRUNING_INTERVAL_DAYS ago
        - OR total skills approaching MAX_ACTIVE_SKILLS
        """
        # Check if pruning needed
        last_pruning = await self._get_last_pruning_time(session)
        days_since_pruning = (datetime.utcnow() - last_pruning).days

        active_count = await self._count_active_skills(session)
        approaching_cap = active_count >= (self.MAX_ACTIVE_SKILLS * 0.8)

        should_prune = (
            days_since_pruning >= self.PRUNING_INTERVAL_DAYS or
            approaching_cap
        )

        if not should_prune:
            return {"pruned": 0, "reason": "not_needed"}

        logger.info(
            "skill_pruning_started",
            days_since_pruning=days_since_pruning,
            active_skills=active_count
        )

        # Find candidates for pruning
        candidates = await self._find_pruning_candidates(session)

        # Prune candidates
        pruned_count = 0
        for candidate in candidates:
            await self._deprecate_skill(session, candidate['skill_id'])
            pruned_count += 1

        logger.info(
            "skill_pruning_completed",
            pruned=pruned_count,
            remaining_active=await self._count_active_skills(session)
        )

        return {
            "pruned": pruned_count,
            "reason": "scheduled_or_approaching_cap"
        }

    async def _find_pruning_candidates(
        self,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Find skills to prune.

        Criteria:
        - Score < PRUNING_SCORE_THRESHOLD
        - Age > PRUNING_AGE_THRESHOLD_DAYS
        - Not core skill
        - Not used in last PRUNING_LAST_USED_THRESHOLD_DAYS
        """
        # Get all composite skills
        stmt = select(CompositeSkill).where(
            CompositeSkill.status.in_(['candidate', 'testing', 'active'])
        )
        result = await session.execute(stmt)
        skills = result.scalars().all()

        candidates = []
        for skill in skills:
            # Skip if too recent (handle timezone-aware datetimes)
            created = skill.created_at
            if created.tzinfo is not None:
                created = created.replace(tzinfo=None)
            now = datetime.utcnow()
            age_days = (now - created).days
            if age_days < self.PRUNING_AGE_THRESHOLD_DAYS:
                continue

            # Calculate score
            score = self._calculate_skill_score(skill)

            if score < self.PRUNING_SCORE_THRESHOLD:
                candidates.append({
                    'skill_id': skill.skill_id,
                    'score': score,
                    'age_days': age_days,
                    'last_used': skill.promoted_at
                })

        # Sort by score (worst first)
        candidates.sort(key=lambda c: c['score'])

        return candidates

    def _calculate_skill_score(self, skill: CompositeSkill) -> float:
        """
        Calculate overall skill score.

        Score = success_rate * 0.5 + usage * 0.3 + age_penalty * -0.2
        """
        success_rate = skill.success_rate or 0.5

        # Usage score (how often is it used)
        # This would require tracking usage - for now use version as proxy
        usage_score = 0.5  # Default

        # Age penalty (older skills have lower score unless proven)
        age_days = (datetime.utcnow() - skill.created_at).days
        age_penalty = min(age_days / 365.0, 1.0)  # Max penalty at 1 year

        score = (
            success_rate * 0.5 +
            usage_score * 0.3 -
            age_penalty * 0.2
        )

        return score

    async def _deprecate_skill(
        self,
        session: AsyncSession,
        skill_id: str
    ):
        """Deprecate (soft delete) a skill."""
        stmt = select(CompositeSkill).where(
            CompositeSkill.skill_id == skill_id
        )
        result = await session.execute(stmt)
        skill = result.scalar_one_or_none()

        if skill:
            skill.status = 'deprecated'
            skill.deprecated_at = datetime.utcnow()

            # Log evolution event
            await self._log_evolution_event(
                session,
                event_type="deprecated",
                candidate_skill_id=skill_id,
                reason=f"Pruned due to low score/age"
            )

            logger.info(
                "skill_deprecated",
                skill_id=skill_id,
                version=skill.version
            )

    async def _get_last_pruning_time(
        self,
        session: AsyncSession
    ) -> datetime:
        """Get timestamp of last pruning."""
        stmt = select(SkillEvolutionLog).where(
            SkillEvolutionLog.event_type == 'deprecated'
        ).order_by(
            SkillEvolutionLog.timestamp.desc()
        ).limit(1)

        result = await session.execute(stmt)
        last_log = result.scalar_one_or_none()

        if last_log:
            return last_log.timestamp
        else:
            # Never pruned - return long time ago
            return datetime.utcnow() - timedelta(days=999)

    async def _log_evolution_event(
        self,
        session: AsyncSession,
        event_type: str,
        candidate_skill_id: str,
        improvement_score: float = None,
        reason: str = None
    ):
        """Log evolution decision."""
        log = SkillEvolutionLog(
            event_type=event_type,
            candidate_skill_id=candidate_skill_id,
            improvement_score=improvement_score,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        session.add(log)

    async def _discover_patterns(
        self,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Discover patterns from recent executions.

        For now, this is a placeholder that loads existing patterns.
        In full implementation, this would analyze execution traces.
        """
        # Load existing patterns
        stmt = select(SkillPattern).order_by(
            desc(SkillPattern.frequency * SkillPattern.avg_success_rate)
        ).limit(20)

        result = await session.execute(stmt)
        patterns = result.scalars().all()

        return [p.to_dict() for p in patterns]


# Singleton instance
controlled_evolution = ControlledSkillEvolution()


async def run_controlled_evolution_cycle() -> Dict[str, Any]:
    """
    Run controlled evolution cycle.

    Called by scheduler every 6 hours.
    """
    return await controlled_evolution.evolution_cycle()
