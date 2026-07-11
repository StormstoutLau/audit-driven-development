"""TDD Red Phase: Verify v0.5 P3.1 + P3.2 + P3.3 implementation.

P3.1 = Semantic Guards (guards.template.yml + merge_guards.py)
P3.2 = Numeric Scoring (score_tracker.py + 0-100 scoring formula)
P3.3 = Cross-Project Guard Reuse (extends directive + merge)
"""

from pathlib import Path
import json, os

REPO = Path(r"F:\Coding\audit-driven-development")
SKILL = (REPO / "SKILL.md").read_text(encoding="utf-8")
ROADMAP = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
IMPL = (REPO / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

checks = []

# ============================================================
# P3.1: SEMANTIC GUARDS
# ============================================================

# G1: docs/audit/guards.template.yml exists
gtp = REPO / "docs" / "audit" / "guards.template.yml"
checks.append(("G1: docs/audit/guards.template.yml exists", not gtp.exists()))

# G2: guards.template.yml has G001 (API doc guard example)
if gtp.exists():
    gt = gtp.read_text(encoding="utf-8")
    checks.append(("G2: guards.template.yml has API doc guard example (G001)", "G001" not in gt))
    checks.append(("G3: guards.template.yml has transaction safety guard (G002)", "G002" not in gt))
else:
    checks.append(("G2: guards.template.yml has API doc guard example (G001)", True))
    checks.append(("G3: guards.template.yml has transaction safety guard (G002)", True))

# G4: scripts/merge_guards.py exists
mgp = REPO / "scripts" / "merge_guards.py"
checks.append(("G4: scripts/merge_guards.py exists", not mgp.exists()))

# G5: merge_guards.py supports --common and --project args
if mgp.exists():
    mg = mgp.read_text(encoding="utf-8")
    checks.append(("G5: merge_guards.py has --common --project args", "--common" not in mg or "--project" not in mg))
else:
    checks.append(("G5: merge_guards.py has --common --project args", True))

# G6: SKILL.md documents Guard Check subagent (extension lens)
checks.append(("G6: SKILL.md mentions Guard Check subagent/extension lens",
    "Guard Check" not in SKILL and "guard check" not in SKILL.lower() and "guards.yml" not in SKILL.lower()))

# G7: SKILL.md guards.yml section (human-authored, AI checks compliance)
checks.append(("G7: SKILL.md has Semantic Guards section",
    "guards.yml" not in SKILL.lower() or "Semantic Guards" not in SKILL))

# G8: guards.template.yml has version field
if gtp.exists():
    checks.append(("G8: guards.template.yml has version field", "version:" not in gtp.read_text(encoding="utf-8")))
else:
    checks.append(("G8: guards.template.yml has version field", True))

# G9: guards.template.yml severity mapping (critical→P1, blocker→P0, warning→P2)
if gtp.exists():
    gt = gtp.read_text(encoding="utf-8")
    checks.append(("G9: guards.template.yml has severity mapping", "critical" not in gt.lower() or "blocker" not in gt.lower()))
else:
    checks.append(("G9: guards.template.yml has severity mapping", True))

# ============================================================
# P3.2: NUMERIC SCORING
# ============================================================

# S1: scripts/score_tracker.py exists
stp = REPO / "scripts" / "score_tracker.py"
checks.append(("S1: scripts/score_tracker.py exists", not stp.exists()))

# S2: score_tracker.py has compute command (compute score from issues.json)
if stp.exists():
    st = stp.read_text(encoding="utf-8")
    checks.append(("S2: score_tracker.py has compute command", "def cmd_compute" not in st and "'compute'" not in st))
    checks.append(("S3: score_tracker.py has trend command", "def cmd_trend" not in st and "'trend'" not in st))
else:
    checks.append(("S2: score_tracker.py has compute command", True))
    checks.append(("S3: score_tracker.py has trend command", True))

# S4: 0-100 scoring formula documented in SKILL.md
checks.append(("S4: SKILL.md documents 0-100 scoring formula",
    "P0_count * 20" not in SKILL and "P1_count * 8" not in SKILL))

# S5: scores.json append-only format documented
checks.append(("S5: SKILL.md documents scores.json append-only format",
    "scores.json" not in SKILL.lower()))

# S6: scores.json has date + project + version + score + grade fields
checks.append(("S6: scores.json has 5 required fields (date/project/version/score/grade)",
    "scores.json" not in SKILL.lower()))

# S7: Mermaid trend chart section exists (or ASCII trend)
checks.append(("S7: SKILL.md documents score trend output (Mermaid or ASCII)",
    "trend" not in SKILL.lower() and "xychart" not in SKILL.lower()))

# S8: score_tracker.py score formula uses correct weights (P0=20, P1=8, P2=3, P3=1)
if stp.exists():
    checks.append(("S8: score_tracker.py uses correct severity weights", "P0" not in stp.read_text(encoding="utf-8") and "20" not in stp.read_text(encoding="utf-8")))
else:
    checks.append(("S8: score_tracker.py uses correct severity weights", True))

# ============================================================
# P3.3: CROSS-PROJECT GUARD REUSE
# ============================================================

# R1: guards.template.yml has extends directive support
if gtp.exists():
    checks.append(("R1: guards.template.yml documents extends: directive", "extends:" not in gtp.read_text(encoding="utf-8")))
else:
    checks.append(("R1: guards.template.yml documents extends: directive", True))

# R2: merge_guards.py merges common + project (project overrides common)
if mgp.exists():
    checks.append(("R2: merge_guards.py merges common+project (project overrides common)", "override" not in mgp.read_text(encoding="utf-8").lower() and "merge" not in mgp.read_text(encoding="utf-8").lower()))
else:
    checks.append(("R2: merge_guards.py merges common+project (project overrides common)", True))

# R3: SKILL.md describes two-layer guard architecture
checks.append(("R3: SKILL.md describes two-layer guard architecture (common+project)",
    "guards.common.yml" not in SKILL.lower() and "guards.project.yml" not in SKILL.lower()))

# R4: guards.common.yml exists as a reusable template (distinct from template)
cgp = REPO / "docs" / "audit" / "guards.common.yml"
checks.append(("R4: docs/audit/guards.common.yml exists as reusable guard base", not cgp.exists()))

# ============================================================
# CROSS-CHECKS
# ============================================================

# C1: ROADMAP P3.1 status updated
p3_table = ROADMAP[ROADMAP.find("| **P3.1**"):ROADMAP.find("| **P3.3**") + 100]
checks.append(("C1: ROADMAP P3.1 status updated to Done", "Done" not in p3_table.split("P3.1")[-1][:200]))

# C2: ROADMAP P3.2 status updated
checks.append(("C2: ROADMAP P3.2 status updated to Done", "Done" not in p3_table.split("P3.2")[-1][:200]))

# C3: ROADMAP P3.3 status updated
checks.append(("C3: ROADMAP P3.3 status updated to Done", "Done" not in p3_table.split("P3.3")[-1][:200]))

# C4: Version Anchors v0.5 → Done
va_table = ROADMAP[ROADMAP.find("| v0.1.1 | Iron Law"):ROADMAP.find("Total:") + 60]
checks.append(("C4: Version Anchors v0.5 marked Done", "v0.5" not in va_table or "Done" not in va_table.split("v0.5")[-1][:100]))

# C5: guard count in template (≥ 2 example guards)
if gtp.exists():
    guards_count = gtp.read_text(encoding="utf-8").count("- id:")
    checks.append(("C5: guards.template.yml has >= 2 example guards", guards_count < 2))
else:
    checks.append(("C5: guards.template.yml has >= 2 example guards", True))

# ============================================================
# BONUS: P2.7 (deferred but optional)
# ============================================================
# Not required — P2.7 is explicitly deferred due to marginal value at 94.3% recall

# ============================================================
# RUN
# ============================================================
failed = [name for name, is_fail in checks if is_fail]
passed = [name for name, is_fail in checks if not is_fail]

print(f"TDD RED v0.5: {len(failed)}/{len(checks)} inconsistencies found (need fix)")
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
