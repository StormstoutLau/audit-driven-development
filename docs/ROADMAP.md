# Roadmap / 改进路线图

> **The audit skill itself must be audited.**
> **审查 skill 本身也必须被审查。**

This document records the systematic improvement plan for the `audit-driven-development` skill, addressing three limitations identified on 2026-07-06. Updated 2026-07-09 with V2 pragmatic enhancement tier (integrating the V2 proposal's seven upgrades into P2/P3 layers).

本文档记录 `audit-driven-development` skill 的系统性改进计划，回应 2026-07-06 识别的三项局限。2026-07-09 更新，吸收 V2 务实增强方案到 P2/P3 层。

---

## Three Limitations / 三项局限

| # | Limitation / 局限 | Root Cause / 根因 | Meta-Problem / 元问题 |
|---|---|---|---|
| 1 | Relies on design doc quality / 依赖设计文档质量 | **Input has no gate / 输入无门** | Garbage spec → garbage audit (GIGO) |
| 2 | Subagent intelligence is a black box / Subagent 是黑盒 | **Process has no calibration / 过程无校准** | Subagent misjudgment → audit misjudgment, non-traceable |
| 3 | Ecosystem unverified / 生态待验证 | **Output has no baseline / 输出无基准** | No ground truth for recall / precision |

**Common root**: Audit quality itself is not audited. The skill is a "distrust system" that has not yet turned distrust on itself.

**共同根因**：审计质量本身未被审计。这个 skill 是个"不信任系统"，但它自己还没被纳入不信任范围。

---

## Priority Tiers / 优先级分层

### P0 — v0.1.1 (Immediate / 立即)

Actions that can be completed within days, addressing the most critical gaps.

数天内可完成，回应最关键裂缝的动作。

| ID | Action / 动作 | Addresses / 回应 | Cost / 成本 |
|---|---|---|---|
| **P0.1** | Subagent prompt explicitization + mandatory evidence pointer / Subagent prompt 显式化 + 强制 evidence pointer | Limitation 2 | 1 day |
| **P0.2** | Spec Quality Gate (Phase 0) / 设计文档质量门 (Phase 0) | Limitation 1 | 2 days |
| **P0.3** | Self-audit case log / 自我审计案例日志 | Limitation 3 | Low (template + first instance) |

**Status / 状态**: ✅ All P0 items implemented in v0.1.1

### P1 — v0.2 (Foundation / 基础层)

| ID | Action / 动作 | Addresses / 回应 | Cost / 成本 |
|---|---|---|---|
| **P1.4** | Reasoning chain schema / 推理链 schema 化 | Limitation 2 | 2 days |
| **P1.5** | Spec Mining Fallback / 设计文档反向挖掘 | Limitation 1 | 3-5 days |
| **P1.6** | Structured audit protocol (JSON schema) / 结构化审计协议 | Limitation 2+3 | 2 days |

**Status / 状态**: ✅ All P1 items implemented in v0.2

### P2 — v0.3–v0.4 (Detection + Repair / 检测 + 修复)

**Design philosophy / 设计哲学**: P2 items split into **Detection** (发现识别错误) and **Repair** (修复验证) capabilities. Detection gives confidence; Repair closes the loop. Every enhancement is a pluggable extension to ADD's existing framework. Hard cost caps on every feature.

P2 项分为 **Detection**（发现识别错误）和 **Repair**（修复验证）两类。检测建立信心，修复闭环验证。每项增强都是 ADD 现有框架的可插拔扩展。每项功能有硬性成本上限。

**Note / 注**: P0.4 and P0.5 were added in v0.2.1 as immediate fixes from the Code_Hub audit (2026-07-10). They are already implemented.

#### Detection Items / 检测侧

| ID | Action / 动作 | Side / 侧 | Addresses / 回应 | Traced to | Cost |
|---|---|---|---|---|---|
| **P0.4** | DIMENSION 6: build config + ADR execution | Detection | Limitation 1+2 | Code_Hub FN-1/FN-2 | ✅ Done |
| **P0.5** | FP type classification | Detection | Limitation 2+3 | Code_Hub §7 | ✅ Done |
| **P2.9** | Detection Calibration: OSS Benchmark | Detection | Limitation 3 | — | ✅ Done (94.3% recall) |
| **P2.8'** | Detection Coverage: Lens-Audit Matrix | Detection | Limitation 2 | V2#3 + P2.8 | ✅ Done (100% Requests recall) |
| **P2.10** | Detection Precision: Evidence Verification | Detection | Limitation 2 | V2#4 | ✅ Done (3 scripts) |
| **P2.7** | Detection Reliability: Dual-Subagent Voting | Detection | Limitation 2 | — | 3 days |

#### Repair Items / 修复侧

| ID | Action / 动作 | Side / 侧 | Addresses / 回应 | Traced to | Cost |
|---|---|---|---|---|---|
| **P2.11** | Repair Cycle: Audit-Fix-Reverify Loop | Repair | Limitation 2 | V2#1 | ✅ Done (iterative audit) |
| **P2.12** | Repair Tracking: State Machine + Incremental Verify | Repair | Limitation 3 | V2#5 | ✅ Done (issues_tracker.py) |
| **P2.13** | Repair Guidance: Structured fix_suggestion + Impact Analysis | Repair | Limitation 2+3 | Security skill 借鉴 | ✅ Done (6-field schema) |

### P3 — v0.5 (Ecosystem: Detection + Repair / 生态：检测+修复)

| ID | Action / 动作 | Side / 侧 | Addresses / 回应 | Traced to | Cost |
|---|---|---|---|---|---|
| **P3.1** | Detection Enhancement: Semantic Guards / 检出增强：语义守卫 | Detection | Limitation 1 | V2#2 | 3 days |
| **P3.2** | Detection Quantification: Numeric Scoring + Trends / 检出量化：数值评分 + 趋势 | Detection | Limitation 3 | V2#6 | 1 day |
| **P3.3** | Repair Knowledge: Cross-Project Guard Reuse / 修复知识：跨项目规则复用 | Repair | Limitation 1 | V2#7 | 2 days |

---

## P0 Details / P0 层详情

### P0.1 — Subagent Prompt Explicitization + Evidence Pointer

**Problem / 问题**: The skill says "dispatch subagents to audit" but never specifies the subagent's actual instructions. The core mechanism is undefined.

**Fix / 修复**:
- Add `Appendix A: Subagent Prompt Templates` to `SKILL.md`
- Define input contract: module code path + spec path + ADR list
- Define output contract: must contain `evidence pointer` (file:line) + `spec section ref` + reasoning chain
- Define checklist: signature consistency / behavior consistency / corrective items / test blind spots (each yes/no/NA + evidence)

**Benefit / 收益**: Black box → white box. The prompt itself becomes reviewable, versionable, improvable.

**Status / 状态**: ✅ Implemented in v0.1.1 (see `SKILL.md` Appendix A)

### P0.2 — Spec Quality Gate (Phase 0)

**Problem / 问题**: If the spec is garbage, the audit is garbage. Currently no gate prevents auditing against a worthless spec.

**Fix / 修复**:
- Add `Phase 0: Spec Quality Gate` to `SKILL.md` (precedes Phase 1)
- 5-minute spec quality assessment, output three tiers:
  - **A (full audit)**: spec contains testable constraints ("must" / "must not" / "threshold X") → full 4-phase audit
  - **B (structural audit)**: spec exists but vague → downgrade to "code vs general engineering principles" (DAG acyclic, single entry, error handling)
  - **C (spec mining)**: spec missing → invoke P1.5 Spec Mining Fallback (v0.2), or refuse audit with reason

**Benefit / 收益**: Prevents false A+ scores from "spec is bad → audit passes trivially". Consistent with "constructive skeptic" identity — distrust input before trusting output.

**Status / 状态**: ✅ Implemented in v0.1.1 (see `SKILL.md` Phase 0)

### P0.3 — Self-Audit Case Log

**Problem / 问题**: No ground truth for detection rate, false positive rate, false negative rate. The skill's effectiveness is unmeasured.

**Fix / 修复**:
- Create `docs/audit-log/` directory
- Establish `docs/audit-log/TEMPLATE.md` as per-audit record template
- Record per audit: findings (P0/P1/P2/P3), false positives, false negatives (discovered post-audit), time cost
- First instance: `docs/audit-log/2026-07-04-factor-miner-v0.1.0.md` (Factor_Miner audit)

**Benefit / 收益**: First step toward ground truth. Proves detection rate on own project before expecting others to adopt.

**Status / 状态**: ✅ Implemented in v0.1.1 (see `docs/audit-log/`)

### P0.4 — Subagent Prompt: DIMENSION 6 (Build Config + ADR Execution Audit) / 构建配置 + ADR 执行审计

**Problem / 问题**: Code_Hub 审计发现两个 FN（FN-1: pyproject.toml 包名→目录映射不一致, FN-2: event_system.py 无迁移前测试）均涉及构建配置文件和 ADR 决策执行验证。当前 Subagent prompt 的 5 维度未覆盖这两个区域。

**Fix / 修复**:
- Template 1 (Module Audit): 新增 DIMENSION 6 — 检查 pyproject.toml/Cargo.toml/package.json 等构建配置的元数据一致性 + ADR 决策执行验证（每个 ADR 的 "Decision:" 项是否在代码中落地）
- Template 2 (Cross-Module): 新增 CHECK 5 — ADR Decision Execution 交叉验证

**Benefit / 收益**: 消除 Code_Hub 审计中发现的 prompt 盲区，将 FN-1/FN-2 类型的漏报在源头捕获。

**Status / 状态**: ✅ Implemented in v0.2.1 (see `SKILL.md` Template 1 DIMENSION 6 + Template 2 CHECK 5)

### P0.5 — FP Tracking: Type Classification / FP 分类跟踪

**Problem / 问题**: Code_Hub 审计首次量化了 FP 率（8.7%），但 FP 模板仅记录了 "Why FP" 和 "Root Cause"，未区分 FP 类型（over-aggressive / factual-error / scope-error），导致无法系统性诊断 Subagent 的哪类偏差需要 prompt 修正。

**Fix / 修复**:
- TEMPLATE.md §5: 新增 "FP Type" 列（over-aggressive / factual-error / scope-error），附带每种类型的定义和纠正方向

**Benefit / 收益**: 分类 FP 后，可统计每类 FP 占比，针对性优化 prompt（如 over-aggressive 占比高 → 调整 severity 阈值；factual-error 占比高 → 强化 evidence pointer 规则）。

**Status / 状态**: ✅ Implemented in v0.2.1 (see `docs/audit-log/TEMPLATE.md` §5)

---

## P1 Details / P1 层详情

### P1.4 — Reasoning Chain Schema

Subagent output must include structured reasoning chain (schema-ized from Appendix A free-text format):

Defined in `schemas/audit-finding.schema.json` §ReasoningChain:
```json
{
  "read": ["bridge/__init__.py L1-50", "ADR-001 §3.1"],
  "checked": "DAG acyclic, bridge does not import memory",
  "found": "L23 `from factor_miner.memory import X` — violates ADR-001 §3.1",
  "confidence_rationale": "grep evidence + AST evidence"
}
```

Optional in v0.2, mandatory in v0.3+.

**Status / 状态**: ✅ Implemented in v0.2 (see `schemas/audit-finding.schema.json` §ReasoningChain, SKILL.md Appendix A REASONING CHAIN section)

### P1.5 — Spec Mining Fallback

When spec is missing (Phase 0 tier C), reverse-mine implicit constraints from:
- `git log --grep="fix\|bug\|violate"` → historical pitfalls = implicit spec
- Function signatures + docstrings → interface contracts
- Test assertions → behavior contracts
- ADRs (if any) → invariants

Output `implicit_spec.md`, re-enter Phase 0, proceed to structural audit if score ≥ 2.

**Status / 状态**: ✅ Implemented in v0.2 (see SKILL.md §Spec Mining Fallback)

### P1.6 — Structured Audit Protocol (JSON Schema)

Canonical schema: `schemas/audit-finding.schema.json` (JSON Schema Draft-07).
Six entity types defined: AuditFinding, EvidencePointer, ReasoningChain, DimensionStatus, ModuleAuditResult, AuditReport.
Example: `schemas/example-audit-report.json`.

Machine-aggregatable, comparable, benchmarkable.

**Status / 状态**: ✅ Implemented in v0.2 (see `schemas/audit-finding.schema.json`, SKILL.md Appendix B)

---

## P2 Details / P2 层详情

### P2.9 — OSS Benchmark / OSS 基准测试 (v0.3)

**Why first / 为何优先**: No benchmark → all quality claims are unverifiable. P2.9 is the primary P2 item addressing Limitation 3 (output has no baseline), alongside P2.12 (fix tracking JSON → machine-readable ground truth over time). Before adding any new capability, we must establish ground truth for the existing one.

没有基准 → 所有质量声明无法验证。P2.9 是回应局限 3（输出无基准）的主要 P2 项，与 P2.12（修复跟踪 JSON → 随时间积累 ground truth）协同。在添加任何新能力前，必须先为现有能力建立 ground truth。

**Fix / 修复**:
- Select 3 OSS projects with known bug history (fixed issues in git history)
- Selection criteria: (a) has tests, (b) has design docs (ADRs, ARCHITECTURE.md, formal spec, or equivalent), (c) ≥50 commits, (d) ≥3 known bugs in history
- Composition requirement: at least 1 project MUST have a formal design spec (Tier A candidate — e.g., FastAPI's OpenAPI spec). Remaining 2 can be Tier B (structural audit). This ensures benchmark measures both full audit AND structural audit capabilities.
- Candidate pool:
  - **Tier A candidates** (formal spec exists): FastAPI (OpenAPI), Django REST Framework (BDFL docs + deprecation policy), SQLAlchemy (extensive architecture docs)
  - **Tier B candidates** (design docs exist, no formal spec): Flask, Requests, Click
- Run ADD audit on each project's pre-fix commit, measure:
  - **Recall**: known bugs detected / total known bugs
  - **Precision**: true problems / total reported (requires manual FP classification)
  - **Prioritization**: what % of P0 findings are real bugs
- Output: 3 case logs + 1 aggregated benchmark report in `docs/benchmark/`

**TP/FP/FN Classification Standard / 匹配标准** (must be documented in `docs/benchmark/README.md` before first audit):
- **Exact match**: finding file + line range overlaps known bug location → TP
- **Close match**: finding file matches known bug file, same category (e.g., both are "behavior"), claim describes the same root cause → TP (flagged as "close, not exact")
- **Related**: finding describes the same problem but different file/category → FP (not a detection of the known bug, even if the claim is semantically related — this must be strict to avoid overcounting recall)
- **FP classification**: any finding with no matching known bug in any of the three tiers above → FP

B 档 benchmark 标注: When a project is Tier B (structural audit), the benchmark-result.json MUST include `audit_mode: "structural"` and the aggregated report MUST separate full-audit recall from structural-audit recall. Tier B recall is expected to be lower (structural audit does not check spec-specific behavior).

**成本控制**: 3 projects × ~3-4 hours each = ~9-12 hours total (including manual TP/FP classification). Cap each audit at 5 subagents × 1 round.

**Dependency / 依赖**: P2.9 depends on P1.6 (JSON schema) for machine-readable output — ✅ already done.

### P2.8' — Lens System + Typed Subagent / 透镜分级 + 类型化 Subagent (v0.3)

**Why merge / 为何合并**: Original P2.8 (Typed Subagent) and V2#3 (Lens Grading) describe the same problem from different angles — P2.8 from "who audits" (specialized agents), V2#3 from "what to audit" (lens enablement). A lens-driven typed subagent system unifies both: each lens maps to 1 typed subagent, each subagent covers exactly 1 lens. This avoids the complexity of "multi-agent weighted fusion" while keeping the benefit of specialization.

原始 P2.8（Subagent 类型化）和 V2#3（透镜分级）从不同角度描述同一问题——P2.8 从"谁审查"（专业化 Agent），V2#3 从"审查什么"（透镜开关）。透镜驱动的类型化 Subagent 统一两者：每个透镜对应 1 个类型化 Subagent，每个 Subagent 只覆盖 1 个透镜。这避免了"多 Agent 加权融合"的复杂性，同时保持了专业化的收益。

**Lens Model / 透镜模型**:

Core Lens（默认开启，5 个，每个对应 1 个 Typed Subagent）:

| Lens / 透镜 | Typed Subagent | Checks / 检查内容 | Maps to Category |
|---|---|---|---|
| 设计对齐 | Design Aligner | Signature consistency + behavior consistency vs spec | signature + behavior |
| 跨模块契约 | Contract Guardian | ADR invariants, dependency graph, unique entry points | contract |
| 错误处理完整性 | Error Handler | Exception coverage, error propagation, retry logic | behavior (subset) |
| 数据验证/边界 | Boundary Checker | Input validation, null checks, edge cases, type safety | behavior (subset) |
| 修正项追踪 | Corrective Tracker | Spec corrective items reflected in code | corrective |

Extension Lens（按需开启，通过 `--lens` 参数）:

| Lens / 透镜 | Enabled by / 开启方式 | Checks / 检查内容 |
|---|---|---|
| 测试盲区 | always-on (merged into each core subagent's dimension 4) | Blind spot detection (existing SKILL.md blind spot rules) |
| 安全扫描 | `--lens security` | XSS, injection, unsafe eval, hardcoded secrets |
| 架构健康 | `--lens architecture` | Circular deps (via madge/dependency-cruiser output), layer violations |

**Output**: Each typed subagent produces a `ModuleAuditResult` JSON (per existing schema in P1.6). The main agent aggregates all lens results into one `AuditReport`.

**Lens Overlap Deduplication / 透镜重叠去重**: When two core lens subagents report findings with the same evidence (identical file + overlapping line range) and same category:
1. If claims are semantically identical → keep one finding, annotate `detected_by: [lens_a, lens_b]`
2. If claims differ (same evidence, different claims) → keep both as independent findings
3. If claims differ but one is a subset of the other → keep the more specific finding, annotate `detected_by: [both]`

This prevents double-counting the same bug in P3.2 scoring and P2.9 recall/precision. The dedup is applied by the main agent during Step 3 (Aggregate) before score calculation.

**Why NOT "24 lenses"**: Cost explosion (24 × full codebase × per-iteration = unsustainable). 5 core + 2 extension = 7 max at any time. Core lens always on, extension lens opt-in.

**Why NOT "multi-agent weighted fusion"**: Trae Skill cannot do multi-agent parallelism. Each typed subagent is a sequential subagent dispatch — the main agent calls them one by one (or limited parallelism within existing Trae subagent model). No "weighted fusion" needed because lenses are non-overlapping by design.

### P2.10 — Deterministic Assist Layer / 确定性辅助层 (v0.4)

**Problem / 问题**: Subagents operate on AI inference alone. File selection, line-number accuracy, and rule recall are all probabilistic. A single hallucinated line number invalidates an evidence pointer (violating the Iron Rule in Appendix A).

**Fix / 修复**: Add 3 deterministic helper scripts that run BEFORE subagent dispatch. Subagents receive pre-verified inputs.

**Script 1: File Selector / 文件选择器** (`scripts/audit_files.py`)
```
Input:  --spec <spec.md> --module <module_name> --base <git_commit>
Output: JSON list of files to audit, generated deterministically via:
       1. Parse spec.md → extract module name → map to file glob
       2. glob the glob → get file list
       3. git diff <base>..HEAD --name-only → get changed files
       4. Intersection of (2) and (3) = audit scope
Cost cap: max 50 files per module. If >50, warn and pick top 50 by git churn.
```

**Script 2: Line Verifier / 行号验证器** (`scripts/verify_lines.py`)
```
Input:  --finding-json <finding.json> --repo <path>
Output: verified.json with line_number_confirmed: true/false
       1. Read the claimed file
       2. Check if the claimed line content matches a keyword from the finding claim
       3. If mismatch, search within ±20 lines for the nearest match
       4. Flag low-confidence findings (no keyword match within ±20 lines)
```

**Script 3: Rule Index / 规则索引** (`scripts/rule_index.py`)
```
Input:  --spec <spec.md> --adrs <dir>
Output: rule_index.json (keyword → constraint mapping)
       1. Parse spec.md → extract all "must" / "must not" / "threshold" statements
       2. Parse ADRs → extract all invariant statements
       3. Index by keyword for fast lookup
Purpose: Subagent queries index instead of "memorizing" all rules
```

**Integration / 集成**: These scripts are NOT subagent tasks. They are deterministic pre-processing run by the main agent via `RunCommand` before any subagent dispatch. If any script fails or times out (cap: 30 seconds each), the audit proceeds without its output — no blocking dependency.

### P2.7 — Inter-Rater Reliability / 双 Subagent 投票 (v0.4)

Same module audited by 2 independent subagents (different lens assignments, so not fully overlapping). Agreement measured per dimension. Disagreement on severity >1 level escalates to manual review flag.

**Why after P2.8'**: Inter-rater reliability requires typed subagents to be meaningful — comparing two generic subagents tells us nothing. After P2.8' (lens system), inter-rater reliability measures agreement between lens-specific agents on their shared dimensions.

**Method / 方法**:
1. Subagent A audits module X with Lens Set {design, contract, error}
2. Subagent B audits module X with Lens Set {boundary, corrective, blind_spot}
3. Dimensions `signature` + `behavior` appear in both A and B (overlap zone)
4. On overlap dimensions, compare findings. Agreement rate = |intersection| / |union|
5. Cohen's kappa calculated per overlapping dimension

**Cost cap / 成本上限**: Max 2 subagents per module. No third arbiter subagent (v0.4 scope is measurement, not resolution). Resolution deferred to v0.5+.

### P2.11 — Iterative Audit / 迭代审查 (v0.4)

**Problem / 问题**: Current audit is single-pass. When P0 findings are fixed, new P0s may emerge from the fix itself (regression). But unlimited iteration is cost-prohibitive.

**Fix / 修复**: Configurable bounded iteration between Step 2 (Audit) and Step 3 (Aggregate). Human-in-the-loop: the Agent audits → reports P0 → pauses; human fixes → commits; Agent resumes with changed files.

```
Parameters (in SKILL.md config section):
  --max_rounds <n>       default=2, max=5
  --stop_condition <s>   "p0_zero" (default) or "p0_p1_zero"
  --incremental_only     only re-audit files touched in previous round (default=true)

Algorithm (HUMAN-IN-THE-LOOP, NOT automated):
  round = 1
  changed_files = <full scope>
  while round <= max_rounds:
    audit(changed_files)                           # Agent step
    report P0 findings to user                     # Agent output
    if stop_condition met or changed_files empty:  # Agent check
      break
    user fixes all P0 findings                     # HUMAN step (Agent WAITS)
    changed_files = files modified in user's fix commit  # Agent reads git diff
    round += 1
  if round == max_rounds and stop_condition not met:
    warn: "Iteration stopped at max_rounds. {n_p0} P0, {n_p1} P1 remain."
```

**Integration with P2.8'**: Round 1 uses core lens. Round 2 optionally switches to a different core lens subset (e.g., Round 1 = design+contract, Round 2 = error+boundary+corrective).

**Cost cap / 成本上限**: max_rounds=5, incremental_only=true means worst case = 5 × (50 files max) subagent passes. Default config: 2 rounds.

### P2.12 — Fix Tracking JSON + `--verify` Mode / 修复跟踪 JSON 化 (v0.4)

**Problem / 问题**: Phase 4 (Fix Baseline) uses a Markdown table. No machine-readable state. No incremental re-audit — must re-run full audit to confirm a fix.

**Fix / 修复**:

1. **issues.json** — Machine-readable state tracker (NOT a replacement for the Markdown table — both are generated in parallel):

```json
{
  "audit_id": "2026-07-09-example-v0.1.0",
  "issues": [
    {
      "id": "BRIDGE-P0-1",
      "file": "bridge/__init__.py",
      "line": 23,
      "severity": "P0",
      "category": "contract",
      "spec_ref": "ADR-001 §3.1",
      "claim": "bridge imports from memory, violating ADR-001 §3.1",
      "status": "open",
      "fix_commit": null,
      "verified_at": null
    }
  ]
}
```

Note: `spec_ref` is preserved from the original `AuditFinding` (P1.6) — this is REQUIRED for `--verify` mode to know which spec section to re-audit against.

2. **`--verify` mode** — Incremental re-audit of fixed files only:

```
Command: audit verify --file bridge/__init__.py
Effect:  Dispatch 1 subagent to audit only bridge/__init__.py against its spec section
         If the subagent reports 0 findings for the previously-fixed issue ID → status → "verified"
         If the subagent re-reports the issue → status remains "open", escalate to user
```

3. **State machine** per issue:
   `open` → `in_progress` → `fixed` (with commit) → `verified` (after --verify pass)

**Integration with P1.6**: issues.json conforms to the existing `AuditFinding` schema — the `status` field is the only addition. This is backward-compatible.

### P2.13 — Repair Guidance: Structured fix_suggestion + Impact Analysis / 修复引导：结构化修复建议 + 影响分析 (v0.4)

**Problem / 问题**: AuditFinding.fix_suggestion is an optional free-text string. Subagents produce vague suggestions ("use TYPE_CHECKING guard"). No impact analysis — "if I fix this, what else breaks?"

**Fix / 修复**: Upgrade fix_suggestion from free-text to structured format:

```json
{
  "fix_suggestion": {
    "steps": ["Step 1: ...", "Step 2: ..."],
    "affected_files": ["bridge/worker.py:45-60"],
    "regression_risk": "low",
    "verification_command": "pytest tests/test_bridge.py::test_evaluate -v"
  },
  "impact": "Violation of ADR-001 §3.1 causes bridge↔memory coupling that prevents independent module testing",
  "mitigation": "If fix is delayed, add TYPE_CHECKING guard as temporary measure until refactor"
}
```

**Borrowed from / 借鉴自**: TRAE `security-best-practices` skill's structured finding format (8 fields including Impact + Mitigation). See §Borrowed Patterns below.

**Human-in-the-loop / 人机协作**: Subagent **suggests** fix_suggestion; human reviews and edits before applying. Never auto-fix.

**Cost / 成本**: 2 days — schema update (backward-compatible) + prompt instruction update.

---

## Borrowed Patterns / 借鉴模式

ADD 从 TRAE 生态内现有 skill 中借鉴了以下模式：

| Pattern / 模式 | From / 来源 | Applied To / 应用到 | Description / 描述 |
|---|---|---|---|
| **Verify-after-fix** | `test-driven-development` | P2.11 Repair Cycle | TDD 的 Verify RED→Verify GREEN 子步骤 → ADD 的"修复后确认问题确实消失" |
| **Audit Completion Checklist** | `test-driven-development` | P2.12 Repair Tracking | TDD 的 Verification Checklist → ADD 的"审计完成前门控清单" |
| **Red Flags table** | `test-driven-development` | SKILL.md anti-patterns | TDD 的 12 条触发条件 → ADD 可扩展反模式为触发列表 |
| **Structured finding (8 fields)** | `security-best-practices` | P2.13 Repair Guidance | Security 的 Impact + Mitigation 字段 → ADD 的 fix_suggestion 结构化 |
| **3-mode architecture** | `security-best-practices` | v0.4+ passive review | Security 的 Generation/Passive/Active → ADD 未来可加 Passive review 模式 |
| **4-state machine** | `executing-plans` | P2.12 Repair Tracking | executing-plans 的 pending→in_progress→completed → ADD 的 open→in_progress→fixed→verified（多一个验证态） |
| **Block-on-failure** | `executing-plans` | P2.11 Repair Cycle | executing-plans 的"阻塞即停止+请求人类介入" → ADD P0 修复失败时的降级策略 |
| **Task Depends On** | `writing-plans` | Fix Priority Matrix | writing-plans 缺少显式依赖跟踪 → ADD 在修复优先级矩阵中新增 Depends On 字段 |
| **Precision command** | `writing-plans` | P2.12 --verify | writing-plans 的"精确命令+预期输出" → ADD verify 模式附带精确 pytest 命令 |

**Key insight / 关键洞察**: ADD 不是从零开始。TRAE 生态中已经有 TDD（验证循环）、security（结构化发现）、executing-plans（状态机）三种成熟模式。ADD 的差异化在于将这些模式应用于**代码与设计文档对齐**这一未被其他 skill 覆盖的利基。

---

## P3 Details / P3 层详情

### P3.1 — Detection Enhancement: Semantic Guards / 检出增强：语义守卫 (v0.5)

**Problem / 问题**: Even with Spec Mining (P1.5) and Spec Quality Gate (P0.2), the ADD skill has no way to enforce project-specific, human-authored rules that AI cannot infer from code or git history. Example: "All public API endpoints must document request/response schema" — this is a semantic constraint, not derivable from code patterns.

**Fix / 修复**:

1. **guards.yml** — Human-authored rule file in `docs/audit/guards.yml`:

```yaml
# Semantic Guards for Project X
# Human-authored. AI checks compliance, does NOT auto-generate rules.
version: "1.0"

guards:
  - id: "G001"
    description: "All public API endpoints MUST document request/response schema"
    scope: "src/api/**/*.ts"
    severity: "critical"
    check: "For each file matching scope, verify that every exported route handler has a JSDoc @schema tag or equivalent"
    
  - id: "G002"
    description: "Database write operations MUST execute within a transaction"
    scope: "src/repository/**/*.ts"
    severity: "blocker"
    check: "For each file matching scope, verify that INSERT/UPDATE/DELETE calls are wrapped in transaction blocks"
```

2. **Guard Check Subagent** — New typed subagent (extension of lens system):
   - Input: guards.yml + scope files
   - Output: `ModuleAuditResult` where category = `"guard"`
   - Severity mapping: `critical` → P1, `blocker` → P0, `warning` → P2

3. **Guard template** (`docs/audit/guards.template.yml`): Starter file with common guard patterns (API docs, transaction safety, error logging, input validation). Users copy and customize.

**Human-in-the-loop / 人机协作**:
- AI NEVER auto-generates guards. The audit report may SUGGEST new guards (Appendix section: "Recommended Guards"), but they stay as suggestions until a human copies them into guards.yml.
- guards.yml is a version-controlled text file. Changes go through PR review like any other code.

**Relationship to existing Phase 0 Spec Quality Gate**: Phase 0 scores the spec's quality. guards.yml is a separate, always-applied check layer independent of spec quality. A project can have A-tier spec AND a guards.yml — they are complementary.

### P3.2 — Detection Quantification: Numeric Scoring + Trend Tracking / 检出量化：数值评分 + 趋势追踪 (v0.5)

**Problem / 问题**: A+ ~ F letter grades are too coarse. No trend over time. A project going from B+ to B+ across 3 audits could mean "stable" or "regressing with offsetting improvements" — indistinguishable.

**Fix / 修复**:

1. **0–100 numeric score**: Derived from finding count weighted by severity.
```
score = max(0, 100 - (P0_count * 20 + P1_count * 8 + P2_count * 3 + P3_count * 1))
```
Maps approximately: A+ = 95+, A = 85-94, B+ = 75-84, B = 65-74, C+ = 55-64, F = <40

2. **scores.json** — Append-only time series:
```json
[
  {"date": "2026-07-04", "project": "Factor_Miner", "version": "v0.1.0", "score": 68, "grade": "B+"},
  {"date": "2026-07-09", "project": "Factor_Miner", "version": "v0.1.1", "score": 82, "grade": "A-"}
]
```

3. **Mermaid trend chart** — Auto-generated in audit report footer:
```mermaid
xychart-beta
  title "Audit Score Trend"
  x-axis ["v0.1.0", "v0.1.1", "v0.2.0"]
  y-axis "Score" 0 --> 100
  line [68, 82, 91]
```

**Cost / 成本**: Pure data processing. No AI involvement. Scores computed from the existing JSON output in P1.6.

### P3.3 — Repair Knowledge: Cross-Project Guard Reuse / 修复知识：跨项目规则复用 (v0.5)

**Problem / 问题**: A team maintaining 5 projects needs the same guards (e.g., transaction safety, API doc requirements) in all 5. Copy-pasting guards.yml across repos is fragile.

**Fix / 修复**: Two-layer guard architecture:

```
docs/audit/
├── guards.common.yml     ← references external template (optional)
└── guards.project.yml    ← project-specific overrides
```

`guards.common.yml` supports an `extends` directive:
```yaml
extends: "@myteam/audit-rules/guards.base.yml"  # or local path: "../shared-rules/guards.base.yml"

guards:
  # Project-specific guards only. Common guards are inherited from extends.
  - id: "P001"
    description: "This project additionally requires..."
```

**Resolution / 合并逻辑**: `scripts/merge_guards.py` resolves extends → merges with project guards → outputs `guards.effective.yml`. Subagent reads only the effective file.

**Deferral rationale / 为何延迟到 v0.5**: This feature is only useful when (a) the guard system is validated (P3.1) AND (b) there are ≥2 active projects using ADD. Both conditions are currently unmet. H2 2026 target.

---

## Ecosystem Validation Strategy / 生态验证策略

Do not chase stars. Chase **verifiable case studies**:

1. **Factor_Miner** (existing, 2026-07-04 audit) → track detection rate over subsequent audits
2. **Ben Wan's project** → one pilot audit, public report
3. **1 OSS project** (with ADR + tests) → public audit report + detection rate (P2.9)
4. **Accept external issues** → improvement backlog, each issue maps to a P0/P1/P2 item

Star count is a lagging indicator. **Reproducible detection rate** is the leading indicator.

Star 数是滞后指标，**可复现的检出率**是领先指标。

**Updated 2026-07-09**: P2.9 (OSS benchmark) is now the highest-priority P2 item. Items 2-4 remain aspirational. The benchmark is the gate with tiered thresholds:

- **Gate pass (proceed)**: Recall >70% on the Tier A project AND average recall across 3 projects >60%
- **Gate soft-fail (fix, then retry)**: Recall 50-70% on Tier A or average 40-60%. Pause feature work. Optimize subagent prompts. Retry benchmark with same projects.
- **Gate hard-fail (re-scope)**: Recall <50% on Tier A or average <40%. Fundamental rethinking needed — the current subagent approach may not be viable for unknown-codebase audits. Re-scope P2/P3 plan.
- **Threshold adjustment**: The specific thresholds (70%/60%) are initial values. After 1 project benchmark, re-evaluate based on difficulty. Document the adjustment rationale in `docs/benchmark/README.md`.

Initial 80% single-threshold was too aggressive for OSS projects where design docs are often informal. Tiered thresholds allow calibration based on real data.

---

## Version Anchors / 版本锚定

| Version / 版本 | Scope / 范围 | Detection / 检测 | Repair / 修复 | Est. Calendar (业余) |
|---|---|---|---|---|
| v0.1.1 | Iron Law + Gate | P0.1 prompt, P0.2 Phase 0, P0.3 case log | — | Done |
| v0.2 | Structured Foundation | P1.4 reason chain, P1.5 spec mining, P1.6 JSON schema | — | Done |
| v0.2.1 | Audit-Driven Improvements | P0.4 DIMENSION 6, P0.5 FP classification | — | Done |
| v0.2.2 | Detection/Repair Duality | SKILL.md alignment, TDD | — | Done |
| v0.3 | Detection Bootstrap | P2.9 (94.3% recall), P2.8' (7 lenses) | P2.12 (state machine + --verify) | ✅ Done |
| v0.4 | Repair Baseline | P2.10 (3 scripts), P2.11 (iterative), P2.13 (6-field fix_suggestion) | — | ✅ Done |
| v0.5 | Ecosystem | P3.1 Guards, P3.2 Scoring | P3.3 Cross-project | ~1.5 weeks (业余 ~1 month) |

Total: P2 complete. 3 P3 items remaining ≈ **1.5 weeks** at hobby-project pace.

---

## Design Constraints / 设计约束

These constraints were derived from the V1 post-mortem and govern all P2/P3 implementation decisions.

这些约束来自 V1 方案评审，约束所有 P2/P3 实施决策。

1. **Trae Skill boundary / Trae Skill 边界**: All features MUST work within SKILL.md + RunCommand + Subagent dispatch. No external schedulers, no persistent knowledge bases, no multi-agent runtime.
2. **Hard cost caps / 硬性成本上限**: Every feature has a numerical cap (max_rounds=5, max_files=50, max_subagents=7, script_timeout=30s). Features that cannot be capped are not implemented.
3. **Human authors rules, AI checks compliance / 人写规则，AI 查合规**: Guards are human-authored YAML. Spec is human-authored markdown. AI never auto-generates constraints — only checks them.
4. **Pluggable, not replacement / 可插拔，非替换**: Every P2/P3 enhancement is opt-in or additive. Core P0/P1 functionality works identically without any P2/P3 feature enabled.
5. **Benchmark before enhance / 先基准，后增强**: P2.9 (OSS benchmark) is the gate. P2.8' (lens system) **design** can proceed in parallel with benchmark data collection (Week 4 of M1), but **implementation** (SKILL.md lens prompts, audit_lens.py) MUST wait until gate passes. If gate hard-fails, redesign subagent prompts before adding lens system complexity. P2.10-P2.12 are blocked on gate pass regardless.

---

## Change Log / 变更日志

| Date / 日期 | Version / 版本 | Change / 变更 |
|---|---|---|
| 2026-07-10 | v0.3 KB-5 resolution | KB-5 (AfterValidator annotation propagation) resolved via MCP tool search. Root cause: FastAPI PR #13314 (Pydantic 2.11 compat) stripped Annotated metadata. Knowledge synthesized into references/python-pydantic-audit-rules.md (3 detection rules, following security-best-practices references/ pattern). MCP search→knowledge synthesis→reference file pattern validated. Decision recorded in .ds/decisions.jsonl + research_graph.json. / KB-5 通过 MCP 工具搜索解决。根因：FastAPI PR #13314 丢弃了 Annotated 元数据。知识合成到 references/python-pydantic-audit-rules.md。MCP 搜索模式已验证。 |
| 2026-07-10 | v0.2.1→v0.5 rename | P2/P3 items renamed for Detection/Repair duality. P2.13 (Repair Guidance) added — structured fix_suggestion + impact analysis borrowed from security-best-practices skill. Borrowed Patterns section added. Version Anchors updated. / P2/P3 项重命名。新增 P2.13 + Borrowed Patterns 章节。 |
| 2026-07-10 | v0.2.1 | P0.4/P0.5 implemented. Subagent prompt DIMENSION 6 + CHECK 5 added. FP template upgraded. Code_Hub case log added. / P0.4/P0.5 实施。DIMENSION 6 + CHECK 5。FP 模板升级。 |
| 2026-07-09 | v0.2→v0.5 roadmap | Integrated V2 pragmatic enhancement proposal. / 整合 V2 务实增强方案。 |
| 2026-07-09 | v0.2 | P1.4/P1.5/P1.6 implemented. / P1.4/P1.5/P1.6 实施。 |
| 2026-07-06 | v0.1.1 | Initial roadmap created. P0.1/P0.2/P0.3 implemented. / 初始路线图创建。 |
