<br>
<div align="center">

<br>
<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/AUDIT-6366f1?style=for-the-badge&logo=checkmarx&logoColor=white&labelColor=1e1e2e">
  <img src="https://img.shields.io/badge/AUDIT-6366f1?style=for-the-badge&logo=checkmarx&logoColor=white&labelColor=fafafa">
</picture>

# Audit-Driven Development

<br>

**Tests pass → Code ships.** That is the lie every team tells itself.\
**测试通过就上线。** 这是每支团队对自己说的谎。

<br>

<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img alt="version" src="https://img.shields.io/badge/version-2.3-6366f1?style=for-the-badge&logo=github&logoColor=white" />
</a>
&nbsp;
<a href="https://opensource.org/licenses/MIT">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" />
</a>
&nbsp;
<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img alt="tdd" src="https://img.shields.io/badge/TDD-199%2F199%20PASS-brightgreen?style=for-the-badge&logo=python&logoColor=white" />
</a>
&nbsp;
<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img alt="score" src="https://img.shields.io/badge/score-97%2F100%20A%2B-16a34a?style=for-the-badge&logo=vercel&logoColor=white" />
</a>

<br>
<br>

```
  ┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
  │  DETECTION   │ ───► │   REPAIR     │ ───► │   KNOWLEDGE      │
  │  7 lenses    │      │  6-stage 闭环 │      │  3-tier ∿ pipeline│
  │  ──────────  │      │  ──────────  │      │  ─────────────── │
  │  Spec truth   │      │  Human loop  │      │  Self-evolving    │
  └──────────────┘      └──────────────┘      └──────────────────┘
```

<br>

> A self-evolving Trae Skill that inserts an independent audit phase between **implementation** and **done**.
> Detection finds what tests miss. Repair closes what detection finds.
> The Knowledge Pipeline learns from every audit — making the system **smarter over time**.

</div>

---

<br>

## The Problem

> **"164 tests passed"** is the most dangerous phrase in software.

Tests verify behavior within a single module. They cannot verify that Module A keeps the promises Module B depends on — that the dependency graph still holds — that the threshold in the spec matches the threshold in the code.

```text
  Tests pass ──→ ✗ Declare done ──→ ❌ Ship broken code

  Tests pass ──→ ✓ ADD Audit ──→ ✅ Real verification
```

**ADD treats the design spec as the source of truth.** Not the test suite.

<table align="center"><tr><td>

| What Tests Miss | What ADD Catches |
|---|---|
| Cross-module contract violations | 7 typed lens subagents scan every contract |
| ADR invariant drift | `rule_index.py` extracts must / must-not / threshold |
| Corrective items left in spec | Corrective Tracking Lens checks every item |
| Design ↔ code threshold mismatch | Design Aligner Lens compares spec values to code |
| Error handlers that silently suppress | Error Handler Lens covers propagation + retry |

</td></tr></table>

---

<br>

## Proof

Three open-source projects audited. Findings verified against known bug databases.

<div align="center">

