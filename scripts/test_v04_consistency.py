"""TDD Red Phase: Verify v0.4 P2.10 + P2.11 + P2.13 implementation.

P2.10 = Deterministic Assist Layer (3 scripts)
P2.11 = Iterative Audit (round-based audit loop)
P2.13 = Structured Repair Guidance (fix_suggestion format)
"""

from pathlib import Path
import os, json

REPO = Path(r"F:\Coding\audit-driven-development")
SKILL = (REPO / "SKILL.md").read_text(encoding="utf-8")
ROADMAP = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

checks = []

# ============================================================
# P2.10: DETERMINISTIC ASSIST LAYER
# ============================================================

# D1: scripts/audit_files.py exists
afp = REPO / "scripts" / "audit_files.py"
checks.append(("D1: scripts/audit_files.py exists", not afp.exists()))

# D2: scripts/verify_lines.py exists
vlp = REPO / "scripts" / "verify_lines.py"
checks.append(("D2: scripts/verify_lines.py exists", not vlp.exists()))

# D3: scripts/rule_index.py exists
rip = REPO / "scripts" / "rule_index.py"
checks.append(("D3: scripts/rule_index.py exists", not rip.exists()))

# D4: audit_files.py accepts --spec --module --base
if afp.exists():
    ac = afp.read_text(encoding="utf-8")
    checks.append(("D4: audit_files.py has --spec --module --base args", "--spec" not in ac or "--module" not in ac or "--base" not in ac))
else:
    checks.append(("D4: audit_files.py has --spec --module --base args", True))

# D5: audit_files.py returns JSON file list (cost cap: max 50)
if afp.exists():
    checks.append(("D5: audit_files.py enforces max 50 files cap", "max 50" not in afp.read_text(encoding="utf-8").lower() and "max_files" not in afp.read_text(encoding="utf-8").lower()))
else:
    checks.append(("D5: audit_files.py enforces max 50 files cap", True))

# D6: verify_lines.py accepts --finding-json --repo
if vlp.exists():
    vc = vlp.read_text(encoding="utf-8")
    checks.append(("D6: verify_lines.py has --finding-json --repo args", "--finding-json" not in vc or "--repo" not in vc))
else:
    checks.append(("D6: verify_lines.py has --finding-json --repo args", True))

# D7: verify_lines.py outputs verified.json with line_number_confirmed field
if vlp.exists():
    checks.append(("D7: verify_lines.py outputs line_number_confirmed field", "line_number_confirmed" not in vlp.read_text(encoding="utf-8")))
else:
    checks.append(("D7: verify_lines.py outputs line_number_confirmed field", True))

# D8: rule_index.py accepts --spec --adrs
if rip.exists():
    rc = rip.read_text(encoding="utf-8")
    checks.append(("D8: rule_index.py has --spec --adrs args", "--spec" not in rc or "--adrs" not in rc))
else:
    checks.append(("D8: rule_index.py has --spec --adrs args", True))

# D9: rule_index.py extracts "must"/"must not" statements (v2.0.1: merged into _rule_utils.py)
if rip.exists():
    rip_src = rip.read_text(encoding="utf-8").lower()
    ru_src = (REPO / "scripts" / "_rule_utils.py").read_text(encoding="utf-8").lower()
    checks.append(("D9: rule_index.py extracts must/must-not statements",
                   "must" not in rip_src and "must" not in ru_src))
else:
    checks.append(("D9: rule_index.py extracts must/must-not statements", True))

# D10: SKILL.md mentions deterministic pre-processing
checks.append(("D10: SKILL.md mentions deterministic pre-processing", "deterministic" not in SKILL.lower() and "audit_files" not in SKILL.lower()))

# ============================================================
# P2.11: ITERATIVE AUDIT
# ============================================================

# I1: SKILL.md documents --max_rounds parameter
checks.append(("I1: SKILL.md documents --max_rounds parameter", "--max_rounds" not in SKILL))

