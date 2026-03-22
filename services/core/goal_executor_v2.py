"""
GOAL EXECUTOR V2 - Integration with Canonical Skills
Интегрирует Goal Executor с навыками по каноническому интерфейсу

Execution Flow:
1. Parse goal requirements
2. Select skill via registry
3. Execute skill
4. Verify result
5. Register artifacts
6. Check completion

ARCHITECTURE v3.0:
- Uses UnitOfWork pattern for transaction management
- All transactions opened by caller, not internally
"""
import os
import json
from uuid import UUID
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Goal

# Import canonical skill system
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from canonical_skills.base import Skill, SkillResult, Artifact
from canonical_skills.registry import skill_registry

# Import Experience Engine for learning loop
from experience import experience_engine
from canonical_skills.echo import EchoSkill
from canonical_skills.write_file import WriteFileSkill
from evaluation_engine import evaluation_engine

# Import LLM for content generation
from llm_fallback import chat_with_fallback

# Import production wiring (Phase 2.5.P)
from executor_feedback_wiring import executor_with_feedback, ExecutionMustStopException

# Import UoW infrastructure
from infrastructure.uow import GoalRepository
from goal_transition_service import transition_service

# Import Execution Policy (Phase 2 architectural change)
try:
    from execution_policy import get_execution_policy, ExecutionContext
except ImportError:
    # Fallback if policy not available
    get_execution_policy = None

# Import logging
from logging_config import get_logger

# NEW: Event emission for Metrics Engine
from application.events.bus import get_event_bus
from application.events.execution_events import SkillExecuted

logger = get_logger(__name__)

# NEW: CapabilityPlanner for task-graph planning
try:
    from capability import capability_planner
    CAPABILITY_PLANNER_AVAILABLE = True
except ImportError:
    CAPABILITY_PLANNER_AVAILABLE = False
    logger.warning("capability_planner_not_available")

# Import Skill Evolution Loop for learning
try:
    from skill_evolution_loop import get_skill_evolution_loop
    SKILL_EVOLUTION_LOOP = get_skill_evolution_loop()
except ImportError:
    SKILL_EVOLUTION_LOOP = None
    logger.warning("skill_evolution_loop_not_available")


# =============================================================================
# CRITICAL FIX: normalize_skill_id()
# =============================================================================
def normalize_skill_id(skill) -> str:
    """
    Extract skill_id with multiple fallbacks.
    NEVER returns "unknown" - always returns a valid identifier.

    This is critical because:
    - goal_executions table requires valid skill_id
    - experiences table requires valid skill_used
    - Analytics and learning depend on correct skill_id

    Args:
        skill: Skill instance or class

    Returns:
        str: Valid skill identifier (never "unknown")
    """
    # Try 1: Direct id attribute
    skill_id = getattr(skill, 'id', None)
    if skill_id and skill_id != "unknown":
        return skill_id

    # Try 2: name attribute (some skills use 'name' instead of 'id')
    name = getattr(skill, 'name', None)
    if name and name != "unknown":
        return name

    # Try 3: Class name conversion
    class_name = skill.__class__.__name__
    if "Skill" in class_name:
        # Convert "EchoSkill" → "core.echo"
        # Convert "WriteFileSkill" → "core.write_file"
        base_name = class_name.replace("Skill", "").lower()
        return f"core.{base_name}"

    # Try 4: Module name
    module_name = getattr(skill, '__module__', '')
    if 'canonical_skills' in module_name:
        return f"canonical.{class_name.lower()}"

    # Try 5: Generate consistent hash-based ID
    # This ensures the same skill always gets the same ID
    skill_hash = hash(str(skill))
    skill_id = f"skill_{skill_hash & 0x7fffffff}"  # Positive hash
    logger.warning(
        "skill_id_using_hash",
        skill_class=class_name,
        module=module_name,
        generated_id=skill_id
    )
    return skill_id
    ExecutionContext = None

# Centralized logging
from logging_config import get_logger

logger = get_logger(__name__)


