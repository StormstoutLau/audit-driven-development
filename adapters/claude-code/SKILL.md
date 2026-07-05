---
name: audit-driven-development
description: "Multi-dimensional audit of code vs design spec alignment. Produces scoring, issue severity, fix priority matrix, and fix baseline. Invoke after implementation completes or when checking code-design alignment."
---

# Audit-Driven Development

## Overview

After implementation, verify code matches design. Find gaps. Fix blockers. Prevent regression.

**Core principle:** Implementation完成 ≠ 设计落地。审查是"代码与设计文档对齐"的独立环节，与"代码质量审查"（code-review-excellence）正交。

**与 executing-plans / test-driven-development 的关系**：
- executing-plans 覆盖"如何实施"
- test-driven-development 覆盖"如何写单 Task 测试"
- **audit-driven-development 覆盖"实施后如何验证整体与设计对齐"** ← 独有环节

## When to Use

**Always invoke when:**
- 多模块实施计划完成后（如 15 Task 全部 done）
- 用户问"检查代码质量与设计文档对齐"
- 跨模块契约需要验证（如依赖图不变式）
- 修复后的回归基线需要建立
- 设计文档版本升级（如 v0.1.0 → v0.1.1）需要审查影响

**Do NOT use for:**
- 通用代码质量审查（用 code-review-excellence）
- 单 Task TDD 流程（用 test-driven-development）
- 实施计划编写（用 writing-plans）
- 实施计划执行（用 executing-plans）

## The Iron Law

```
NO "IMPLEMENTATION COMPLETE" WITHOUT AN AUDIT-DRIVEN REVIEW
```

164 tests passed 不等于设计落地。测试通过是必要非充分条件。

**测试覆盖不到的 4 类盲区**（必须在审查中识别）：
1. 断言恒真式（assertion always true）
2. 单文件检查盲区（`inspect.getsource()` 看不到跨文件传递依赖）
3. 设计文档独有约束无测试（如 ADR 不变式、策略 G/K）
4. 修正阻断性项无测试（如先行者偏差防护、逃生舱独立检测）

## The Audit Framework: 4 Phases

```dot
digraph audit_cycle {
    rankdir=LR;
    p1 [label="Phase 1\nSpec Inventory", shape=box, style=filled, fillcolor="#ffcccc"];
    p2 [label="Phase 2\nMulti-Dimensional Audit", shape=box, style=filled, fillcolor="#ccffcc"];
    p3 [label="Phase 3\nFix Priority Matrix", shape=box, style=filled, fillcolor="#ccccff"];
    p4 [label="Phase 4\nFix Baseline + Tracking", shape=box, style=filled, fillcolor="#fffccc"];
    next [label="Next\n(fix / regression / iterate)", shape=ellipse];

    p1 -> p2 -> p3 -> p4 -> next;
}
```

### Phase 1: Spec Inventory (设计文档盘点)

**Goal**: 列出所有需要审查的"对齐维度"

1. **收集所有设计文档**（spec 文件、ADR、架构文档）
2. **为每个文档标记版本状态**: `draft / audited / revised`
3. **为每个模块识别对应的 spec**:
   - 模块 → spec 文件 → spec 章节
4. **识别跨模块契约**: ADR 不变式、接口契约、依赖图

**Output**: 审查维度清单（每维度 = 1 模块 vs 1 spec + N 跨模块契约）

### Phase 2: Multi-Dimensional Audit (多维度审查)

**Goal**: 对每个维度执行对齐审查，识别问题

**派发 subagent 并行审查**（每个模块 1 个 subagent + 跨模块契约 1 个 subagent）：

每个 subagent 的任务：
1. 读取模块代码 + 对应 spec
2. 逐章节核对：spec 说"做什么" vs 代码"做了什么"
3. 检查签名一致性（方法名、参数、返回值）
4. 检查行为一致性（策略、阈值、不变式）
5. 检查修正项落实（spec 中的"修正 9.x"是否在代码中体现）
6. 识别测试盲区

