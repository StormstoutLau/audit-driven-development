# ADD Framework Architecture / 架构文档

> **版本**: v2.8 | **更新日期**: 2026-08-12 | **维护者**: Scott
> **源文档**: 本文档整合自 SKILL.md、ROADMAP.md、DEVLOG.md 及 v2.0-v2.8 设计 spec，无新增断言。

---

## 1. 系统定位

**ADD (Audit-Driven Development) = "SAST Findings Validator"**

ADD 不是 SAST Tool（不自建 detection），而是消费 SAST 工具（Semgrep/CodeQL）输出的 findings，用 4-Level 验证门过滤虚假 findings，再经知识管线沉淀反例规则。

**核心公式**:
```
SAST Output (3000+ rules) → ADD 4-Level Verification Gate → Verified Findings → Knowledge Pipeline → Rule Evolution
```

**与 SAST 工具的分工**:
| 维度 | SAST Tool (Semgrep/CodeQL) | ADD Framework |
|------|---------------------------|---------------|
| 职责 | 检测 (Detection) | 验证 (Verification) |
| 输入 | 源代码 | SAST findings + 源代码 |
| 输出 | 原始 findings | 已验证 findings + hallucination_log |
| 规模 | 3000+ 规则 | 4-Level 验证 + 6 步知识闭环 |
| 护城河 | 规则覆盖率 | 验证精度 + 自演化规则 |

来源: [DEVLOG.md D1](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md)

---

## 2. 整体架构

### 2.1 三轨系统

```
┌─────────────────────────────────────────────────────────────┐
│                    ADD Framework                             │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Detection   │  │ Repair      │  │ Knowledge           │ │
│  │ (检测轨)    │  │ (修复轨)    │  │ (知识轨)            │ │
│  │             │  │             │  │                     │ │
│  │ SAST 消费  │  │ Fix 建议   │  │ 6 步闭环            │ │
│  │ 4-Lvl 验证 │  │ 状态机跟踪 │  │ hallucination_log   │ │
│  │ 幻觉防护   │  │ 回归测试   │  │ 规则自演化          │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│         └────────────────┴────────────────────┘            │
│                          │                                  │
│                   verified_findings.json                    │
│                   hallucination_log.json                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 5-Phase 审计管线

```
Phase 0: Spec Quality Gate
    │  (5 维度评分 → A/B/C 分档)
    ▼
Phase 1: Spec Inventory
    │  (模块 → spec 映射 + 跨模块契约识别)
    ▼
Phase 2: Multi-Dimensional Audit
    │  (Subagent 并行 × 7 lenses → 结构化 findings)
    ▼
Phase 3: Fix Priority Matrix
    │  (P0-P3 分级 + Tier 1/2/3 排序)
    ▼
Phase 3.5: Finding Verification ← 幻觉防护硬门
    │  (4-Level 验证: L1 文件 → L2 行号 → L3 关键词 → L4 结构)
    ▼
Phase 4: Fix Baseline + Tracking
    │  (修复基线 + 状态机 open→fixed→verified)
    ▼
  Output: 审计报告 + 修复跟踪表 + hallucination_log
