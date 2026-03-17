"""
AUTO DECOMPOSER - Background decomposer for stuck non-atomic goals
================================================================

Автоматически decomposes pending non-atomic goals.

Problem: Non-atomic goals created but never decomposed
Solution: Background job finds stuck goals and decomposes them

Author: AI-OS Core Team
Date: 2026-02-11
Severity: CRITICAL FIX
"""

from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from database import AsyncSessionLocal
from models import Goal
from goal_decomposer import goal_decomposer

# Centralized logging
from logging_config import get_logger

logger = get_logger(__name__)


class AutoDecomposer:
    """
    Автоматически decomposes pending non-atomic goals

    КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ для stuck goals
    """

    def __init__(self):
        self.stuck_threshold_hours = 1  # 1 hour in pending = trigger decompose

    async def scan_and_decompose_stuck_goals(self) -> Dict:
        """
        Сканирует и decomposes застрявшие цели

        Returns:
            {
                "scanned": int,
                "decomposed": int,
                "skipped": int,
                "failed": int,
                "details": [...]
            }
        """
        async with AsyncSessionLocal() as db:
            # Находим pending non-atomic goals старше threshold
            threshold_time = datetime.now() - timedelta(hours=self.stuck_threshold_hours)

            stmt = select(Goal).where(
                and_(
                    Goal.status == "pending",
                    Goal.is_atomic == False,
                    Goal.created_at < threshold_time
                )
            ).order_by(Goal.created_at.asc())

            result = await db.execute(stmt)
            stuck_goals = result.scalars().all()

            report = {
                "scanned": len(stuck_goals),
                "decomposed": 0,
                "skipped": 0,
                "failed": 0,
                "details": []
            }

            for goal in stuck_goals:
                try:
                    # Проверяем: есть ли уже дети
                    stmt_children = select(func.count(Goal.id)).where(
                        Goal.parent_id == goal.id
                    )
                    result_children = await db.execute(stmt_children)
                    child_count = result_children.scalar() or 0

                    if child_count > 0:
                        # Уже decomposed - skip
                        report["skipped"] += 1
                        report["details"].append({
                            "goal_id": str(goal.id),
                            "title": goal.title[:50],
                            "action": "skipped",
                            "reason": f"already has {child_count} children"
                        })
                        continue

                    # Decompose
                    logger.info("auto_decomposing_goal", goal_title=goal.title)
                    logger.debug("goal_id", goal_id=str(goal.id))
                    logger.debug("goal_depth", depth=goal.depth_level)
                    logger.debug("goal_type", goal_type=goal.goal_type)
                    import datetime as dt
                    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                    created = goal.created_at.replace(tzinfo=None) if goal.created_at.tzinfo else goal.created_at
                    logger.debug("goal_age_hours", age=f"{(now - created).total_seconds() / 3600:.1f}")

                    # Try decomposition
                    subgoals = await goal_decomposer.decompose_goal(
                        goal_id=str(goal.id),
                        max_depth=3
                    )

                    if subgoals:
                        # Evaluate decomposition confidence
                        confidence = await evaluate_decomposition_confidence(goal, subgoals)
                        logger.info("decomposition_confidence", 
                                   goal_id=str(goal.id),
                                   confidence=confidence,
                                   threshold=DECOMPOSITION_CONFIDENCE_THRESHOLD)
                        
                        if confidence >= DECOMPOSITION_CONFIDENCE_THRESHOLD:
                            # High confidence - proceed with decomposition
                            report["decomposed"] += 1
                            report["details"].append({
                                "goal_id": str(goal.id),
                                "title": goal.title[:50],
                                "action": "decomposed",
                                "children_created": len(subgoals),
                                "confidence": confidence
                            })
                            logger.info("subgoals_created", count=len(subgoals))
                        else:
                            # Low confidence - ask questions instead
                            logger.info("low_confidence_asking_questions",
                                       goal_id=str(goal.id),
                                       confidence=confidence)
                            
                            questions = await create_decomposition_questions(goal, subgoals, db)
                            
                            report["details"].append({
                                "goal_id": str(goal.id),
                                "title": goal.title[:50],
                                "action": "questions_created",
                                "questions_count": len(questions),
                                "confidence": confidence,
                                "reason": "Low decomposition confidence"
                            })
                    else:
                        # Decompose вернул [] - возможно цель теперь atomic
                        await db.refresh(goal)

                        if goal.is_atomic:
                            report["skipped"] += 1
                            report["details"].append({
                                "goal_id": str(goal.id),
                                "title": goal.title[:50],
                                "action": "skipped",
                                "reason": "marked as atomic by decomposer"
                            })
                            logger.info("marked_as_atomic")
                        else:
                            # No decomposition - create questions
                            logger.info("decomposition_failed_creating_questions",
                                       goal_id=str(goal.id))
                            questions = await create_decomposition_questions(goal, [], db)
                            
                            report["details"].append({
                                "goal_id": str(goal.id),
                                "title": goal.title[:50],
                                "action": "questions_created",
                                "questions_count": len(questions),
                                "reason": "Decomposition returned empty"
                            })

                except Exception as e:
                    report["failed"] += 1
                    report["details"].append({
                        "goal_id": str(goal.id),
                        "title": goal.title[:50],
                        "action": "error",
                        "error": str(e)
                    })
                    logger.error("decompose_error", error=str(e))

            return report

    async def decompose_all_pending_non_atomic(self) -> Dict:
        """
        forcibly decompose ВСЕ pending non-atomic goals

        Использовать для emergency unblocking!
        """
        async with AsyncSessionLocal() as db:
            stmt = select(Goal).where(
                and_(
                    Goal.status == "pending",
                    Goal.is_atomic == False
                )
            ).order_by(Goal.created_at.asc())

            result = await db.execute(stmt)
            pending_goals = result.scalars().all()

            report = {
                "total": len(pending_goals),
                "decomposed": 0,
                "skipped": 0,
                "failed": 0
            }

            logger.info("emergency_decomposition_start")
            logger.warning("emergency_decomposition", count=len(pending_goals))

            import datetime as dt
            now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

            for i, goal in enumerate(pending_goals, 1):
                logger.info("emergency_decomposing", index=i, total=len(pending_goals), title=goal.title)
                created = goal.created_at.replace(tzinfo=None) if goal.created_at.tzinfo else goal.created_at
                logger.debug("goal_age_days", age=f"{(now - created).total_seconds() / 86400:.1f}")

                try:
                    subgoals = await goal_decomposer.decompose_goal(
                        goal_id=str(goal.id),
                        max_depth=3
                    )

                    if subgoals:
                        report["decomposed"] += 1
                        logger.info("subgoals_created", count=len(subgoals))
                    else:
                        await db.refresh(goal)
                        if goal.is_atomic:
                            report["skipped"] += 1
                            logger.debug("skipped_marked_atomic")
                        else:
                            report["failed"] += 1
                            logger.warning("decompose_failed_no_subgoals")

                except Exception as e:
                    report["failed"] += 1
                    logger.error("decompose_error", error=str(e))

            return report


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

