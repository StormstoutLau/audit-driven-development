# Roadmap / 改进路线图

> **The audit skill itself must be audited.**
> **审查 skill 本身也必须被审查。**

This document records the systematic improvement plan for the `audit-driven-development` skill, addressing three limitations identified on 2026-07-06.

本文档记录 `audit-driven-development` skill 的系统性改进计划，回应 2026-07-06 识别的三项局限。

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

### P1 — v0.2 (Aligned with DLQ introduction / 与 DLQ 引入同期)

| ID | Action / 动作 | Addresses / 回应 | Cost / 成本 |
|---|---|---|---|
| **P1.4** | Reasoning chain schema / 推理链 schema 化 | Limitation 2 | 2 days |
| **P1.5** | Spec Mining Fallback / 设计文档反向挖掘 | Limitation 1 | 3-5 days |
| **P1.6** | Structured audit protocol (JSON schema) / 结构化审计协议 | Limitation 2+3 | 2 days |

### P2 — v0.3+ (Aligned with dual-workstation parallelism / 与双工作站并行同期)

| ID | Action / 动作 | Addresses / 回应 | Cost / 成本 |
|---|---|---|---|
| **P2.7** | Inter-rater reliability (dual subagent voting) / 双 subagent 投票 | Limitation 2 | 3 days |
| **P2.8** | Subagent specialization (typed agents) / Subagent 类型化 | Limitation 2 | 2 days |
| **P2.9** | OSS benchmark (recall/precision on known bugs) / OSS 基准测试 | Limitation 3 | 1 week |

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

---

## P1 Details / P1 层详情

### P1.4 — Reasoning Chain Schema

Subagent output must include structured reasoning chain:
```
Read: bridge/__init__.py L1-50, ADR-001 §3.1
Checked: DAG acyclic, bridge does not import memory
Found: L23 `from factor_miner.memory import X` — violates ADR-001 §3.1
Confidence: high (grep evidence + AST evidence)
```

### P1.5 — Spec Mining Fallback

When spec is missing (Phase 0 tier C), reverse-mine implicit constraints from:
- `git log --grep="fix\|bug\|violate"` → historical pitfalls = implicit spec
- Function signatures + docstrings → interface contracts
- Test assertions → behavior contracts
- ADRs (if any) → invariants

Output `implicit_spec.md`, then proceed to normal audit.

### P1.6 — Structured Audit Protocol (JSON Schema)

```python
class AuditFinding(BaseModel):
    severity: Literal["P0","P1","P2","P3"]
    category: Literal["signature","behavior","corrective","blind_spot","contract"]
    evidence_file: str
    evidence_line: tuple[int, int]
    spec_ref: str  # "ADR-001 §3.1" or "spec.md §2.3"
    claim: str
    confidence: float
    fix_cost: Literal["1-line","<10-line","refactor"]
```

Machine-aggregatable, comparable, benchmarkable.

---

## P2 Details / P2 层详情

### P2.7 — Inter-Rater Reliability

Same module audited by 2 independent subagents. Disagreement > threshold escalates to third arbiter subagent. Output agreement rate (Cohen's kappa) as audit quality metric.

### P2.8 — Subagent Specialization

Replace generic subagents with typed experts:
- **ADR Guardian**: dependency graph invariants only
- **Signature Checker**: signature consistency only
- **Blind Spot Hunter**: test blind spots only
- **Corrective Tracker**: spec corrective items only

### P2.9 — OSS Benchmark

Select 3-5 OSS projects with known bug history (fixed issues). Run audit, compare:
- Recall: known bugs detected / total known bugs
- Precision: true problems / total reported
- Kappa across subagent configurations

Public results as case study.

---

## Ecosystem Validation Strategy / 生态验证策略

Do not chase stars. Chase **verifiable case studies**:

1. **Factor_Miner** (existing, 2026-07-04 audit) → track detection rate over subsequent audits
2. **Ben Wan's project** → one pilot audit, public report
3. **1 OSS project** (with ADR + tests) → public audit report + detection rate
4. **Accept external issues** → improvement backlog, each issue maps to a P0/P1/P2 item

Star count is a lagging indicator. **Reproducible detection rate** is the leading indicator.

Star 数是滞后指标，**可复现的检出率**是领先指标。

---

## Version Anchors / 版本锚定

| Version / 版本 | Scope / 范围 | P Items / 包含项 |
|---|---|---|
| v0.1.1 | Immediate fixes / 立即修复 | P0.1, P0.2, P0.3 |
| v0.2 | DLQ introduction / DLQ 引入 | P1.4, P1.5, P1.6 |
| v0.3+ | Dual-workstation parallelism / 双工作站并行 | P2.7, P2.8, P2.9 |

---

## Change Log / 变更日志

| Date / 日期 | Version / 版本 | Change / 变更 |
|---|---|---|
| 2026-07-06 | v0.1.1 | Initial roadmap created. P0.1/P0.2/P0.3 implemented. / 初始路线图创建。P0.1/P0.2/P0.3 实施。 |
