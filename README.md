<div align="center">

# Audit-Driven Development

**Tests pass → Code ships.** That is the lie every team tells itself.\
**测试通过就上线。** 这是每支团队对自己说的谎。

<br>

<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img src="https://img.shields.io/badge/version-2.3-6366f1?style=for-the-badge&logo=github&logoColor=white" />
</a>
<a href="https://opensource.org/licenses/MIT">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" />
</a>
<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img src="https://img.shields.io/badge/TDD-199%2F199%20PASS-brightgreen?style=for-the-badge&logo=python&logoColor=white" />
</a>
<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img src="https://img.shields.io/badge/score-97%2F100%20A%2B-16a34a?style=for-the-badge&logo=vercel&logoColor=white" />
</a>

<br>
<br>

<table align="center">
<tr>
  <td align="center"><b>Detection</b></td>
  <td align="center"><b>Repair</b></td>
  <td align="center"><b>Knowledge</b></td>
  <td align="center"><b>Adapters</b></td>
</tr>
<tr>
  <td align="center"><img src="https://img.shields.io/badge/7-lenses-blue?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/6_stage-闭环-orange?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/3_tier-进化管道-6366f1?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/7-IDEs-32a873?style=for-the-badge" /></td>
</tr>
</table>

<br>

> A self-evolving Trae Skill that inserts an independent audit phase between implementation and done.\
> **Detection** finds what tests miss. **Repair** closes what detection finds.\
> **Knowledge Pipeline** learns from every audit — making the system smarter over time.

</div>

---

## The Problem

> **"164 tests passed"** is the most dangerous phrase in software.

Tests verify behavior within a single module. They cannot verify that Module A keeps the promises Module B depends on — or that the dependency graph still holds — or that the threshold in the spec matches the threshold in the code. **ADD treats the design spec as the source of truth.** Not the test suite.

---

## Proof

Three open-source projects audited. Findings verified against known bug databases.

<table align="center">
<tr>
  <td align="center"><h3>Flask 3.1.2</h3></td>
  <td align="center"><h3>FastAPI 0.115.8</h3></td>
  <td align="center"><h3>Requests 2.33.0</h3></td>
</tr>
<tr>
  <td align="center">
    <img src="https://img.shields.io/badge/recall-100%25-success?style=for-the-badge" /><br>
    <sub>3/3 bugs found · F₁ 94.1%</sub>
  </td>
  <td align="center">
    <img src="https://img.shields.io/badge/recall-83%25-yellow?style=for-the-badge" /><br>
    <sub>5/6 bugs found · F₁ 83.9%</sub>
  </td>
  <td align="center">
    <img src="https://img.shields.io/badge/recall-100%25-success?style=for-the-badge" /><br>
    <sub>4/4 bugs found · F₁ 100%</sub>
  </td>
</tr>
</table>

<table align="center">
<tr>
  <td align="center"><b>Avg Recall</b><br><h2>94.3%</h2></td>
  <td align="center"><b>Avg Precision</b><br><h2>91.3%</h2></td>
  <td align="center"><b>Avg F₁</b><br><h2>92.6%</h2></td>
</tr>
</table>

---

## Architecture: Detection → Repair → Knowledge

ADD v2.0+ introduces a **dual-track knowledge pipeline** — the system learns from every audit.

```
┌─────────────────── Knowledge Pipeline ───────────────────┐
│                                                            │
│  Detection Track (越检越准)       Repair Track (越修越精)    │
│         │                                  │               │
│  v2.0: benchmark → guards         v2.0: fix_suggestion    │
│  v2.1: git history mining         v2.1: history matching  │
│  v2.1: audit-log → rules          v2.1: reward signal ▲▼  │
│  v2.2: LLM generalization         v2.2: fix recipe book   │
│  v2.3: MCP external search        v2.3: live knowledge    │
│         │                                  │               │
│         ▼                                  ▼               │
│  ┌──────────┐                     ┌──────────────┐        │
│  │ Detection│──── shared infra ──►│    Repair    │        │
│  │  Rules   │                     │   Recipes    │        │
│  └──────────┘                     └──────────────┘        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Scripts (28 total, v2.3)

| Layer | Script | Track |
|---|---|---|
| **Core** (v0.1–v1.0) | [audit_files.py](scripts/audit_files.py) · [rule_index.py](scripts/rule_index.py) · [verify_lines.py](scripts/verify_lines.py) · [issues_tracker.py](scripts/issues_tracker.py) · [score_tracker.py](scripts/score_tracker.py) · [merge_guards.py](scripts/merge_guards.py) | Detection + Repair |
| **Knowledge** (v2.0) | [rule_extractor.py](scripts/rule_extractor.py) · [spec_graph.py](scripts/spec_graph.py) · [inter_rater.py](scripts/inter_rater.py) | Knowledge Pipeline |
| **Learning** (v2.1) | [diff_miner.py](scripts/diff_miner.py) · [rule_suggester.py](scripts/rule_suggester.py) · [fix_history.py](scripts/fix_history.py) | Detection + Repair |
| **Generalization** (v2.2) | [llm_generalize.py](scripts/llm_generalize.py) · [fix_recipes.py](scripts/fix_recipes.py) · [rule_validator.py](scripts/rule_validator.py) | Shared Engine |
| **External** (v2.3) | [mcp_lookup.py](scripts/mcp_lookup.py) · [benchmark_syncer.py](scripts/benchmark_syncer.py) · [live_knowledge.py](scripts/live_knowledge.py) | External Injection |

---

## Knowledge Pipeline: Three-Tier Evolution

```
Tier 1: Internal Learning (v2.1)
  diff_miner        → git log --grep="fix|bug|CVE" → pattern clusters
  rule_suggester    → audit-log TP/FP/FN analysis → guard suggestions
  fix_history       → difflib semantic match + scores.json reward signal
                   → ▲ trending = relax threshold, ▼ = tighten

