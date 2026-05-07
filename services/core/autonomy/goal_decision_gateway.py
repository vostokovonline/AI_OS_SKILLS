"""
GOAL DECISION GATEWAY v1.0
==========================

ЕДИНСТВЕННАЯ точка записи статуса цели.

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────┐
│                    SOURCES (Read-only)                       │
├─────────────────────────────────────────────────────────────┤
│  StrictEvaluator    → StrictEvidence (binary)               │
│  CompletionEngine   → BeliefEvidence (probabilistic)        │
│  ManualApprove      → AuthorityEvidence (human)             │
│  Invariants         → InvariantEvidence (system)            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 GOAL DECISION GATEWAY                        │
│                                                              │
│  collect_evidence() → DecisionPacket                         │
│  evaluate_policy()  → Decision                               │
│  commit()           → MUTATES goal.status (ONLY PLACE)      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                    goal.status = X

INVARIANTS:
- ТОЛЬКО GoalDecisionGateway имеет право писать goal.status
- Все остальные возвращают Evidence
- Decision детерминирован и логируется
- Replay возможен по DecisionPacket

Author: AI-OS Core Team
Date: 2026-02-23
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID


class EvidenceType(str, Enum):
    STRICT = "strict"
    BELIEF = "belief"
    AUTHORITY = "authority"
    INVARIANT = "invariant"
    HEURISTIC = "heuristic"


class DecisionType(str, Enum):
    DONE = "done"
    FAILED = "failed"
    ACTIVE = "active"
    PROVISIONAL_DONE = "provisional_done"
    FROZEN = "frozen"
    BLOCKED = "blocked"


@dataclass
class Evidence:
    type: EvidenceType
    source: str
    supports_done: bool
    confidence: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "source": self.source,
            "supports_done": self.supports_done,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata
        }


@dataclass
class DecisionPacket:
    goal_id: UUID
    collected_at: datetime
    evidence: List[Evidence] = field(default_factory=list)
    
    def add(self, evidence: Evidence):
        self.evidence.append(evidence)
    
    def by_type(self, evidence_type: EvidenceType) -> List[Evidence]:
        return [e for e in self.evidence if e.type == evidence_type]
    
    @property
    def has_authority(self) -> bool:
        return any(e.type == EvidenceType.AUTHORITY and e.supports_done 
                   for e in self.evidence)
    
    @property
    def belief_confidence(self) -> float:
        belief_ev = self.by_type(EvidenceType.BELIEF)
        if not belief_ev:
            return 0.0
        return max(e.confidence for e in belief_ev)
    
    @property
    def strict_verdict(self) -> Optional[bool]:
        strict_ev = self.by_type(EvidenceType.STRICT)
        if not strict_ev:
            return None
        return all(e.supports_done for e in strict_ev)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": str(self.goal_id),
            "collected_at": self.collected_at.isoformat(),
            "evidence": [e.to_dict() for e in self.evidence],
            "summary": {
                "has_authority": self.has_authority,
                "belief_confidence": self.belief_confidence,
                "strict_verdict": self.strict_verdict
            }
        }


@dataclass
class Decision:
    goal_id: UUID
    decision_type: DecisionType
    new_status: str
    reason: str
    packet: DecisionPacket
    decided_at: datetime
    policy_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": str(self.goal_id),
            "decision_type": self.decision_type.value,
            "new_status": self.new_status,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat(),
            "policy_version": self.policy_version,
            "evidence_summary": self.packet.to_dict()["summary"]
        }


class DecisionPolicy:
    """
    Детерминированная политика принятия решений.
    
    Policy v1.0:
    1. Authority → DONE (человек всегда прав)
    2. Strict + Belief > 0.7 → DONE
    3. Strict only → PROVISIONAL_DONE (требует подтверждения)
    4. Belief only → ACTIVE (нужны строгие доказательства)
    5. Invariant violation → BLOCKED
    """
    
    VERSION = "1.0"
    BELIEF_THRESHOLD = 0.7
    
    def evaluate(self, packet: DecisionPacket) -> Decision:
        decision_type, new_status, reason = self._apply_rules(packet)
        
        return Decision(
            goal_id=packet.goal_id,
            decision_type=decision_type,
            new_status=new_status,
            reason=reason,
            packet=packet,
            decided_at=datetime.utcnow(),
            policy_version=self.VERSION
        )
    
    def _apply_rules(self, packet: DecisionPacket) -> tuple[DecisionType, str, str]:
        invariant_block = self._check_invariants(packet)
        if invariant_block:
            return invariant_block
        
        if packet.has_authority:
            return (
                DecisionType.DONE,
                "done",
                "Authority override: human-approved decision"
            )
        
        strict_verdict = packet.strict_verdict
        belief_conf = packet.belief_confidence
        
        if strict_verdict is True and belief_conf >= self.BELIEF_THRESHOLD:
            return (
                DecisionType.DONE,
                "done",
                f"Strict + Belief verified (confidence={belief_conf:.2f})"
            )
        
        if strict_verdict is True:
            return (
                DecisionType.PROVISIONAL_DONE,
                "provisional_done",
                f"Strict verified, but belief confidence low ({belief_conf:.2f})"
            )
        
        if strict_verdict is False:
            return (
                DecisionType.FAILED,
                "failed",
                "Strict evaluator rejected completion"
            )
        
        return (
            DecisionType.ACTIVE,
            "active",
            f"Insufficient evidence (strict=None, belief={belief_conf:.2f})"
        )
    
    def _check_invariants(self, packet: DecisionPacket) -> Optional[tuple]:
        invariant_ev = packet.by_type(EvidenceType.INVARIANT)
        blockers = [e for e in invariant_ev if not e.supports_done]
        
        if blockers:
            reasons = [e.reason for e in blockers]
            return (
                DecisionType.BLOCKED,
                "blocked",
                f"Invariant violations: {'; '.join(reasons)}"
            )
        
        return None


class GoalDecisionGateway:
    """
    ЕДИНСТВЕННЫЙ gateway для записи статуса.
    
    Usage:
        gateway = GoalDecisionGateway()
        
        packet = await gateway.collect_evidence(session, goal_id)
        decision = gateway.evaluate(packet)
        
        if decision.decision_type != DecisionType.BLOCKED:
            await gateway.commit(session, goal_id, decision)
    """
    
    def __init__(self):
        self._policy = DecisionPolicy()
        self._decision_log: Dict[str, Decision] = {}
    
    async def collect_evidence(
        self,
        session,
        goal_id: UUID
    ) -> DecisionPacket:
        """
        Собирает evidence от всех источников.
        
        Sources:
        1. CompletionEngine → BeliefEvidence
        2. StrictEvaluator → StrictEvidence
        3. Manual approvals → AuthorityEvidence
        4. System invariants → InvariantEvidence
        """
        packet = DecisionPacket(
            goal_id=goal_id,
            collected_at=datetime.utcnow()
        )
        
        await self._collect_belief_evidence(session, goal_id, packet)
        await self._collect_strict_evidence(session, goal_id, packet)
        self._collect_authority_evidence(session, goal_id, packet)
        self._collect_invariant_evidence(session, goal_id, packet)
        
        return packet
    
    async def _collect_belief_evidence(
        self, session, goal_id: UUID, packet: DecisionPacket
    ):
        try:
            from autonomy.completion_engine import get_completion_engine
            
            engine = get_completion_engine()
            result = await engine.evaluate(session, goal_id)
            
            confidence = result.truth_estimate.confidence_true
            supports_done = confidence >= 0.5
            
            packet.add(Evidence(
                type=EvidenceType.BELIEF,
                source="CompletionEngine.v2.4",
                supports_done=supports_done,
                confidence=confidence,
                reason=result.reason,
                metadata={
                    "uncertainty": result.truth_estimate.uncertainty,
                    "evidence_count": result.truth_estimate.evidence_count,
                    "conflicted": len(result.truth_estimate.conflicted_predicates) > 0
                }
            ))
        except Exception as e:
            packet.add(Evidence(
                type=EvidenceType.BELIEF,
                source="CompletionEngine",
                supports_done=False,
                confidence=0.0,
                reason=f"Evaluation error: {str(e)}"
            ))
    
    async def _collect_strict_evidence(
        self, session, goal_id: UUID, packet: DecisionPacket
    ):
        try:
            from goal_strict_evaluator import GoalStrictEvaluator
            
            evaluator = GoalStrictEvaluator(session)
            result = await evaluator.evaluate(goal_id)
            
            packet.add(Evidence(
                type=EvidenceType.STRICT,
                source="GoalStrictEvaluator",
                supports_done=result.get("is_complete", False),
                confidence=1.0 if result.get("is_complete") else 0.0,
                reason=result.get("reason", "No reason provided"),
                metadata={"mode": result.get("mode", "unknown")}
            ))
        except Exception as e:
            pass
    
    def _collect_authority_evidence(
        self, session, goal_id: UUID, packet: DecisionPacket
    ):
        from models import Goal
        import asyncio
        
        try:
            goal = asyncio.get_event_loop().run_until_complete(
                session.get(Goal, goal_id)
            )
            
            if goal and goal.completion_mode == "manual":
                if goal.status == "done":
                    packet.add(Evidence(
                        type=EvidenceType.AUTHORITY,
                        source="ManualApproval",
                        supports_done=True,
                        confidence=1.0,
                        reason="Human-approved completion"
                    ))
        except Exception:
            pass
    
    def _collect_invariant_evidence(
        self, session, goal_id: UUID, packet: DecisionPacket
    ):
        from models import Goal
        import asyncio
        
        try:
            goal = asyncio.get_event_loop().run_until_complete(
                session.get(Goal, goal_id)
            )
            
            if goal:
                if goal.is_atomic and not goal.artifacts:
                    packet.add(Evidence(
                        type=EvidenceType.INVARIANT,
                        source="AtomicGoalInvariant",
                        supports_done=False,
                        confidence=1.0,
                        reason="Atomic goal has no artifacts"
                    ))
        except Exception:
            pass
    
    def evaluate(self, packet: DecisionPacket) -> Decision:
        return self._policy.evaluate(packet)
    
    async def commit(
        self,
        session,
        goal_id: UUID,
        decision: Decision
    ) -> Dict[str, Any]:
        """
        ЕДИНСТВЕННОЕ место где мутируется goal.status.
        
        Raises:
            RuntimeError: Если вызван напрямую без going через evaluate()
        """
        from models import Goal
        from logging_config import get_logger
        
        logger = get_logger(__name__)
        
        goal = await session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        old_status = goal._status
        new_status = decision.new_status
        
        if old_status == new_status:
            return {
                "changed": False,
                "old_status": old_status,
                "new_status": new_status,
                "decision": decision.to_dict()
            }
        
        goal._internal_set_status(new_status)
        
        self._decision_log[str(goal_id)] = decision
        
        logger.info(
            "goal_status_committed",
            goal_id=str(goal_id)[:8],
            old_status=old_status,
            new_status=new_status,
            decision_type=decision.decision_type.value,
            reason=decision.reason,
            policy_version=decision.policy_version
        )
        
        return {
            "changed": True,
            "old_status": old_status,
            "new_status": new_status,
            "decision": decision.to_dict()
        }
    
    def get_decision_log(self, goal_id: UUID) -> Optional[Decision]:
        return self._decision_log.get(str(goal_id))


_gateway: Optional[GoalDecisionGateway] = None


def get_decision_gateway() -> GoalDecisionGateway:
    global _gateway
    if _gateway is None:
        _gateway = GoalDecisionGateway()
    return _gateway


def reset_decision_gateway():
    global _gateway
    _gateway = GoalDecisionGateway()