**Output per dimension**: 审查报告（评分 + 问题列表 + 测试盲区）

### Phase 3: Fix Priority Matrix (修复优先级矩阵)

**Goal**: 按"影响×成本"排序所有问题，识别 Tier 1

**问题分级**:
| 级别 | 含义 | 必须修复 |
|---|---|---|
| **P0 Blocker** | 阻断核心功能 / 违反不变式 / 数据丢失 | 立即 |
| **P1 Critical** | 策略失效 / 严重 bug / 测试盲区 | 本轮 |
| **P2 Major** | 行为偏差 / 性能问题 / 文档不一致 | 下一轮 |
| **P3 Minor** | 命名 / 注释 / 风格 | 可选 |

**修复 Tier**:
- **Tier 1**: P0 Blocker（全部修复）
- **Tier 2**: P1 Critical + 低成本 P2（如 1 行修复）
- **Tier 3**: 剩余 P2 + P3

**排序启发式**:
1. 阻断性问题 > 严重问题 > 中度问题
2. 1 行修复的 P0 优先于 100 行重构的 P1
3. 影响多模块的问题优先于单模块问题
4. 修正项未落实优先于新增问题（修正项是设计承诺）

### Phase 4: Fix Baseline + Tracking (修复基线 + 跟踪表)

**Goal**: 建立修复基线，防止回归

1. **写入审查报告**: `docs/audit/YYYY-MM-DD-code-quality-audit.md`
2. **修复跟踪表**:

```markdown
| 编号 | 严重度 | 描述 | 状态 | 提交 | 测试验证 |
|---|---|---|---|---|---|
| P0-1 | Blocker | xxx | ✅ 已修复 | commit_hash | 164 tests passed |
| P0-2 | Blocker | yyy | 🚧 修复中 | - | - |
| P1-1 | Critical | zzz | ⬜ 待修复 | - | - |
```

3. **每项修复后立即重跑测试**（零回归原则）
4. **修复完成后更新审查报告**（状态 → ✅，提交 commit_hash）

## Scoring System

每个维度评分（A+ 到 F）:

| 评分 | 含义 | 标准 |
|---|---|---|
| **A+** | 完美对齐 | 0 P0/P1, ≤2 P2 |
| **A** | 优秀 | 0 P0/P1, ≤5 P2 |
| **A-** | 良好 | 0 P0, ≤2 P1 |
| **B+** | 合格 | 0 P0, ≤4 P1 |
| **B** | 基本合格 | 0 P0, ≤6 P1 |
| **B-** | 勉强合格 | 0 P0, 任意 P1 数 |
| **C+** | 不合格 | 1+ P0 修复后 |
| **C** | 严重不合格 | 多项 P0 |
| **F** | 灾难性 | 设计与实现完全脱节 |

**修复后预期评分提升**必须在审查报告中标注（如 Memory: C+ → B+）。

## ADR Dependency Graph Invariants

ADR（架构决策记录）定义的依赖图不变式是审查的核心。检查方法：

### 1. 静态依赖检查（必须）

```bash
# 检查禁止的 import 关系
grep -r "from factor_miner.memory" factor_miner/bridge/  # 应为空
grep -r "from factor_miner.generator" factor_miner/bridge/  # 应为空
```

### 2. 动态依赖检查（必须）

```python
# 用 inspect.getsource() 检查单文件是不够的！
# 必须检查传递依赖链：
# bridge → generator → memory  # 反例，违反 ADR
```

### 3. TYPE_CHECKING 守卫模式

