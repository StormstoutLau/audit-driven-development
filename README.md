# Audit-Driven Development / 审查驱动开发

> **Multi-dimensional audit of code vs design spec alignment.**
> **代码与设计文档对齐的多维度审查。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A [Trae Skill](https://docs.trae.ai/en/skills) that enforces an independent audit phase **after** implementation and **before** declaring "done". It scores code against design specs, identifies blind spots tests cannot catch, and produces a fix priority matrix with regression-safe baselines.

一个 [Trae Skill](https://docs.trae.ai/en/skills)，在实施完成**之后**、声明"完成"**之前**强制执行独立的审查环节。它对代码与设计文档的对齐度评分，识别测试覆盖不到的盲区，并产出回归安全的修复优先级矩阵。

---

## Table of Contents / 目录

- [Why / 为什么需要](#why--为什么需要)
- [The Iron Law / 铁律](#the-iron-law--铁律)
- [When to Use / 何时使用](#when-to-use--何时使用)
- [The 4-Phase Audit Framework / 四阶段审查框架](#the-4-phase-audit-framework--四阶段审查框架)
- [Scoring System / 评分系统](#scoring-system--评分系统)
- [Installation / 安装](#installation--安装)
- [Quick Start / 快速开始](#quick-start--快速开始)
- [Step-by-Step Process / 逐步流程](#step-by-step-process--逐步流程)
- [Test Blind Spots / 测试盲区](#test-blind-spots--测试盲区)
- [Boundaries with Other Skills / 与其他 Skill 的边界](#boundaries-with-other-skills--与其他-skill-的边界)
- [Anti-Patterns / 反模式](#anti-patterns--反模式)
- [Examples / 示例](#examples--示例)
- [License](#license)

---

## Why / 为什么需要

**English**

"164 tests passed" is necessary but **not sufficient**. Tests verify behavior, but they cannot catch:

1. **Assertion tautologies** — `assert x or not x` always passes
2. **Single-file inspection blind spots** — `inspect.getsource()` misses cross-file transitive dependencies
3. **Design-only constraints without tests** — ADR invariants, policy G/K, strategy E decision matrix
4. **Corrective items not implemented** — spec says "fix 9.1 look-ahead bias" but code doesn't reflect it

Implementation completion ≠ design landing. Audit is an **independent** phase, orthogonal to code review (`code-review-excellence`) and TDD (`test-driven-development`).

**中文**

"164 个测试通过"是必要条件但**非充分条件**。测试验证行为，但无法捕获：

1. **断言恒真式** — `assert x or not x` 永远通过
2. **单文件检查盲区** — `inspect.getsource()` 看不到跨文件传递依赖
3. **设计文档独有约束无测试** — ADR 不变式、策略 G/K、策略 E 决策矩阵
4. **修正项未落实** — spec 写了"修正 9.1 先行者偏差防护"，代码却没有体现

实施完成 ≠ 设计落地。审查是**独立**环节，与代码审查（`code-review-excellence`）和 TDD（`test-driven-development`）正交。

---

## The Iron Law / 铁律

```
NO "IMPLEMENTATION COMPLETE" WITHOUT AN AUDIT-DRIVEN REVIEW
没有审查驱动的复核，不得声明"实施完成"
```

Tests passing is a necessary but insufficient condition for design landing. The audit phase is mandatory.

测试通过是设计落地的必要非充分条件。审查环节是强制的。

---

## When to Use / 何时使用

**Always invoke when / 始终在以下场景调用:**

- Multi-module implementation plan completed (e.g., all 15 Tasks done)
  多模块实施计划完成后（如 15 个 Task 全部 done）
- User asks "check code quality vs design spec alignment"
  用户问"检查代码质量与设计文档对齐"
- Cross-module contracts need verification (e.g., dependency graph invariants)
  跨模块契约需要验证（如依赖图不变式）
- Regression baseline needs to be established after fixes
  修复后的回归基线需要建立
- Design doc version upgrade (e.g., v0.1.0 → v0.1.1) requires impact review
  设计文档版本升级（如 v0.1.0 → v0.1.1）需要审查影响

**Do NOT use for / 不要用于:**

- General code quality review → use `code-review-excellence`
  通用代码质量审查 → 用 `code-review-excellence`
- Single Task TDD flow → use `test-driven-development`
  单 Task TDD 流程 → 用 `test-driven-development`
- Implementation plan writing → use `writing-plans`
  实施计划编写 → 用 `writing-plans`
- Implementation plan execution → use `executing-plans`
  实施计划执行 → 用 `executing-plans`

---

## The 4-Phase Audit Framework / 四阶段审查框架

```
Phase 1: Spec Inventory     →  Phase 2: Multi-Dimensional Audit
设计文档盘点                    多维度审查
                                        ↓
Phase 4: Fix Baseline      ←  Phase 3: Fix Priority Matrix
修复基线 + 跟踪表               修复优先级矩阵
```

### Phase 1: Spec Inventory / 设计文档盘点

**Goal / 目标**: List all alignment dimensions to audit / 列出所有需要审查的"对齐维度"

1. Collect all design docs (spec files, ADRs, architecture docs)
   收集所有设计文档（spec 文件、ADR、架构文档）
2. Tag version status for each: `draft / audited / revised`
   为每个文档标记版本状态
3. Map each module to its spec (module → spec file → spec section)
   为每个模块识别对应的 spec
4. Identify cross-module contracts: ADR invariants, interface contracts, dependency graph
   识别跨模块契约：ADR 不变式、接口契约、依赖图

**Output / 输出**: Audit dimension checklist (each dimension = 1 module vs 1 spec + N cross-module contracts)
审查维度清单（每维度 = 1 模块 vs 1 spec + N 跨模块契约）

### Phase 2: Multi-Dimensional Audit / 多维度审查

**Goal / 目标**: Audit each dimension for alignment, identify issues
对每个维度执行对齐审查，识别问题

**Dispatch subagents in parallel / 派发 subagent 并行审查**:
- 1 subagent per module + 1 subagent for cross-module contracts
  每个模块 1 个 subagent + 跨模块契约 1 个 subagent

Each subagent's task / 每个 subagent 的任务:
1. Read module code + corresponding spec
   读取模块代码 + 对应 spec
2. Section-by-section check: spec says "what to do" vs code "does what"
   逐章节核对：spec 说"做什么" vs 代码"做了什么"
3. Check signature consistency (method name, params, return value)
   检查签名一致性（方法名、参数、返回值）
4. Check behavior consistency (policies, thresholds, invariants)
   检查行为一致性（策略、阈值、不变式）
5. Check corrective items implementation (is spec's "fix 9.x" reflected in code?)
   检查修正项落实（spec 中的"修正 9.x"是否在代码中体现）
6. Identify test blind spots
   识别测试盲区

**Output per dimension / 每维度输出**: Audit report (score + issue list + test blind spots)
审查报告（评分 + 问题列表 + 测试盲区）

### Phase 3: Fix Priority Matrix / 修复优先级矩阵

**Goal / 目标**: Sort all issues by "impact × cost", identify Tier 1
按"影响×成本"排序所有问题，识别 Tier 1

**Issue levels / 问题分级**:

| Level / 级别 | Meaning / 含义 | Must fix / 必须修复 |
|---|---|---|
| **P0 Blocker** | Blocks core function / violates invariant / data loss. 阻断核心功能 / 违反不变式 / 数据丢失 | Immediately / 立即 |
| **P1 Critical** | Policy failure / severe bug / test blind spot. 策略失效 / 严重 bug / 测试盲区 | This round / 本轮 |
| **P2 Major** | Behavior deviation / perf issue / doc inconsistency. 行为偏差 / 性能问题 / 文档不一致 | Next round / 下一轮 |
| **P3 Minor** | Naming / comments / style. 命名 / 注释 / 风格 | Optional / 可选 |

**Fix tiers / 修复层级**:
- **Tier 1**: P0 Blocker (all / 全部修复)
- **Tier 2**: P1 Critical + low-cost P2 (e.g., 1-line fix). P1 Critical + 低成本 P2（如 1 行修复）
- **Tier 3**: Remaining P2 + P3. 剩余 P2 + P3

### Phase 4: Fix Baseline + Tracking / 修复基线 + 跟踪表

**Goal / 目标**: Establish fix baseline, prevent regression
建立修复基线，防止回归

1. Write audit report: `docs/audit/YYYY-MM-DD-code-quality-audit.md`
   写入审查报告
2. Fix tracking table / 修复跟踪表:

```markdown
| # / 编号 | Severity / 严重度 | Description / 描述 | Status / 状态 | Commit / 提交 | Test / 测试验证 |
|---|---|---|---|---|---|
| P0-1 | Blocker | xxx | ✅ Fixed / 已修复 | commit_hash | 164 tests passed |
| P0-2 | Blocker | yyy | 🚧 Fixing / 修复中 | - | - |
| P1-1 | Critical | zzz | ⬜ Pending / 待修复 | - | - |
```

3. Rerun tests immediately after each fix (zero regression principle)
   每项修复后立即重跑测试（零回归原则）
4. Update audit report after fix (status → ✅, commit hash)
   修复完成后更新审查报告

---

## Scoring System / 评分系统

Each dimension is scored from A+ to F / 每个维度评分（A+ 到 F）:

| Score / 评分 | Meaning / 含义 | Standard / 标准 |
|---|---|---|
| **A+** | Perfect alignment / 完美对齐 | 0 P0/P1, ≤2 P2 |
| **A** | Excellent / 优秀 | 0 P0/P1, ≤5 P2 |
| **A-** | Good / 良好 | 0 P0, ≤2 P1 |
| **B+** | Pass / 合格 | 0 P0, ≤4 P1 |
| **B** | Basic pass / 基本合格 | 0 P0, ≤6 P1 |
| **B-** | Marginal pass / 勉强合格 | 0 P0, any P1 count / 任意 P1 数 |
| **C+** | Fail / 不合格 | 1+ P0 after fix / 修复后 |
| **C** | Severe fail / 严重不合格 | Multiple P0 / 多项 P0 |
| **F** | Catastrophic / 灾难性 | Design and implementation completely disconnected. 设计与实现完全脱节 |

**Expected score improvement after fix must be noted in audit report** (e.g., Memory: C+ → B+).
**修复后预期评分提升必须在审查报告中标注**（如 Memory: C+ → B+）。

---

## Installation / 安装

### Trae IDE / Trae IDE

1. Copy `SKILL.md` to your Trae skills directory:
   将 `SKILL.md` 复制到 Trae skills 目录:

   ```
   .trae/skills/audit-driven-development/SKILL.md
   ```

2. Trae will auto-discover the skill on next session.
   Trae 会在下次会话自动发现该 skill。

### Trae Solo / Trae Solo

For Trae Solo, place the skill in the project-level skills directory:
对于 Trae Solo，将 skill 放在项目级 skills 目录:

```
<project>/.trae/skills/audit-driven-development/SKILL.md
```

### Verification / 验证

After installation, invoke in Trae chat:
安装后，在 Trae 聊天中调用:

```
Check code quality vs design spec alignment for the current project.
检查当前项目的代码质量与设计文档对齐。
```

The skill will activate automatically when it detects implementation completion or audit-related requests.
当检测到实施完成或审查相关请求时，skill 会自动激活。

---

## Quick Start / 快速开始

### Minimal Example / 最小示例

After a multi-module implementation is complete (all tasks done, tests passing):

多模块实施完成后（所有 task 完成，测试通过）:

1. **Invoke the skill / 调用 skill**:
   ```
   Audit the current implementation against the design specs.
   审查当前实现与设计文档的对齐。
   ```

2. **The skill will / skill 会**:
   - Collect all spec files, ADRs, architecture docs
     收集所有 spec 文件、ADR、架构文档
   - Dispatch parallel subagents (1 per module + 1 for cross-module contracts)
     派发并行 subagent（每模块 1 个 + 跨模块契约 1 个）
   - Aggregate scores and issues
     汇总评分和问题
   - Produce fix priority matrix
     产出修复优先级矩阵
   - Write audit report to `docs/audit/YYYY-MM-DD-code-quality-audit.md`
     将审查报告写入 `docs/audit/YYYY-MM-DD-code-quality-audit.md`

3. **Review the report / 审查报告**:
   - Fix all P0 Blockers first (Tier 1)
     先修复所有 P0 Blocker（Tier 1）
   - Rerun tests after each fix (zero regression)
     每项修复后重跑测试（零回归）
   - Update tracking table status to ✅
     更新跟踪表状态为 ✅

### Typical Output / 典型输出

```
Audit Report: 2026-07-04
Scope: Factor_Miner v0.1.0
Baseline: commit 0b5f796

Summary:
- 11 P0 Blockers (Tier 1 - immediate fix)
- 10 P1 Critical (Tier 2 - this round)
-  7 P2 Major (Tier 3 - next round)
-  0 P3 Minor

Module Scores:
- DSL:          A-
- Memory:       C+ → B+ (after P0 fix)
- Generator:    A-
- Bridge:       B+
- Orchestrator: B+

Cross-Module Contracts:
- ADR-001 dependency graph: 2 violations found
- Strategy E decision matrix: 1 blind spot
- Session isolation: 1 violation found

Next Steps:
A. Fix P0 blockers (4 are 1-line fixes)
B. Add contract tests for 7 blind spots
C. Fix P1 critical issues
```

---

## Step-by-Step Process / 逐步流程

### Step 1: Inventory / 清点

1. Collect all design docs (spec / ADR / architecture docs)
   收集所有设计文档
2. List module manifest + corresponding spec
   列出模块清单 + 对应 spec
3. Identify cross-module contracts (ADR invariants, interface contracts)
   识别跨模块契约
4. Create `TodoWrite` to track audit tasks
   创建 `TodoWrite` 跟踪审查任务

### Step 2: Audit (Parallel Subagents) / 审查（并行 Subagent）

**Dispatch one subagent per module / 每个模块派发独立 subagent**:
- Input: module code + corresponding spec
  输入：模块代码 + 对应 spec
- Output: score + issue list + test blind spots
  输出：评分 + 问题列表 + 测试盲区

**Dispatch one subagent for cross-module contracts / 跨模块契约审查派发独立 subagent**:
- Input: ADR + architecture docs + all module code
  输入：ADR + 架构文档 + 所有模块代码
- Output: invariant violations + transitive dependency chains
  输出：不变式违反列表 + 传递依赖链

### Step 3: Aggregate + Prioritize / 汇总 + 排序

1. Aggregate all subagent reports
   汇总所有 subagent 报告
2. Classify by P0/P1/P2/P3
   按 P0/P1/P2/P3 分级
3. Sort by Tier 1/2/3
   按 Tier 1/2/3 排序
4. Identify "low-cost high-impact" fixes (1-line P0 fix first)
   识别"低成本高影响"修复（1 行修复的 P0 优先）

### Step 4: Fix Baseline / 修复基线

1. Write `docs/audit/YYYY-MM-DD-code-quality-audit.md`
2. Fill fix tracking table (status ⬜)
   填充修复跟踪表（状态 ⬜）
3. Commit baseline commit
   提交基线 commit

### Step 5: Fix P0 Blockers (Iterative) / 修复 P0（迭代）

1. Sort Tier 1 by fix cost (1-line fix first)
   按修复成本排序 Tier 1（1 行修复优先）
2. Fix one by one / 逐项修复
3. Rerun all tests immediately after each fix
   每项修复后立即重跑全部测试
4. Update tracking table (status ✅ + commit_hash)
   更新跟踪表

### Step 6: Final Report / 最终报告

1. Update audit report (all P0 status ✅)
   更新审查报告
2. Note expected score improvement after fix
   标注修复后预期评分提升
3. Commit final commit
   提交最终 commit
4. Output next-step options (contract tests / P1 fix / empirical phase)
   输出下一步选项

---

## Test Blind Spots / 测试盲区

Tests passing ≠ code correct. After each P0/P1 fix, check test blind spots:
测试通过 ≠ 代码正确。每项 P0/P1 修复后必须检查测试盲区:

### Blind Spot 1: Assertion Tautology / 断言恒真式

```python
# ❌ Wrong / 错误：tautology / 恒真式
assert report.success or not report.success  # always True / 永远 True

# ✅ Correct / 正确：specific value / 具体值
assert report.success is True
assert report.decision == "p_succ_candidate"
```

### Blind Spot 2: Single-File Inspection / 单文件检查盲区

```python
# ❌ inspect.getsource(Bridge.evaluate) only sees one file
#    inspect.getsource 只看单文件

# ✅ Must check cross-file transitive dependencies:
#    必须检查跨文件传递依赖：
#    bridge.py import generator.data_structures
#    generator.data_structures import memory.data_structures
#    → bridge → memory transitive dependency (violates ADR)
#    → bridge → memory 传递依赖（违反 ADR）
```

### Blind Spot 3: Design-Only Constraints Without Tests / 设计文档独有约束无测试

- ADR invariants (dependency graph, unique entry points)
  ADR 不变式（依赖图、唯一入口）
- Strategy G (cross-session isolation)
  策略 G（跨 session 隔离）
- Strategy K (archive trigger conditions)
  策略 K（归档触发条件）
- Strategy E (double-gate decision matrix)
  策略 E（双门决策矩阵）

**Must add end-to-end contract tests** to cover these constraints.
**必须新增端到端契约测试**覆盖这些约束。

### Blind Spot 4: Corrective Items Without Tests / 修正阻断性项无测试

- Fix 9.1 (look-ahead bias protection) → must have cutoff test
  修正 9.1（先行者偏差防护）→ 必须有 cutoff 测试
- Fix 9.7 (escape hatch independent AST detection) → must have LLM false-claim test
  修正 9.7（逃生舱独立 AST 检测）→ 必须有 LLM 自我声明错误的测试
- Fix 9.10 (schema_version) → must have version field test
  修正 9.10（schema_version）→ 必须有版本字段测试

---

## Boundaries with Other Skills / 与其他 Skill 的边界

| Capability / 能力 | This skill / 本 skill | Other skill / 其他 skill |
|---|---|---|
| Code vs design doc alignment / 代码与设计文档对齐 | ✅ | - |
| Multi-dimensional audit + scoring / 多维度审查 + 评分 | ✅ | - |
| Fix priority matrix / 修复优先级矩阵 | ✅ | - |
| ADR dependency graph invariants / ADR 依赖图不变式 | ✅ | - |
| Test blind spot identification / 测试盲区识别 | ✅ | - |
| General code quality / 通用代码质量 | - | `code-review-excellence` |
| Single Task TDD / 单 Task TDD | - | `test-driven-development` |
| Implementation plan writing / 实施计划编写 | - | `writing-plans` |
| Implementation plan execution / 实施计划执行 | - | `executing-plans` |
| Spec management / 规格管理 | - | `OpenSpec` / `Spec Kit` |

### Integration Workflow / 集成工作流

**Pre-skills (implementation phase) / 前置 skill（实施阶段）**:
- `writing-plans` → generate implementation plan / 生成实施计划
- `executing-plans` → execute implementation plan / 执行实施计划
- `test-driven-development` → single Task TDD / 单 Task TDD

**This skill (audit phase) / 本 skill（审查阶段）**:
- `audit-driven-development` → post-implementation audit + fix baseline
  实施后审查 + 修复基线

**Post-skills (fix phase) / 后置 skill（修复阶段）**:
- Back to `test-driven-development` to fix P0
  回到 `test-driven-development` 修复 P0
- Optional: add contract tests (using TDD)
  可选：新增契约测试

---

## Anti-Patterns / 反模式

### ❌ Anti-Pattern 1: "Tests pass, good to go" / "测试通过就行"

164 tests passed is an illusion. Test blind spots (assertion tautologies, single-file inspection, design constraints without tests) make test passing meaningless.
164 个测试通过是假象。测试盲区让测试通过失去意义。

### ❌ Anti-Pattern 2: "No rerun after fix" / "修复后不重跑"

Every P0 fix must rerun all tests. Zero regression is a hard constraint.
每项 P0 修复后必须重跑全部测试。零回归是硬约束。

### ❌ Anti-Pattern 3: "No baseline after audit" / "审查后不建立基线"

Audit report must be written to `docs/audit/` as fix baseline. Verbal audit doesn't count.
审查报告必须写入 `docs/audit/`，作为修复基线。口头审查不算数。

### ❌ Anti-Pattern 4: "Fix P0 and P1 together" / "P0 和 P1 一起修"

Fix all P0 (Tier 1) first, then P1 (Tier 2). Mixing makes regression localization difficult.
先修完所有 P0（Tier 1），再修 P1（Tier 2）。混修会让回归定位困难。

### ❌ Anti-Pattern 5: "Single-file view only" / "只看单文件"

`inspect.getsource()` can't see transitive dependencies. Must use grep / ast analysis for cross-file dependency chains.
`inspect.getsource()` 看不到传递依赖。必须用 grep / ast 分析跨文件依赖链。

---

## Examples / 示例

### Real-World Application / 实战应用

This skill was developed and validated during the [Factor_Miner](https://github.com/StormstoutLau/Factor_Miner) project audit on 2026-07-04. Key results:

本 skill 在 2026-07-04 的 [Factor_Miner](https://github.com/StormstoutLau/Factor_Miner) 项目审查中开发并验证。关键结果:

- **Scope / 审查范围**: 6 modules, 4 design docs (v0.1.0-audited), 1 ADR
  6 个模块，4 份设计文档（v0.1.0-audited），1 份 ADR
- **Issues found / 发现问题**: 11 P0 + 10 P1 + 7 P2
- **Test blind spots / 测试盲区**: 7 categories, 21 contract tests added
  7 类盲区，新增 21 个契约测试
- **Fix outcome / 修复结果**: All 11 P0 fixed, 164 tests passed (zero regression)
  11 项 P0 全部修复，164 个测试通过（零回归）
- **Score improvement / 评分提升**: Memory C+ → B+, Orchestrator B → B+
- **Audit report / 审查报告**: [docs/audit/2026-07-04-code-quality-audit.md](https://github.com/StormstoutLau/Factor_Miner/blob/master/docs/audit/2026-07-04-code-quality-audit.md)

### Audit Report Template / 审查报告模板

See [`SKILL.md`](./SKILL.md) §Templates for the complete audit report skeleton and fix commit message template.
完整的审查报告骨架和修复提交信息模板见 [`SKILL.md`](./SKILL.md) §Templates。

---

## License

[MIT](./LICENSE) © 2026 StormstoutLau
