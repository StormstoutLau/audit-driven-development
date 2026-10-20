# 关键决策记录 / Decision Records

> **格式**: ADR (Architecture Decision Record) — 每条决策含 Status/Context/Decision/Consequences
> **维护规则**: 每次重大决策后追加新记录，不修改历史记录（superseded 状态除外）
> **来源**: 整合自 DEVLOG.md、ROADMAP.md、v3-roadmap-reassessment.md、各版本设计 spec

---

## 决策索引

| ID | 标题 | 状态 | 日期 | 影响范围 |
|----|------|------|------|---------|
| ADR-001 | ADD 定位为 "SAST Findings Validator" | ✅ Accepted | 2026-08-12 | 全局战略 |
| ADR-002 | 中期路线从"补全 Detection"转向"深化 Verification" | ✅ Accepted | 2026-08-12 | v3.0+ 路线 |
| ADR-003 | 新增 T17 (Spec-driven Audit) + T18 (Lean4 子集) | ✅ Accepted | 2026-08-12 | v3.5+ 路线 |
| ADR-004 | T16 (学习闭环 RL) 明确边界为"规则级 RL" | ✅ Accepted | 2026-08-12 | v2.8 + 远期 |
| ADR-005 | T9' 采用 L5 层架构，Joern 优先 + AST 兜底 | ✅ Accepted | 2026-08-12 | T9' |
| ADR-006 | T12 弃用 Big-Vul，改用 CVEfixes + ICVul | ✅ Accepted | 2026-08-12 | T12 |
| ADR-007 | T17 分层实施（L0-L4），从 OpenAPI 开始 | ✅ Accepted | 2026-08-12 | T17 |
| ADR-008 | T18 以 Lean4 为主，Dafny 为 fallback | ✅ Accepted | 2026-08-12 | T18 |
| ADR-009 | T8' 优先于 T11 实施 | ✅ Accepted | 2026-08-12 | T8', T11 |
| ADR-010 | T11 采用 tree-sitter-java，非 javalang/Spoon | ✅ Accepted | 2026-08-12 | T11 |
| ADR-011 | T12 采用半自动标注方案 ($48K) | ✅ Accepted | 2026-08-12 | T12 |
| ADR-012 | T9' 三态验证结果 (true/false/null) | ✅ Accepted | 2026-08-12 | T9' |
| ADR-013 | T17 是 T18 的前置条件 | ✅ Accepted | 2026-08-12 | T17, T18 |
| ADR-014 | T18 目标会议: CAV/TACAS/OOPSLA | ✅ Accepted | 2026-08-12 | T18 |
| ADR-015 | 取消 T7 (AST pattern detection) | ✅ Accepted | 2026-08-12 | v3.0 路线 |
| ADR-016 | T9 重新定位: 检测 taint → 验证 taint | ✅ Accepted | 2026-08-12 | T9' |
| ADR-017 | T8 重构: 自建 import graph → 深化 Joern | ✅ Accepted | 2026-08-12 | T8' |
| ADR-018 | L4 verified=False 直接移除 (非降级) | ✅ Accepted | v2.7.3 | verify_findings.py |
| ADR-019 | Joern CPG 三层降级架构 | ✅ Accepted | v2.4 | joern_cpg.py |
| ADR-020 | hallucination_log 默认输出到 docs/audit/ | ✅ Accepted | v2.7.3 | verify_findings.py |
| ADR-021 | benchmark_calibrate 必须在 rule_suggester 之前 | ✅ Accepted | v2.7.3 | live_knowledge.py |
| ADR-022 | 字段名 threshold_used 跨脚本对齐 | ✅ Accepted | v2.7.3 | fix_history.py |
| ADR-023 | Python ≥ 3.9，标准库优先，不引入新 runtime 依赖 | ✅ Accepted | v0.1 | 全局约束 |
| ADR-024 | 向后兼容: threshold=None 等价 v2.7 | ✅ Accepted | v2.7.3 | verify_findings.py |
| ADR-025 | 进度文件原子写入 (.tmp + replace) | ✅ Accepted | v2.6 | 全局约束 |

---

## ADR-001: ADD 定位为 "SAST Findings Validator"

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Decision Maker**: Scott
- **Source**: [DEVLOG.md D1](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md)

### Context

原框架有 10 个 Gap，其中 G1 (无 Detection) 和 G2 (无 taint) 被标记为致命。需要决定 ADD 是自建 detection 能力还是消费现有 SAST 工具输出。

### Decision

v2.8 通过 T3/T4 (Semgrep/CodeQL 转换器) 消费 SAST 工具输出，而非自建 detection 能力。ADD 定位为"SAST findings 的下游验证器"——消费 SAST 输出，用 4-Level 验证门过滤虚假 findings。

### Rationale

1. Semgrep/CodeQL 有 3000+ 条规则，ADD 7 lenses 永远追不上
2. 4-Level 验证门 + Self-evolving rule pipeline 是 ADD 的真正护城河
3. convergence-analysis.md 研究确认：ADD 的价值在"验证"而非"检测"

### Consequences

- **正面**: 资源聚焦于验证精度，避免与 SAST 工具正面竞争
- **负面**: 依赖 SAST 工具输出质量，无法独立检测
- **影响**: 中期路线取消 T7 (AST pattern detection)，T9 重新定位为"验证 taint"

---

## ADR-002: 中期路线从"补全 Detection"转向"深化 Verification"

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [DEVLOG.md D2](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md)

### Context

ADR-001 确认 ADD 定位为 Validator 后，原 v3.0 路线（T7/T8/T9 侧重 detection）需要调整。

### Decision

