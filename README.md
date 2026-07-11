<div align="center">

# Audit-Driven Development

**Tests pass → Code ships.**  That is the lie every team tells itself.\
**测试通过就上线。** 这是每支团队对自己说的谎。

<br>

<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img src="https://img.shields.io/badge/version-1.0-blue?style=for-the-badge&logo=github&logoColor=white" />
</a>
<a href="https://opensource.org/licenses/MIT">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" />
</a>
<a href="https://github.com/StormstoutLau/audit-driven-development">
  <img src="https://img.shields.io/badge/TDD-96%2F96%20PASS-brightgreen?style=for-the-badge&logo=python&logoColor=white" />
</a>

<br>
<br>

<table align="center">
<tr>
  <td align="center"><b>Detection</b></td>
  <td align="center"><b>Repair</b></td>
  <td align="center"><b>Benchmark</b></td>
  <td align="center"><b>Adapters</b></td>
</tr>
<tr>
  <td align="center"><img src="https://img.shields.io/badge/7-lenses-blue?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/4_stage-loop-orange?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/94.3%25-recall-success?style=for-the-badge" /></td>
  <td align="center"><img src="https://img.shields.io/badge/7-IDEs-32a873?style=for-the-badge" /></td>
</tr>
</table>

<br>

> A Trae Skill that inserts an independent audit phase **between implementation and done**. \
> Detection finds what tests miss. Repair closes what detection finds.

</div>

---

## The Problem

> **"164 tests passed"** is the most dangerous phrase in software.

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#f0f9ff"
    primaryBorderColor: "#0369a1"
    secondaryColor: "#fef3c7"
    secondaryBorderColor: "#b45309"
    tertiaryColor: "#fef2f2"
    tertiaryBorderColor: "#dc2626"
    nodeBorder: "#94a3b8"
    edgeLabelBackground: "#ffffff"
---
flowchart LR
    subgraph Pass["Tests Pass"]
        direction TB
        A["🧪 Tautologies<br><i>assert x or not x</i>"] --> C["⚠️ Verification Illusion"]
        B["🔍 Single-file Only<br><i>inspect.getsource</i>"] --> C
    end
    subgraph Miss["What Tests Miss"]
        direction TB
        D["📐 ADR Invariants"]
        E["🔗 Cross-Module Contracts"]
        F["📝 Corrective Items"]
        G["📏 Design Thresholds"]
    end
    C ==>|"False confidence<br>Declare done"| H["❌ Ship Broken Code"]
    Miss ==>|"ADD catches<br>these"| I["✅ Real Verification"]

    style H fill:#fecaca,stroke:#dc2626,stroke-width:2px
    style I fill:#bbf7d0,stroke:#16a34a,stroke-width:2px
    style C fill:#fef08a,stroke:#ca8a04,stroke-width:2px,stroke-dasharray: 5 5
    style Pass fill:none,stroke:#94a3b8,stroke-dasharray: 3 3
    style Miss fill:none,stroke:#94a3b8,stroke-dasharray: 3 3
```

Tests verify behavior within a single module. They cannot verify that Module A keeps the promises Module B depends on — or that the dependency graph still holds — or that the threshold in the spec matches the threshold in the code.

**ADD treats the design spec as the source of truth.** Not the test suite.

---

## Proof

Three open-source projects, audited by ADD. Findings verified against known bug databases.

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

```mermaid
---
config:
  theme: base
  themeVariables:
    xyChart:
      backgroundColor: "#ffffff"
      titleColor: "#334155"
      xAxisLabelColor: "#64748b"
      yAxisLabelColor: "#64748b"
---
xychart-beta
    title "Recall by Project"
    x-axis ["Flask", "FastAPI", "Requests"]
    y-axis "Recall %" 0 --> 100
    bar [100, 83, 100]
