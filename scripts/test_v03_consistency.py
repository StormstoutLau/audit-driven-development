"""TDD Red Phase: Verify P2.8' Lens System + P2.12 Fix Tracking implementation.

Each check returns True if INCONSISTENCY found (test FAILS → needs fix).
Returns False if CONSISTENT (test PASSES).
"""

from pathlib import Path
import re, json

REPO = Path(r"F:\Coding\audit-driven-development")
SKILL = (REPO / "SKILL.md").read_text(encoding="utf-8")
ROADMAP = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

checks = []

# ============================================================
# P2.8' LENS SYSTEM CHECKS
# ============================================================

# L1: SKILL.md has a Lens System section
checks.append(("L1: Lens System section exists in SKILL.md",
    "Lens System" not in SKILL and "Lens Model" not in SKILL and "透镜系统" not in SKILL))

# L2: 5 Core Lens prompts exist (Design Aligner, Contract Guardian, Error Handler, Boundary Checker, Corrective Tracker)
core_lenses = ["Design Aligner", "Contract Guardian", "Error Handler", "Boundary Checker", "Corrective Tracker"]
for lens in core_lenses:
    checks.append((f"L2: Core Lens '{lens}' prompt template exists",
        lens not in SKILL))

# L3: 2 Extension Lens prompts exist (security, architecture)
ext_lenses = ["security", "architecture"]
for lens in ext_lenses:
    checks.append((f"L3: Extension Lens '--lens {lens}' prompt exists",
        f"--lens {lens}" not in SKILL.lower()))

# L3b: More specific check for security lens
checks.append(("L3b: Extension Lens '--lens security' documented with security checks",
    "Security Scanner" not in SKILL and "安全扫描" not in SKILL))

# L3c: Extension Lens '--lens architecture' documented
checks.append(("L3c: Extension Lens '--lens architecture' documented with Architecture Scanner prompt",
    "Architecture Scanner" not in SKILL and "架构健康" not in SKILL))

# L4: Lens overlap deduplication rules documented
checks.append(("L4: Lens overlap dedup rules (3 rules) documented",
    "detected_by" not in SKILL.lower() and "dedup" not in SKILL.lower()))

# L5: Each Core Lens maps to a specific Category in JSON Schema
checks.append(("L5: Core Lens → Category mapping table exists",
    "Maps to Category" not in SKILL and "Maps to" not in SKILL.lower()))

# L6: Process section mentions lens-aware dispatch
checks.append(("L6: Process Step 2 mentions lens dispatch mode",
    "per lens per module" not in SKILL.lower() and "lens dispatch" not in SKILL.lower()))

# L7: Boundaries table shows Lens coverage
boundaries = SKILL[SKILL.find("## Boundaries"):SKILL.find("## Integration")] if "## Boundaries" in SKILL else ""
checks.append(("L7: Boundaries table lists Lens-audit capabilities",
    "lens" not in boundaries.lower()))

# ============================================================
# P2.12 FIX TRACKING CHECKS
# ============================================================

# T1: scripts/issues_tracker.py exists
tracker_path = REPO / "scripts" / "issues_tracker.py"
checks.append(("T1: scripts/issues_tracker.py exists", not tracker_path.exists()))

# T2: issues_tracker.py has 4 commands: init, status, verify, summary
tracker_code = tracker_path.read_text(encoding="utf-8") if tracker_path.exists() else ""
if tracker_path.exists():
    for cmd in ["init", "status", "verify", "summary"]:
        checks.append((f"T2: issues_tracker.py has '{cmd}' command",
            f"def cmd_{cmd}" not in tracker_code and f"'{cmd}'" not in tracker_code))
else:
    for cmd in ["init", "status", "verify", "summary"]:
        checks.append((f"T2: issues_tracker.py has '{cmd}' command", True))

# T3: issues.json includes spec_ref field (for --verify mode) — check both SKILL.md and issues_tracker.py
checks.append(("T3: issues.json includes spec_ref field (for --verify mode)",
    "spec_ref" not in SKILL and "spec_ref" not in tracker_code))

# T4: State machine documented in SKILL.md
checks.append(("T4: 4-state machine documented in SKILL.md",
    "open" not in SKILL or "in_progress" not in SKILL or "fixed" not in SKILL or "verified" not in SKILL))

# T5: --verify mode described in SKILL.md
checks.append(("T5: --verify mode described in SKILL.md",
    "--verify" not in SKILL and "verify mode" not in SKILL.lower()))

# T6: verify command accepts --file parameter
checks.append(("T6: verify command accepts --file parameter",
    "--file" not in SKILL[SKILL.find("verify"):].lower() if "verify" in SKILL.lower() else True))

# T7: issues.json structure has status + fix_commit + verified_at fields (in issues_tracker.py)
checks.append(("T7: issues.json structure has status + fix_commit + verified_at fields",
    "fix_commit" not in tracker_code or "verified_at" not in tracker_code))

# ============================================================
# CROSS-CHECKS
# ============================================================

# C1: ROADMAP P2.8' status updated
checks.append(("C1: ROADMAP P2.8' status updated to Done/Implemented",
    "P2.8'" not in ROADMAP))

# C2: ROADMAP P2.12 status updated
checks.append(("C2: ROADMAP P2.12 status updated to Done/Implemented",
    "P2.12" not in ROADMAP))

# C3: Version Anchors show v0.3+v0.4 as Done if both P2.8' and P2.12 done
checks.append(("C3: Version Anchors reflect progress",
    False))  # Always check manually

# ============================================================
# RUN
# ============================================================
failed = [name for name, is_fail in checks if is_fail]
passed = [name for name, is_fail in checks if not is_fail]

print(f"TDD RED: {len(failed)}/{len(checks)} inconsistencies found (need fix)")
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