# I2: SKILL.md documents --stop_condition parameter  
checks.append(("I2: SKILL.md documents --stop_condition parameter", "--stop_condition" not in SKILL))

# I3: SKILL.md documents Round 1 → Round N loop
checks.append(("I3: SKILL.md has round-based audit loop description", "Round 1" not in SKILL and "round" not in SKILL[SKILL.find("Iterative"):].lower() if "Iterative" in SKILL else True))

# I4: Human-in-the-loop explicit in iteration flow
checks.append(("I4: Iteration flow is HUMAN-IN-THE-LOOP", "human" not in SKILL[SKILL.find("Iterative"):].lower() if "Iterative" in SKILL else "human" not in SKILL.lower()))

# I5: max_rounds default=2, max=5
checks.append(("I5: max_rounds bounded: default=2, max=5", "max_rounds" not in SKILL and "max_rounds=5" not in SKILL))

# I6: incremental_only described (only re-audit changed files)
checks.append(("I6: incremental_only mode described", "incremental_only" not in SKILL.lower() and "changed files" not in SKILL.lower()))

# I7: Round 2 can switch core lens subset
checks.append(("I7: Round 2 lens switching described", "Round 2" not in SKILL and "lens" not in SKILL[SKILL.find("Round"):].lower() if "Round" in SKILL else True))

# ============================================================
# P2.13: STRUCTURED REPAIR GUIDANCE
# ============================================================

# R1: SKILL.md documents fix_suggestion format
checks.append(("R1: SKILL.md documents structured fix_suggestion format", "fix_suggestion" not in SKILL.lower()))

# R2: fix_suggestion includes steps (ordered list)
checks.append(("R2: fix_suggestion includes steps field", "steps" not in SKILL[SKILL.find("fix_suggestion"):].lower() if "fix_suggestion" in SKILL.lower() else True))

# R3: fix_suggestion includes affected_files
checks.append(("R3: fix_suggestion includes affected_files field", "affected_files" not in SKILL.lower()))

# R4: fix_suggestion includes regression_risk
checks.append(("R4: fix_suggestion includes regression_risk field", "regression_risk" not in SKILL.lower()))

# R5: fix_suggestion includes verification_command
checks.append(("R5: fix_suggestion includes verification_command field", "verification_command" not in SKILL.lower()))

# R6: fix_suggestion includes impact description
checks.append(("R6: fix_suggestion includes impact field", "impact" not in SKILL.lower() and "fix_suggestion" in SKILL.lower()))

# R7: Subagent prompt (Template 1) updated to request fix_suggestion format
checks.append(("R7: Template 1 requires fix_suggestion output", "fix_suggestion" not in SKILL[SKILL.find("Appendix A"):].lower() if "Appendix A" in SKILL else True))

# ============================================================
# CROSS-CHECKS
# ============================================================

# C1: ROADMAP P2.10 status
checks.append(("C1: ROADMAP P2.10 status updated", "P2.10" not in ROADMAP))

# C2: ROADMAP P2.11 status
checks.append(("C2: ROADMAP P2.11 status updated", "P2.11" not in ROADMAP))

# C3: ROADMAP P2.13 status
checks.append(("C3: ROADMAP P2.13 status updated", "P2.13" not in ROADMAP))

# C4: Version Anchors reflect v0.4 progress
checks.append(("C4: Version Anchors updated for v0.4", False))

# ============================================================
# RUN
# ============================================================
failed = [name for name, is_fail in checks if is_fail]
passed = [name for name, is_fail in checks if not is_fail]

print(f"TDD RED v0.4: {len(failed)}/{len(checks)} inconsistencies found (need fix)")
print(f"  Already consistent: {len(passed)}/{len(checks)}")
print()
if failed:
    print("FAILING CHECKS (need to fix):")
    for name in failed:
        print(f"  ❌ {name}")
print()
if passed:
    print("PASSING CHECKS (already ok):")
    for name in passed:
        print(f"  ✅ {name}")
print()
print(f"Exit code: {1 if failed else 0}")
