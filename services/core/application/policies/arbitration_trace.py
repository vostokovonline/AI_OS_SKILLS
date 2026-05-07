"""
Arbitration Trace - Minimal Decision Ledger
===========================================

Записывает ТОЛЬКО выбор policy. Ничего больше.

Принципы:
- Trace создаётся на один arbitration cycle (per-use-case)
- Никаких глобальных singleton
- Flush после commit (fire-and-forget)
- Только выбор - не результат execution
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass
class ArbitrationRecord:
    """
    ОДНА запись выбора.
    
    Минимальная форма - только решение, не результат.
    """
    cycle_id: "UUID"
    intent_id: "UUID"
    policy_name: str
    
    # Scores (why this was chosen/rejected)
    utility: float
    cost: float
    risk: float
    
    # Decision
    selected: bool
    rejection_reason: Optional[str] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ArbitrationTrace:
    """
    Per-cycle trace для записей выбора.
    
    Создаётся UseCase, передаётся в Policy.
    После commit - flush в storage.
    """
    
    def __init__(self, cycle_id: "UUID", policy_name: str):
        self.cycle_id = cycle_id
        self.policy_name = policy_name
        self._records: List[ArbitrationRecord] = []
    
    def record(
        self,
        intent_id: "UUID",
        utility: float,
        cost: float,
        risk: float,
        selected: bool,
        rejection_reason: Optional[str] = None
    ) -> None:
        """Записать одно решение (вызывается Policy)"""
        self._records.append(ArbitrationRecord(
            cycle_id=self.cycle_id,
            intent_id=intent_id,
            policy_name=self.policy_name,
            utility=utility,
            cost=cost,
            risk=risk,
            selected=selected,
            rejection_reason=rejection_reason
        ))
    
    def get_records(self) -> List[ArbitrationRecord]:
        """Получить все записи"""
        return self._records.copy()
    
    def count(self) -> int:
        return len(self._records)
    
    def summary(self) -> dict:
        """Краткая сводка"""
        selected = sum(1 for r in self._records if r.selected)
        return {
            "cycle_id": str(self.cycle_id),
            "policy": self.policy_name,
            "total": len(self._records),
            "selected": selected,
            "rejected": len(self._records) - selected
        }


# НЕ используем! Это был hidden singleton - ошибка.
# Trace должен создаваться UseCase и передаваться в Policy.
#
# Правильная модель:
#   trace = ArbitrationTrace(cycle_id=uuid4(), policy_name="GreedyUtility")
#   selected = await policy.select(scored, budget, trace=trace)
#   await uow.commit()
#   await trace.flush()  # AFTER commit
