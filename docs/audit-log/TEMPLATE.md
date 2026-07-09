# Audit Case Log Template / 审计案例日志模板

> Copy this file to `YYYY-MM-DD-<project>-<version>.md` and fill in.
> 复制此文件为 `YYYY-MM-DD-<project>-<version>.md` 并填写。

---

## 1. Metadata / 元数据

| Field / 字段 | Value / 值 |
|---|---|
| Project / 项目 | |
| Version / 版本 | |
| Audit Date / 审计日期 | |
| Auditor / 审计者 | |
| Baseline Commit / 基线提交 | |
| Spec Quality Tier / Spec 质量档位 | A / B / C |
| Skill Version / Skill 版本 | |

---

## 2. Spec Inventory / 设计文档清单

| Doc / 文档 | Version / 版本 | Status / 状态 |
|---|---|---|
| | | draft / audited / revised |

---

## 3. Findings Summary / 发现汇总

| Severity / 严重度 | Count / 数量 | Fixed This Round / 本轮修复 | Remaining / 剩余 |
|---|---|---|---|
| P0 Blocker | | | |
| P1 Critical | | | |
| P2 Major | | | |
| P3 Minor | | | |

---

## 4. Module Scores / 模块评分

| Module / 模块 | Score Before / 修复前评分 | Score After / 修复后评分 | Notes / 备注 |
|---|---|---|---|
| | | | |

---

## 5. False Positives / 误报

Issues reported by subagents that turned out NOT to be real problems after manual review.

subagent 报告但人工复核后确认不是真问题的项。

| # | Finding / 发现 | Why False Positive / 为何误报 | Root Cause / 根因 |
|---|---|---|---|
| | | | |

---

## 6. False Negatives / 漏报

Issues discovered AFTER the audit (in subsequent development, testing, or production) that the audit missed.

审计后发现、但 audit 未检出的真实问题。

| # | Issue / 问题 | When Discovered / 何时发现 | Why Missed / 为何漏报 |
|---|---|---|---|
| | | | |

---

## 7. Time Cost / 时间成本

| Phase / 阶段 | Time (min) / 时间 (分钟) | Notes / 备注 |
|---|---|---|
| Phase 0: Spec Quality Gate | | |
| Phase 1: Spec Inventory | | |
| Phase 2: Multi-Dimensional Audit | | |
| Phase 3: Fix Priority Matrix | | |
| Phase 4: Fix Baseline | | |
| Total / 总计 | | |

---

## 8. Detection Rate / 检出率

(To be calculated after false negatives are collected over time.)

(在收集足够漏报数据后计算。)

| Metric / 指标 | Value / 值 | Formula / 公式 |
|---|---|---|
| Precision / 精度 | | TP / (TP + FP) |
| Recall / 召回率 | | TP / (TP + FN) |
| F1 | | 2 * P * R / (P + R) |

Where:
- TP = true positives (real problems found)
- FP = false positives (reported but not real)
- FN = false negatives (real but missed)

---

## 9. Lessons Learned / 经验教训

What did this audit reveal about the skill itself?

本次审计揭示了 skill 本身的什么问题？

- |
- |

---

## 10. Skill Improvement Actions / Skill 改进动作

Actions triggered by this audit's lessons (link to ROADMAP.md items).

由本次审计经验触发的改进动作（关联 ROADMAP.md 条目）。

| ROADMAP ID | Action / 动作 | Priority / 优先级 |
|---|---|---|
| | | |