- **取消** T7 (AST pattern detection) — 违背战略定位
- **重新定位** T9: 检测 taint → 验证 taint (验证 Semgrep/CodeQL 报告的 source→sink 可达性)
- **重构** T8: 自建 import graph → 深化 Joern 跨文件验证
- **提升优先级** T12: benchmark 规模是验证泛化能力的前提
- **降级** T10: IDE 集成非核心护城河

### Consequences

- 资源投入到"如何更精准地过滤虚假 findings"
- T9' (验证 taint) 成为修复 G2 致命 Gap 的唯一路径

---

## ADR-003: 新增 T17 (Spec-driven Audit) + T18 (Lean4 子集)

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [DEVLOG.md D3](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md), [convergence-analysis.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-convergence-analysis.md)

### Context

convergence-analysis.md 研究结论：
- 当前框架在多轮审计下不可达 1 概率收敛 (Rice 定理、Cousot 抽象解释、Fano 不等式)
- 引入 Lean4 后可实现"分层混合收敛"：形式化子集强收敛 (P=R=1, H=0) + 非形式化子集有界收敛
- 用户提供 spec 时，spec 覆盖范围内可达"条件性 1 收敛"

### Decision

- **T17**: Spec-driven Audit — 用户提供 spec 时，spec 覆盖范围内 P=R=1, H=0
- **T18**: Lean4 形式化验证子集 — 形式化子集上 P=R=1, H=0

### Consequences

- 提供实现强收敛的唯一路径
- 学术价值: "分层混合收敛"是新颖的学术贡献（目标 CAV/TACAS/OOPSLA）
- 需要大量长期投入（6-12 月+）

---

## ADR-004: T16 (学习闭环 RL) 明确边界为"规则级 RL"

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [DEVLOG.md D4](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md)

### Context

原 T16 定义为"学习闭环的真实 RL"（无边界，易被理解为模型级 RL）。

### Decision

- v2.8 T1 已实现"规则级 RL" (threshold→min_keywords 映射驱动 L3 行为)
- "模型级 RL" (调整 LLM 权重) 是远期目标，不在当前框架范围内

### Consequences

- 避免过度承诺
- "规则级 RL"是当前可实现的，"模型级 RL"需要训练基础设施

---

## ADR-005: T9' 采用 L5 层架构，Joern 优先 + AST 兜底