```

<table align="center">
<tr>
  <td align="center"><b>Avg Recall</b><br><h2>94.3%</h2></td>
  <td align="center"><b>Avg Precision</b><br><h2>91.3%</h2></td>
  <td align="center"><b>Avg F₁</b><br><h2>92.6%</h2></td>
</tr>
</table>

The one remaining false negative — an AfterValidator propagation bug in FastAPI — was traced to its root cause via MCP search and written as a reusable detection rule. [→ reference](references/python-pydantic-audit-rules.md)

---

## Architecture

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#e8f5e9"
    primaryBorderColor: "#388e3c"
    secondaryColor: "#fff8e1"
    secondaryBorderColor: "#f9a825"
    tertiaryColor: "#ffebee"
    tertiaryBorderColor: "#d32f2f"
---
flowchart TB
    S["📋 Spec + ADRs"] --> P1["1. Inventory<br><i>Map modules → specs</i>"]
    C["💻 Source Code"] --> P2
    P1 --> P2["2. Lens Audit<br><i>7 typed subagents</i>"]
    P2 --> P3["3. Aggregate<br><i>Dedup + classify</i>"]
    P3 --> P4["4. Fix Baseline<br><i>issues.json</i>"]
    P4 --> P5["5. Fix P0<br><i>Human-in-the-loop</i>"]
    P5 --> P6["6. Final Report<br><i>scores.json + trend</i>"]

    subgraph Lens["Seven Typed Subagents"]
        direction LR
        L1["🧬 Design"]
        L2["🔗 Contract"]
        L3["🛡️ Errors"]
        L4["🔲 Boundary"]
        L5["📝 Corrective"]
        L6["🔐 Security"]
        L7["🏗️ Architecture"]
    end
    P2 -.->|dispatch| Lens

    style S fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style C fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Lens fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,stroke-dasharray: 4 2
    style P1 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style P2 fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    style P3 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style P4 fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style P5 fill:#ffcdd2,stroke:#d32f2f,stroke-width:2px
    style P6 fill:#b2dfdb,stroke:#00796b,stroke-width:2px
```

| Phase | Side | What |
|---|---|---|
| 1–3 | **Detection** (green) | Spec inventory → Lens audit → Aggregate findings |
| 4–6 | **Repair** (amber→red→teal) | Baseline → Fix P0 → Final report |

### The Seven Lenses

Each lens is a typed subagent prompt. Five always active. Two opt-in via `--lens`.

| | Lens | Specializes In |
|---|---|---|
| 🧬 | Design Alignment | Signature + behavior match vs spec |
| 🔗 | Cross-Module Contract | ADR invariants · dependency graph · entry points |
| 🛡️ | Error Handling | Exception coverage · propagation · retry logic |
| 🔲 | Boundary Conditions | Input validation · null checks · edge cases |
| 📝 | Corrective Tracking | Spec corrective items reflected in code |
| 🔐 | Security Scanning `--lens security`  | XSS · injection · path traversal · secrets |
| 🏗️ | Architecture Health `--lens architecture` | Circular deps · layer violations · dead imports |

### The Scripts

| Script | Does |
|---|---|
| `audit_files.py` | Deterministic scope — zero AI hallucination |
| `rule_index.py` | Constraint extraction — must / must-not / threshold |
| `verify_lines.py` | Evidence check — keyword match ±20 lines |
| `issues_tracker.py` | State machine — `open → in_progress → fixed → verified` |
| `score_tracker.py` | 0–100 scoring + ASCII trend chart |
| `merge_guards.py` | Guard merge — project overrides common by id |

---

## The Iron Law

> # "NO IMPLEMENTATION COMPLETE" WITHOUT AN AUDIT-DRIVEN REVIEW

The audit phase is **mandatory**. Not optional. Not "if we have time."

> Tests passing is the gate **to** audit. Audit passing is the gate **to** done.

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#e8f5e9"
    primaryBorderColor: "#16a34a"
    tertiaryColor: "#ffebee"
    tertiaryBorderColor: "#dc2626"