消除静态依赖边的标准模式：

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from factor_miner.memory.data_structures import P_succRecord  # 仅类型注解，运行时不导入
```

**审查规则**: 如果 `data_structures.py` 需要 import 其他模块的类型，必须用 `TYPE_CHECKING` 守卫，否则违反依赖图不变式。

### 4. 两个唯一入口原则

检查以下不变式:
- **Memory 写入**: 只有 orchestrator 调用 `memory.write_*()`
- **Registry 算子调用**: 只有 DSL interpreter 调用 `registry.get()`

## Test Blind Spot Detection

测试通过 ≠ 设计落地。每项 P0/P1 修复后必须检查测试盲区：

### 盲区 1: 断言恒真式
```python
# ❌ 错误示例：恒真式
assert report.success or not report.success  # 永远 True
# ✅ 正确：具体值
assert report.success is True
assert report.decision == "p_succ_candidate"
```

### 盲区 2: 单文件检查盲区
```python
# ❌ inspect.getsource(Bridge.evaluate) 只看单文件
# ✅ 必须检查跨文件传递依赖：
#    bridge.py import generator.data_structures
#    generator.data_structures import memory.data_structures
#    → bridge → memory 传递依赖（违反 ADR）
```

### 盲区 3: 设计文档独有约束无测试
- ADR 不变式（依赖图、唯一入口）
- 策略 G（跨 session 隔离）
- 策略 K（归档触发条件）
- 策略 E（双门决策矩阵）

**必须新增端到端契约测试**覆盖这些约束。

### 盲区 4: 修正阻断性项无测试
- 修正 9.1（先行者偏差防护）→ 必须有 cutoff 测试
- 修正 9.7（逃生舱独立 AST 检测）→ 必须有 LLM 自我声明错误的测试
- 修正 9.10（schema_version）→ 必须有版本字段测试

## Templates

### Template 1: 审查报告骨架

```markdown
# 代码质量与设计文档对齐审查报告

**日期**: YYYY-MM-DD
**审查范围**: <项目名> v<版本>
**审查基线**: <commit_hash>

## 0. 修复跟踪表

| 编号 | 严重度 | 模块 | 描述 | 状态 | 提交 | 测试验证 |
|---|---|---|---|---|---|---|
| P0-1 | Blocker | xxx | yyy | ⬜/🚧/✅ | - | - |

## 1. 审查范围与方法

### 1.1 设计文档清单
- <doc1> (v<version>)
- <doc2> (v<version>)

### 1.2 审查维度
- 维度 1: <module> vs <spec>
- 维度 N: 跨模块契约 (ADR-xxx + Architecture §x)

### 1.3 审查方法
- Subagent-Driven 并行审查
- 每维度独立评分
- 跨维度问题汇总

## 2. 模块审查结果

### 2.1 <Module> 模块 (评分: X)

#### 严重问题
- P0-1: <描述>
  - 位置: <file:line>
  - 不一致: <spec 说 X，代码做 Y>
  - 影响: <导致 Z 失效>
  - 修复建议: <具体方案>

#### 中度问题
- ...

#### 轻微问题
- ...

#### 测试盲区
- ...

## 3. 跨模块契约审查

### 3.1 ADR-001 依赖图不变式
- ✅/❌ <不变式 1>
- ✅/❌ <不变式 2>

### 3.2 接口契约
- ...

## 4. 修复优先级矩阵

### Tier 1: P0 Blocker (立即修复)
1. P0-1: <描述> (修复成本: 1 行 / 影响范围: 全局)

### Tier 2: P1 Critical + 低成本 P2
...

### Tier 3: 剩余 P2 + P3
...

## 5. 测试盲区汇总
...

## 6. 修复后预期评分提升
- <Module>: X → Y
- ...

## 7. 下一步建议
- A. 修复 P0 阻断性问题
- B. 新增契约测试覆盖盲区
- C. 修复 P1 严重问题
```

### Template 2: 修复提交信息

```
fix: resolve N P0 blockers from code quality audit

修复代码质量审查发现的 N 项阻断性问题，<test_count> tests passed 零回归。

## 修复内容

### <Module> (N 项)
- P0-1: <修复内容>
  原因：<为什么会有这个问题>
  修复：<具体改了什么>

...

## 测试验证

<test_count> tests passed (零回归)

## 文档