| | Flask 3.1.2 | FastAPI 0.115.8 | Requests 2.33.0 |
|---|---|---|---|
| **Bugs Found** | 3 / 3 | 5 / 6 | 4 / 4 |
| **Recall** | ![](https://img.shields.io/badge/100%25-success?style=flat-square) | ![](https://img.shields.io/badge/83%25-yellow?style=flat-square) | ![](https://img.shields.io/badge/100%25-success?style=flat-square) |
| **F₁** | 94.1% | 83.9% | 100% |

<br>

| | Recall | Precision | F₁ |
|---|---|---|---|
| **Average** | **94.3%** | **91.3%** | **92.6%** |

</div>

---

<br>

## Architecture · Detection → Repair → Knowledge

```
                          ┌───────────────────────┐
                          │    AUDIT ENGINE        │
                          │  Phase 1·2·3·4·5·6    │
                          └───────────┬───────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
  ┌───────────────┐         ┌───────────────┐         ┌───────────────────┐
  │  DETECTION    │         │    REPAIR     │         │    KNOWLEDGE       │
  │  Track        │   ───►  │    Track      │   ───►  │    Pipeline        │
  │  (越检越准)    │  shared │  (越修越精)    │  shared │  (self-evolving)   │
  ├───────────────┤   infra ├───────────────┤   infra ├───────────────────┤
  │ v2.0: bench→  │         │ v2.0: schema  │         │ v2.1: diff_miner   │
  │       guard   │         │               │         │       rule_suggest │
  │ v2.1: git     │         │ v2.1: history │◄────────│       fix_history  │
  │       mining  │         │       match   │  reward │                   │
  │ v2.2: LLM    │         │ v2.2: recipe  │  signal │ v2.2: generalize   │
  │       rule    │         │       book    │   ▲/▼   │       validate     │
  │ v2.3: MCP    │         │ v2.3: live    │         │ v2.3: external     │
  │       search  │         │       update  │         │       injection    │
  └───────────────┘         └───────────────┘         └───────────────────┘
```

### The Rewards Loop

```
  scores.json trend ▲
         │
         ├──改善 → fix_history threshold 0.60 (宽松 · 复用更多方案)
         ├──退化 → fix_history threshold 0.80 (严格 · 避免无效修复)
         └──3连▲ → confident mode (threshold -0.05)
```

This is a **real RL loop** running on real audit data. No simulation.

### 28 Scripts · 5 Layers

```
  Core ──── v0.1→v1.0  │  audit_files · rule_index · verify_lines
           (6 scripts)  │  issues_tracker · score_tracker · merge_guards
  ──────────────────────┤
  Knowledge ─ v2.0      │  rule_extractor · spec_graph · inter_rater
           (3 scripts)  │
  ──────────────────────┤
  Learning ── v2.1      │  diff_miner · rule_suggester · fix_history
           (3 scripts)  │
  ──────────────────────┤
  Generalize  v2.2      │  llm_generalize · fix_recipes · rule_validator
           (3 scripts)  │
  ──────────────────────┤
  External ── v2.3      │  mcp_lookup · benchmark_syncer · live_knowledge
           (3 scripts)  │
```

<br>

---

## Version Journey · 7 Days · 8 Versions

```
  7/6   7/7-9   7/9-10   7/10-11   7/11    7/11    7/12    7/12    7/12
   │      │       │        │        │       │       │       │       │
  v0.1 → v0.2 → v0.3 →  v0.4  →  v1.0 → v2.0 → v2.1 → v2.2 → v2.3
   │      │       │        │        │       │       │       │       │
  Iron   Struct  Detec   Repair   Eco-   Know-   Dual-   LLM    External
  Law    Foundation tion  Baseline system  ledge   Track   Gen    Injection
  ─────────────────────────────────────────────────────────────────────
  1 行   4 个     12 个   15 个    15 个   16 个   20 个   24 个   28 个
  SKILL 脚本     脚本    脚本     脚本    脚本    脚本    脚本    scripts
```

<br>

---

## Quick Start

```bash
# ── Full knowledge pipeline ──────────────────────────────────

# Phase 0.5 · Load existing knowledge
python scripts/spec_graph.py --spec SKILL.md --adrs docs --repo .

# Phase 3.5 · Pattern mining + history matching (v2.1)
python scripts/diff_miner.py --repo . --since "2024-01-01"
python scripts/fix_history.py --findings issues.json --history-dir docs/audit

# Phase 3.6 · LLM generalization prompt (v2.2)
python scripts/llm_generalize.py --source-dir docs/audit --output-dir docs/audit

# Phase 3.7 · External knowledge lookup (v2.3)
python scripts/mcp_lookup.py --findings issues.json --output docs/audit/mcp_queries.json

# Post-audit · auto-update all knowledge (v2.3)
python scripts/live_knowledge.py --audit-dir docs/audit

# Track scores over time
python scripts/score_tracker.py trend docs/audit/scores.json
```

### Self-Audit Score History

```
  Date       Version              Score   Grade   Trend
  ─────────────────────────────────────────────────────
  07-11      v2.0-self-audit         0      F       ●
  07-12      v2.0.1-reaudit          0      F      ─+0
  07-12      v2.0.1-final           97     A+     ▲+97
  07-12      v2.3-self-audit        97     A+      ─+0
  ─────────────────────────────────────────────────────
  7天后:     从F的废墟到A+的steady state
```

<br>

---

## Installation

<p align="center">

| | | | | | | |
|---|---|---|---|---|---|---|
| ![](https://img.shields.io/badge/Trae-SKILL.md-6366f1?style=flat-square) | ![](https://img.shields.io/badge/Claude_Code-SKILL.md-d97706?style=flat-square) | ![](https://img.shields.io/badge/Cursor-.mdc-2563eb?style=flat-square) | ![](https://img.shields.io/badge/Codex-AGENTS.md-10b981?style=flat-square) | ![](https://img.shields.io/badge/Copilot-instructions.md-0284c7?style=flat-square) | ![](https://img.shields.io/badge/Windsurf-.windsurfrules-6366f1?style=flat-square) | ![](https://img.shields.io/badge/OpenCode-AGENTS.md-ec4899?style=flat-square) |

</p>

All 7 adapters auto-synced from `SKILL.md` via `scripts/sync_adapters.py`. Drop-in compatible. Zero config.

<br>

---

## Technical Summary

| | |
|---|---|
| **Scripts** | 28 production · 8 test suites |
| **TDD** | **199/199** all passing |
| **Benchmark Recall** | 94.3% (Flask 100% · FastAPI 83% · Requests 100%) |
| **Self-Audit** | **97/100 A+** — steady state after v2.0.1 fixes |
| **Knowledge** | 3-tier ∿ Internal Learning → AI Generalization → External Injection |
| **Recipes** | 5 built-in human-authored + LLM-generated |
| **Dependencies** | Zero — pure Python stdlib + PyYAML |
| **Adapters** | 7 IDEs drop-in compatible |

<br>

---

<div align="center">

[MIT](./LICENSE) © 2026 StormstoutLau

<br>

</div>