```

来源: [SKILL.md §The Audit Framework: 5 Phases](file:///f:/Coding/audit-driven-development/SKILL.md)

---

## 3. 4-Level 验证门（核心组件）

### 3.1 验证层级

| Level | 验证内容 | 通过条件 | 失败后果 | 适用 | 实现 |
|-------|---------|---------|---------|------|------|
| **L1** | 文件存在性 | `evidence.file` 在 repo 中存在 | `unverified` → 移出基线 | P0+P1 | `verify_findings.py` |
| **L2** | 行号有效性 | `evidence.line_start` 在文件行数范围内 | `unverified` → 移出基线 | P0+P1 | `verify_findings.py` |
| **L3** | 关键词匹配 | claim 关键词在 ±20 行内出现 | `unverified` → 移出基线 | P0 only | `verify_findings.py` |
| **L4** | 结构性验证 | 代码模式与 claim 类型一致 | `partial` → P0 降级 P1 | P0 only | Tier 1/2/3 降级 |

### 3.2 L4 三层降级架构

```
L4 结构性验证
    │
    ├─ Tier 1: Joern CPG (~95% 准确率)
    │   ├─ 依赖: Joern CLI v4.0+ + JDK 21 (可选)
    │   ├─ 覆盖: dead_code, import_related, **taint** (v3.0 T9' Phase 1)
    │   ├─ 缓存: mtime hash, 24h TTL (/tmp/add_joern_cache/)
    │   └─ 跨环境: Windows 需 WSL2 (F:\foo → /mnt/f/foo)
    │
    ├─ Tier 2: Python ast CFG (~90% 准确率)
    │   ├─ 依赖: Python 3.8+ 标准库 (零依赖)
    │   ├─ 覆盖: dead_code, import_related, **taint** (过程内 def-use, v3.0 T9' Phase 1)
    │   └─ 实现: CFGBuilder + BFS 可达性 + 3-color DFS 环检测
    │
    └─ Tier 3: 正则启发式 (~42% 准确率)
        ├─ 依赖: 无
        ├─ 覆盖: 所有 claim 类型
        └─ 永不崩溃 (任何环境下可用)
```

**降级规则**: Tier 1 → Tier 2 → Tier 3，任一 Tier 返回 `verified=None` 即触发降级，异常被捕获并降级。

### 3.2.1 taint 分支 (v3.0 T9' Phase 1)

**语义层 L5，机制层复用 L4**（[ADR-026](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L578)）：
新增独立函数 `_verify_l5_taint` 承载 taint 专属裁决（Tier 1 Joern `reachableBy` → Tier 2 ast def-use
→ Tier 3 regex），由 `verify_l4_structural` 在 `"taint" in claim_types` 时调用，结果写入既有
`checks["taint"]`，**不新建并行管线**；`verification_level` 数值域保持 `1..4`（**不引入 5**）。

| 项 | 值 |
|---|---|
| 识别 | 双通道：结构化 `evidence.cwe ∈ TAINT_CWE_SET`（8 项）/ `analysis_kind == "taint"`；文本 `TAINT_PATTERNS` |
| 三态字段 | `taint_verified` (True/False/None) · `taint_mode` ("exact"/"broad") · `taint_disproof_action` ("downgrade"/"remove") |
| 证伪动作 | 默认 `downgrade`（[ADR-027](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L615)）；`remove` 需显式 CLI/env |
| kill switch | `ADD_TAINT_DISABLE=1` ⇒ 识别与分派全域关闭 ⇒ 全量裁决与 v2.8 逐位一致 |
| 无裁决 | `sink_nodes == 0`（sink 未定位）与"无路径"数值同形 ⇒ 必返回 `verified=None`，不落 `checks["taint"]` |

来源: [设计 spec](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-design.md), [实施 spec](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-implementation.md), [scripts/verify_findings.py](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py)

### 3.2.2 跨模块契约分支（v3.0 T19）

把「Spec↔Code 契约对齐」中**分层依赖**这一子类从 **LLM 透镜（概率性）转为确定性规则**（[ADR-028](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L669)）。
范本为 import-linter 的 `layers` 语义（层序 + **间接依赖**检测），但**自实现、零新增依赖**（遵守 [ADR-023](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L525-L542)，故**不引入 import-linter 包**）。

| 项 | 值 |
|---|---|
| 识别 | 双通道：结构化 `category == "contract"`（**经新增可选参数传入**）/ `evidence.analysis_kind == "contract"`；文本 `CONTRACT_PATTERNS`（**禁用裸 `layers?` / `contract`**，实证收紧） |
| 声明载体 | `docs/audit/guards.yml` 的**可选** `contract` 子对象：`root`（图根）· `kind: layers` · `layers`（**高→低**）· `allow`（**反向例外白名单**） |
| 实现位置 | [`scripts/contract_graph.py`](file:///f:/Coding/audit-driven-development/scripts/contract_graph.py)（Tier 2，纯 stdlib；复用 `ast_cfg.build_import_graph`） |
| 三态字段 | `contract_verified` (True/False/None) · `contract_kind` · `contract_rule_id` |
| 证伪动作 | `False` ⇒ 依 [ADR-018](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L426) **移除**（默认 `disproof_action="remove"`，不改 `structural_false`） |
| kill switch | `ADD_CONTRACT_DISABLE=1` ⇒ 识别与分派全域关闭 ⇒ 与 v3.0-T9' 现状**逐位一致** |
| **图完整性哨兵** | `模块数 > 1 且 内部边 == 0`（**静默退化**，最重实测发现）⇒ 判 `graph_incomplete` ⇒ **`None`**，**绝不 `False`**（防"假 False"） |
| 无裁决 | `None` ⇒ **不落 `checks["contract"]`**，回落 `generic`（Tier 3） |
| 动态 import | 只影响「被禁方向 + 无路径」支 ⇒ 该支降为 `None`；允许方向的 `False` 与已确认的 `True` 不受影响 |

**已知局限（诚实披露）**：图完整性哨兵会误杀「**天然无内部依赖**」的仓库（⇒ 全部契约请求返回 `None`，方向偏保守）。

来源: [设计 spec v1.1](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T19-contract-design.md), [实施 spec v1.1](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T19-contract-implementation.md), [Step 2 补测](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-v3.0-T19-contract-verification-research.md)

来源: [SKILL.md §Phase 3.5](file:///f:/Coding/audit-driven-development/SKILL.md), [scripts/verify_findings.py](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py), [scripts/joern_cpg.py](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py), [scripts/ast_cfg.py](file:///f:/Coding/audit-driven-development/scripts/ast_cfg.py)

### 3.2.3 Findings schema 分层与激活（v3.0 T20）

| 维度 | 定义 |
|---|---|
| 分层 schema | `AuditFinding`（审计判断，canonical，**逐字节不动**）· `SastFinding`（工具事实，新增） |
| 新增文件 | [`schemas/sast-finding.schema.json`](file:///f:/Coding/audit-driven-development/schemas/sast-finding.schema.json) · [`scripts/validate_findings.py`](file:///f:/Coding/audit-driven-development/scripts/validate_findings.py)（纯 stdlib draft-07 受限子集） |
| `category` 生产者 | Phase 2 透镜（权威）· Semgrep `extra.metadata.add_category` **显式透传**（值须 ∈ 5 值枚举）；**value-level 映射表为空**；CodeQL 不支持（禁止发明字段） |
| `analysis_kind` | 仅证据驱动：`dataflow_trace`（Semgrep）/ `codeFlows`（CodeQL）存在 ⇒ `"taint"`；**禁止按规则名推断** |
| 前置校验 | Phase 3.5 之前 `validate_findings.py --schema audit`；不支持关键字 ⇒ 退出码 2（不静默） |
| 消费端容错 | `issues_tracker` 缺 `category` ⇒ `"unknown"`（不 KeyError）· `inter_rater` 统一 `_finding_category()` + `unknown` 桶恒存在 |
| 边界 | `l4_eligible` / `dimension` 只增不删；`verify_findings.py` **零改动**；882 条语料**零改写** |

来源: [设计 spec v1.3](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T20-findings-schema-design.md), [ADR-029](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md), [Step 2 调研](file:///f:/Coding/audit-driven-development/docs/research/2026-10-20-v3.0-T20-findings-schema-research.md)

### 3.3 Claim 类型分类

| Claim Type | 模式匹配 | 验证逻辑 |
|-----------|---------|---------|
| `missing` | missing/lacks/absent/without | 验证声称的元素确实缺失 |
| `wrong` | wrong/incorrect/invalid/mismatch | 验证错误模式确实存在 |
| `violates` | violates/breaks/conflicts | 验证违反模式确实存在 |
| `dead_code` | dead code/unreachable/unused | 验证代码跟随 return/raise/exit |
| `import_related` | import/from X import | 验证 import 语句存在 |
| `taint`（v3.0 T9'） | `TAINT_PATTERNS` / `evidence.cwe ∈ TAINT_CWE_SET` / `analysis_kind=="taint"` | L4 内 `taint` 分支（`_verify_l5_taint`，见 §3.2.1） |
| `contract_related`（v3.0 T19） | `CONTRACT_PATTERNS` / `category=="contract"` / `analysis_kind=="contract"` | L4 内 `contract` 分支（`contract_graph.verify_contract`，见 §3.2.2） |
| `hallucination_pattern` | 命中 `rule_suggestions.json` 的反例规则 | 调用方据此降级 severity |
| `generic` | (以上均不匹配) | 关键词存在性检查 |

**保守策略**: L4 无法提取 claim 关键词时返回 `confirmed=False`，触发 P0→P1 降级。

---

## 4. 知识管线（6 步闭环）

### 4.1 闭环架构

```
hallucination_log.json (幻觉记录)
    │
    ▼
[Step 1] benchmark_calibrate ← 检查 recall 回归，触发规则回滚
    │
    ▼
[Step 2] rule_suggester ← 消费 hallucination_log 生成反例规则
    │   (reason count ≥3 的 hallucination 模式 → 规则)
    ▼
[Step 3] diff_miner ← git 历史 → bug 模式
    │
    ▼
[Step 4] fix_history ← 修复历史 → threshold 调整 (RL 信号)
    │   (输出 threshold_used 字段)
    ▼
[Step 5] llm_generalize ← 具体规则 → 通用规则
    │
    ▼
[Step 6] fix_recipes ← 修复配方库 (人类 + LLM 双源)
    │
    ▼
rule_validator ← benchmark 复测验证规则有效性
    │
    ▼
live_knowledge.py ← 触发全部 6 步，post-audit 自动更新
```

### 4.2 RL 闭环（v2.8 T1）

```
scores.json (审计评分趋势)
    │
    ▼
threshold → min_keywords 映射
    │
    ├─ 0.85 (严格) → min_keywords=2
    ├─ 0.70 (默认) → min_keywords=1
    └─ 0.55 (宽松) → min_keywords=1
    │
    ▼
L3 关键词匹配行为调整
    │
    ▼
hallucination_log (新幻觉记录)
    │
    ▼
rule_suggester (反例规则生成)
```

**关键约束**:
- 步骤顺序: benchmark_calibrate 必须在 rule_suggester 之前（保证 hallucination_log 先填充再被消费）
- 字段对齐: fix_history 输出 `threshold_used`，verify_findings 读取相同字段名
- 消费端验证: 函数签名声明的新参数必须在函数体内真正调用（v2.7.3 教训：dead parameter 模式）

来源: [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md), [scripts/live_knowledge.py](file:///f:/Coding/audit-driven-development/scripts/live_knowledge.py)

---

## 5. 脚本层级（48 个 Python 文件）

### 5.1 核心验证器层

| 脚本 | 职责 | 大小 | 关键 API |
|------|------|------|---------|
| [verify_findings.py](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py) | 4-Level 验证主调度 | 44KB | `verify_all_findings()`, `verify_l3()`, `verify_l4_structural()` |
| [joern_cpg.py](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py) | Tier 1 Joern CPG 验证 | 36KB | `verify_dead_code()`, `verify_imports()`, `is_available()` |
| [ast_cfg.py](file:///f:/Coding/audit-driven-development/scripts/ast_cfg.py) | Tier 2 AST CFG 验证 | 26KB | `CFGBuilder`, `BFSReachability`, `ImportGraph` |

### 5.2 SAST 集成层（v2.8 新增）

| 脚本 | 职责 | 输入 | 输出 |
|------|------|------|------|
| [semgrep_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/semgrep_to_findings.py) | Semgrep → ADD findings | Semgrep JSON | ADD findings JSON |
| [codeql_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/codeql_to_findings.py) | CodeQL SARIF → ADD findings | SARIF 2.0-2.2 | ADD findings JSON |
| [cwe_rules.py](file:///f:/Coding/audit-driven-development/scripts/cwe_rules.py) | CWE Top 25 映射 | finding | enriched finding |

### 5.3 知识管线层

| 脚本 | 步骤 | 职责 |
|------|------|------|
| [diff_miner.py](file:///f:/Coding/audit-driven-development/scripts/diff_miner.py) | Step 3 | git → bug 模式 |
| [fix_history.py](file:///f:/Coding/audit-driven-development/scripts/fix_history.py) | Step 4 | 修复历史 → threshold |
| [rule_suggester.py](file:///f:/Coding/audit-driven-development/scripts/rule_suggester.py) | Step 2 | hallucination_log → 反例规则 |
| [llm_generalize.py](file:///f:/Coding/audit-driven-development/scripts/llm_generalize.py) | Step 5 | 具体规则 → 通用规则 |
| [fix_recipes.py](file:///f:/Coding/audit-driven-development/scripts/fix_recipes.py) | Step 6 | 修复配方库 |
| [rule_validator.py](file:///f:/Coding/audit-driven-development/scripts/rule_validator.py) | 验证 | benchmark 复测 |
| [live_knowledge.py](file:///f:/Coding/audit-driven-development/scripts/live_knowledge.py) | 调度 | 触发全部 6 步 |

### 5.4 数据集转换层

| 脚本 | 数据源 | 语言 |
|------|--------|------|
| [swebench_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/swebench_to_findings.py) | SWE-bench | Python |
| [defects4j_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/defects4j_to_findings.py) | Defects4J | Java |
| [bigvul_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/bigvul_to_findings.py) | Big-Vul | C/C++ |
| [cvefixes_to_findings.py](file:///f:/Coding/audit-driven-development/scripts/cvefixes_to_findings.py) | CVEfixes | 多语言 |

### 5.5 基础设施层

| 脚本 | 职责 |
|------|------|
| [run_phase8_benchmark.py](file:///f:/Coding/audit-driven-development/scripts/run_phase8_benchmark.py) | Benchmark 执行 + P/R/F1 计算 |
| [download_linux_commits.py](file:///f:/Coding/audit-driven-development/scripts/download_linux_commits.py) | Linux kernel commit 批量下载 (断点续传) |
| [download_repos.py](file:///f:/Coding/audit-driven-development/scripts/download_repos.py) | GitHub URL 推断 + 克隆 |

---

## 6. 数据流

### 6.1 主数据流

```
SAST Tool (Semgrep/CodeQL)
    │
    ├─ semgrep_to_findings.py ──→ ADD findings JSON
    ├─ codeql_to_findings.py ──→ ADD findings JSON (+ CWE enrich)
    │
    ▼
Phase 2: Multi-Dimensional Audit (Subagent × 7 lenses)
    │
    ▼
Phase 3: Fix Priority Matrix (P0-P3 分级)
    │
    ▼
Phase 3.5: 4-Level Verification
    │
    ├─ verified_findings.json (通过验证的 findings)
    ├─ hallucination_log.json (幻觉记录)
    │
    ▼
Phase 4: Fix Baseline + Tracking
    │
    ├─ 审计报告 (docs/audit/)
    ├─ 修复跟踪表 (issues_tracker.py)
    │
    ▼
Knowledge Pipeline (6 步闭环)
    │
    ├─ 反例规则 (rules/)
    ├─ threshold 调整 (scores.json → min_keywords)
    │
    ▼
下一轮审计 (规则已更新)
```

### 6.2 Benchmark 数据流

```
数据集 (SWE-bench/Defects4J/Big-Vul/CVEfixes)
    │
    ├─ *_to_findings.py → findings.json
    │
    ▼
v2.6-full-benchmark.json (687 findings 聚合)
    │
    ▼
run_phase8_benchmark.py
    │
    ├─ Precision = TP / (TP + FP)
    ├─ Recall = TP / (TP + FN)
    └─ F1 = 2 × P × R / (P + R)
    │
    ▼
benchmark-report.json (P=75.0%, R=85.7%, F1=80.0%)
```

---

## 7. 设计约束（硬约束）

来源: [ROADMAP.md §Design Constraints](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md), [project_memory.md](file:///c:/Users/Peng/.trae-cn/memory/projects/-f-Coding-audit-driven-development--p2-0a0c3482eab4d19b9046/project_memory.md)

1. **Python ≥ 3.9，标准库优先** — 不引入新 runtime 依赖（Spoon/JavaParser 违反此约束）
2. **向后兼容硬规则** — `threshold=None` 等价 v2.7，schema 字段只增不删，CLI 参数带默认值
3. **进度文件原子写入** — 必须使用 `.tmp + replace()` 避免文件损坏
4. **所有 middleware async/await** — 禁止 callback 风格
5. **Joern CPG 三层降级** — `verified=None, tier=0` 统一 schema 触发降级，永不崩溃
6. **JOERN_DISABLE 环境变量** — 支持隔离 Joern 功能
7. **hallucination_log 默认输出** — `docs/audit/hallucination_log.json`
8. **L4 verified=False 移除** — 非 P0→P1 降级，直接移除以减少假阴性
9. **Dead_code 双验证** — Joern True + Tier 2 True → 保留 Tier 1 结果，不一致 → Tier 2 优先
10. **Import_related Joern verified=False** — 降级到 Tier 2 验证（pysrc2cpg 局限）

---

## 8. 版本演进里程碑

| 版本 | 日期 | 核心交付 | TDD |
|------|------|---------|-----|
| v0.1.1 | 2026-07-06 | Iron Law + Spec Gate | — |
| v0.2 | 2026-07-09 | Structured Foundation (JSON schema, spec mining) | — |
| v0.3 | 2026-07-10 | 7 lenses, 94.3% recall | — |
| v0.4 | 2026-07-11 | Iterative audit, fix tracking | — |
| v1.0 | 2026-07-11 | Guards, scoring, cross-project | 96/96 |
| v2.0 | 2026-07-11 | Knowledge Pipeline (rule_extractor, spec_graph) | — |
| v2.1 | 2026-07-12 | Dual-Track Learning (diff_miner, fix_history) | 29/29 |
| v2.2 | 2026-07-12 | LLM Generalization + Recipe Book | 25/25 |
| v2.3 | 2026-07-12 | External Knowledge + Community | 22/22 |
| v2.4 | 2026-08-05 | CPG Integration (Joern + AST CFG 三层降级) | 66/66 |
| v2.5 | 2026-08-06 | Learning Pipeline Closure (6 步闭环) | — |
| v2.6 | 2026-08-11 | Dataset Integration (687 findings, 3 languages) | — |
| v2.7 | 2026-08-12 | Closure + L4 Multilang (5 断点修复) | — |
| v2.8 | 2026-08-12 | SAST Integration + CWE + RL Threshold | 491/491 |

来源: [ROADMAP.md §Version Anchors](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)

---

## 9. Gap 闭合状态（v2.8 后）

| Gap | 原状态 | v2.8 后 | v3.0 目标 |
|-----|--------|---------|-----------|
| G1 无 Detection | 🔴 致命 | ✅ 解决 (T3/T4 消费 SAST) | — |
| G2 无 taint | 🔴 致命 | 🔴 仍存在 | T9' 解决 |
| G3 无 CWE/CVE | 🟠 严重 | 🟡 部分解决 (T5 CWE 映射) | — |
| G4 无跨文件 | 🟠 严重 | 🟡 部分缓解 (Joern CPG) | T8' 解决 |
| G5 语言窄 | 🟠 严重 | 🟡 部分缓解 (v2.7.1 多语言) | T11 提升 |
| G6 无 IDE | 🟡 中等 | 🟡 仍存在 | T10 解决 |
| G7 无 CI/CD | 🟡 中等 | ✅ 解决 (T2 GitHub Actions) | — |
| G8 规则生态 0 | 🟡 中等 | 🟡 仍存在 | T14 解决 |
| G9 Benchmark 小 | 🟡 中等 | 🟡 部分缓解 (687 findings) | T12 解决 |
| G10 Loop 展示非决策 | 🟡 中等 | ✅ 解决 (T1 RL 闭环) | — |

**总结**: 10 个 Gap 中 4 个已解决，3 个部分缓解，3 个仍存在。致命级 Gap 从 2 个降至 1 个。

来源: [DEVLOG.md §Gap 闭合追踪](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md)

---

## 10. 参考文档

### 10.1 内部文档

- [SKILL.md](file:///f:/Coding/audit-driven-development/SKILL.md) — Skill 定义（5-Phase 审计框架 + 7 lenses）
- [ROADMAP.md](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md) — 路线图（v0.1→v3.0+）
- [DEVLOG.md](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md) — 开发日志
- [DECISIONS.md](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md) — 关键决策记录
- [DEVELOPMENT_WORKFLOW.md](file:///f:/Coding/audit-driven-development/docs/DEVELOPMENT_WORKFLOW.md) — 开发流程规范

### 10.2 研究文档

- [convergence-analysis.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-convergence-analysis.md) — 1 概率收敛研究
- [v3-roadmap-reassessment.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md) — v3.0+ 路线重新评估
- [T11-T8prime-feasibility-research.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-T11-T8prime-feasibility-research.md) — T11/T8' 可行性调研

### 10.3 v2.8 实施文档

- [v2.8-short-term-improvements.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md) — 设计 spec
- [v2.8-implementation-spec.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-implementation-spec.md) — 实施 spec
- [v2.8-acceptance-audit-checklist.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-checklist.md) — 验收清单 (126 项)
- [v2.8-acceptance-audit-report.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-report.md) — 验收报告 (126/126)

---

## 11. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-12 | v1.0 | 初版创建。整合 SKILL.md + ROADMAP.md + DEVLOG.md + v2.8 spec，描述系统定位、5-Phase 管线、4-Level 验证门、6 步知识闭环、48 脚本层级、数据流、设计约束、Gap 闭合状态。 |

---

**文档结束**
