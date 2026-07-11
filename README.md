# Audit-Driven Development

> **Tests passing is necessary. It is not sufficient.**
> **测试通过是必要的。但不是充分的。**

[![Version](https://img.shields.io/badge/version-1.0-blue)](https://github.com/StormstoutLau/audit-driven-development)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TDD](https://img.shields.io/badge/TDD-96%2F96%20PASS-brightgreen)](https://github.com/StormstoutLau/audit-driven-development)
[![Benchmark](https://img.shields.io/badge/recall-94.3%25-success)](https://github.com/StormstoutLau/audit-driven-development/tree/main/docs/benchmark)

A Trae Skill that enforces an independent audit phase between implementation and done. It scores code against design specs, identifies blind spots tests cannot catch, and produces a fix priority matrix. Detection finds misalignment. Repair closes the loop.

---

## The Problem

```
Tests Pass ≠ Code Correct
```

"164 tests passed" is the most dangerous phrase in software. It means:

- Did the test assert the **right thing**? — Tautologies pass silently
- Does the test see **across file boundaries**? — `inspect.getsource()` is single-file only
- Does the test know the **design invariants**? — ADR rules have no tests
- Were **corrective items** actually implemented? — Spec says "fix 9.1", code may not

Tests verify behavior within a single module. They cannot verify that Module A follows the contract Module B expects — or that the dependency graph still holds — or that the policy threshold in the spec matches the one in the code.

ADD sits between implementation and declaration — an independent verification pass that treats the design spec as the source of truth, not the test suite.

---

## Proof

Three open-source projects, audited by ADD. Results verified against known bug databases.

| Project | Version | Known Bugs | Detected | Recall | Precision | F₁ |
|---------|---------|------------|----------|--------|-----------|-----|
| Flask | 3.1.2 | 3 | 3 | **100%** | 89% | 94.1% |
| FastAPI | 0.115.8 | 6 | 5 | **83%** | 85% | 83.9% |
| Requests | 2.33.0 | 4 | 4 | **100%** | 100% | 100% |

| Aggregate | |
|---|---|
| Average Recall | **94.3%** |
| Average Precision | **91.3%** |
| Average F₁ | **92.6%** |

The one remaining false negative — an AfterValidator annotation propagation bug in FastAPI 0.115.8 — was traced to its root cause via MCP search and documented as a reusable detection rule.

---

## Capabilities

```
┌─────────────────────────────────────────────────────────┐
│                     ADD — v1.0                           │
│                                                         │
│  Detection                  │  Repair                   │
│  ─────────────────────────  │  ───────────────────────  │
│  Multi-dimension audit      │  Fix priority matrix      │
│  7 typed lens subagents     │  Structured fix_suggestion│
│  Spec mining + JSON output  │  issues.json state machine│
│  Deterministic pre-process  │  open→fixed→verified loop │
│  Benchmark calibration      │  Iterative audit rounds   │
│  Semantic guard enforcement │  Incremental --verify     │
│  0-100 numeric scoring      │  Cross-project guard reuse│
└─────────────────────────────────────────────────────────┘
```

### The 7 Lenses

Each lens is a typed subagent prompt that specializes in one audit dimension. Five are always active; two are opt-in.

| Lens | Subagent | What It Checks |
|------|----------|---------------|
| Design Alignment | Design Aligner | Signature + behavior consistency vs spec |
| Cross-Module Contract | Contract Guardian | ADR invariants, dependency graph, entry points |
| Error Handling | Error Handler | Exception coverage, propagation, retry logic |
| Boundary Conditions | Boundary Checker | Input validation, null checks, edge cases |
| Corrective Tracking | Corrective Tracker | Spec corrective items reflected in code |
| Security Scanning | `--lens security` | XSS, injection, path traversal, secrets |
| Architecture Health | `--lens architecture` | Circular deps, layer violations, dead imports |

### The Scripts

| Script | Purpose |
|--------|---------|
| `audit_files.py` | Deterministic file selection — no AI hallucination |
| `verify_lines.py` | Evidence pointer verification — keyword match ±20 lines |
| `rule_index.py` | Constraint index — must/must-not/threshold extraction |
| `issues_tracker.py` | State machine — `open → in_progress → fixed → verified` |
| `score_tracker.py` | 0–100 numeric scoring with ASCII trend chart |
| `merge_guards.py` | Cross-project guard merge — project overrides common |

---

## The Iron Law

```
NO "IMPLEMENTATION COMPLETE" WITHOUT AN AUDIT-DRIVEN REVIEW
```

The audit phase is mandatory. Not optional. Not "if we have time." Tests passing is the gate to audit — audit passing is the gate to done.

---

## When to Use

**Invoke ADD when:**
- A multi-module implementation plan is complete
- Cross-module contracts need verification
- A design doc version upgrade requires impact review
- You need a regression baseline after a fix sprint

**Do not use for:**
- General code quality review → `code-review-excellence`
- Single-task TDD → `test-driven-development`
- Implementation planning → `writing-plans`

ADD is orthogonal. It does not replace code review or TDD — it complements them by verifying a dimension neither covers: **alignment between what the spec says and what the code does**.

---

## Quick Start

```
Audit the current implementation against the design specs.
```

The skill auto-activates when it detects implementation completion or audit requests.

**What happens:**
1. Collects spec files, ADRs, architecture docs
2. Runs deterministic pre-processing (file selection, rule index)
3. Dispatches lens-specific subagents (1 per lens per module)
4. Aggregates findings into P0/P1/P2/P3 priority matrix
5. Outputs `issues.json` with `fix_suggestion` blocks
6. Generates `docs/audit/YYYY-MM-DD-code-quality-audit.md`

**After the report:**
- Fix all P0 first (`issues_tracker.py status --id <ID> --to in_progress`)
- Rerun tests after each fix
- Verify: `issues_tracker.py verify --file <fixed_file>`
- Score: `score_tracker.py compute issues.json`

---

## Installation

| Tool | Adapter | Install Path |
|------|---------|-------------|
| **Trae** | `SKILL.md` | `.trae/skills/audit-driven-development/` |
| **Claude Code** | `adapters/claude-code/SKILL.md` | `.claude/skills/audit-driven-development/` |
| **Cursor** | `adapters/cursor/audit-driven-development.mdc` | `.cursor/rules/` |
| **Codex** | `adapters/codex/AGENTS.md` | `AGENTS.md` (project root) |
| **GitHub Copilot** | `adapters/github-copilot/copilot-instructions.md` | `.github/copilot-instructions.md` |
| **Windsurf** | `adapters/windsurf/.windsurfrules` | `.windsurfrules` (project root) |
| **OpenCode** | `adapters/opencode/AGENTS.md` | `AGENTS.md` (project root) |

Seven adapters. One skill. All adapter files are auto-synced from `SKILL.md` via `scripts/sync_adapters.py`.

---

## Boundaries

| ADD Covers | Other Skills Cover |
|---|---|
| Code vs design spec alignment | General code quality (`code-review-excellence`) |
| Multi-dimensional audit | Single-task TDD (`test-driven-development`) |
| Fix priority matrix | Implementation planning (`writing-plans`) |
| Dependency graph invariants | Implementation execution (`executing-plans`) |
| Test blind spot detection | Spec management (`OpenSpec`) |
| Structured repair guidance | |
| Semantic guard enforcement | |
| Iterative audit rounds | |
| Numeric scoring + trends | |

---

## Development

Built over 5 versions, each independently shippable, each passing full TDD regression.

| Version | Detection | Repair | Status |
|---------|-----------|--------|--------|
| v0.1.1 | Iron Law + Gate | — | ✅ |
| v0.2 | Spec Mining + JSON Schema | — | ✅ |
| v0.2.1 | DIMENSION 6 + FP Classification | — | ✅ |
| v0.3 | OSS Benchmark (94.3%) + 7 Lenses | State Machine + --verify | ✅ |
| v0.4 | Deterministic Preprocess + Iterative Audit | Structured fix_suggestion | ✅ |
| v0.5 → 1.0 | Semantic Guards + Numeric Scoring | Cross-project Guard Reuse | ✅ |

**TDD Coverage**: 96/96 checks across 4 version-specific test suites, all passing.

---

## License

[MIT](./LICENSE) © 2026 StormstoutLau