auto_decomposer = AutoDecomposer()

# Confidence threshold for auto-decomposition
DECOMPOSITION_CONFIDENCE_THRESHOLD = 0.7


async def analyze_uncertainty(goal: Goal, subgoals: List[Dict]) -> Dict[str, float]:
    """
    Analyze what exactly the system is uncertain about.
    
    Returns uncertainty scores for:
    - first_step: How unsure about starting point
    - criteria: How unsure about success criteria  
    - constraints: How unsure about limitations
    """
    uncertainty = {
        "first_step": 0.5,
        "criteria": 0.5,
        "constraints": 0.5
    }
    
    if not subgoals:
        # No decomposition at all - high uncertainty in all
        uncertainty = {"first_step": 0.9, "criteria": 0.9, "constraints": 0.9}
        return uncertainty
    
    # Analyze subgoals for uncertainty indicators
    titles = [sg.get("title", "").lower() for sg in subgoals]
    
    # Check for first_step uncertainty
    first_step_indicators = ["начать", "старт", "инициировать", "начальный", "первый", "start", "begin"]
    if any(any(ind in t for ind in first_step_indicators) for t in titles):
        uncertainty["first_step"] = 0.2  # Clear starting point
    
    # Check for criteria uncertainty  
    generic_terms = ["and", "or", "etc", "other", "various", "success", "выполнить", "реализовать"]
    generic_count = sum(1 for t in titles if any(term in t for term in generic_terms))
    if generic_count > len(titles) * 0.5:
        uncertainty["criteria"] = 0.8  # Many generic goals = unclear criteria
    
    # Check for constraints uncertainty
    complex_description = len(goal.description or "") > 200
    if complex_description:
        uncertainty["constraints"] = 0.7
    
    # Check if subgoals have clear scope
    vague_terms = ["другие", "прочее", "остальное", "various", "other", "etc"]
    vague_count = sum(1 for t in titles if any(term in t for term in vague_terms))
    if vague_count > 0:
        uncertainty["criteria"] = max(uncertainty["criteria"], 0.6)
    
    return uncertainty


async def generate_specific_question(goal: Goal, uncertainty_type: str) -> Dict:
    """
    Generate a specific question based on uncertainty type.
    """
    base_question = {
        "first_step": {
            "text": f"С чего конкретно начать выполнение цели '{goal.title}'?",
            "type": "first_step"
        },
        "criteria": {
            "text": f"По каким конкретным критериям можно определить, что цель '{goal.title}' выполнена?",
            "type": "criteria"
        },
        "constraints": {
            "text": f"Какие есть ограничения или требования для '{goal.title}'?",
            "type": "constraints"
        }
    }
    
    return base_question.get(uncertainty_type, base_question["criteria"])