Tier 2: AI Generalization (v2.2)
  llm_generalize    → L1(git diffs)→L2(guards)→L3(fixes) prompt builder
  fix_recipes       → 5 built-in + LLM-imported recipe book
  rule_validator    → benchmark recall validation of generalized rules

Tier 3: External Injection (v2.3)
  mcp_lookup        → MCP search for P0 findings without fix_suggestion
  benchmark_syncer  → OSS project monitor (FastAPI/Flask/Requests/Django)
  live_knowledge    → post-audit auto-update of all knowledge files
```

### The Rewards Loop

`scores.json` trend acts as reinforcement signal:

- ▲ (improving) → `fix_history` threshold relaxed — reuse more solutions
- ▼ (declining) → threshold tightened — avoid reusing ineffective fixes
- 3 consecutive ▲ → **confident mode** — threshold drops 0.05 extra

This is a real RL loop running on real audit data.

---

## Version Journey

```
v0.1 ──→ Iron Law + Gate                    (Jul 6)
v0.2 ──→ Structured Foundation              (Jul 7-9)
v0.3 ──→ Detection: 94.3% recall, 7 lenses  (Jul 9-10)
v0.4 ──→ Repair: state machine + iterative  (Jul 10-11)
v1.0 ──→ Ecosystem: guards + scoring        (Jul 11)
   │
v2.0 ──→ Knowledge Pipeline                   (Jul 11)
         Benchmark→guard extraction
         Spec↔code mapping
         Inter-rater reliability (Cohen's κ)
   │
v2.1 ──→ Dual-Track Learning                  (Jul 12)
         diff_miner + rule_suggester
         fix_history with reward signal
   │
v2.2 ──→ LLM Generalization + Recipe Book     (Jul 12)
         Shared LLM engine for rules + fixes
         5 built-in repair recipes
   │
v2.3 ──→ External Knowledge Injection          (Jul 12)
         MCP search pipeline
         Benchmark project syncer
         Live knowledge auto-update
```

---

## Quick Start

```bash
# Full pipeline — detection through repair, knowledge auto-updates

# Phase 0.5: Load existing knowledge
python scripts/spec_graph.py --spec SKILL.md --adrs docs --guards docs/audit/guards.learned.yml --repo .

# Phase 3.5: Mine patterns + match history (v2.1)
python scripts/diff_miner.py --repo . --since "2024-01-01"
python scripts/fix_history.py --findings <new_issues.json> --history-dir docs/audit

# Phase 3.6: Build LLM generalization prompt (v2.2)
python scripts/llm_generalize.py --source-dir docs/audit --output-dir docs/audit

# Phase 3.7: External knowledge lookup (v2.3)
python scripts/mcp_lookup.py --findings <issues.json> --output docs/audit/mcp_queries.json

# Post-audit: auto-update all knowledge (v2.3)
python scripts/live_knowledge.py --audit-dir docs/audit

# Track scores over time
python scripts/score_tracker.py trend docs/audit/scores.json
```

### Score Trend (Self-Audit History)

```
Date         Version           Score Grade  Trend
07-11        v2.0-self-audit      0     F     ●
07-12        v2.0.1-reaudit       0     F    ─+0
07-12        v2.0.1-final        97    A+   ▲+97
07-12        v2.3-self-audit     97    A+    ─+0
```

---

## Installation

<p align="center">
  <img src="https://img.shields.io/badge/Trae-SKILL.md-6366f1?style=flat-square&logo=traefik&logoColor=white" />
  <img src="https://img.shields.io/badge/Claude_Code-SKILL.md-d97706?style=flat-square" />
  <img src="https://img.shields.io/badge/Cursor-.mdc-2563eb?style=flat-square&logo=cursor&logoColor=white" />
  <img src="https://img.shields.io/badge/Codex-AGENTS.md-10b981?style=flat-square" />
  <img src="https://img.shields.io/badge/Copilot-instructions.md-0284c7?style=flat-square&logo=github&logoColor=white" />
  <img src="https://img.shields.io/badge/Windsurf-.windsurfrules-6366f1?style=flat-square" />
  <img src="https://img.shields.io/badge/OpenCode-AGENTS.md-ec4899?style=flat-square" />
</p>

| Tool | Path |
|---|---|
| Trae | `.trae/skills/audit-driven-development/` |
| Claude Code | `.claude/skills/audit-driven-development/` |
| Cursor | `.cursor/rules/` |
| Codex / OpenCode | `AGENTS.md` |
| Copilot | `.github/copilot-instructions.md` |
| Windsurf | `.windsurfrules` |

All 7 adapters auto-synced from `SKILL.md` via `scripts/sync_adapters.py`.

---

## Technical Summary

| Metric | Value |
|---|---|
| Scripts | 28 production scripts |
| TDD Coverage | **199/199** across 8 test suites |
| Benchmark Recall | 94.3% (Flask 100% · FastAPI 83% · Requests 100%) |
| Self-Audit Score | **97/100 A+** |
| Knowledge Layers | 3-tier (Internal Learning → AI Generalization → External Injection) |
| Repair Recipes | 5 built-in human-authored + LLM-imported |
| External Dependencies | Zero (pure Python stdlib + PyYAML) |

---

## License

[MIT](./LICENSE) © 2026 StormstoutLau