更新 docs/audit/YYYY-MM-DD-code-quality-audit.md 修复跟踪表。
```

## Process: Step-by-Step

### Step 1: Inventory
1. 收集所有设计文档（spec / ADR / 架构文档）
2. 列出模块清单 + 对应 spec
3. 识别跨模块契约（ADR 不变式、接口契约）
4. 创建 TodoWrite 跟踪审查任务

### Step 2: Audit (Parallel Subagents)
**对每个模块派发独立 subagent**:
- 输入：模块代码 + 对应 spec
- 输出：评分 + 问题列表 + 测试盲区

**跨模块契约审查派发独立 subagent**:
- 输入：ADR + 架构文档 + 所有模块代码
- 输出：不变式违反列表 + 传递依赖链

### Step 3: Aggregate + Prioritize
1. 汇总所有 subagent 报告
2. 按 P0/P1/P2/P3 分级
3. 按 Tier 1/2/3 排序
4. 识别"低成本高影响"修复（1 行修复的 P0 优先）

### Step 4: Fix Baseline
1. 写入 `docs/audit/YYYY-MM-DD-code-quality-audit.md`
2. 填充修复跟踪表（状态 ⬜）
3. 提交基线 commit

### Step 5: Fix P0 Blockers (Iterative)
1. 按修复成本排序 Tier 1（1 行修复优先）
2. 逐项修复
3. 每项修复后立即重跑测试
4. 更新跟踪表（状态 ✅ + commit_hash）

### Step 6: Final Report
1. 更新审查报告（所有 P0 状态 ✅）
2. 标注修复后预期评分提升
3. 提交最终 commit
4. 输出下一步选项（契约测试 / P1 修复 / 实证阶段）

## Critical Anti-Patterns

### ❌ 反模式 1: "测试通过就行"
164 tests passed 是假象。测试盲区（断言恒真式、单文件检查、设计约束无测试）让测试通过失去意义。

### ❌ 反模式 2: "修复后不重跑"
每项 P0 修复后必须重跑全部测试。零回归是硬约束。

### ❌ 反模式 3: "审查后不建立基线"
审查报告必须写入 `docs/audit/`，作为修复基线。口头审查不算数。

### ❌ 反模式 4: "P0 和 P1 一起修"
先修完所有 P0（Tier 1），再修 P1（Tier 2）。混修会让回归定位困难。

### ❌ 反模式 5: "只看单文件"
`inspect.getsource()` 看不到传递依赖。必须用 grep / ast 分析跨文件依赖链。

## Boundaries with Other Skills

| 能力 | 由本 skill 覆盖 | 由其他 skill 覆盖 |
|---|---|---|
| 代码与设计文档对齐 | ✅ | - |
| 多维度审查 + 评分 | ✅ | - |
| 修复优先级矩阵 | ✅ | - |
| ADR 依赖图不变式 | ✅ | - |
| 测试盲区识别 | ✅ | - |
| 通用代码质量 | - | code-review-excellence |
| 单 Task TDD | - | test-driven-development |
| 实施计划编写 | - | writing-plans |
| 实施计划执行 | - | executing-plans |
| 规格管理 | - | OpenSpec / Spec Kit |

## Integration

**前置 skill（实施阶段）**:
- `writing-plans` → 生成实施计划
- `executing-plans` → 执行实施计划
- `test-driven-development` → 单 Task TDD

**本 skill（审查阶段）**:
- `audit-driven-development` → 实施后审查 + 修复基线

**后置 skill（修复阶段）**:
- 回到 `test-driven-development` 修复 P0
- 可选：新增契约测试（用 TDD）

## Remember

- 实施完成 ≠ 设计落地
- 测试通过 ≠ 代码正确
- 审查是独立环节，不是可选步骤
- 修复基线必须文档化
- P0 优先于 P1，1 行修复优先于 100 行重构
- 传递依赖链是 ADR 违反的常见来源
- 修正项未落实是设计承诺的违反