- **Status**: ✅ Accepted **（Clarified by [ADR-026](#adr-026-t9-phase-1-中-l5-层-解释为语义调度层c1-裁决) — "L5" 解释为语义/调度层；未 Superseded）**
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D1](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

T9' 需要验证 SAST 工具报告的 taint finding 是否有真实 source→sink 可达路径。需选择验证引擎。

### Decision

T9' 采用 L5 层架构（独立层级，taint finding 专属），Joern 优先 + AST 兜底。复用现有 Tier 1→2→3 降级机制。

### Rationale

- ADD 已集成 Joern CPG，`reachableByFlows` API 天然适合验证模式
- MVP 2-3 天可交付
- 非破坏性：L1-L4 对所有 finding 保持不变

### Consequences

- taint finding 触发 L5 验证，其他 finding 不受影响
- 三态输出: `taint_verified: true | false | null`

---

## ADR-006: T12 弃用 Big-Vul，改用 CVEfixes + ICVul

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D2](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

Big-Vul 标签准确率仅 25-54%（[来源](https://arxiv.org/html/2512.10485v2)），会导致 benchmark 评估失真。

### Decision

弃用 Big-Vul，改用 CVEfixes (5,495 VFCs) + ICVul (15,396 函数，92% 准确率) 作为主干数据源。

### Consequences

- 提升标签质量，减少噪声污染
- 需要重建 CVEfixes 数据（本地 26 条是合成占位数据）

---

## ADR-007: T17 分层实施（L0-L4），从 OpenAPI 开始

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D3](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

Spec-driven Audit 需要选择 spec 格式和实施路径。

### Decision

T17 分 5 层渐进式实施：
- L0: OpenAPI 3.1 (接口级，自动化)
- L1: EARS (行为级，半自动)
- L2: TLA+ (状态机级，模型检验)
- L3: Hoare Triple (契约级，形式化验证)
- L4: Lean4/Coq (全证明级，交互式)

从 L0 (OpenAPI) 开始，降低 spec 编写成本。

### Consequences

- 渐进式采用，每层可独立交付价值
- L0-L1 可在 1-3 月内实现条件性 1 收敛

---

## ADR-008: T18 以 Lean4 为主，Dafny 为 fallback

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D4](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

需选择形式化验证工具。

### Decision

以 Lean4 为主（学术价值最高），Dafny 为 fallback（学习曲线低，auto-active 验证）。

### Rationale

- Lean4 LLM 辅助最强（AlphaProof, LeanCopilot）
- Dafny 在 miniF2F-Dafny 上 Claude Opus 4.6 达 62.7% pass@4
- Lean4 生态: 270K+ theorems (Mathlib)

### Consequences

- 如 Lean4 翻译成功率 <20%，切换到 Dafny (Plan B)

---

## ADR-009: T8' 优先于 T11 实施

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D5](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

T11 (Java AST CFG) 与 T8' (Joern 深化) 不存在硬依赖关系，需决定实施顺序。

### Decision

T8' 优先于 T11 实施。

### Rationale

T8' 修复 Joern 跨文件能力后，Java 可通过 javasrc2cpg 获得 Tier 1 验证；T11 作为 Tier 2 fallback，可在 T8' 完成后再扩展，避免双重维护成本。

---

## ADR-010: T11 采用 tree-sitter-java，非 javalang/Spoon

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D6](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

需选择 Java AST 解析方案。

### Decision

采用 tree-sitter-java + 自建 CFG。

### Rationale

- javalang: 2018 停更，Java 8+ 解析失败
- Spoon/JavaParser: 引入 JVM 依赖，违反 ADR-023 (Python ≥ 3.9，标准库优先)
- tree-sitter-java: 增量解析、错误恢复、跨语言统一

### Consequences

- 需自建 CFG（工作量约 8 天、1150 行代码）

---

## ADR-011: T12 采用半自动标注方案 ($48K)

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D7](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

全量人工标注 5000 findings 成本 $120K (中位)，超预算。

### Decision

采用半自动 consensus 弱标注 + 抽样精标方案：
- 4 工具批量运行 → 自动弱标签
- Diff-based 自动过滤
- Uncertain 子集 (~1250 条) 3 标注者人工标注
- 10% 抽样验证弱标签

### Consequences

- 成本 $48K，相比全量标注节省 60%
- 需 3 名标注者，目标 Krippendorff's Alpha ≥0.80

---

## ADR-012: T9' 三态验证结果 (true/false/null)

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D8](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

Taint 验证结果需要表达"确认可达"、"确认不可达"、"无法确定"三种状态。

### Decision

三态输出:
- `taint_verified: true` — 路径确认可达，保留 finding
- `taint_verified: false` — 路径不可达（sanitizer 阻断/不可达代码），降级或移除 finding
- `taint_verified: null` — 无法确定，保留 finding（保守策略）

---

## ADR-013: T17 是 T18 的前置条件

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D9](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

T18 (Lean4 形式化验证) 需要 spec 作为输入。

### Decision

T17 必须先于 T18 实现，至少 T17 的 L0-L1 层级（OpenAPI + EARS）需要先就绪。

### Consequences

- T17 提供 spec 格式定义 → T18 需要 spec 作为形式化验证的输入
- T17 提供契约提取机制 → T18 需要契约作为 Lean4 定理的前提

---

## ADR-014: T18 目标会议: CAV/TACAS/OOPSLA

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [v3-roadmap-reassessment.md D10](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)

### Context

T18 的"分层混合收敛"具有学术价值，需选择目标发表会议。

### Decision

首选 CAV 或 TACAS（形式化验证核心会议），次选 OOPSLA（面向应用）。

### Rationale

- CAV: 形式化验证的核心会议
- TACAS: 验证工具和算法
- OOPSLA: 面向实际应用的 PL 研究

---

## ADR-015: 取消 T7 (AST pattern detection)

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [ROADMAP.md v3.0+](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)

### Context

ADR-001 确认 ADD = Validator 后，T7 (自建 AST detection) 违背战略定位。

### Decision

取消 T7。v2.8 战略转向后 G1 已通过消费 SAST 输出解决，自建 detection 违背定位。

---

## ADR-016: T9 重新定位: 检测 taint → 验证 taint

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [ROADMAP.md v3.0+](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)

### Context

原 T9 是"检测 taint"，与 Validator 定位不一致。

### Decision

T9 重新定位为 T9': "验证 taint" — 验证 Semgrep/CodeQL 报告的 taint finding source→sink 可达性，与 Validator 定位一致。

---

## ADR-017: T8 重构: 自建 import graph → 深化 Joern

- **Status**: ✅ Accepted
- **Date**: 2026-08-12
- **Source**: [ROADMAP.md v3.0+](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)

### Context

原 T8 是"自建 import graph"，与 Joern CPG 功能重复。

### Decision

T8 重构为 T8': "深化 Joern 跨文件验证" — 修复 5 个已识别断裂 + 重构 verify_imports()，避免与 Joern 重复。

---

## ADR-018: L4 verified=False 直接移除 (非降级)

- **Status**: ✅ Accepted
- **Date**: v2.7.3
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

L4 verified=False 的 findings 原为 P0→P1 降级，但会导致假阴性。

### Decision

L4 verified=False findings 直接移除（非降级），以减少假阴性。verified=None findings 仍降级为 P1 人工审核。

---

## ADR-019: Joern CPG 三层降级架构

- **Status**: ✅ Accepted
- **Date**: v2.4
- **Source**: [ROADMAP.md v2.4](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)

### Context

L4 结构性验证需要高精度后端，但 Joern 在某些环境不可用。

### Decision

三层降级架构:
- Tier 1: Joern CPG (~95% 准确率) — 可选依赖
- Tier 2: Python ast CFG (~90% 准确率) — 零依赖 fallback
- Tier 3: 正则启发式 (~42% 准确率) — 永不崩溃

统一 schema: `verified=None, tier=0` 触发降级。

### Consequences

- 任何环境下 Tier 3 正则始终可用，保证不崩溃
- 准确率随 Tier 下降而下降，但功能不中断

---

## ADR-020: hallucination_log 默认输出到 docs/audit/

- **Status**: ✅ Accepted
- **Date**: v2.7.3
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

幻觉记录需要持久化以便 post-mortem 分析。

### Decision

verify_findings.py 默认输出 hallucination_log.json 到 `docs/audit/hallucination_log.json`。

### Consequences

- 幻觉记录可被 rule_suggester 消费，生成反例规则
- 幻觉记录可被 benchmark_calibrate 消费，检查 recall 回归

---

## ADR-021: benchmark_calibrate 必须在 rule_suggester 之前

- **Status**: ✅ Accepted
- **Date**: v2.7.3
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

v2.7.3 发现闭环数据流断裂: rule_suggester 在 benchmark_calibrate 之前运行 → 读取空 hallucination_log → 生成 0 条规则。

### Decision

live_knowledge.py 步骤顺序: benchmark_calibrate 必须在 rule_suggester 之前运行，保证 hallucination_log 先填充再被消费。

### Rationale

"生产者先于消费者" — 数据流闭环的基本原则。

---

## ADR-022: 字段名 threshold_used 跨脚本对齐

- **Status**: ✅ Accepted
- **Date**: v2.7.3
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

v2.7.3 发现字段名不匹配: fix_history 输出 "threshold_used" 但 verify_findings 读取 "effective_threshold" → 闭环字段名断裂。

### Decision

fix_history.py 输出字段名是 "threshold_used"，verify_findings.py 读取时必须用相同字段名。闭环字段名必须跨脚本对齐。

---

## ADR-023: Python ≥ 3.9，标准库优先，不引入新 runtime 依赖

- **Status**: ✅ Accepted
- **Date**: v0.1
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

需要确保框架的可移植性和低依赖性。

### Decision

Python ≥ 3.9，标准库优先，不引入新 runtime 依赖。

### Consequences

- Spoon/JavaParser (JVM 依赖) 被排除在 T11 方案之外
- SARIF 解析使用纯 stdlib 实现，不引入 sarif-tools 依赖

---

## ADR-024: 向后兼容: threshold=None 等价 v2.7

- **Status**: ✅ Accepted
- **Date**: v2.7.3
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

v2.7.3 引入 RL threshold 调整，需确保向后兼容。

### Decision

向后兼容硬规则: `threshold=None` 等价 v2.7，schema 字段只增不删，CLI 参数带默认值。

---

## ADR-025: 进度文件原子写入 (.tmp + replace)

- **Status**: ✅ Accepted
- **Date**: v2.6
- **Source**: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

### Context

进度文件写入过程中断会导致文件损坏。

### Decision

进度文件必须使用 `.tmp + replace()` 原子写入方式避免文件损坏。

---

## ADR-026: T9' Phase 1 中 "L5 层" 解释为语义/调度层（C1 裁决）

- **Status**: ✅ Accepted
- **Date**: 2026-10-20
- **Source**: [2026-10-20-T9prime-C1-C4-decision-analysis.md §2](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-T9prime-C1-C4-decision-analysis.md)
- **Related**: [ADR-005](#adr-005-t9-采用-l5-层架构joern-优先--ast-兜底)（Clarified，非 Superseded）

### Context

[ADR-005](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L143) 规定 T9' "采用 L5 层架构（独立层级，taint finding 专属）"，而同文档同句又要求"**复用现有 Tier 1→2→3 降级机制**"。设计 spec 的 D-T9'-2 采纳"L4 内新增 taint 分支 + 独立调度函数 `_verify_l5_taint`"，曾被判定为与 ADR-005 存在"字面冲突"（spec §11 C1）。

### Decision

**T9' Phase 1 中，"L5 层"解释为语义/调度层独立，而非独立管线**：

1. **语义层独立**：新增 `_verify_l5_taint()` 独立调度函数 + 对外三态字段 `taint_verified`（满足 ADR-005 的"独立层级"与 ADR-012 的三态要求）；
2. **机制层复用**：该函数由 `verify_l4_structural` 调用，结果写入既有 `checks["taint"]`，复用既有聚合器与 Tier 1→2→3 降级链；**不新建并行管线**；
3. **编号层不变**：`verification_level` 数值域保持 `1..4`（见 ADR-027）。

### Rationale

逐字复核 ADR-005 后判定：**调和方案不构成对 ADR-005 的违背**，理由为一手证据：

- ADR-005 的 Decision 原文**已明文授权机制复用**（"复用现有 Tier 1→2→3 降级机制"）⇒ 机制层复用是 ADR-005 的要求，非偏离；
- ADR-005 的 Consequences 仅约束两项可观测行为——"三态输出 `taint_verified: true | false | null`"与"其他 finding 不受影响"——调和方案**全部满足**；
- ADR-005 全文**未出现**"独立入口 / 独立聚合器 / `verification_level == 5`"等实现形态约束。

因原始决策未变更，本 ADR 属**诠释（Clarification）**而非取代：ADR-005 状态行追加 `(Clarified by ADR-026)`，**不置 Superseded**。（依据 AWS Prescriptive Guidance：ADR 接受后不可变，变更须新建 ADR 并置旧 ADR 为 Superseded；本处仅诠释，故不做 Superseded。）

### Consequences

- 采纳 spec D-T9'-2 的调和方案，MVP 不建并行管线（避免复制聚合器 [L444-L472](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L444-L472) 与移除判定 [L746-L749](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L746-L749) 并长期同步）；
- 若未来 T9' Phase 2 需要真正的独立管线，须**新建 ADR** 并显式 supersede 本 ADR；
- 排除的幻觉：spec 曾记"不采纳则成本与回归面翻倍"——该量化无实测依据，实际可测量成本为 3 个接线点需复制并长期同步。

---

## ADR-027: T9' Phase 1 收敛策略 — taint 证伪默认降级 + CWE 集合定稿 + 不引入 level 5（C2–C4 裁决）

- **Status**: ✅ Accepted
- **Date**: 2026-10-20
- **Source**: [2026-10-20-T9prime-C1-C4-decision-analysis.md §3-§5](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-T9prime-C1-C4-decision-analysis.md)
- **Related**: [ADR-005](#adr-005-t9-采用-l5-层架构joern-优先--ast-兜底) · [ADR-006](#adr-006-t12-弃用-big-vul改用-cvefixes--icvul) · [ADR-012](#adr-012-t9-三态验证结果-truefalsenull) · [ADR-018](#adr-018-l4-verifiedfalse-直接移除-非降级)

### Context

设计 spec §11 遗留 C2–C4 三项决策：taint 证伪默认动作（降级 vs 移除）、`TAINT_CWE_SET` 成员集合、`verification_level` 是否引入 5。裁决需同时回答三个问题，且三项互不冲突、同属"Phase 1 收敛策略"。

### Decision

**C2 — 证伪动作**: MVP 默认 `downgrade`（`taint_verified=false` → `action="partial"`，P0→P1 降级，不进 hallucination_log 删除路径）；提供 `--taint-disproof=<downgrade|remove>` 与 env `ADD_TAINT_DISPROOF` 覆盖。**切换为 `remove` 的判据（三条全部满足）**：

1. 语料升级为 ADR-006 指定的 **CVEfixes / ICVul**（高准确率标注），不再以 Big-Vul 为主；
2. benchmark 能**度量** taint 通道的 precision 与误删率（taint 类 finding 占比达可统计阈值）；
3. 以 `--taint-disproof=remove` 跑 A/B，误删率 ≤ 可接受阈值。

**C3 — `TAINT_CWE_SET` 定稿**: 保留 8 项，分三档：

| 档 | 成员 | 依据 |
|----|------|------|
| I 已验证 + 有真实命中 | `CWE-079` / `CWE-089` / `CWE-022` | 上游 CodeQL `@kind path-problem`，`precision=high` |
| II 已验证 + 零命中（能力储备） | `CWE-078` / `CWE-502` / `CWE-611` | 上游 `@kind path-problem`；现存语料零命中 |
| III 需附加限定 | `CWE-094` / `CWE-918` | 094 命中样本受 Big-Vul 标签噪声污染；918 上游 `precision=medium`（唯一非 high） |

两条**必读限定**：
- 通道 A 的子条件 `evidence["analysis_kind"] == "taint"` 在 `scripts/**` **无生产者**，且 D-T9'-6 规定 MVP 不改 SAST 转换器 ⇒ **该子条件在 MVP 不可达**，标注为 Phase 2 预留接入点（不删）；
- 通道 A 在**现存 benchmark 语料上不可激活**（`docs/benchmark/**` 中 `"cwe"` / `"rule_id"` / `"owasp"` 三键零命中，882 条语料无一来自 SAST 转换器）⇒ 其收益在当前基准为 0，验证须待 Phase 2（T12）引入转换器语料；MVP 仅由单元测试覆盖。
- "CWE ∈ 集合 ⇒ taint 断言"**仅在该 CWE 由 taint-mode / `path-problem` 规则报出时成立**；对数据集标签 CWE（bigvul / cvefixes）不成立（新增风险 R9）。

**C4 — `verification_level`**: **不引入 5**，数值域保持 `1..4`。taint 语义由新增字段 `taint_verified` / `taint_mode` / `taint_disproof_action` 承载。

### Rationale

**C2 降级优先的依据（三重）**：

- **杠杆率实测**: taint 分类候选 **30 / 882 = 3.4%** ⇒ 无论选降级还是移除，影响面本身仅 3.4%；且其中含 Big-Vul 标签噪声（CWE-094 的 5 条命中样本为 CVE 描述，与代码注入无关）⇒ 用不可靠标签驱动"删除"会把噪声写入 `hallucination_log`，经 ADR-021 顺序污染 `rule_suggester` 规则生成；
- **误报代价不对称（社区案例锚点）**: Sadowski et al., *Lessons from Building Static Analysis Tools at Google*, CACM 61(4) 2018 ([DOI:10.1145/3188720](https://doi.org/10.1145/3188720))——Tricorder 团队"通过禁用表现不佳的分析来最小化有效误报"，开发者对静态分析有强忽略倾向；*Software Engineering at Google* p.419-420 定义 "effective false positive" 并强调 "low false-positive rates are often critical"。**类比限定**：Tricorder 的"误报"指报给开发者的噪声，本处的对应物是"误删真阳性（污染 fix baseline）"——方向一致、载体不同，属**结构性类比**；
- **ADR-018 不可跨类外推**: ADR-018 的"`verified=False` 直接移除"针对 L4 dead_code/import 类（Tier 2 AST 可高置信证伪），而 taint 在 MVP 存在系统性跨过程假阴性（spec R2）⇒ 同类"False"置信度不同，不应套用同一动作。ADR-012 原文写"降级**或**移除"，故本决策落在其允许范围内。

**C4 不引入 5 的依据**: 收益与 `taint_verified` 三态字段冗余；向受约束枚举字段引入新值属 SemVer 2.0.0 意义上的**不兼容变更**（[SemVer 2.0.0](https://semver.org/spec/v2.0.0.html)）；全仓唯一消费点为 `test_v35_consistency.py` L114-115。

### Consequences

- **G2 在 MVP 为"部分修复"**（可降级、可标记，不可过滤删除）——已诚实披露，非掩盖；
- 新增实现要件（否则本 ADR 不成立）：`structural_false` 判定（[verify_findings.py L746-L749](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L746-L749)）必须扩展为同时要求 `c.get("disproof_action", "remove") != "downgrade"`；
- AC-2b 的 `TAINT_CWE_SET` 逐项取证表**已于 2026-10-20 完成**（见裁决分析 E-1）；
- 新增风险 **R9**：`evidence.cwe` 来源质量不一致（SAST 工具自报 vs 数据集标签），须文档显式区分、不混用；
- 本 ADR 取代 spec §11 中 C2/C3/C4 的"待确认"状态；D-T9'-4 的"⚠️ 与 ADR-018 局部偏离"标记**予以保留**（因 ADR-018 未被修改）。

---

## ADR-028: T19 跨模块契约确定性验证 — Tier 2 纯 stdlib + **不引入 import-linter 依赖** + 图完整性哨兵

- **Status**: ✅ Accepted
- **Date**: 2026-10-20
- **Source**: [设计 spec v1.1 D-T19-1~6](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T19-contract-design.md) · [Step 4/6 审计追溯（H1–H10 / G-1–G-10）](file:///f:/Coding/audit-driven-development/docs/audit/2026-10-20-v3.0-T19-contract-spec-audit-trace.md) · [Step 2 补测（F-1~F-5）](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-v3.0-T19-contract-verification-research.md)
- **Related**: [ADR-001](#adr-001-add-定位为-sast-findings-validator) · [ADR-018](#adr-018-l4-verifiedfalse-直接移除-非降级) · [ADR-023](#adr-023-python--39标准库优先不引入新-runtime-依赖) · [ADR-026](#adr-026-t9-phase-1-中-l5-层-解释为语义调度层c1-裁决)

### Context

补强调研（[§7 #12，P0](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-ADD-v3.0-reinforcement-research.md)）指出：ADD 自称最独有的护城河「Spec↔Code 契约对齐」由 **7 个 LLM 透镜**承担，属**概率性判断**；而**跨模块契约类断言无任何确定性验证** —— `classify_claim` 无 `contract` 类型，`verify_l4_structural` 仅结构化验证 `dead_code` / `import_related`，其余落 Tier 3 正则。同时 `docs/audit/guards.yml` 的 `check` 字段是**自由文本、不可机械执行**（guards 是半死文件）。

范本选型遇到一个硬约束冲突：**import-linter**（`layers` 语义 + 间接依赖检测）正是所需能力，但 [ADR-023](#adr-023-python--39标准库优先不引入新-runtime-依赖) 规定「Python ≥ 3.9、标准库优先、**不引入新 runtime 依赖**」且**无例外条款**（其 Consequences 明确排除过 JVM 依赖与 `sarif-tools`）。

### Decision

**D1 — 新 claim 类型 `contract_related`**（与 `import_related` 平行）。双通道识别（**仅 `_contract_enabled()` 时生效**）：① 结构化 — `category == "contract"`（经**新增可选参数** `classify_claim(claim, evidence=None, category=None)` 传入）或 `evidence.analysis_kind == "contract"`；② 文本 — 模块级预编译 `CONTRACT_PATTERNS`（**禁用裸 `layers?` 与裸 `contract`**）。

**D2 — 契约声明扩展 `docs/audit/guards.yml`**（**只增不删**）：新增**可选** `contract` 子对象，含 `root`（**图根**，相对仓库根）、`kind`（当前唯一取值 `layers`）、`layers`（顺序 = **高 → 低**）、`allow`（**反向例外白名单** —— 显式允许特定「低→高」边）。既有 `id` / `description` / `scope` / `severity` / `check` 五字段语义**不变**。

**D3 — Tier 2 纯 stdlib 契约求值：明确不引入 import-linter 依赖。** 复用既有 `ast_cfg.build_import_graph`；新能力放独立模块 `scripts/contract_graph.py`（**不改 `ast_cfg.py`**，避免触碰 `test_v24` 等既有套件的被测对象）。**因此本 ADR 不修订 ADR-023**。

**D4 — 三态裁决 + 图完整性哨兵。** `True` = claim 断言成立；`False` = 声明合法且图完整但断言不成立（依 ADR-018 移除）；**`None` = 无裁决（调用方不写 check，回落 generic）**。**哨兵**：`图模块数 > 1 且 内部边数 == 0` ⇒ 判 `graph_incomplete` ⇒ **`None`**（**绝不 `False`**）。

**D5 — kill switch `ADD_CONTRACT_DISABLE=1`** ⇒ 识别与分派全域关闭；新增 3 字段 `contract_verified` / `contract_kind` / `contract_rule_id` **仅在该 finding 被分类为 `contract_related` 时写入**。

**D6 — 不新增 CLI 参数**（无需降级/移除二选一）；**不改 `structural_false`**（contract 的 `disproof_action` 默认 `"remove"`，既有条件已支持）；**不引入 `verification_level = 5`**（沿用 ADR-026）。

### Rationale

- **D3 的依据（为何是自研而非引入）**: 所需能力（层序 + 间接依赖 + 方向判定）在既有导入图上约百余行即可实现；引入外部依赖会带来 env 探测 / 缓存 / 降级 / **许可**的额外面，而收益仅为语义等价。ADR-023 无例外条款，且「零依赖」本身是 ADD 的差异化资产。
- **D4 哨兵的依据（F-1 实测）**: `build_import_graph('.')` 在仓库根返回 **2164 模块 / 0 内部边**（**静默退化**，无异常）。0 边图与「确实无依赖」数值同形 ⇒ 若不拦截，**任何**违规断言都会得到「无反向路径」⇒ 系统性**假 False**。这与 taint 的 `sink_nodes == 0` 教训同型。
- **D1 新增 `category` 参数的依据（Step 4 审计 H5）**: `category` 是 finding 的**顶层字段**，而 `classify_claim` 及其**唯一调用点**均不接收它 ⇒ 不改则通道 A 的 `category` 判据**永远不可达**。修正方式为**可选参数**（默认 `None` 时行为与 v3.0-T9' 完全一致）。
- **D4「动态 import」作用域的细化（Step 9 实施期）**: v1.0 曾规定「涉事模块含动态 import ⇒ 无条件跳过」，实施期实测发现该规则**过强** —— ADD 自身 `scripts/verify_findings.py` 即含 `__import__`（F-5），导致**真实用例永久不可求值**。精化后：动态 import 只可能**隐藏边**，故**仅将「被禁方向 + 无路径」这一支降为 `None`**；允许方向的 `False` 与已确认的 `True` 不受影响。
- **D2 `allow` 重定义为「反向例外」的依据（Step 4 审计 H1）**: 层序**本身已允许**「高→低」⇒ 若把 `allow` 定义为「高→低白名单」则该字段**语义为空、无任何约束力**。

### Consequences

- **W1 得到部分修复**：跨模块契约断言由概率判断转为**可复算的结构裁决**，且**零新增依赖**；
- **新增已知局限（G-5，诚实披露）**: 图完整性哨兵会误杀「**天然无内部依赖**」的仓库（模块间确无 import 边 ⇒ 判 `graph_incomplete` ⇒ 全部契约请求返回 `None`）。**方向偏保守（安全），明确不修**；
- **触发面 = 0（休眠）**: 在现存 **882 条 benchmark 语料**上，结构化通道（`category` / `analysis_kind` 字段**整体不存在**，F-3）与文本通道（收紧后正则 **0 命中**，T4_35 断言）**均无命中** ⇒ contract 分支在当前语料上**不产生任何裁决**。能力覆盖由**合成 repo 夹具（T1/T2/T3 共 31 项）**与**真实 repo 用例（T3_30，ADD 自身 F-2 实边）**承担。**该结论不得被误读为"功能已被语料验证"**；
- **新增实现要件（否则本 ADR 不成立）**: ① `classify_claim` 的 `category` 可选参数与调用点传参；② `verify_l4_structural` 的 contract 分支；③ generic 门条件追加 `"contract_related"`；④ 3 字段的**条件写入**（承载关闭态逐位一致性）；⑤ `_contract_enabled()` 调用点 ≥2；
- 未改动 `ast_cfg.py` / `merge_guards.py` / `spec_graph.py` / `structural_false` / CLI 参数面（`git diff` 可核）。

---

## ADR-029: Findings schema 分层（AuditFinding = 审计判断 / SastFinding = 工具事实）+ `category` 生产者 = 显式声明 + `analysis_kind` 证据驱动 + 纯 stdlib 校验器

- **Status**: ✅ Accepted
- **Date**: 2026-10-20
- **Source**: [设计 spec v1.3 D-T20-1~8](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T20-findings-schema-design.md) · [Step 4/6/8/9 审计追溯](file:///f:/Coding/audit-driven-development/docs/audit/2026-10-20-v3.0-T20-findings-schema-spec-audit-trace.md) · [Step 2 调研](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-v3.0-T20-findings-schema-research.md)
- **Related**: [ADR-001](#adr-001-add-定位为-sast-findings-validator) · [ADR-023](#adr-023-python--39标准库优先不引入新-runtime-依赖) · [ADR-028](#adr-028-t19-跨模块契约确定性验证--tier-2-纯-stdlib--不引入-import-linter-依赖--图完整性哨兵)

### Context

T19 交付后，benchmark 语料（882 条）上 **contract 通道裁决面 ≈ 0**。补测证明根因**不是语料规模**，而是 schema 自身断裂：
- `category` 字段在转换器产物中**零出现**（882/882 缺失）⇒ `contract` 结构化通道永不可达；
- 转换器产物与 canonical `AuditFinding` schema（8 必填 + `additionalProperties:false`）**二元不兼容**；
- `issues_tracker.py` 对缺字段**强取**⇒ KeyError；`inter_rater.py` 分组缺 category 时**静默失真**（`unknown` 桶恒空）。
⇒ T12（语料扩展）之前必须先**修复 schema 激活缺口**，否则任何新语料仍无法进入结构化通道。

### Decision

**D1 — 分层 schema**（`AuditFinding` **逐字节不动**，新增 `SastFinding`）：
- `AuditFinding` = 审计透镜产物，必填 `spec_ref`/`confidence`/`fix_cost`（反幻觉链路核心语义），SAST 转换器不具备这些字段 ⇒ 不能强行统一；
- `SastFinding` = 工具产物，仅校验不写入 Phase 4 状态机；`category` **可选**；`evidence` **开放**（容纳工具溯源键），严格性放在**顶层**（防字段漂移）。

**D2 — `category` 生产者 = 显式声明，value-level 映射表为空**：
- 权威来源：Phase 2 透镜（`AuditFinding`）按 SKILL.md 定义写 `category`；
- 受限来源：仅当上游规则元数据**显式声明** `extra.metadata.add_category ∈ canonical 5 值枚举` 时透传（Semgrep）。未标注 ⇒ 省略；禁止猜测（如 `security → behavior`）。
- CodeQL 侧无与 `add_category` 等价的官方字段 ⇒ **禁止发明字段名**；若将来确有需求，需先取得一手来源再单独立项。

**D3 — `analysis_kind` 仅证据驱动**：
- Semgrep：`result.extra.dataflow_trace` 存在 ⇒ `evidence.analysis_kind = "taint"`；不存在 ⇒ **省略**；
- CodeQL：SARIF `result.codeFlows` 存在 ⇒ 同上；不存在 ⇒ **省略**；
- **禁止**按 `check_id`/`ruleId` 名称推断（如含 `injection` 即判 taint）。

**D4 — 新增 `scripts/validate_findings.py`（纯 stdlib draft-07 受限子集解释器）**：
- 解释**真实 schema 文件**（`type` / `required` / `enum` / `pattern` / `format` / `minimum` / `minLength` / `items` / `properties` / `additionalProperties` / `$ref`）；
- 不支持的关键字 ⇒ `SchemaError`（退出码 2），**不静默忽略**；
- `_extract_findings()` 支持三种形态（list / `{"findings":[]}` / AuditReport 展平 `module_results`+`cross_module_results`），否则 `--schema audit` 校验 0 条并**假绿**（G-1）。

**D5 — golden case 是"激活"唯一验收判据**：
- synthetic canonical finding（`category="contract"`、`claim="verify_findings imports ast_cfg"`）端到端跑 `verify_single_finding`，断言 `contract_verified is False`（合规方向 ⇒ 断言不成立）且 `action="unverified"`。
- 预期值由 `guards.yml` 层序**推导**而非猜测。

**D6 — `l4_eligible` 与 `dimension` 只增不删、语义不动**：
- 不改写 855 条 `l4_eligible=False`；不翻开关；`dimension` 原样保留。**不**与 `category` 互转（另一轴）。

**D7 — 消费端修复 KeyError 与静默失真**：
- `issues_tracker.py`：`finding["category"]` → `finding.get("category") or "unknown"`；
- `inter_rater.py`：统一 `_finding_category()` 访问器 + 显式 `unknown` 桶（`setdefault` 恒存在）。

### Rationale

- **D1 的依据**：`confidence` 是反幻觉链路核心语义（high=grep+AST / medium=grep / low=推断）。转换器没有"置信度"概念，填任何值都是编造；强行统一会削弱反幻觉基石。
- **D2 的依据**：上游 `metadata.category`（security/correctness/…）是**领域**标签，与审计透镜的**判断类型**不同轴（调研 §3 已证 `dimension` 出现 10 种失控取值）。强行映射 = 假精确；保守省略的代价是"不被契约通道识别"，等价于今日行为；而错误映射的代价是**假裁决进入修复基线**（依 ADR-018 会被移除）⇒ 非对称风险选保守侧。
- **D4 的依据**：若把校验规则硬编码进脚本，schema 文件变成**装饰品**（T19 已识别的"dead parameter"反模式）。解释 schema 文件才能让"schema 是契约"成立；子集化是可控成本（无外部依赖）。
- **D6 的依据**：翻开关会让 C/C++/Java finding 进入不支持的 L4 路径（Joern v2.6 无 Java 结构化验证），产生假裁决。

### Consequences

- `schemas/audit-finding.schema.json` **零改动**（向后兼容）；`schemas/sast-finding.schema.json` 作为工具产物 schema 新增；
- `verify_findings.py` **零改动**（AC-22），不改 CLI 参数面；
- `docs/benchmark/**` **零改动**（AC-19），既有语料全部合法；
- 新增实现要件（否则本 ADR 不成立）：① `schemas/sast-finding.schema.json`；② `validate_findings.py` 纯 stdlib draft-07 子集解释器；③ 转换器 `add_category` 透传 + `dataflow_trace` / `codeFlows` ⇒ `analysis_kind`；④ 消费端 `.get("category")` 容错；⑤ `_finding_category()` + `unknown` 桶显式；⑥ TDD **35 项**；
- **契约激活依赖 Phase 2 透镜**：`contract`/`taint` 通道的激活前提是 finding 带有 `category` 或 `evidence.analysis_kind`；当前语料不满足，能力覆盖由**合成 fixture** + **golden case** 承担；
- 休眠披露：882 条语料中 `contract` 与 `taint` 结构化通道**均零触发** ⇒ Δ=0 仅证明无副作用，不证明功能已被语料验证（同 T19 AC-8 教训）。

### Confirmation / 可机械核验的断言

| # | 命令 | 通过判据 |
|---|---|---|
| C-1 | `py -m pytest scripts/test_v30_t20_findings_schema_consistency.py -q` | **35 passed** |
| C-2 | `py scripts/validate_findings.py --schema sast --findings <8 个语料文件>` | `checked 882 ...: 0 error(s)` |
| C-3 | `py scripts/validate_findings.py --schema audit --findings schemas/example-audit-report.json` | `checked 5 ...: 0 error(s)` |
| C-4 | `git diff --exit-code schemas/audit-finding.schema.json scripts/verify_findings.py docs/benchmark` | 空 diff |
| C-5 | `grep -c "_finding_category(" scripts/inter_rater.py` | ≥ 3（非死函数） |

---

## 待决策事项

| ID | 待决策 | 触发条件 | 选项 | 当前倾向 |
|----|--------|---------|------|---------|
| P1 | T18 是否升级为 Plan B (Dafny) | Lean4 翻译成功率 <20% | 继续 Lean4 / 切换 Dafny | 继续 Lean4 |
| P2 | T12 是否公开 benchmark | T12 完成后 | Zenodo 发布 / 内部使用 | Zenodo 发布 |
| P3 | T17 spec 格式标准化 | T17 L1 完成后 | 采用 EARS / 自定义 DSL | 采用 EARS |
| P4 | T9' Phase 2 启动时机 | T9' Phase 1 benchmark 验证后 | 立即 / 等 T12 完成 | 等 T12 完成 |

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-08-12 | 初版创建。整合 DEVLOG.md (D1-D4) + v3-roadmap-reassessment.md (D1-D10) + project_memory.md (ADR-018~025) + ROADMAP.md (ADR-015~017)，共 25 条 ADR。 |
| 2026-10-20 | 新增 **ADR-026**（T9' Phase 1 "L5 层" 解释为语义/调度层，Clarification）与 **ADR-027**（T9' Phase 1 收敛策略：taint 证伪默认降级 + `TAINT_CWE_SET` 定稿 8 项分三档 + 不引入 `verification_level=5`），来源为 [C1–C4 执行裁决分析](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-T9prime-C1-C4-decision-analysis.md)。ADR-005 状态行追加 `Clarified by ADR-026`（未 Superseded）。 |
| 2026-10-20 | 新增 **ADR-029**（T20 Findings schema 分层：`AuditFinding` 不动 + 新增 `SastFinding`；`category` 生产者 = 显式声明；`analysis_kind` 证据驱动；纯 stdlib draft-07 子集校验器；golden case 为激活唯一判据），来源为 [T20 设计 spec v1.3](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T20-findings-schema-design.md)。 |

---

**文档结束**