async def evaluate_decomposition_confidence(goal: Goal, subgoals: List[Dict]) -> float:
    """
    Evaluate confidence in decomposition quality.
    
    Factors:
    - Number of subgoals (too few = unclear, too many = overwhelming)
    - Subgoal specificity (generic = low confidence)
    - Coverage of original goal
    
    Returns:
        Confidence score 0.0 - 1.0
    """
    if not subgoals:
        return 0.0
    
    confidence = 0.5  # Base
    
    # Factor 1: Reasonable number of subgoals (3-7 is ideal)
    if 3 <= len(subgoals) <= 7:
        confidence += 0.2
    elif len(subgoals) < 3:
        confidence -= 0.1
    elif len(subgoals) > 10:
        confidence -= 0.1
    
    # Factor 2: Check if subgoals are specific enough
    generic_terms = ["and", "or", "etc", "other", "various", "multiple"]
    for sg in subgoals:
        title = sg.get("title", "").lower()
        if any(term in title for term in generic_terms):
            confidence -= 0.05
    
    # Factor 3: Goal complexity (longer description = more complex)
    if len(goal.description or "") > 100:
        confidence -= 0.1  # Complex goals need more clarification
    
    return max(0.0, min(1.0, confidence))


async def create_decomposition_questions(goal: Goal, subgoals: List[Dict], db) -> List[Dict]:
    """
    Create SPECIFIC clarification questions based on what system is uncertain about.
    
    The system analyzes decomposition and asks ONLY about areas of uncertainty.
    """
    from models import DecompositionSession, DecompositionQuestion
    import uuid
    
    questions = []
    
    # Analyze what we're uncertain about
    uncertainty = await analyze_uncertainty(goal, subgoals)
    logger.info("uncertainty_analysis", 
                goal_id=str(goal.id),
                first_step=uncertainty["first_step"],
                criteria=uncertainty["criteria"],
                constraints=uncertainty["constraints"])
    
    # Find areas with highest uncertainty (above threshold)
    UNCERTAINTY_THRESHOLD = 0.5
    uncertain_areas = [k for k, v in uncertainty.items() if v >= UNCERTAINTY_THRESHOLD]
    
    # If everything is certain, don't ask questions
    if not uncertain_areas:
        logger.info("no_uncertainty_questions_not_needed", goal_id=str(goal.id))
        return []
    
    # Create session
    session = DecompositionSession(
        goal_id=goal.id,
        goal_title=goal.title,
        status="pending"
    )
    db.add(session)
    await db.flush()
    
    # Generate ONE specific question about the most uncertain area
    # Sort by uncertainty level
    uncertain_areas.sort(key=lambda x: uncertainty[x], reverse=True)
    primary_uncertainty = uncertain_areas[0]
    
    question_data = await generate_specific_question(goal, primary_uncertainty)
    
    question = DecompositionQuestion(
        id=uuid.uuid4(),
        session_id=session.id,
        question_text=question_data["text"],
        question_index=1,
        asked_by="system",
        question_type=question_data["type"]
    )
    db.add(question)
    
    questions.append({
        "id": str(question.id),
        "text": question.question_text,
        "type": question.question_type,
        "uncertainty_score": uncertainty[primary_uncertainty],
        "reason": f"System is {uncertainty[primary_uncertainty]*100:.0f}% uncertain about {primary_uncertainty}"
    })
    
    # If there are multiple uncertain areas, add follow-up note
    if len(uncertain_areas) > 1:
        second_uncertainty = uncertain_areas[1]
        follow_up_text = f"Также интересуют детали по: {second_uncertainty.replace('_', ' ')}"
        question.question_text += f"\n\n{follow_up_text}"
        questions[0]["text"] = question.question_text
        questions[0]["secondary_uncertainty"] = second_uncertainty
    
    await db.commit()
    
    # Send Telegram notification about questions
    try:
        from telegram_notifier import send_decomposition_notification
        # Send the actual question, not just a notification
        if questions:
            await send_decomposition_notification(
                goal_id=str(goal.id),
                goal_title=goal.title,
                question_data={"text": questions[0].get("text", ""), "id": questions[0].get("id", "")}
            )
    except Exception as e:
        logger.warning("telegram_question_notification_failed", error=str(e))
    
    logger.info("smart_questions_created", 
                goal_id=str(goal.id), 
                questions_count=len(questions),
                primary_uncertainty=primary_uncertainty,
                uncertainty_score=uncertainty[primary_uncertainty])
    
    return questions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_auto_decompose() -> Dict:
    """Run auto-decomposition for stuck goals"""
    return await auto_decomposer.scan_and_decompose_stuck_goals()


async def emergency_decompose_all() -> Dict:
    """Emergency: decompose ALL pending non-atomic goals"""
    return await auto_decomposer.decompose_all_pending_non_atomic()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        logger.info("Testing Auto Decomposer...\n")

        # Test 1: Scan for stuck goals
        report = await auto_decomposer.scan_and_decompose_stuck_goals()

        logger.info("emergency_decomposition_start")
        logger.info(f"AUTO-DECOMPOSE REPORT")
        logger.info(f"{'='*70}")
        logger.info(f"Scanned: {report['scanned']}")
        logger.info(f"Decomposed: {report['decomposed']}")
        logger.info(f"Skipped: {report['skipped']}")
        logger.info(f"Failed: {report['failed']}")

    asyncio.run(test())