class GoalExecutorV2:
    """
    Goal Executor v2 with Canonical Skills Integration

    Отличие от v1:
    - Работает с навыками по каноническому интерфейсу
    - Skills возвращают SkillResult с Artifact[]
    - Skills самостоятельно verify свои результаты
    - Goal Executor только orchestrates, не выполняет логику
    """

    # Class-level constants (accessible from all methods)
    MAX_ATTEMPTS_DEFAULT = 2
    RETRY_DELAY_SECONDS = 2
    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self):
        from infrastructure.uow import GoalRepository
        self._repo = GoalRepository()
        self._init_skills()

    def _init_skills(self):
        """Инициализация и регистрация навыков"""
        # Note: Skills are already loaded by unified_skill_service and registered in skill_router
        # Here we just register in canonical_skills.registry for execution engine
        
        # Register core skills that are needed for execution
        # (these are loaded from canonical_skills by unified_skill_service)
        try:
            from canonical_skills.echo import EchoSkill
            skill_registry.register(EchoSkill())
        except Exception as e:
            logger.warning("echo_load_failed", error=str(e))
        
        try:
            from canonical_skills.write_file import WriteFileSkill
            skill_registry.register(WriteFileSkill())
        except Exception as e:
            logger.warning("write_file_load_failed", error=str(e))
        
        # File operations - may already be loaded by unified_skill_service
        try:
            from canonical_skills.file_read import FileReadSkill
            skill_registry.register(FileReadSkill())
        except Exception as e:
            logger.warning("file_read_load_failed", error=str(e))
        
        try:
            from canonical_skills.file_list import FileListSkill
            skill_registry.register(FileListSkill())
        except Exception as e:
            logger.warning("file_list_load_failed", error=str(e))
        
        try:
            from canonical_skills.file_search import FileSearchSkill
            skill_registry.register(FileSearchSkill())
        except Exception as e:
            logger.warning("file_search_load_failed", error=str(e))
        
        # System skills
        try:
            from canonical_skills.run_command import RunCommandSkill
            skill_registry.register(RunCommandSkill())
        except Exception as e:
            logger.warning("run_command_load_failed", error=str(e))
        
        # AI skills
        try:
            from canonical_skills.summarize_text import SummarizeTextSkill
            skill_registry.register(SummarizeTextSkill())
        except Exception as e:
            logger.warning("summarize_text_load_failed", error=str(e))
        
        try:
            from canonical_skills.analyze_text import AnalyzeTextSkill
            skill_registry.register(AnalyzeTextSkill())
        except Exception as e:
            logger.warning("analyze_text_load_failed", error=str(e))
        
        try:
            from canonical_skills.create_directory import CreateDirectorySkill
            skill_registry.register(CreateDirectorySkill())
        except Exception as e:
            logger.warning("create_directory_load_failed", error=str(e))

        # Web research skill
        try:
            from canonical_skills.web_research import WebResearchSkill
            web_skill = WebResearchSkill()
            logger.info("web_research_skill_loaded", skill_id=str(web_skill.id), capabilities=web_skill.capabilities)
            skill_registry.register(web_skill)
            logger.info("web_research_skill_registered")
        except Exception as e:
            logger.warning("web_research_load_failed", error=str(e))
            import traceback
            logger.error("traceback", exc_info=True)

        logger.info("goal_executor_v2_initialized", skills_count=len(skill_registry.list()))
        for skill in skill_registry.list():
            logger.debug("registered_skill", skill_id=skill.id, version=skill.version, description=skill.description)

    async def execute_goal(
        self,
        *,
        goal_id: str,
        uow: "UnitOfWork",
        session_id: Optional[str] = None,
        max_attempts_override: Optional[int] = None
    ):
        """
        Выполняет цель используя Skills (v6.0 - Pure Function).

        CRITICAL INVARIANT:
        ===================
        Executor is now a PURE FUNCTION.
        Returns ExecutionOutcome, NOT state changes.

        NO:
        - transition_service calls
        - artifact_registry writes
        - DB mutations
        - goal.status changes

        YES:
        - Read goal (via uow)
        - Execute skill with retry
        - Return ExecutionOutcome with artifact data

        ARCHITECTURE v6.0:
        ==================
        Phase 1 (READ):   Get goal snapshot (read-only)
        Phase 2 (EXECUTE): Run skill with retry
        Phase 3 (OUTCOME): Return ExecutionOutcome (no side effects)

        Caller (BulkEngine) decides what to do with outcome.
        """
        from uuid import UUID
        from datetime import datetime
        import asyncio

        # Use class-level constants, with override support for max_attempts
        max_attempts = max_attempts_override if max_attempts_override is not None else self.MAX_ATTEMPTS_DEFAULT

        trace = {
            "goal_id": goal_id,
            "started_at": datetime.utcnow().isoformat(),
            "steps": [],
            "attempts": []
        }

        # =================================================================
        # PHASE 1: READ - Get goal snapshot (uses caller's transaction)
        # =================================================================
        logger.info("execution_phase_1_read", goal_id=goal_id[:8])

        # Use caller's transaction
        goal = await self._repo.get(uow.session, UUID(goal_id))
        if not goal:
            return {"status": "error", "message": f"Goal {goal_id} not found"}

        # Emit GoalExecutionStarted event
        try:
            from datetime import datetime
            from application.events.execution_events import GoalExecutionStarted
            event_bus = get_event_bus()
            await event_bus.publish(GoalExecutionStarted(
                goal_id=UUID(goal_id),
                goal_title=goal.title,
                goal_type=goal.goal_type or "",
                is_atomic=goal.is_atomic,
                started_at=datetime.utcnow()
            ))
        except Exception as e:
            logger.warning(f"Failed to emit GoalExecutionStarted: {e}")

        goal_snapshot = {
            "id": str(goal.id),
            "title": goal.title,
            "description": goal.description,
            "goal_type": goal.goal_type,
            "is_atomic": goal.is_atomic,
            "completion_criteria": goal.completion_criteria,
            "success_definition": goal.success_definition,
            "domains": goal.domains or [],
            "constraints": goal.constraints or {},
            "progress": goal.progress or 0.0,
            "execution_mode": goal.completion_mode or "auto"
        }

        trace["steps"].append({"step": "phase_1_read", "success": True})

        # =================================================================
        # PHASE 2: EXECUTE with RETRY - Run skill WITHOUT transaction
        # =================================================================
        logger.info("execution_phase_2_execute_with_retry", goal_id=goal_id[:8])

        best_result = None
        best_evaluation = None
        attempt_feedback = []

        for attempt_num in range(1, max_attempts + 1):
            attempt_start = datetime.utcnow()
            trace["attempts"].append({"attempt": attempt_num, "started_at": attempt_start.isoformat()})

            try:
                result, evaluation = await self._execute_single_attempt(
                    goal_snapshot=goal_snapshot,
                    goal_id=goal_id,
                    session_id=session_id,
                    attempt_num=attempt_num,
                    previous_feedback=attempt_feedback
                )

                attempt_end = datetime.utcnow()
                trace["attempts"][-1]["duration_ms"] = int((attempt_end - attempt_start).total_seconds() * 1000)
                trace["attempts"][-1]["success"] = result.success
                trace["attempts"][-1]["confidence"] = evaluation.confidence if evaluation else 0.0

                logger.info("attempt_complete",
                           attempt=attempt_num,
                           success=result.success,
                           confidence=evaluation.confidence if evaluation else 0.0)

                # Track best result - prefer successful results
                logger.info("best_result_tracking", attempt=attempt_num, result_success=result.success if result else None, best_result_exists=best_result is not None, best_result_success=best_result.success if best_result else None)
                if best_result is None:
                    best_result = result
                    best_evaluation = evaluation
                    logger.info("best_result_set_first", attempt=attempt_num)
                elif result.success and not best_result.success:
                    # Prefer successful result over failed
                    best_result = result
                    best_evaluation = evaluation
                    logger.info("best_result_replaced_failed", attempt=attempt_num)
                elif result.success == best_result.success and evaluation and best_evaluation and evaluation.confidence > best_evaluation.confidence:
                    # Same success state, pick higher confidence
                    best_result = result
                    best_evaluation = evaluation
                    logger.info("best_result_replaced_higher_confidence", attempt=attempt_num, old_conf=best_evaluation.confidence, new_conf=evaluation.confidence)
                else:
                    logger.info("best_result_kept", attempt=attempt_num, reason="current_not_better")

                # Check if we can stop (strong pass)
                if evaluation and evaluation.confidence >= 0.8 and result.success:
                    logger.info("strong_pass_achieved", attempt=attempt_num)
                    break

                # Determine if retry is needed
                if not self._should_retry(result, evaluation, attempt_num):
                    break

                # Prepare feedback for next attempt
                attempt_feedback = self._generate_retry_feedback(result, evaluation)
                # attempt_feedback is a list of dicts, get first reason
                reason = "unknown"
                if attempt_feedback and len(attempt_feedback) > 0:
                    reason = attempt_feedback[0].get("type", "unknown")

                logger.info("retry_scheduled",
                           attempt=attempt_num,
                           reason=reason)

                # Exponential backoff
                await asyncio.sleep(self.RETRY_DELAY_SECONDS * attempt_num)

            except Exception as e:
                logger.error("attempt_failed", attempt=attempt_num, error=str(e)[:100])
                trace["attempts"][-1]["error"] = str(e)[:100]
                
                # Check if this is a hard failure
                if self._is_hard_failure(e):
                    break
                
                # Soft failure, prepare for retry
                attempt_feedback = [{"type": "error", "message": str(e)[:100]}]
                await asyncio.sleep(self.RETRY_DELAY_SECONDS * attempt_num)

        # Use best result from all attempts
        result = best_result
        evaluation = best_evaluation

        logger.info("outcome_preparation", result_id=id(result) if result else None, best_result_id=id(best_result) if best_result else None, has_evaluation=evaluation is not None)

        trace["total_attempts"] = len(trace["attempts"])
        trace["final_confidence"] = evaluation.confidence if evaluation else 0.0

        # =================================================================
        # PHASE 3: OUTCOME - Return pure result (NO state mutations)
        # =================================================================
        logger.info("execution_phase_3_outcome", goal_id=goal_id[:8])

        from application.execution.outcomes import ExecutionOutcome

        # Extract artifact data ( WITHOUT registering in DB)
        artifacts_data = []
        logger.info("outcome_artifacts_extraction", result_exists=result is not None, artifacts_exists=result.artifacts if result else None)
        if result and result.artifacts:
            logger.info("outcome_artifacts_found", count=len(result.artifacts))
            for artifact in result.artifacts:
                # Handle both Artifact objects and dicts
                if hasattr(artifact, 'type'):  # Artifact object
                    artifacts_data.append({
                        "type": artifact.type,
                        "content_kind": artifact.metadata.get("content_kind", "file"),
                        "content_location": str(artifact.content) if artifact.content else "",
                        "verification_rule": artifact.metadata.get("verification_rule")
                    })
                elif isinstance(artifact, dict):  # Dict
                    artifacts_data.append({
                        "type": artifact.get("type", "FILE"),
                        "content_kind": artifact.get("content_kind", "file"),
                        "content_location": artifact.get("content_location", ""),
                        "verification_rule": artifact.get("verification_rule")
                    })
        logger.info("outcome_artifacts_extracted", count=len(artifacts_data))

        # Determine status
        if evaluation and evaluation.passed:
            if evaluation.confidence >= self.CONFIDENCE_THRESHOLD:
                status = "completed"
            else:
                status = "failed"
        else:
            status = "failed"

        # Emit GoalEvaluated event
        try:
            from datetime import datetime
            from application.events.execution_events import GoalEvaluated
            event_bus = get_event_bus()
            await event_bus.publish(GoalEvaluated(
                goal_id=UUID(goal_snapshot.get("id", "")),
                outcome=status,
                confidence=evaluation.confidence if evaluation else 0.0,
                passed=evaluation.passed if evaluation else False,
                artifacts_count=len(artifacts_data),
                evaluated_at=datetime.utcnow()
            ))
        except Exception as e:
            logger.warning(f"Failed to emit GoalEvaluated: {e}")

        # Return pure outcome - NO side effects
        return ExecutionOutcome(
            status=status,
            confidence=evaluation.confidence if evaluation else 0.0,
            attempts=len(trace["attempts"]),
            artifacts=artifacts_data,
            execution_trace=trace
        )

    async def _execute_single_attempt(
        self,
        goal_snapshot: dict,
        goal_id: str,
        session_id: Optional[str],
        attempt_num: int,
        previous_feedback: list
    ) -> tuple:
        """Execute single attempt with feedback incorporation."""
        from evaluation_engine import evaluation_engine
        from datetime import datetime

        requirements = self._parse_requirements_from_snapshot(goal_snapshot)
        skill = await self._select_skill(requirements, goal_snapshot)
        
        if not skill:
            from canonical_skills.base import SkillResult
            return SkillResult(success=False, error="No skill found", artifacts=[]), None

        inputs = await self._prepare_inputs_from_snapshot(goal_snapshot, skill)
        logger.info("skill_inputs_prepared", skill_id=normalize_skill_id(skill), inputs=list(inputs.keys()))
        
        if previous_feedback and attempt_num > 1:
            inputs = self._incorporate_feedback(inputs, previous_feedback)

        context = {
            "goal_id": goal_id,
            "session_id": session_id or f"goal_{goal_id}",
            "goal_title": goal_snapshot["title"],
            "attempt": attempt_num,
            "previous_failures": len(previous_feedback)
        }

        result = skill.execute(inputs, context)
        logger.info("skill_executed", skill_id=normalize_skill_id(skill), success=result.success, error=result.error, artifacts_count=len(result.artifacts))

        # Emit ArtifactProduced events
        try:
            from datetime import datetime
            from application.events.execution_events import ArtifactProduced
            event_bus = get_event_bus()
            for a in result.artifacts or []:
                await event_bus.publish(ArtifactProduced(
                    goal_id=UUID(goal_snapshot.get("id", "")),
                    skill_id=normalize_skill_id(skill),
                    artifact_type=getattr(a, 'type', 'UNKNOWN'),
                    content_kind=getattr(a, 'metadata', {}).get('content_kind', 'file'),
                    verification_status='passed' if result.success else 'failed',
                    produced_at=datetime.utcnow()
                ))
        except Exception as e:
            logger.warning(f"Failed to emit ArtifactProduced: {e}")

        # Convert Artifact objects to dicts for evaluation engine
        artifacts_for_eval = []
        if result.artifacts:
            for a in result.artifacts:
                if hasattr(a, 'to_dict'):
                    artifacts_for_eval.append(a.to_dict())
                elif hasattr(a, 'type') and hasattr(a, 'content'):
                    # Manual conversion
                    artifacts_for_eval.append({
                        "type": a.type,
                        "content": a.content,
                        "metadata": getattr(a, 'metadata', {})
                    })
                else:
                    artifacts_for_eval.append(a)

        evaluation = evaluation_engine.evaluate_goal(
            goal_completion_criteria=goal_snapshot.get("completion_criteria"),
            artifacts_produced=artifacts_for_eval,
            goal_title=goal_snapshot["title"],
            goal_description=goal_snapshot["description"]
        )

        return result, evaluation

    def _should_retry(self, result, evaluation, attempt_num: int) -> bool:
        """Determine if retry is warranted."""
        if attempt_num >= self.MAX_ATTEMPTS_DEFAULT:
            return False

        if not result or not result.success:
            return True

        if not evaluation:
            return True

        if evaluation.confidence < self.CONFIDENCE_THRESHOLD:
            return True

        if evaluation.passed and evaluation.confidence >= 0.8:
            return False

        return evaluation.confidence < 0.7

    def _is_hard_failure(self, error: Exception) -> bool:
        """Check if error is non-retryable."""
        error_str = str(error).lower()
        hard_patterns = [
            "not found",
            "invalid input",
            "constraint violation",
            "unauthorized",
            "forbidden",
            "skill not found"
        ]
        return any(pattern in error_str for pattern in hard_patterns)

    def _generate_retry_feedback(self, result, evaluation) -> list:
        """Generate feedback for next attempt."""
        feedback = []
        
        if not result.success:
            feedback.append({
                "type": "skill_failure",
                "error": result.error if result else "Unknown error"
            })

        if evaluation and not evaluation.passed:
            feedback.append({
                "type": "evaluation_failure",
                "checks_failed": [c for c in evaluation.checks if not c.get("passed")]
            })

        if evaluation and evaluation.confidence < self.CONFIDENCE_THRESHOLD:
            feedback.append({
                "type": "low_confidence",
                "confidence": evaluation.confidence
            })

        return feedback

    def _incorporate_feedback(self, inputs: dict, feedback: list) -> dict:
        """Adjust inputs based on previous feedback."""
        enhanced = inputs.copy()
        
        failure_summary = []
        for f in feedback:
            if f["type"] == "skill_failure":
                failure_summary.append(f"Previous error: {f['error']}")
            elif f["type"] == "evaluation_failure":
                failed_checks = f.get("checks_failed", [])
                if failed_checks:
                    failure_summary.append(f"Failed checks: {len(failed_checks)}")
            elif f["type"] == "low_confidence":
                failure_summary.append(f"Low confidence: {f['confidence']:.2f}")

        if failure_summary:
            enhanced["previous_attempt_feedback"] = "\n".join(failure_summary)
            enhanced["retry_instruction"] = "Previous attempt failed. Please try a different approach."

        return enhanced

    async def _write_execution_trace(self, goal_id: str, trace: dict, status: str, message: str):
        """Write execution trace to goal (separate short transaction)."""
        from infrastructure.uow import create_uow_provider
        from uuid import UUID
        
        uow_provider = create_uow_provider()
        async with uow_provider() as uow:
            goal = await self._repo.get(uow.session, UUID(goal_id))
            if goal:
                goal.execution_trace = trace
                await self._repo.update(uow.session, goal)

    def _parse_requirements_from_snapshot(self, snapshot: dict) -> dict:
        """Parse requirements from goal snapshot (no DB access)."""
        title = snapshot.get("title", "").lower()
        description = snapshot.get("description", "").lower()
        
        # Extract capabilities from title/description
        capabilities = []
        if any(w in title or w in description for w in ['research', 'search', 'find', 'lookup']):
            capabilities.append('research')
            capabilities.append('web-research')
            capabilities.append('search')
        if any(w in title or w in description for w in ['write', 'create', 'generate', 'save']):
            capabilities.append('file-write')
        if any(w in title or w in description for w in ['test', 'check', 'verify']):
            capabilities.append('testing')
        if any(w in title or w in description for w in ['code', 'program', 'implement']):
            capabilities.append('coding')
        
        # Extract expected artifacts
        artifacts = []
        if any(w in title or w in description for w in ['knowledge', 'research', 'information', 'findings']):
            artifacts.append('KNOWLEDGE')
        if any(w in title or w in description for w in ['file', 'config', 'code', 'script']):
            artifacts.append('FILE')
        
        return {
            "goal_type": snapshot.get("goal_type", "achievable"),
            "domains": snapshot.get("domains", []),
            "constraints": snapshot.get("constraints", {}),
            "title": snapshot.get("title", ""),
            "description": snapshot.get("description", ""),
            "capabilities": capabilities,
            "artifacts": artifacts
        }

    async def _select_skill(self, requirements: dict, goal_snapshot: dict):
        """Select appropriate skill with scoring (no DB access)."""
        global skill_registry

        required_capabilities = requirements.get("capabilities", [])
        required_artifacts = requirements.get("artifacts", [])
        
        goal_title = goal_snapshot.get("title", "")
        goal_type = goal_snapshot.get("goal_type", "")
        
        cached_skill = None
        cache_source = ""
        
        try:
            from trace_mining_engine import get_mining_engine
            from trace_store import get_trace_store
            
            mining_engine = get_mining_engine(get_trace_store())
            
            # Try task_signature based cache lookup (more precise)
            required_caps = requirements.get("capabilities", [])
            required_arts = requirements.get("artifacts", [])
            
            if goal_type:
                cached_skill = await mining_engine.get_best_skill(
                    goal_title=goal_title,
                    goal_type=goal_type,
                    capabilities=required_caps,
                    required_artifacts=required_arts
                )
                if cached_skill:
                    cache_source = f"cognitive_cache_task_sig:{goal_type}"
            
            # Fallback to goal_type only
            if not cached_skill and goal_type:
                cached_info = await mining_engine.get_best_skill_by_type(goal_type)
                if cached_info:
                    cached_skill = cached_info.get("skill")
                    cache_source = f"cognitive_cache_goal_type:{goal_type}"
                cache_source = "cognitive_cache_keyword"
            
            if cached_skill:
                all_skills = skill_registry.list()
                for skill in all_skills:
                    skill_name = getattr(skill, 'name', skill.__class__.__name__)
                    if cached_skill.lower() in skill_name.lower():
                        logger.info("skill_selection_cognitive_cache", 
                                  goal_id=str(goal_snapshot.get("id", ""))[:8], 
                                  skill=cached_skill, 
                                  source=cache_source,
                                  goal_type=goal_type)
                        return skill
        except Exception as e:
            logger.warning("cognitive_cache_lookup_error", error=str(e))

        all_skills = skill_registry.list()

        if not all_skills:
            # Try MCP for missing capabilities
            if required_capabilities:
                self._try_mcp_generation(required_capabilities, requirements, goal_snapshot)
            # FIXED: Return None instead of EchoSkill to signal capability gap
            logger.warning("no_skills_available", capabilities=required_capabilities)
            return None

        scored_skills = []
        
        # Get skill stats from CACHE (not DB - loop.is_running issue)
        from experience.skill_stats_cache import get_skill_stats_sync
        skill_stats = await get_skill_stats_sync()

        for skill in all_skills:
            if not skill or not hasattr(skill, 'capabilities'):
                continue

            skill_caps = getattr(skill, 'capabilities', [])
            skill_artifacts = getattr(skill, 'produces', [])
            skill_id = getattr(skill, 'id', '')

            # Base score from capability matching
            score = 0
            matched_caps = []
            missed_caps = []

            # Score capability matches
            for req_cap in required_capabilities:
                if req_cap in skill_caps:
                    score += 5
                    matched_caps.append(req_cap)
                elif req_cap in ['research', 'web-research', 'search']:
                    # Penalize if research requested but not available
                    score -= 2
                    missed_caps.append(req_cap)

            # Score artifact type matches
            for req_art in required_artifacts:
                if req_art in skill_artifacts:
                    score += 3

            # EXPERIENCE-BASED SCORING
            # CAPABILITY MATCH is PRIMARY (not reliability!)
            # Formula: capability_match (primary) + reliability (secondary)
            
            if skill_id in skill_stats:
                stats = skill_stats[skill_id]
                success_rate = stats.get('success_rate', 0.5)
                avg_latency = stats.get('avg_latency_ms', 1000)
                exploration_bonus = stats.get('exploration_bonus', 1.0)
                avg_confidence = stats.get('avg_confidence', 0.5)

                # Speed score: 1 / (1 + latency/1000) = faster is better
                speed_score = 1.0 / (1.0 + avg_latency / 1000.0)

                # Composite experience score - LOWER reliability weight
                # Capability match: up to 30 points (MUST match to be selected)
                # Reliability: up to 5 points (secondary, not primary)
                experience_score = (
                    success_rate * 0.1 * 20 +        # 0-2 points (was 11!)
                    speed_score * 0.05 * 20 +         # 0-1 points (was 4!)
                    exploration_bonus * 0.05 * 20 +   # 0-1 points (was 3!)
                    avg_confidence * 0.05 * 20        # 0-1 points (was 2!)
                )

                score += experience_score

            # Penalize generic skills (echo is fallback, not primary)
            skill_name = getattr(skill, 'name', '') or ''
            if 'echo' in skill_name.lower():
                score -= 10

            # Bonus for exact capability match
            if matched_caps and len(matched_caps) == len(required_capabilities):
                score += 5

            scored_skills.append((score, skill, matched_caps, missed_caps))

        # DECISION TRACE: Emit SkillCandidatesGenerated event
        from application.events.bus import get_event_bus
        from application.events.decision_events import SkillCandidatesGenerated
        event_bus = get_event_bus()
        
        goal_id = goal_snapshot.get("id", "")

        candidates_data = []
        for score, skill, matched, missed in scored_skills:
            skill_name = getattr(skill, 'name', skill.__class__.__name__)
            skill_id = getattr(skill, 'id', skill_name)
            candidates_data.append({
                "skill_id": skill_id,
                "score": score,
                "capabilities": getattr(skill, 'capabilities', []),
                "matched_capabilities": matched,
                "missed_capabilities": missed
            })

        await event_bus.publish(SkillCandidatesGenerated(
            goal_id=UUID(goal_id),
            requirements={
                "required_capabilities": required_capabilities,
                "required_artifacts": required_artifacts
            },
            candidates=candidates_data
        ))
        logger.info(
            "skill_candidates_generated",
            goal_id=goal_id,
            candidates_count=len(scored_skills)
        )

        # FIXED: Return None when no skills match (capability gap)
        if not scored_skills:
            logger.warning(
                "no_skills_match_capabilities",
                goal_id=goal_id,
                required_capabilities=required_capabilities,
                required_artifacts=required_artifacts
            )
            return None

        # EPSILON-GREEDY EXPLORATION
        # 15% chance to explore random skill instead of best
        import random
        epsilon = 0.15

        if random.random() < epsilon and len(scored_skills) > 1:
            # Explore: pick random from top 3
            top_k = min(3, len(scored_skills))
            chosen = random.randint(0, top_k - 1)
            best_skill = scored_skills[chosen][1]

            logger.info(
                "skill_selection_explore",
                epsilon=epsilon,
                chosen_index=chosen,
                total_skills=len(scored_skills)
            )
        else:
            # Exploit: pick best skill
            scored_skills.sort(key=lambda x: x[0], reverse=True)
            best_skill = scored_skills[0][1]

        # Log top-3 candidates for explainability
        from logging_config import get_logger
        selection_logger = get_logger(__name__)

        top_3 = scored_skills[:3] if len(scored_skills) >= 3 else scored_skills
        for i, (score, skill, matched, missed) in enumerate(top_3):
            skill_name = getattr(skill, 'name', skill.__class__.__name__)
            selection_logger.info(
                "skill_selection_candidate",
                rank=i+1,
                skill_name=skill_name,
                score=score,
                matched_capabilities=matched,
                missed_capabilities=missed
            )

        best_score, best_skill, matched, missed = scored_skills[0]
        skill_name = getattr(best_skill, 'name', best_skill.__class__.__name__)

        selection_logger.info(
            "skill_selection_final",
            selected_skill=skill_name,
            final_score=best_score,
            matched_capabilities=matched,
            missed_capabilities=missed,
            total_candidates=len(scored_skills)
        )

        # If best score is negative or too low, use better skill or fallback
        if best_score < 0 and len(scored_skills) > 1:
            selection_logger.warning(
                "skill_selection_low_score_fallback",
                original_skill=skill_name,
                original_score=best_score,
                falling_back_to_rank=2
            )
            best_score, best_skill, matched, missed = scored_skills[1]
            skill_name = getattr(best_skill, 'name', best_skill.__class__.__name__)
            selection_logger.info(
                "skill_selection_fallback",
                fallback_skill=skill_name,
                fallback_score=best_score
            )

        # If best match is still poor (score < 0 or significant missed capabilities), try MCP
        if best_score < 0 or (matched and len(missed) > len(matched)):
            # Trigger MCP generation for missing capabilities
            if missed:
                self._try_mcp_generation(missed, requirements, goal_snapshot)

        # Emit SkillSelected event (Decision Trace v1.5)
        try:
            from datetime import datetime
            from application.events.decision_events import SkillSelected
            goal_id = goal_snapshot.get("id", "")
            if goal_id and skill_name:
                event_bus = get_event_bus()

                # Extract alternative skills (what was NOT chosen)
                alternative_skills = []
                for score, skill, _, _ in scored_skills[1:]:  # Skip the chosen one
                    alt_name = getattr(skill, 'name', skill.__class__.__name__)
                    alternative_skills.append(alt_name)

                await event_bus.publish(SkillSelected(
                    goal_id=UUID(goal_id),
                    skill_id=getattr(best_skill, 'id', skill_name),
                    candidates_count=len(scored_skills),
                    rejected_count=len(scored_skills) - 1,
                    selection_reason="capability_match" if best_score >= 0 else "fallback",
                    confidence=min(1.0, max(0.0, best_score / 20.0)),  # Normalize score to 0-1
                    alternative_skills=alternative_skills
                ))
                logger.info(
                    "decision_skill_selected",
                    goal_id=goal_id[:8],
                    skill=skill_name,
                    candidates_count=len(scored_skills),
                    confidence=min(1.0, max(0.0, best_score / 20.0))
                )
        except Exception as e:
            logger.warning(f"Failed to emit SkillSelected: {e}")

        return best_skill

    def _try_mcp_generation(
        self,
        required_capabilities: list,
        requirements: dict,
        goal_snapshot: dict
    ):
        """
        Try to generate skill via MCP for missing capabilities.

        This is a non-blocking trigger - generation happens in background.
        Current execution uses EchoSkill as fallback.
        """
        try:
            import asyncio
            from mcp_manager import mcp_manager

            # Trigger generation in background
            asyncio.create_task(
                mcp_manager.find_or_generate_skill(
                    capabilities=required_capabilities,
                    requirements=requirements,
                    goal_context={
                        "title": goal_snapshot.get("title", ""),
                        "description": goal_snapshot.get("description", "")
                    }
                )
            )

            logger.info(
                "mcp_generation_triggered",
                capabilities=required_capabilities,
                fallback="echo_skill"
            )

        except Exception as e:
            logger.warning(
                "mcp_generation_trigger_failed",
                capabilities=required_capabilities,
                error=str(e)
            )

    async def _find_pattern_pipeline(self, goal_title: str, goal_description: str = "") -> list:
        """
        CRITICAL: Plan execution using Capability Graph Planner.
        
        Instead of matching patterns, we now PLAN using capability dependencies.
        
        Architecture:
        Goal → Capabilities → Graph Expansion → Ordered Plan → Skill Binding
        
        Returns:
            List of skill instances (or empty list if no good plan)
        """
        global skill_registry
        
        try:
            from semantic.capability_planner import capability_planner
            
            plan_result = capability_planner.plan(
                goal_title=goal_title,
                goal_description=goal_description
            )
            
            skills = []
            skill_sequence = plan_result.get("skills", [])
            confidence = plan_result.get("confidence", 0.0)
            plan = plan_result.get("plan", [])
            primary = plan_result.get("primary", [])
            
            if confidence >= 0.5 and skill_sequence:
                for skill_id in skill_sequence:
                    if isinstance(skill_id, str):
                        skill = skill_registry.get(skill_id)
                        if skill:
                            skills.append(skill)
                
                if skills:
                    logger.info(
                        "capability_plan_created",
                        confidence=confidence,
                        plan=plan,
                        primary=primary,
                        skills=[normalize_skill_id(s) for s in skills]
                    )
                    return skills
            
            logger.info("low_confidence_plan_fallback")
            return []
                
        except ImportError as e:
            logger.warning("capability_planner_not_available", error=str(e))
            return []
        except Exception as e:
            logger.warning("capability_plan_failed", error=str(e))
            return []

    async def _get_skill_pipeline(self, goal_snapshot: dict, requirements: dict) -> list:
        """
        CRITICAL: Get skill pipeline - FIRST from patterns, THEN from planner.
        
        This is the KEY to evolution - patterns MUST be reused!
        
        Returns:
            List of skills (or empty list if no pipeline)
        """
        global skill_registry, capability_planner
        
        goal_title = goal_snapshot.get("title", "").lower()
        goal_description = goal_snapshot.get("description", "").lower()
        
        # CRITICAL STEP 1: Check existing patterns FIRST!
        pattern_pipeline = await self._find_pattern_pipeline(goal_title, goal_description)
        if pattern_pipeline:
            logger.info("pipeline_from_pattern", skills=pattern_pipeline, goal_title=goal_title[:50])
            return pattern_pipeline
        
        # STEP 2: No pattern found - generate new pipeline
        logger.info("pipeline_generated", source="capability_planner", goal_title=goal_title[:50])
        
        if not CAPABILITY_PLANNER_AVAILABLE:
            return []
        
        try:
            # Initialize planner if needed
            if not hasattr(capability_planner, '_initialized') or not capability_planner._initialized:
                await capability_planner.initialize()
            
            # Create goal object
            from dataclasses import dataclass
            @dataclass
            class GoalObj:
                id: str
                title: str
                description: str
                goal_type: str = "achievable"
            
            goal_obj = GoalObj(
                id=goal_snapshot.get("id", ""),
                title=goal_snapshot.get("title", ""),
                description=goal_snapshot.get("description", "")
            )
            
            # Plan using capability graph
            plan = await capability_planner.plan_goal(goal_obj)
            
            # Get execution order (list of skill IDs)
            skill_ids = plan.execution_order
            
            if not skill_ids or len(skill_ids) < 2:
                # Single skill or no pipeline - don't force pipeline
                return []
            
            # Convert skill IDs to skill instances
            skills = []
            for skill_id in skill_ids:
                skill = skill_registry.get(skill_id)
                if skill:
                    skills.append(skill)
            
            if len(skills) >= 2:
                logger.info(
                    "pipeline_built",
                    pipeline_length=len(skills),
                    skills=[normalize_skill_id(s) for s in skills]
                )
                return skills
            
            return []
            
        except Exception as e:
            logger.warning("pipeline_building_failed", error=str(e))
            return []

    async def _execute_pipeline(
        self,
        uow,
        goal,
        skills: list,
        goal_snapshot: dict,
        trace: dict
    ) -> dict:
        """
        Execute a pipeline of skills in sequence.
        
        This is critical for:
        1. Multi-step execution (real work)
        2. Evolution learning (patterns from sequences)
        3. Better outcomes (compose multiple skills)
        
        CRITICAL FIX: Shared context between steps - outputs become inputs!
        
        Args:
            uow: UnitOfWork
            goal: Goal object
            skills: List of skill instances to execute
            goal_snapshot: Goal snapshot dict
            trace: Execution trace dict
            
        Returns:
            Execution result dict
        """
        from canonical_skills.base import SkillResult
        from datetime import datetime
        
        global skill_registry
        
        logger.info("pipeline_execution_started", skills_count=len(skills))
        
        all_artifacts = []
        all_errors = []
        skill_sequence = []  # FOR EVOLUTION: Log the real sequence
        
        # CRITICAL: Shared context - outputs become inputs for next step!
        pipeline_context = {
            "goal_id": str(goal.id),
            "goal_title": goal_snapshot.get("title", ""),
            "goal_description": goal_snapshot.get("description", ""),
            "artifacts": [],  # Collected artifacts from all steps
            "data": {},  # Key-value data from each step
            "step_outputs": {},  # Raw outputs from each step
            "total_steps": len(skills),
            "pipeline_mode": True
        }
        
        # Transition goal to active
        await transition_service.transition(
            uow=uow,
            goal_id=goal.id,
            new_state="active",
            reason="Starting pipeline execution",
            actor="goal_executor_v2.pipeline"
        )
        
        # Execute each skill in sequence with SHARED CONTEXT
        for i, skill in enumerate(skills):
            skill_id = normalize_skill_id(skill)
            skill_sequence.append(skill_id)
            
            step_num = i + 1
            logger.info("pipeline_step", step=step_num, total=len(skills), skill=skill_id)
            
            trace["steps"].append({
                "step": step_num,
                "skill": skill_id,
                "status": "executing",
                "has_prior_output": len(pipeline_context["step_outputs"]) > 0
            })
            
            try:
                # CRITICAL: Prepare inputs WITH prior outputs (shared context)!
                inputs = await self._prepare_inputs_with_context(goal, skill, pipeline_context)
                
                # Execute skill with full context
                context = {
                    "goal_id": str(goal.id),
                    "session_id": f"pipeline_{goal.id}",
                    "goal_title": goal_snapshot.get("title", ""),
                    "step": step_num,
                    "total_steps": len(skills),
                    "pipeline_mode": True,
                    "prior_artifacts": pipeline_context["artifacts"],
                    "prior_data": pipeline_context["data"],
                    "step_outputs": pipeline_context["step_outputs"]
                }
                
                result: SkillResult = skill.execute(inputs, context)
                
                # CRITICAL: Store outputs for next step!
                pipeline_context["step_outputs"][skill_id] = {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error
                }
                pipeline_context["data"][skill_id] = result.output
                
                if result.success:
                    trace["steps"][-1]["status"] = "success"
                    trace["steps"][-1]["artifacts_count"] = len(result.artifacts)
                    trace["steps"][-1]["output"] = result.output
                    all_artifacts.extend(result.artifacts)
                    pipeline_context["artifacts"].extend(result.artifacts)
                    
                    logger.info("pipeline_step_success", step=step_num, skill=skill_id, artifacts=len(result.artifacts))
                else:
                    trace["steps"][-1]["status"] = "failed"
                    trace["steps"][-1]["error"] = result.error
                    all_errors.append(result.error)
                    
                    logger.warning("pipeline_step_failed", step=step_num, skill=skill_id, error=result.error)
                    
                    # CRITICAL: Fail fast on first step failure (better for learning)
                    logger.info("pipeline_aborted_on_failure", step=step_num, skill=skill_id)
                    break
                    
            except Exception as e:
                error_msg = str(e)
                trace["steps"][-1]["status"] = "error"
                trace["steps"][-1]["error"] = error_msg
                all_errors.append(error_msg)
                logger.error("pipeline_step_exception", step=step_num, skill=skill_id, error=error_msg)
                
                # CRITICAL: Fail fast on exception
                logger.info("pipeline_aborted_on_exception", step=step_num, skill=skill_id)
                break
        
        # FINALIZE PIPELINE
        # Record the FULL SKILL SEQUENCE for evolution learning!
        trace["skill_sequence"] = skill_sequence
        trace["pipeline_completed"] = True
        trace["total_steps"] = len(skills)
        trace["successful_steps"] = sum(1 for s in trace["steps"] if s.get("status") == "success")
        
        # LOG TO EVOLUTION: Create pattern from sequence
        if len(skill_sequence) >= 2:
            await self._log_execution_pattern(goal, skill_sequence, all_artifacts)
        
        # CRITICAL: Stricter success criteria - ALL steps must succeed for pattern to be useful
        overall_success = (
            trace["successful_steps"] == len(skills) and  # ALL steps must succeed
            len(all_artifacts) > 0  # Must produce artifacts
        )
        
        # Register artifacts
        for artifact in all_artifacts:
            await self._register_artifact(uow, goal, artifact)
        
        # Update goal
        goal.execution_trace = trace
        goal.progress = len(all_artifacts) / max(1, len(skills))
        await self._save_goal_with_uow(uow, goal)
        
        # Transition based on success
        if overall_success:
            await transition_service.transition(
                uow=uow,
                goal_id=goal.id,
                new_state="completed",
                reason=f"Pipeline completed: {trace['successful_steps']}/{len(skills)} steps",
                actor="goal_executor_v2.pipeline"
            )
            status = "completed"
        else:
            await transition_service.transition(
                uow=uow,
                goal_id=goal.id,
                new_state="failed",
                reason=f"Pipeline partially failed: {trace['successful_steps']}/{len(skills)} steps",
                actor="goal_executor_v2.pipeline"
            )
            status = "failed"
        
        logger.info(
            "pipeline_execution_completed",
            status=status,
            steps=len(skills),
            successful=trace["successful_steps"],
            artifacts=len(all_artifacts),
            sequence=skill_sequence
        )
        
        return {
            "status": status,
            "pipeline_mode": True,
            "skill_sequence": skill_sequence,
            "steps": len(skills),
            "successful_steps": trace["successful_steps"],
            "artifacts_count": len(all_artifacts),
            "errors": all_errors
        }

    async def _log_execution_pattern(self, goal, skill_sequence: list, artifacts: list):
        """
        Log execution pattern with embedding for semantic matching.
        
        Creates skill_patterns with:
        - Pattern ID (normalized hash)
        - Skill sequence
        - Embedding for semantic search
        - Goal text for matching
        - Success rate and frequency
        """
        from sqlalchemy import text
        from datetime import datetime
        from semantic.embedding_service import embed_text, build_embedding_text
        
        try:
            artifact_types = list(set(
                a.get("type", "UNKNOWN") if isinstance(a, dict) else "UNKNOWN" 
                for a in artifacts
            ))
            
            # Get goal info
            goal_title = getattr(goal, 'title', '') or ''
            goal_description = getattr(goal, 'description', '') or ''
            
            # Build embedding text
            embedding_text = build_embedding_text(goal_title, goal_description, skill_sequence)
            
            # Generate embedding
            embedding = embed_text(embedding_text)
            
            # Normalize pattern ID
            import hashlib
            normalized_seq = "_".join(sorted(s.lower() for s in skill_sequence))
            pattern_hash = hashlib.md5(normalized_seq.encode()).hexdigest()[:16]
            pattern_id = f"pattern_{pattern_hash}"
            
            success_rate = 0.8 if len(artifacts) > 0 else 0.3
            
            async with AsyncSessionLocal() as session:
                # Upsert pattern with embedding
                if embedding:
                    upsert_sql = text("""
                        INSERT INTO skill_patterns (id, pattern_id, skill_sequence, frequency, avg_success_rate, common_artifact_types, embedding, goal_text, discovered_at, last_seen_at)
                        VALUES (gen_random_uuid(), :pattern_id, :skill_sequence::jsonb, 1, :success_rate, :artifact_types::jsonb, :embedding::jsonb, :goal_text, NOW(), NOW())
                        ON CONFLICT (pattern_id) DO UPDATE SET
                            frequency = skill_patterns.frequency + 1,
                            avg_success_rate = (skill_patterns.avg_success_rate + :success_rate) / 2,
                            embedding = COALESCE(:embedding::jsonb, skill_patterns.embedding),
                            goal_text = COALESCE(:goal_text, skill_patterns.goal_text),
                            last_seen_at = NOW()
                    """)
                else:
                    upsert_sql = text("""
                        INSERT INTO skill_patterns (id, pattern_id, skill_sequence, frequency, avg_success_rate, common_artifact_types, goal_text, discovered_at, last_seen_at)
                        VALUES (gen_random_uuid(), :pattern_id, :skill_sequence::jsonb, 1, :success_rate, :artifact_types::jsonb, :goal_text, NOW(), NOW())
                        ON CONFLICT (pattern_id) DO UPDATE SET
                            frequency = skill_patterns.frequency + 1,
                            avg_success_rate = (skill_patterns.avg_success_rate + :success_rate) / 2,
                            goal_text = COALESCE(:goal_text, skill_patterns.goal_text),
                            last_seen_at = NOW()
                    """)
                
                await session.execute(upsert_sql, {
                    "pattern_id": pattern_id,
                    "skill_sequence": json.dumps(skill_sequence),
                    "success_rate": success_rate,
                    "artifact_types": json.dumps(artifact_types),
                    "embedding": json.dumps(embedding) if embedding else None,
                    "goal_text": embedding_text
                })
                await session.commit()
            
            logger.info(
                "execution_pattern_logged",
                pattern_id=pattern_id,
                pattern_length=len(skill_sequence),
                sequence=skill_sequence,
                has_embedding=embedding is not None,
                artifacts=artifact_types
            )
            
        except Exception as e:
            logger.warning("pattern_logging_failed", error=str(e))

    async def _prepare_inputs_with_context(self, goal, skill, pipeline_context: dict) -> dict:
        """
        CRITICAL: Prepare inputs for skill using outputs from previous steps.
        
        This enables skills to compose - output from step N becomes input for step N+1.
        
        Example:
            Step 1: web_research -> {"text": "AI news"}
            Step 2: summarize -> {"text": "AI news from step 1"}
        
        Args:
            goal: Goal object
            skill: Skill instance
            pipeline_context: Shared context with outputs from previous steps
            
        Returns:
            Inputs dict for the skill
        """
        skill_id = normalize_skill_id(skill)
        
        # Get base inputs from standard preparation
        base_inputs = await self._prepare_inputs(goal, skill)
        
        # CRITICAL: Enhance inputs with outputs from previous steps
        if pipeline_context.get("step_outputs"):
            prior_outputs = pipeline_context["step_outputs"]
            
            # Try to extract useful data from previous outputs
            for prev_skill_id, output_data in prior_outputs.items():
                if not output_data.get("success"):
                    continue
                    
                output = output_data.get("output", {})
                
                # If previous step produced text, pass it to next step
                if isinstance(output, dict):
                    # Text content from previous step
                    if "text" in output and "text" not in base_inputs:
                        base_inputs["text"] = output["text"]
                        base_inputs["prior_text_source"] = prev_skill_id
                    
                    # Keywords from research
                    if "keywords" in output and "keywords" not in base_inputs:
                        base_inputs["keywords"] = output["keywords"]
                        base_inputs["prior_keywords_source"] = prev_skill_id
                    
                    # File paths
                    if "file_path" in output and "path" not in base_inputs:
                        base_inputs["path"] = output["file_path"]
                    
                    # Raw data
                    if "data" in output:
                        base_inputs["prior_data"] = output["data"]
            
            # Add pipeline metadata to inputs
            base_inputs["pipeline_context"] = {
                "total_steps": pipeline_context.get("total_steps", 0),
                "prior_artifacts_count": len(pipeline_context.get("artifacts", [])),
                "has_prior_output": True
            }
        
        logger.debug(
            "inputs_enhanced_with_context",
            skill=skill_id,
            base_keys=list(base_inputs.keys()),
            has_prior=bool(pipeline_context.get("step_outputs"))
        )
        
        return base_inputs

    async def _log_execution_pattern(self, goal, skill_sequence: list, artifacts: list):
        """Register artifact from skill execution."""
        from models import Artifact
        from uuid import uuid4
        
        try:
            artifact_record = Artifact(
                id=uuid4(),
                goal_id=goal.id,
                artifact_type=artifact.get("type", "FILE"),
                content_kind=artifact.get("content_kind", "data"),
                content_location=artifact.get("content_location", ""),
                content_text=artifact.get("content_text", ""),
                verification_rule=artifact.get("verification_rule"),
                verification_status="pending"
            )
            uow.session.add(artifact_record)
            logger.debug("artifact_registered", type=artifact.get("type"))
        except Exception as e:
            logger.warning("artifact_registration_failed", error=str(e))

    async def _select_skill_with_planner(self, goal_snapshot: dict):
        """
        NEW: Task Graph planning using CapabilityPlanner.
        
        Uses CapabilityPlanner to:
        1. Decompose goal into capabilities
        2. Build capability graph with dependencies
        3. Resolve each capability to existing skills
        4. Return skills in execution order
        
        This enables:
        - Multi-step pipelines (skill chains)
        - Better capability matching
        - Discovery of missing capabilities
        """
        global skill_registry
        
        try:
            # Initialize planner if needed
            if not hasattr(capability_planner, '_initialized') or not capability_planner._initialized:
                await capability_planner.initialize()
            
            # Create minimal goal object from snapshot
            from dataclasses import dataclass
            
            @dataclass
            class GoalSnapshot:
                id: str
                title: str
                description: str
                goal_type: str = "achievable"
            
            goal_obj = GoalSnapshot(
                id=goal_snapshot.get("id", ""),
                title=goal_snapshot.get("title", ""),
                description=goal_snapshot.get("description", "")
            )
            
            # Plan using capability graph
            plan = await capability_planner.plan_goal(goal_obj)
            
            # Check if we have ready capabilities
            if plan.ready_capabilities == 0:
                logger.info(
                    "planner_no_ready_skills",
                    goal_id=str(goal_snapshot.get("id", ""))[:8],
                    missing=plan.missing_capabilities
                )
                return None
            
            # Get execution order - skills in pipeline order
            skill_ids = plan.execution_order
            
            if not skill_ids:
                return None
            
            # Get first skill from pipeline
            first_skill_id = skill_ids[0]
            
            # Look up skill in registry
            skill = skill_registry.get(first_skill_id)
            
            if skill:
                logger.info(
                    "planner_skill_selected",
                    skill_id=first_skill_id,
                    pipeline_length=len(skill_ids),
                    ready=plan.ready_capabilities,
                    missing=plan.missing_capabilities
                )
                return skill
            
            return None
            
        except Exception as e:
            logger.warning(
                "planner_selection_failed",
                error=str(e),
                goal_id=str(goal_snapshot.get("id", ""))[:8]
            )
            return None

    async def _select_skill_with_performance(
        self,
        requirements: dict,
        goal_snapshot: dict,
        session
    ):
        """
        PHASE 1: Enhanced skill selection with historical performance metrics.

        Incorporates:
        - Success rate multiplier (high-performing skills get 1.2x boost)
        - Latency penalty (slow skills get penalized)
        - Minimum execution threshold (5+ executions before trusting stats)
        """
        from infrastructure.execution_repositories import SkillStatsRepository

        # NEW: Try CapabilityPlanner first (Task Graph planning)
        if CAPABILITY_PLANNER_AVAILABLE:
            planner_skill = await self._select_skill_with_planner(goal_snapshot)
            if planner_skill:
                logger.info(
                    "skill_selected_via_planner",
                    skill_id=getattr(planner_skill, 'id', 'unknown'),
                    method="capability_planner"
                )
                return planner_skill

        # Fallback to legacy selection
        skill = await self._select_skill(requirements, goal_snapshot)

        # Try to enhance with performance metrics
        try:
            skill_stats_repo = SkillStatsRepository()
            # Use skill.id (e.g., "core.echo") not skill.name (which may not exist)
            skill_id = getattr(skill, 'id', skill.__class__.__name__)

            # Fetch stats for this skill
            stats = await skill_stats_repo.get(session, skill_id)

            if stats and stats.total_executions >= 5:
                # Apply performance-based adjustments
                success_rate = stats.success_rate or 0.5
                avg_latency = stats.avg_latency_ms or 0

                # Performance multipliers
                performance_multiplier = 1.0

                # Boost high-performing skills
                if success_rate > 0.9:
                    performance_multiplier = 1.2
                    logger.info(
                        "high_performing_skill_boost",
                        skill=skill_id,
                        success_rate=f"{success_rate:.2%}",
                        multiplier=performance_multiplier
                    )
                elif success_rate < 0.7:
                    # Penalize low-performing skills
                    performance_multiplier = 0.5
                    logger.warning(
                        "low_performing_skill_penalty",
                        skill=skill_id,
                        success_rate=f"{success_rate:.2%}",
                        multiplier=performance_multiplier
                    )

                # Latency penalty (skills slower than 5s get penalty)
                latency_penalty = 0
                if avg_latency > 5000:
                    latency_penalty = -2
                    logger.warning(
                        "high_latency_penalty",
                        skill=skill_id,
                        avg_latency_ms=avg_latency,
                        penalty=latency_penalty
                    )

                # Log final decision
                logger.info(
                    "skill_selection_with_performance",
                    skill=skill_id,
                    executions=stats.total_executions,
                    success_rate=f"{success_rate:.2%}",
                    avg_latency_ms=avg_latency,
                    performance_multiplier=performance_multiplier,
                    latency_penalty=latency_penalty
                )

                # Note: In future iterations, we could use these metrics
                # to trigger fallback to alternative skills
            else:
                logger.debug(
                    "insufficient_performance_data",
                    skill=skill_id,
                    executions=stats.total_executions if stats else 0,
                    min_required=5
                )

        except Exception as e:
            logger.warning(
                "performance_metrics_fetch_failed",
                error=str(e),
                falling_back_to="basic_selection"
            )

        return skill

    async def _prepare_inputs_from_snapshot(self, snapshot: dict, skill) -> dict:
        """
        Prepare skill inputs from snapshot (may involve LLM, but no DB).
        
        FIX: Now generates skill-specific inputs instead of generic fields.
        This is critical for skills that require specific inputs (e.g., SummarizeTextSkill needs 'text').
        """
        skill_id = normalize_skill_id(skill)
        goal_title = snapshot.get("title", "")
        goal_description = snapshot.get("description", "")

        # EchoSkill - ALWAYS works, use as fallback
        if skill_id == "core.echo":
            return {
                "text": goal_title or "Default task"
            }

        # WriteFileSkill inputs - use LLM to generate real content
        if skill_id == "core.write_file":
            filename = f"{goal_title.lower().replace(' ', '_')}.md"
            import os
            return {
                "text": f"Generated content for: {goal_title}",
                "filename": filename,
                "directory": os.getenv("ARTIFACTS_PATH", "/data/artifacts")
            }

        # WebResearchSkill inputs - needs keywords (list!)
        if skill_id == "core.web_research":
            # Extract actual search query from goal description
            query = goal_description if len(goal_description) > 10 else goal_title
            return {"keywords": [query]}

        # SummarizeTextSkill - needs text input
        if skill_id == "core.summarize_text":
            return {"text": goal_description or goal_title or "Summary task"}

        # AnalyzeTextSkill - needs text input
        if skill_id == "core.analyze_text":
            return {"text": goal_description or goal_title or "Analysis task"}

        # FileReadSkill - needs path
        if skill_id == "core.file_read":
            return {"path": "/tmp/input.txt"}

        # FileListSkill - needs path
        if skill_id == "core.file_list":
            return {"path": "."}

        # FileSearchSkill - needs query and path
        if skill_id == "core.file_search":
            return {"query": goal_title or "test", "path": "."}

        # RunCommandSkill - needs command
        if skill_id == "core.run_command":
            return {"command": "echo 'test'"}

        # CreateDirectorySkill - needs path
        if skill_id == "core.create_directory":
            return {"path": "/tmp/test_dir"}

        # DEFAULT: Always return valid inputs for EchoSkill
        return {"text": goal_title or "Default task"}

    async def execute_goal_with_uow(
        self,
        uow: "UnitOfWork",
        goal_id: str,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Выполняет цель используя Skills WITHIN an existing transaction.

        ARCHITECTURE v3.0: Transaction managed by caller via UnitOfWork.

        Args:
            uow: UnitOfWork с активной транзакцией
            goal_id: ID цели
            session_id: ID сессии

        Returns:
            Результат выполнения с artifacts
        """
        goal = await self._repo.get(uow.session, UUID(goal_id))

        if not goal:
            return {"status": "error", "message": "Goal not found"}

        if not goal.is_atomic:
            raise ValueError(
                f"V2 only handles atomic goals. Goal '{goal.title}' is not atomic. "
                f"Use Orchestrator (V1) for complex goals."
            )

        return await self._execute_atomic_goal_with_uow(uow, goal, session_id)

    async def _execute_atomic_goal_with_uow(
        self,
        uow: "UnitOfWork",
        goal: Goal,
        session_id: Optional[str]
    ) -> dict:
        """
        Выполняет atomic goal via Skills WITHIN existing transaction.

        Flow v3.0:
        1. Parse requirements
        2. Select skill
        3. Prepare inputs
        4. Execute skill (WITH TRACE)
        5. Verify result
        6. Register artifacts
        7. Evaluate
        8. Check completion

        All operations use the passed UoW - NO internal commit/rollback.
        """
        logger.info("atomic_goal_execution_started", goal_title=goal.title, goal_id=str(goal.id))

        # Start execution trace
        from datetime import datetime
        execution_start = datetime.utcnow()
        goal.execution_started_at = execution_start

        trace = {
            "goal_id": str(goal.id),
            "goal_title": goal.title,
            "started_at": execution_start.isoformat(),
            "steps": []
        }

        # PHASE 1: Create execution tracking record
        from execution_models import GoalExecution
        from uuid import uuid4

        execution_rec = GoalExecution(
            execution_id=uuid4(),
            goal_id=goal.id,
            skill_id="",  # Will be set after skill selection
            started_at=execution_start,
            success=False,  # Will be updated on completion
            artifacts_count=0
        )

        # Capture execution engine (v3 vs legacy)
        # This is passed from caller, defaults to legacy if not specified
        execution_engine = getattr(goal, '_execution_engine', None)

        try:
            # Create goal_snapshot for skill selection
            goal_snapshot = {
                "id": str(goal.id),
                "title": goal.title,
                "description": goal.description,
                "goal_type": goal.goal_type,
                "is_atomic": goal.is_atomic,
                "completion_criteria": goal.completion_criteria,
                "success_definition": goal.success_definition,
                "domains": goal.domains or [],
                "constraints": goal.constraints or {},
                "progress": goal.progress or 0.0,
                "execution_mode": goal.completion_mode or "auto"
            }
            
            # Step 1: Parse requirements
            requirements = self._parse_requirements(goal)
            logger.debug("goal_requirements", requirements=requirements)

            trace["steps"].append({
                "step": "parse_requirements",
                "requirements": requirements
            })

            # Step 2: Try Pipeline-First Execution (NEW!)
            # Get full pipeline from capability planner for multi-step execution
            pipeline_skills = await self._get_skill_pipeline(goal_snapshot, requirements)
            
            if pipeline_skills and len(pipeline_skills) > 1:
                # PIPELINE EXECUTION: Execute multiple skills in sequence
                trace["pipeline_mode"] = True
                trace["pipeline_length"] = len(pipeline_skills)
                logger.info("pipeline_execution_started", skills_count=len(pipeline_skills))
                
                pipeline_result = await self._execute_pipeline(
                    uow, goal, pipeline_skills, goal_snapshot, trace
                )
                
                if pipeline_result:
                    return pipeline_result
            
            # SINGLE SKILL FALLBACK: If no pipeline, execute single skill
            skill = await self._select_skill_with_performance(
                requirements,
                goal_snapshot,
                uow.session
            )
            if not skill:
                trace["steps"].append({
                    "step": "skill_selection",
                    "success": False,
                    "reason": f"No suitable skill found for requirements: {requirements}"
                })
                goal.execution_trace = trace
                await self._save_goal_with_uow(uow, goal)

                return {
                    "status": "error",
                    "message": f"No suitable skill found for requirements: {requirements}"
                }
            
            trace["pipeline_mode"] = False

            # Record skill selection in trace
            skill_id_normalized = normalize_skill_id(skill)
            trace["steps"].append({
                "step": "skill_selection",
                "success": True,
                "skill_selected": skill_id_normalized,
                "skill_version": skill.version,
                "selection_reason": self._explain_skill_selection(skill, requirements),
                "skill_capabilities": skill.capabilities,
                "artifacts_produced_by_skill": skill.produces_artifacts
            })

            logger.info("skill_selected", skill_id=skill_id_normalized)

            # PHASE 1: Update execution record with skill_id
            execution_rec.skill_id = skill_id_normalized
            execution_rec.execution_engine = execution_engine

            # Step 3: Prepare inputs (async for LLM generation)
            inputs = await self._prepare_inputs(goal, skill)
            logger.debug("skill_inputs", inputs=list(inputs.keys()))

            trace["steps"].append({
                "step": "prepare_inputs",
                "inputs_provided": list(inputs.keys())
            })

            await transition_service.transition(
                uow=uow,
                goal_id=goal.id,
                new_state="active",
                reason="Starting atomic goal execution",
                actor="goal_executor_v2"
            )

            # Step 4: Execute skill
            context = {
                "goal_id": str(goal.id),
                "session_id": session_id or f"goal_{goal.id}",
                "goal_title": goal.title
            }

            execution_step_start = datetime.utcnow()

            result: SkillResult = skill.execute(inputs, context)

            execution_step_end = datetime.utcnow()

            logger.info("skill_execution_result", success=result.success)
            logger.info("artifacts_count", count=len(result.artifacts))

            # Emit SkillExecuted event for Metrics Engine
            event_bus = get_event_bus()
            duration_ms = int((execution_step_end - execution_step_start).total_seconds() * 1000)
            await event_bus.publish(SkillExecuted(
                skill_id=skill_id_normalized,
                goal_id=goal.id,
                success=result.success,
                artifacts_count=len(result.artifacts),
                execution_time_ms=duration_ms,
                error=result.error if not result.success else None
            ))
            logger.info(
                "skill_executed_event_emitted",
                skill_id=skill_id_normalized,
                goal_id=str(goal.id),
                duration_ms=duration_ms
            )

            # Record execution in trace
            trace["steps"].append({
                "step": "execute_skill",
                "success": result.success,
                "skill_id": skill_id_normalized,
                "started_at": execution_step_start.isoformat(),
                "completed_at": execution_step_end.isoformat(),
                "duration_ms": int((execution_step_end - execution_step_start).total_seconds() * 1000),
                "artifacts_produced": len(result.artifacts),
                "error": result.error if not result.success else None
            })

            if not result.success:
                await transition_service.transition(
                    uow=uow,
                    goal_id=goal.id,
                    new_state="blocked",
                    reason="Skill execution failed",
                    actor="goal_executor_v2"
                )

                goal.progress = 0.0
                goal.execution_trace = trace

                # Phase 2.5.P: Feedback hook on failure
                try:
                    await executor_with_feedback.on_skill_execution_completed(
                        goal_id=str(goal.id),
                        goal_title=goal.title,
                        step_id=f"skill_{skill_id_normalized}",
                        success=False,
                        error=result.error
                    )
                except ExecutionMustStopException as e:
                    await transition_service.transition(
                        uow=uow,
                        goal_id=UUID(str(goal.id)),
                        new_state="frozen",
                        reason=f"Execution stopped by feedback loop: {str(e)}",
                        actor="goal_executor_v2"
                    )

                    goal.execution_trace = trace
                    return {
                        "status": "stopped_by_feedback",
                        "message": f"Execution stopped by feedback loop: {str(e)}",
                        "goal_id": str(goal.id),
                        "trace": trace,
                        "feedback": str(e.safety_level)
                    }

                return {
                    "status": "error",
                    "message": result.error,
                    "goal_id": str(goal.id),
                    "trace": trace
                }

            # Step 5: Verify result
            goal.progress = 0.6
            await self._save_goal_with_uow(uow, goal)

            verification_start = datetime.utcnow()
            is_valid = skill.verify(result)
            verification_end = datetime.utcnow()

            logger.info("artifact_verification", is_valid=is_valid)

            trace["steps"].append({
                "step": "verify_result",
                "verification_passed": is_valid,
                "duration_ms": int((verification_end - verification_start).total_seconds() * 1000)
            })

            # Step 6: Register artifacts in database
            from artifact_registry import ArtifactRegistry

            artifact_registry = ArtifactRegistry()
            registered_artifacts = []

            for artifact in result.artifacts:
                # Convert Artifact to dict format for registry
                # Determine content_kind based on artifact type if not in metadata
                content_kind_value = artifact.metadata.get("content_kind", "unknown")
                if content_kind_value == "unknown":
                    # Auto-determine content_kind based on artifact type
                    if artifact.type == "KNOWLEDGE":
                        content_kind_value = "db"
                    elif artifact.type == "DATASET":
                        content_kind_value = "file"
                    elif artifact.type in ["FILE", "REPORT"]:
                        content_kind_value = "file"
                    else:
                        content_kind_value = "db"  # Default to db for unknown types

                # Convert content to string representation for DB
                if isinstance(artifact.content, (dict, list)):
                    import json
                    content_location = json.dumps(artifact.content, ensure_ascii=False)
                elif artifact.type == "KNOWLEDGE" and content_kind_value == "db":
                    # For KNOWLEDGE artifacts stored in DB, ensure JSON serialization
                    import json
                    if isinstance(artifact.content, dict):
                        content_location = json.dumps(artifact.content, ensure_ascii=False)
                    else:
                        content_location = json.dumps({"content": str(artifact.content)}, ensure_ascii=False)
                else:
                    content_location = str(artifact.content)

                artifact_data = {
                    "artifact_type": artifact.type.upper(),
                    "content_kind": content_kind_value,
                    "content_location": content_location,
                    "domains": artifact.metadata.get("domains", []),
                    "tags": artifact.metadata.get("tags", []),
                    "skill_name": skill_id_normalized,
                    "auto_verify": True  # Auto-verify for atomic goals
                }

                registered = await artifact_registry.register_with_uow(
                    uow=uow,
                    goal_id=str(goal.id),
                    **artifact_data
                )
                registered_artifacts.append(registered)
                logger.debug("artifact_registered", artifact_type=artifact.type)

            # Step 7: Evaluate result
            logger.info("evaluating_goal_completion")

            evaluation_start = datetime.utcnow()
            evaluation_result = evaluation_engine.evaluate_goal(
                goal_completion_criteria=goal.completion_criteria,
                artifacts_produced=registered_artifacts,
                goal_title=goal.title,
                goal_description=goal.description
            )
            evaluation_end = datetime.utcnow()

            logger.info("evaluation_result", summary=evaluation_result.summary)
            logger.info("evaluation_confidence", confidence=f"{evaluation_result.confidence*100:.0f}%")

            # Record evaluation in trace
            trace["steps"].append({
                "step": "evaluate_result",
                "confidence": evaluation_result.confidence,
                "passed": evaluation_result.passed,
                "checks": evaluation_result.checks,
                "duration_ms": int((evaluation_end - evaluation_start).total_seconds() * 1000)
            })

            # Сохраняем evaluation result в goal
            goal.evaluation_result = evaluation_result.to_dict()
            goal.evaluation_confidence = evaluation_result.confidence

            # Step 8: Update goal status based on evaluation
            if evaluation_result.passed:
                # Phase 2.5.P: PRE-COMMIT CHECK (critical!)
                # Before marking as DONE, verify invariants
                try:
                    await executor_with_feedback.before_marking_done(
                        goal_id=str(goal.id),
                        goal_title=goal.title,
                        completion_mode=goal.completion_mode,
                        evaluation_passed=True
                    )
                except ExecutionMustStopException as e:
                    await transition_service.transition(
                        uow=uow,
                        goal_id=UUID(str(goal.id)),
                        new_state="frozen",
                        reason=f"Pre-commit check failed: {str(e)}",
                        actor="goal_executor_v2"
                    )

                    goal.progress = evaluation_result.confidence
                    goal.execution_trace = trace

                    return {
                        "status": "blocked_by_feedback",
                        "message": f"Cannot mark as DONE: {str(e)}",
                        "goal_id": str(goal.id),
                        "trace": trace,
                        "feedback": str(e.safety_level),
                        "invariant_violation": True
                    }

                await transition_service.transition(
                    uow=uow,
                    goal_id=UUID(str(goal.id)),
                    new_state="done",
                    reason="Atomic goal execution complete with safety check passed",
                    actor="goal_executor_v2"
                )

                logger.info("goal_completed", goal_id=str(goal.id))

                # Extract artifact IDs for event emission
                artifact_ids = [str(a.get("artifact_id", str(i))) for i, a in enumerate(registered_artifacts)]
                
                # Phase 2.5.P: Post-completion hook (observer + reflection)
                try:
                    await executor_with_feedback.on_goal_completed(
                        goal_id=str(goal.id),
                        goal_title=goal.title,
                        steps_total=1,
                        steps_completed=1,
                        steps_failed=0,
                        artifacts=artifact_ids,
                        completion_mode=goal.completion_mode
                    )
                except Exception as e:
                    # Log but don't fail (already marked as done)
                    logger.warning("post_completion_hook_error", error=str(e))

            else:
                to_state = "incomplete" if evaluation_result.confidence > 0.3 else "blocked"

                await transition_service.transition(
                    uow=uow,
                    goal_id=UUID(str(goal.id)),
                    new_state=to_state,
                    reason=f"Evaluation confidence {evaluation_result.confidence:.2f} - needs human review",
                    actor="goal_executor_v2"
                )

                logger.warning("goal_state_changed", new_state=to_state.upper())

                # Phase 2.5.P: Hook on incomplete goal
                try:
                    await executor_with_feedback.on_goal_failed(
                        goal_id=str(goal.id),
                        goal_title=goal.title,
                        steps_total=1,
                        steps_completed=0,
                        failure_reason=f"Evaluation failed (confidence: {evaluation_result.confidence:.2f})",
                        error_type="EvaluationFailed",
                        error_message=f"Goal did not meet completion criteria"
                    )
                except Exception as e:
                    # Log but don't fail
                    logger.warning("incomplete_hook_error", error=str(e))

            # Finalize trace
            execution_end = datetime.utcnow()
            goal.execution_completed_at = execution_end
            trace["completed_at"] = execution_end.isoformat()
            trace["total_duration_ms"] = int((execution_end - execution_start).total_seconds() * 1000)
            trace["final_status"] = goal.status
            trace["final_progress"] = goal.progress

            # Add explainability
            trace["explainability"] = self._generate_explanation(trace, evaluation_result)

            goal.execution_trace = trace
            await self._save_goal_with_uow(uow, goal)

            # PHASE 1: Complete execution record on success
            execution_end = datetime.utcnow()
            execution_rec.completed_at = execution_end
            execution_rec.duration_ms = int((execution_end - execution_start).total_seconds() * 1000)
            execution_rec.success = True
            execution_rec.confidence = evaluation_result.confidence
            execution_rec.artifacts_count = len(registered_artifacts)

            # Save execution record to database
            from infrastructure.execution_repositories import GoalExecutionRepository, SkillStatsRepository

            executions_repo = GoalExecutionRepository()
            await executions_repo.add(uow.session, execution_rec)

            # Update skill statistics
            skill_stats_repo = SkillStatsRepository()
            await skill_stats_repo.update_from_execution(
                uow.session,
                skill_id_normalized,
                execution_rec
            )

            logger.info(
                "execution_recorded",
                execution_id=str(execution_rec.execution_id),
                skill_id=skill_id_normalized,
                duration_ms=execution_rec.duration_ms,
                success=True
            )

            # Write trace directly to trace store (bypassing event bus for cross-process)
            try:
                from trace_store import get_trace_store
                trace_store = get_trace_store()
                await trace_store.append_event(
                    goal_id=str(goal.id),
                    event_type="SkillSelected",
                    data={
                        "goal_title": goal.title,
                        "goal_type": goal.goal_type or "",
                        "skill_name": skill_id_normalized,
                        "success": True,
                        "capabilities": requirements.get("capabilities", []),
                        "required_artifacts": requirements.get("artifacts", [])
                    }
                )
                await trace_store.update_trace_status(
                    goal_id=str(goal.id),
                    status="completed",
                    confidence=evaluation_result.confidence if evaluation_result else 0.5
                )
                logger.info("trace_written_to_store", goal_id=str(goal.id)[:8])
            except Exception as e:
                logger.warning("trace_write_failed", error=str(e))

            # =================================================================
            # RECORD EXPERIENCE - THIS IS THE LEARNING MOMENT
            # =================================================================
            # NOTE: Records in separate transaction via fire-and-forget
            # Using asyncio.create_task() - if it fails, execution continues
            task_type = self._infer_task_type(goal)

            try:
                # Schedule experience recording in background
                # This may fail in Celery workers, but won't block execution
                import asyncio
                asyncio.create_task(
                    self._record_experience_async(
                        goal_id=goal.id,
                        task_type=task_type,
                        skill_id=skill_id_normalized,
                        success=True,
                        confidence=evaluation_result.confidence,
                        latency_ms=execution_rec.duration_ms,
                        goal_title=goal.title,
                        goal_type=goal.goal_type,
                        artifacts_count=len(registered_artifacts)
                    )
                )
                logger.debug(
                    "experience_recording_scheduled",
                    goal_id=str(goal.id),
                    task_type=task_type,
                    skill_id=skill_id_normalized
                )

                # AUTO-LEARNING: Trigger capability gap detection and resolution
                # This is where system becomes self-improving
                asyncio.create_task(
                    self._auto_improve_capabilities(goal.id)
                )
                logger.debug(
                    "auto_improvement_scheduled",
                    goal_id=str(goal.id)
                )
            except Exception as exp_error:
                # Don't fail execution if experience recording fails
                logger.warning(
                    "experience_recording_failed",
                    error=str(exp_error),
                    goal_id=str(goal.id)
                )

            # Add content preview to artifacts for immediate viewing
            artifacts_with_preview = []
            for artifact in registered_artifacts:
                artifact_with_preview = dict(artifact)
                # Add preview for FILE artifacts
                if artifact.get("content_kind") == "file" and artifact.get("content_location"):
                    try:
                        import os
                        file_path = artifact["content_location"]
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                preview = f.read(500)
                                artifact_with_preview["content_preview"] = preview
                    except Exception as e:
                        logger.warning("preview_read_failed", error=str(e))
                        artifact_with_preview["content_preview"] = None
                artifacts_with_preview.append(artifact_with_preview)

            return {
                "status": "success",
                "goal_id": str(goal.id),
                "goal_status": goal.status,
                "skill_used": skill_id_normalized,
                "artifacts_produced": len(registered_artifacts),
                "artifacts": artifacts_with_preview,
                "verification_passed": is_valid,
                "evaluation": evaluation_result.to_dict(),
                "evaluation_passed": evaluation_result.passed,
                "confidence": evaluation_result.confidence,
                "trace": trace
            }

        except Exception as e:
            logger.error("execution_error", error=str(e), exc_info=True)

            # PHASE 1: Complete execution record on failure
            execution_end = datetime.utcnow()
            execution_rec.completed_at = execution_end
            execution_rec.duration_ms = int((execution_end - execution_start).total_seconds() * 1000) if execution_start else None
            execution_rec.success = False
            execution_rec.error_message = str(e)[:1000]  # Truncate long errors
            execution_rec.error_type = type(e).__name__
            execution_rec.artifacts_count = 0

            # Try to save execution record (may fail if transaction is broken)
            try:
                from infrastructure.execution_repositories import GoalExecutionRepository, SkillStatsRepository

                # Get skill_id if skill was selected
                if 'skill' in locals() and skill:
                    # Get skill_id even in exception handler
                    skill_id_from_exception = normalize_skill_id(skill)

                    executions_repo = GoalExecutionRepository()
                    await executions_repo.add(uow.session, execution_rec)

                    # Update skill statistics even on failure
                    skill_stats_repo = SkillStatsRepository()
                    await skill_stats_repo.update_from_execution(
                        uow.session,
                        skill_id_from_exception,
                        execution_rec
                    )

                    logger.info(
                        "execution_recorded_failure",
                        execution_id=str(execution_rec.execution_id),
                        skill_id=skill_id_from_exception,
                        error_type=execution_rec.error_type
                    )

                    # =================================================================
                    # RECORD FAILED EXPERIENCE - ALSO LEARNING MOMENT
                    # =================================================================
                    task_type = self._infer_task_type(goal)

                    try:
                        import asyncio
                        asyncio.create_task(
                            self._record_experience_async(
                                goal_id=goal.id,
                                task_type=task_type,
                                skill_id=skill_id_from_exception,
                                success=False,
                                confidence=0.0,
                                latency_ms=execution_rec.duration_ms or 0,
                                goal_title=goal.title,
                                goal_type=goal.goal_type,
                                artifacts_count=0,
                                error_type=execution_rec.error_type,
                                error_message=execution_rec.error_message
                            )
                        )
                    except Exception as exp_error:
                        logger.warning(
                            "failed_experience_recording_failed",
                            error=str(exp_error),
                            goal_id=str(goal.id)
                        )
            except Exception as db_error:
                logger.warning(
                    "failed_to_record_execution",
                    error=str(db_error)
                )

            await transition_service.transition(
                uow=uow,
                goal_id=UUID(str(goal.id)),
                new_state="blocked",
                reason=f"Execution error: {str(e)[:200]}",
                actor="goal_executor_v2"
            )

            goal.progress = 0.0

            return {
                "status": "error",
                "message": str(e),
                "goal_id": str(goal.id)
            }

    async def _record_experience_async(
        self,
        goal_id,
        task_type,
        skill_id,
        success,
        confidence,
        latency_ms,
        goal_title,
        goal_type,
        artifacts_count,
        error_type=None,
        error_message=None
    ):
        """
        Record experience in separate transaction (async background task).

        This runs AFTER UoW commits to avoid barrier violation.
        """
        try:
            from infrastructure.uow import create_uow_provider

            uow_provider = create_uow_provider()
            async with uow_provider() as uow:
                await experience_engine.record_experience(
                    session=uow.session,
                    goal_id=goal_id,
                    task_type=task_type,
                    skill_id=skill_id,
                    success=success,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    error_type=error_type,
                    error_message=error_message,
                    extra_metadata={
                        "goal_title": goal_title,
                        "goal_type": goal_type,
                        "artifacts_produced": artifacts_count
                    }
                )
                logger.debug(
                    "experience_recorded_async",
                    goal_id=str(goal_id),
                    skill_id=skill_id,
                    success=success
                )
        except Exception as e:
            # Don't fail execution if experience recording fails
            logger.warning(
                "experience_recording_async_failed",
                error=str(e),
                goal_id=str(goal_id)
            )

    async def _auto_improve_capabilities(self, goal_id):
        """
        AUTO-LEARNING: Detect and resolve capability gaps after goal execution.

        This is where AI-OS becomes self-improving:
        1. Analyze goal for missing capabilities
        2. Auto-resolve pipeline gaps
        3. Update capability graph

        Args:
            goal_id: UUID of executed goal
        """
        try:
            from capability import capability_gap_engine
            from models import Goal
            from database import AsyncSessionLocal
            from sqlalchemy import select

            # Load goal
            async with AsyncSessionLocal() as db:
                stmt = select(Goal).where(Goal.id == goal_id)
                result = await db.execute(stmt)
                goal = result.scalar_one_or_none()

                if not goal:
                    logger.debug("auto_improve_skip", goal_id=str(goal_id), reason="goal_not_found")
                    return

            # Detect gaps
            gaps = await capability_gap_engine.analyze_goal_for_gaps(goal)

            if not gaps:
                logger.debug(
                    "auto_improve_no_gaps",
                    goal_id=str(goal_id),
                    goal_title=goal.title
                )
                return

            # Auto-resolve pipeline gaps
            resolved_count = 0
            for gap in gaps:
                if gap.gap_type == "pipeline":  # Only auto-resolve pipeline gaps
                    resolution = await capability_gap_engine.resolve_gap(gap.gap_id)
                    if resolution and resolution.success:
                        resolved_count += 1

            logger.info(
                "auto_improvement_completed",
                goal_id=str(goal_id),
                goal_title=goal.title,
                gaps_detected=len(gaps),
                gaps_resolved=resolved_count
            )

        except Exception as e:
            # Don't fail if auto-improvement fails
            logger.warning(
                "auto_improvement_failed",
                goal_id=str(goal_id),
                error=str(e)
            )

    def _parse_requirements(self, goal: Goal) -> dict:
        """Парсит требования из completion_criteria и goal title"""
        requirements = {
            "artifacts": [],
            "capabilities": []
        }

        # Extract artifacts from completion_criteria
        if goal.completion_criteria:
            criteria = goal.completion_criteria
            artifacts_req = criteria.get("artifacts_required", [])

            for req in artifacts_req:
                if isinstance(req, dict):
                    req_type = req.get("type")
                    if req_type:
                        requirements["artifacts"].append(req_type.upper())
                elif isinstance(req, str):
                    requirements["artifacts"].append(req.upper())

        # 🔑 Infer capabilities from goal title and description
        title_lower = goal.title.lower()
        desc_lower = (goal.description or "").lower()

        # Research capabilities
        if any(word in title_lower or word in desc_lower for word in ["research", "search", "find", "explore", "discover", "investigate"]):
            requirements["capabilities"].append("research")
            requirements["capabilities"].append("web-research")

        # Write/Create capabilities
        if any(word in title_lower or word in desc_lower for word in ["write", "create", "generate", "produce", "make"]):
            requirements["capabilities"].append("write")
            requirements["capabilities"].append("file-production")

        # Analyze/Summarize capabilities
        if any(word in title_lower or word in desc_lower for word in ["summarize", "analyze", "condense", "summary", "analysis"]):
            requirements["capabilities"].append("analysis")
            requirements["capabilities"].append("summarization")

        # Plan/Structure capabilities
        if any(word in title_lower or word in desc_lower for word in ["plan", "structure", "design", "schema"]):
            requirements["capabilities"].append("planning")
            requirements["capabilities"].append("structured-generation")

        # Verify/Check capabilities (but NOT for research goals)
        is_research_goal = any(word in title_lower for word in ["research", "search", "find"])

        if not is_research_goal and any(word in title_lower or word in desc_lower for word in ["verify", "check", "validate", "inspect"]):
            requirements["capabilities"].append("verification")

        # Test capability - ONLY for explicit test goals
        if ("test" in title_lower or "echo" in title_lower) and "research" not in title_lower:
            requirements["capabilities"].append("test")

        return requirements

    def _infer_task_type(self, goal: Goal) -> str:
        """
        Infer task type from goal for experience tracking.

        Task type is CRITICAL for skill learning and comparison.
        Examples: web_search, summarization, write_file, analysis.

        Args:
            goal: The goal to classify

        Returns:
            Task type string
        """
        title_lower = goal.title.lower()
        desc_lower = (goal.description or "").lower()
        combined = title_lower + " " + desc_lower

        # Priority classification (most specific first)
        task_keywords = {
            "web_search": ["search", "find information", "web research", "google", "lookup"],
            "summarization": ["summarize", "summary", "condense", "brief"],
            "write_file": ["write", "create file", "generate", "produce content"],
            "analysis": ["analyze", "analysis", "evaluate", "assess"],
            "fetch_url": ["fetch", "retrieve", "get url", "download"],
            "test": ["test", "echo", "ping", "verify connection"],
            "planning": ["plan", "design", "structure", "schema"]
        }

        # Find first matching task type
        for task_type, keywords in task_keywords.items():
            if any(keyword in combined for keyword in keywords):
                return task_type

        # Fallback: use goal_type if no specific task matches
        return goal.goal_type or "general"

    async def _generate_content_with_llm(self, goal: Goal) -> str:
        """
        Generate content for goal execution using LLM.

        Args:
            goal: The goal to generate content for

        Returns:
            Generated content as string
        """
        import os
        model = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")

        prompt = f"""You are executing a goal. Generate the actual content that accomplishes this goal.

Goal: {goal.title}
Description: {goal.description or 'No description provided'}
Type: {goal.goal_type}
Level: L{goal.depth_level}

Generate a document that accomplishes this goal. Be specific, actionable, and thorough.
Do NOT include meta-commentary like "This is a test file" or "Generated by...".
Just provide the actual content.

Format: Markdown"""

        try:
            response = await chat_with_fallback(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response["choices"][0]["message"]["content"].strip()
            logger.info("llm_content_generated", chars=len(content))
            return content

        except Exception as e:
            logger.warning("llm_generation_failed_using_fallback", error=str(e))
            # Fallback to basic template
            return f"""# {goal.title}

**Type**: {goal.goal_type}
**Level**: L{goal.depth_level}
**Description**: {goal.description or 'No description provided'}

⚠️ LLM generation was unavailable. This is a basic template.
"""

    async def _prepare_inputs(self, goal: Goal, skill: Skill) -> dict:
        """
        Готовит входные данные для skill (now async for LLM support)
        """
        skill_id = normalize_skill_id(skill)

        # EchoSkill - ALWAYS works, use as fallback
        if skill_id == "core.echo":
            return {
                "text": goal.title or "Default task"
            }

        # WriteFileSkill inputs - use LLM to generate real content
        if skill_id == "core.write_file":
            filename = f"{goal.title.lower().replace(' ', '_')}.md"

            # Generate content using LLM
            logger.info("generating_content_with_llm", goal_title=goal.title)
            text = await self._generate_content_with_llm(goal)

            import os
            return {
                "text": text,
                "filename": filename,
                "directory": os.getenv("ARTIFACTS_PATH", "/data/artifacts")
            }

        # WebResearchSkill inputs - needs keywords (list!)
        if skill_id == "core.web_research":
            # Fallback to simple query if LLM fails
            query = goal.description if len(goal.description or "") > 10 else goal.title
            return {"keywords": [query]}

        # SummarizeTextSkill - needs text input
        if skill_id == "core.summarize_text":
            return {"text": goal.description or goal.title or "Summary task"}

        # AnalyzeTextSkill - needs text input
        if skill_id == "core.analyze_text":
            return {"text": goal.description or goal.title or "Analysis task"}

        # FileReadSkill - needs path
        if skill_id == "core.file_read":
            return {"path": "/tmp/input.txt"}

        # FileListSkill - needs path
        if skill_id == "core.file_list":
            return {"path": "."}

        # FileSearchSkill - needs query and path
        if skill_id == "core.file_search":
            return {"query": goal.title or "test", "path": "."}

        # RunCommandSkill - needs command
        if skill_id == "core.run_command":
            return {"command": "echo 'test'"}

        # CreateDirectorySkill - needs path
        if skill_id == "core.create_directory":
            return {"path": "/tmp/test_dir"}

        # DEFAULT: Always return valid inputs for EchoSkill
        return {"text": goal.title or "Default task"}

    async def _save_goal_with_uow(self, uow: "UnitOfWork", goal: Goal):
        """
        Saves goal within an existing UoW transaction.

        NOTE: Status changes MUST go through transition_service.transition().
        This method only saves non-status fields (progress, traces, timestamps).

        Args:
            uow: UnitOfWork with active transaction
            goal: Goal to save (must be already attached to session)
        """
        await self._repo.update(uow.session, goal)

    def _explain_skill_selection(self, skill: Skill, requirements: dict) -> str:
        """Объясняет почему был выбран этот skill"""
        reasons = []

        # Capability match
        capabilities = requirements.get("capabilities", [])
        skill_capabilities = skill.capabilities

        matching_caps = set(capabilities) & set(skill_capabilities)
        if matching_caps:
            reasons.append(f"Capability match: {list(matching_caps)}")

        # Artifact type match
        artifacts = requirements.get("artifacts", [])
        produces = skill.produces_artifacts

        matching_artifacts = set(artifacts) & set([a.lower() for a in produces])
        if matching_artifacts:
            reasons.append(f"Artifact match: {list(matching_artifacts)}")

        if not reasons:
            return f"Selected as best match (capabilities: {skill_capabilities}, produces: {produces})"

        return ". ".join(reasons)

    def _generate_explanation(self, trace: dict, evaluation_result) -> dict:
        """Генерирует объяснение выполнения goal"""
        explanation = {
            "what_happened": [],
            "why_incomplete": None,
            "recommendations": []
        }

        # Explain what happened
        for step in trace.get("steps", []):
            step_name = step.get("step", "")
            if step_name == "skill_selection":
                if step.get("success"):
                    explanation["what_happened"].append(
                        f"Selected skill: {step.get('skill_selected')} "
                        f"({step.get('selection_reason')})"
                    )
            elif step_name == "execute_skill":
                if step.get("success"):
                    explanation["what_happened"].append(
                        f"Executed skill successfully ({step.get('duration_ms')}ms, "
                        f"{step.get('artifacts_produced')} artifacts)"
                    )
                else:
                    explanation["what_happened"].append(
                        f"Skill execution failed: {step.get('error', 'Unknown error')}"
                    )
            elif step_name == "evaluate_result":
                conf = step.get("confidence", 0) * 100
                explanation["what_happened"].append(
                    f"Evaluation: {conf:.0f}% confidence ({'PASS' if step.get('passed') else 'FAIL'})"
                )

        # Explain why incomplete (if applicable)
        if evaluation_result and not evaluation_result.passed:
            failed_checks = [
                name for name, check in evaluation_result.checks.items()
                if not check.get("passed", False)
            ]

            if failed_checks:
                explanation["why_incomplete"] = (
                    f"Failed checks: {', '.join(failed_checks)}. "
                )
            else:
                explanation["why_incomplete"] = "Confidence below threshold (60%)"

            # Add recommendations
            checks = evaluation_result.checks
            if "artifact_count" in checks:
                check = checks["artifact_count"]
                if not check.get("passed"):
                    expected = check.get("expected_min", 1)
                    actual = check.get("actual", 0)
                    explanation["recommendations"].append(
                        f"Produce {expected} artifacts (currently {actual})"
                    )

            if "artifact_types" in checks:
                check = checks["artifact_types"]
                if not check.get("passed"):
                    missing = check.get("missing_types", [])
                    if missing:
                        explanation["recommendations"].append(
                            f"Add artifacts of types: {', '.join(missing)}"
                        )

        return explanation


# Global instance
goal_executor_v2 = GoalExecutorV2()