---
flowchart LR
    A["✅ Tests Pass"] --> B{"🔍 ADD Audit"}
    B -->|"P0 = 0"| C["✅ Done<br><i>design landed</i>"]
    B -->|"P0 > 0"| D["🔧 Fix P0<br><i>human-in-the-loop</i>"]
    D --> A

    style C fill:#bbf7d0,stroke:#16a34a,stroke-width:2px
    style D fill:#fecaca,stroke:#dc2626,stroke-width:2px
    style B fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px
```

---

## When to Use

<table>
<tr><th>✅ Invoke ADD</th><th>❌ Use Another Skill</th></tr>
<tr valign="top">
<td>

- Multi-module plan is complete
- Cross-module contracts need verification
- Design doc version upgrade
- Regression baseline after fix sprint

</td>
<td>

- General code quality → `code-review-excellence`
- Single-task TDD → `test-driven-development`
- Implementation planning → `writing-plans`

</td>
</tr>
</table>

ADD is orthogonal. It complements code review and TDD by verifying the dimension neither covers: **alignment between what the spec says and what the code does**.

---

## Quick Start

```bash
# One command. In any AI coding tool.
Audit the current implementation against the design specs.

# What happens: 6-phase automated audit → priority matrix → issues.json
```

**After the report:**

```bash
# Track fixes through the state machine
python scripts/issues_tracker.py init docs/audit/<report>.json
python scripts/issues_tracker.py status --id BRIDGE-P0-1 --to in_progress
  # ... fix the code (this is the HUMAN step) ...
python scripts/issues_tracker.py status --id BRIDGE-P0-1 --to fixed
python scripts/issues_tracker.py verify --file bridge/__init__.py

# Compute and track scores over time
python scripts/score_tracker.py compute docs/audit/issues.json --project MyApp --version v0.2.0
python scripts/score_tracker.py trend docs/audit/scores.json
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

| Tool | Adapter | Path |
|---|---|---|
| Trae | `SKILL.md` | `.trae/skills/audit-driven-development/` |
| Claude Code | `adapters/claude-code/SKILL.md` | `.claude/skills/audit-driven-development/` |
| Cursor | `adapters/cursor/audit-driven-development.mdc` | `.cursor/rules/` |
| Codex | `adapters/codex/AGENTS.md` | `AGENTS.md` |
| Copilot | `adapters/github-copilot/copilot-instructions.md` | `.github/copilot-instructions.md` |
| Windsurf | `adapters/windsurf/.windsurfrules` | `.windsurfrules` |
| OpenCode | `adapters/opencode/AGENTS.md` | `AGENTS.md` |

All adapters auto-synced from `SKILL.md` via `scripts/sync_adapters.py`.

---

## Development

```mermaid
---
config:
  theme: base
---
timeline
    title  ADD · Five Versions to 1.0
    v0.1     : Iron Law + Gate
    v0.2     : Structured Foundation
             : Spec Mining · JSON Schema
    v0.3     : Detection Bootstrap
             : 94.3% Recall · 7 Lenses
    v0.4     : Repair Baseline
             : Iterative Audit · Deterministic Preprocess
    v1.0     : Ecosystem
             : Semantic Guards · Numeric Scoring
```

| Version | Detection Side | Repair Side |
|---|---|---|
| v0.1.1 | Iron Law + Gate | — |
| v0.2 | Spec Mining + JSON Schema | — |
| v0.2.1 | DIMENSION 6 + FP Classification | — |
| v0.3 | 94.3% Benchmark + 7 Lenses | State Machine + `--verify` |
| v0.4 | Deterministic Preprocess + Iterative Audit | Structured `fix_suggestion` |
| v1.0 | Semantic Guards + Numeric Scoring | Cross-project Guard Reuse |

> **TDD**: 96/96 checks across 4 test suites, all passing. **Perf**: 94.3% recall across 3 OSS projects.

---

## License

[MIT](./LICENSE) © 2026 StormstoutLau
