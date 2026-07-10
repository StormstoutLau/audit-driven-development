"""TDD Red Phase: Check SKILL.md vs ROADMAP Detection/Repair duality consistency.

Each check returns True if INCONSISTENCY found (test FAILS → needs fix).
Returns False if CONSISTENT (test PASSES).
"""

import re
from pathlib import Path

REPO = Path(r"F:\Coding\audit-driven-development")
SKILL = (REPO / "SKILL.md").read_text(encoding="utf-8")
ROADMAP = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

checks = []

# === DETECTION/REPAIR MENTIONS ===

# R1: Overview should mention Detection/Repair duality
overview_section = SKILL[SKILL.find("## Overview"):SKILL.find("## When to Use")]
checks.append((
    "R1: Overview mentions Detection capability",
    "detection" not in overview_section.lower() and "检测" not in overview_section
))
checks.append((
    "R2: Overview mentions Repair capability",
    "repair" not in overview_section.lower() and "修复" not in overview_section
))

# R3: "When to Use" should distinguish Detection vs Repair scenarios
when_section = SKILL[SKILL.find("## When to Use"):SKILL.find("## The Iron Law")]
checks.append((
    "R3: When-to-Use distinguishes Detection vs Repair",
    "detection" not in when_section.lower() and "repair" not in when_section.lower() 
    and "检测" not in when_section and "修复" not in when_section
))

# === PROCESS STEP LABELS ===

# R4: Steps 1-3 should be labeled as Detection
process_section = SKILL[SKILL.find("## Process: Step-by-Step"):SKILL.find("## Critical Anti-Patterns")]
checks.append((
    "R4: Steps 1-3 labeled as Detection phase",
    not re.search(r'(?i)detection|检测', process_section[:process_section.find("### Step 3:") + 100])
))

# R5: Steps 4-6 should be labeled as Repair phase 
# (Step 4 = Fix Baseline, Step 5 = Fix P0, Step 6 = Final Report)
checks.append((
    "R5: Steps 4-6 labeled as Repair phase",
    not re.search(r'(?i)repair|修复.*phase|修复.*阶段', process_section[process_section.find("### Step 4:"):])
))

# === STEP 5: VERIFY-AFTER-FIX ===

# R6: Step 5 should have Verify-after-fix sub-step (borrowed from TDD)
step5_start = process_section.find("### Step 5:")
step5_end = process_section.find("### Step 6:")
step5_section = process_section[step5_start:step5_end]
checks.append((
    "R6: Step 5 has Verify-after-fix sub-step (Verify FIX)",
    "verify" not in step5_section.lower() or ("confirm" not in step5_section.lower() and "确认" not in step5_section)
))

# R7: Step 5 should have human-in-the-loop annotation
checks.append((
    "R7: Step 5 has human-in-the-loop annotation",
    "human" not in step5_section.lower() and "人工" not in step5_section.lower()
))

# === AUDIT COMPLETION CHECKLIST ===

# R8: Should have Audit Completion Checklist (borrowed from TDD)
checks.append((
    "R8: Audit Completion Checklist present",
    "completion checklist" not in SKILL.lower() and "完成.*清单" not in SKILL.lower() and "completion check" not in SKILL.lower()
))

# === BOUNDARIES TABLE ===

# R9: Boundaries table should show Repair capabilities
boundaries_section = SKILL[SKILL.find("## Boundaries"):SKILL.find("## Integration")]
checks.append((
    "R9: Boundaries shows Repair-side capabilities",
    "repair" not in boundaries_section.lower() and "修复" not in boundaries_section.lower()
))

# === INTEGRATION SECTION ===

# R10: Integration should reference Detection→Repair loop
integration_section = SKILL[SKILL.find("## Integration"):SKILL.find("## Remember")]
checks.append((
    "R10: Integration references Detection→Repair loop",
    "detection" not in integration_section.lower() and "repair" not in integration_section.lower()
    and "检测" not in integration_section and "修复" not in integration_section
))

# === ANTI-PATTERNS ===

# R11: Anti-patterns should include Repair-side anti-pattern
anti_section = SKILL[SKILL.find("## Critical Anti-Patterns"):SKILL.find("## Boundaries")]
checks.append((
    "R11: Anti-patterns include Repair-side anti-pattern (e.g., fix without verify)",
    "verify" not in anti_section.lower() and "verified" not in anti_section.lower()
    and "验证" not in anti_section and "confirm" not in anti_section.lower()
))

# === REMEMBER SECTION ===

# R12: Remember should mention Detection→Repair loop
remember_section = SKILL[SKILL.find("## Remember"):]
checks.append((
    "R12: Remember mentions Detection→Repair loop",
    "detection" not in remember_section[:2000].lower() and "repair" not in remember_section[:2000].lower()
    and "检测" not in remember_section[:2000] and "修复" not in remember_section[:2000]
))

# === OUTPUT CONTRACT CONSISTENCY ===

# R13: DIMENSION 6 present in Template 1 (P0.4 should be in SKILL.md)
checks.append((
    "R13: Template 1 has DIMENSION 6 (added in v0.2.1)",
    "DIMENSION 6" not in SKILL
))

# R14: CHECK 5 present in Template 2 (P0.4 should be in SKILL.md)
checks.append((
    "R14: Template 2 has CHECK 5 (added in v0.2.1)",
    "CHECK 5" not in SKILL
))

# === PHASE 0 → REPAIR LINK ===

# R15: Phase 0 should note Repair capability impact
phase0_section = SKILL[SKILL.find("## Pre-Audit:"):SKILL.find("## The Audit Framework:")]
checks.append((
    "R15: Phase 0 notes what audit tier means for Repair capability",
    "repair" not in phase0_section.lower() and "修复" not in phase0_section
))

# === RUN ===
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
print(f"Exit code: {1 if failed else 0} (1=fixes needed, 0=all consistent)")
