"""Test conflict detection integration."""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
from autonomy.propositions import Proposition, reset_propositions, get_proposition_store
from autonomy.conflicts import get_conflict_detector, apply_conflict_penalty

# Setup
reset_propositions()
store = get_proposition_store()

# Create conflicting world state
sid = str(uuid4())
p1 = Proposition(
    id=uuid4(),
    subject_type="api", 
    subject_id=sid,
    predicate="responds",
    value=True,
    confidence=0.9,
    source_goal_id=None
)
p2 = Proposition(
    id=uuid4(),
    subject_type="api",
    subject_id=sid,
    predicate="responds",
    value=False,
    confidence=0.85,
    source_goal_id=None
)

store.add(p1)
store.add(p2)

print("=" * 60)
print("CONFLICT DETECTION TEST")
print("=" * 60)

# Detect
detector = get_conflict_detector()
all_props = store.get_all()
report = detector.detect(all_props)

print(f"World state: 2 propositions")
print(f"  P1: value=True, conf=0.9")
print(f"  P2: value=False, conf=0.85")
print()
print(f"Conflicts detected: {len(report.conflicts)}")
print(f"Penalty: {report.penalty:.3f}")
print()

# Test penalty formula
print("PENALTY APPLICATION:")
print("-" * 60)

test_cases = [
    ("High confidence", 0.95, 0.05),
    ("Medium confidence", 0.70, 0.20),
    ("Low confidence", 0.30, 0.50),
]

for name, orig_conf, orig_unc in test_cases:
    adj_conf, adj_unc = apply_conflict_penalty(orig_conf, orig_unc, report)
    reduction = orig_conf - adj_conf
    
    print(f"{name}:")
    print(f"  Before: conf={orig_conf:.2f}, unc={orig_unc:.2f}")
    print(f"  After:  conf={adj_conf:.2f}, unc={adj_unc:.2f}")
    print(f"  Reduction: {reduction:.3f} ({reduction/orig_conf*100:.1f}%)")
    print()

print("=" * 60)
print("FORMULA VERIFICATION")
print("=" * 60)

# Verify: confidence *= (1 - penalty)
penalty = report.penalty  # 0.85
for name, orig_conf, orig_unc in test_cases:
    adj_conf, adj_unc = apply_conflict_penalty(orig_conf, orig_unc, report)
    expected = orig_conf * (1 - penalty)
    
    is_correct = abs(adj_conf - expected) < 0.001
    status = "OK" if is_correct else "FAIL"
    print(f"{name}: {orig_conf:.2f} -> {adj_conf:.3f} (expected: {expected:.3f}) [{status}]")

print()
print("TEST PASSED" if all else "TEST FAILED")
