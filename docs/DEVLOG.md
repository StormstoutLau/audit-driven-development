# Development Log / 开发日志

> 记录 ADD Framework 的开发决策、版本演进和关键转折点。
> Record development decisions, version evolution, and key turning points.

---

## 2026-10-20 · v3.0 T19 (跨模块契约确定性验证, Tier 2 纯 stdlib) 交付

### 背景

「Spec↔Code 契约对齐」中的**分层依赖**子类此前只能由 **LLM 透镜（概率性）** 判定，无确定性复核手段：
一个"低层模块反向依赖高层模块"的 finding 无法被 4-Level 验证门机械证真/证伪。
T19 以 [import-linter](https://github.com/seddonym/import-linter) 的 `layers` 语义（**层序 + 间接依赖检测**）为**范本**，
在 ADD 内**自实现**该求值（**零新增依赖**，遵守 [ADR-023](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L525-L542)，
**不引入 import-linter 包**）。

### 交付内容

| 文件 | 变更 |
|------|------|
| [scripts/contract_graph.py](file:///f:/Coding/audit-driven-development/scripts/contract_graph.py) | **新增**（Tier 2，纯 stdlib）：`_build_graph`（缓存 + **图完整性哨兵**）/ `_mtime_sig`（排除 `__pycache__`/`.venv`/`.git`）/ `layer_of`（最长前缀）/ `find_path`（BFS + 前驱回溯，返**实际路径**）/ `evaluate_contract`（三态 + `incomplete` 支）/ `load_contract_declarations` / `_validate_layers` / `verify_contract`（对外唯一入口） |
| [scripts/verify_findings.py](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py) | **六处追加式改动**（+61 / −5）：① `classify_claim(claim, evidence=None, category=None)` 新增可选参数；② 模块级 `CONTRACT_PATTERNS`（9 条，**禁裸 `layers?`/`contract`**）+ `_CONTRACT_DISABLE_ENV` + `_contract_enabled()`；③ 调用点传 `finding.get("category")`；④ L4 内新增 `contract` 分支；⑤ generic 门条件增 `contract_related`；⑥ 3 个 `contract_*` 字段**仅在分类命中时写入** |
| [scripts/test_v30_contract_consistency.py](file:///f:/Coding/audit-driven-development/scripts/test_v30_contract_consistency.py) | **新增** TDD **37 项**（T1 识别 9 / T2 图与求值 13 / T3 端到端与降级 9 / T4 兼容与 kill switch 6），**pytest 模块** |
| [docs/audit/guards.yml](file:///f:/Coding/audit-driven-development/docs/audit/guards.yml) | **新增**：ADD 自身真实契约（源自 **F-2 实测依赖边**），`root: "scripts"` + **5 层**（高→低）+ `allow: []` |
| [docs/audit/guards.template.yml](file:///f:/Coding/audit-driven-development/docs/audit/guards.template.yml) | **纯追加**（+35 / −0）：`contract` 子对象字段语义 + **反向例外**构造法 + 已知局限说明 |

### 关键工程事实（Step 2 补测 F-1~F-5 + 实施期实测）

1. **图根敏感 + 静默退化（最重发现 F-1）**：`build_import_graph('.')` 得 **2164 模块 / 0 内部边**（仓库根下含
   benchmark 克隆与外部脚本，且**不报错**）；`build_import_graph('scripts')` 得 **56 模块 / 46 边**（含 T19 新增 2 脚本）。
   ⇒ 0 边图与"确实无依赖"**数值同形**，若不拦截将产生**系统性假 False** ⇒ **图完整性哨兵**（模块 > 1 且内部边 = 0 ⇒ `None`）
   是**必需项**，非防御性冗余。
2. **语料零触发（F-3 + F-4）**：882 条 benchmark 语料中 `category` / `evidence.analysis_kind` 字段**整体不存在**
   ⇒ 结构化通道命中 **0**；旧文本正则（含裸 `layers?`）4/882 **全为噪声**（命中 `msPostGISLayerSetTimeFilter` 等标识符子串）
   ⇒ 收紧为**带词边界的中英短语集**，命中亦为 0。
3. **动态 import 只可能"隐藏边"**：ADD 自身 `scripts/verify_findings.py` 含 `__import__`（F-5）；
   若按 v1.0 设计「涉事即整体跳过」，则**真实用例永久不可求值**（T3_30 首次 RED 的根因）。
   ⇒ 细化为：**仅**「被禁方向 + 无路径」支降为 `None`（图可能不完整 ⇒ 不可判 `False`）；「允许方向的 `False`」与「已确认的 `True`」**不受影响**。
4. **索引语义钉死**：`layers[0]` = **最高层** ⇒ `idx(src) < idx(dst)` = **允许方向**（⇒ `False`）；
   `idx(src) > idx(dst)` = **被禁方向**；**间接依赖（传递路径）同属违规**。`allow` = **反向例外白名单**（非"高→低白名单"，后者语义空转）。
5. **反幻觉**：`verify_findings.py` 净增 **+56 行** ⇒ design §8 的 11 处行号引用**全部右移**（已在 Step 10 逐项复验并双列记录）。

### 验收结果

- TDD：`py -m pytest scripts/test_v30_contract_consistency.py` → **37 passed**（0 failed）。
- 零回归：`test_v24` **153** / `test_v27` **68** / `test_e2e_v24_integration` **22** / `test_v28` **25** / `test_v30_taint` **41** 全通过。
- **kill switch 逐位一致**（`ADD_CONTRACT_DISABLE=1` vs 默认，同语料 **687 findings**）：剔除 `timestamp`/`latency*` 后
  `json.dumps(sort_keys=True)` **完全相等**（70,131 B）、递归键集合**相等**、逐 finding `action`+`outcome` 差异 **0**、两臂**均无** `contract_*` 键。
- **指标非退化**：ΔP = ΔR = ΔF1 = **0**（P=75.0 / R=71.4 / F1=73.2 / tp-fp-fn-tn = 15-5-6-176）。
  > **休眠披露**：Δ=0 属**代数必然**（语料零触发），只能证明"无副作用"，**不能**证明"功能已被语料验证"；
  > 功能正确性由**合成 repo 强制命中**证据独立承载（T2 13 项 + T3 9 项）。
- 性能：图缓存生效（同根二次调用**建图 1 次**）；`scripts/` 规模下单次 `verify_contract` **163 ms**（≤ 250 ms）。
- 真实用例：ADD 自身 `scripts/` 的 7 条实边**全部合规**（`verified=False`，无违规）。
- **验收**：对接 checklist **59 项 → 59 PASS / 0 FAIL**（P0 45/45）。

### 决策记录

- [ADR-028](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L669)：T19 = 跨模块契约确定性验证（Tier 2 纯 stdlib）；
  识标 `contract_related` 双通道；声明载体 = `guards.yml` 可选 `contract` 子对象；`root` 字段（实证修正 X-1）；
  `allow` **反向例外**白名单；三态裁决 + **图完整性哨兵（绝不假 False）**；kill switch `ADD_CONTRACT_DISABLE`；
  **不改 `structural_false` / 不引入 level 5 / 不新增 CLI 参数**；**不引入 import-linter 依赖**。

### 已知局限（诚实披露）

- **图完整性哨兵会误杀「天然无内部依赖」的仓库**（模块 > 1 且内部边 = 0 ⇒ 全部契约请求 `None`）。
  **方向偏保守（安全），明确不修**。
- benchmark 语料对 contract 通道**零触发** ⇒ 收益待 T12 引入 SAST 转换器语料（`analysis_kind == "contract"`）后方可兑现。
- 文本通道 `CONTRACT_PATTERNS` 为**非穷举**中英短语集（9 条），不覆盖所有契约表述。
- `_load_yaml` 依赖**可选** `PyYAML`；缺失时契约声明不可解析 ⇒ 全部请求 `None`（既有模式，非新依赖）。

### Step 10 新发现并修正（净增量）

1. **实现缺陷 F-1**：`guards.yml` 曾误声明 **6 层**（多出惰性 `_rule_utils`）⇒ 删至 **5 层**（与 design spec 一致），复跑 37 passed。
2. **checklist 自身错误 F-2**：§8 附录 A 映射有误 ⇒ 改为 `AC-1 → R3 · A10` / `AC-22 → R3 · T4_35`。
3. **spec 陈旧引用 F-3**：design §8 行号表改**双列**（原行号 / 现行号）并逐项复验（**审计轨迹追加，版本保持 v1.1**）。
4. **验证方法细化 F-4**：`AC-24` 后半句（本仓库缺省 `.` 触发哨兵）以机械探针补证（`_build_graph('.')` ⇒ `None`）。
5. 以上均**不涉及设计决策变更** ⇒ **未新增 ADR**（`ADR-028` 仍为 T19 唯一决策记录）。

**验收报告**: [2026-10-20-v3.0-T19-contract-acceptance-audit-report.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-10-20-v3.0-T19-contract-acceptance-audit-report.md)

---

## 2026-10-20 · v3.0 T9' Phase 1 (Taint 验证能力, Joern MVP) 交付

### 背景

G2（无 taint 验证）是 v2.8 后**唯一**致命 Gap：SAST 工具报告的 taint finding（source→sink
污点可达）无法被 4-Level 验证门复核，只能落到 Tier 3 正则，导致该类别 finding 的假阳性无法被过滤。
T9' 定位为「**验证** taint」（复核 SAST 报告的 source→sink 可达性），**不是**「检测 taint」（不自建污点检测引擎，ADR-016）。

### 交付内容

| 文件 | 变更 |
|------|------|
| [scripts/verify_findings.py](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py) | `TAINT_CWE_SET`（8 项）/ `TAINT_PATTERNS` / `_CWE_ID_RE` / `_taint_enabled()` / `_resolve_taint_disproof()` / `_extract_taint_cwe()` / `_verify_taint_regex()` / `_verify_l5_taint()`；`classify_claim(claim, evidence=None)` 双通道识别；`verify_l4_structural(..., evidence, taint_disproof)` + taint 分支 + generic 门条件改写 (E-5)；`structural_false` 尊重 `disproof_action` |
| [scripts/joern_cpg.py](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py) | `INPUT_API_REGEX` / `_TAINT_QUERY_MEMO`(512 有界) / `_gen_taint_flow_script()`(broad+exact 双变体) / `verify_taint_flow()`(三态)；`_run_joern_query` / `_generate_cpg` 补 `cwd=` (N-1) |
| [scripts/ast_cfg.py](file:///f:/Coding/audit-driven-development/scripts/ast_cfg.py) | `_INPUT_ASSIGN_CALLS` / `_INPUT_ATTR_BASES` / `_iter_assignments` / `_collect_taint_names` / `verify_taint_flow_in_source()`（过程内 def-use）/ `verify_taint_flow()`（文件级包装） |
| [scripts/test_v30_taint_consistency.py](file:///f:/Coding/audit-driven-development/scripts/test_v30_taint_consistency.py) | 新建 TDD **41 tests**（T1 14 / T2 11 / T3 10 / T4 4 / T0.10 / T6.1） |

### 关键工程事实（T0 实测 + 实施期实测）

1. **T0 阻断门（R1/R1b/R1c/R1d）全闭合**：`reachableBy` 可用但 `Traversal.reachableBy(Traversal)=0`
   ⇒ sink/source **至少一侧须为 `.l`(List)**；裸 `cpg.call.lineNumber(N)` 实测**跨文件**命中 9 个 call
   ⇒ **必须按 `sink_file` 过滤**（E-1）；`cpg.call.name(regex)` 对点分调用按**末段名**渲染
   ⇒ `INPUT_API_REGEX = ^(input|raw_input|getenv|getpass|get|getlist)$`（已删 `loads|load`）。
2. **N-1 副作用修正**：`joern --script` 会在调用者 CWD 生成 `workspace/<cpg>/` CPG 副本（仓库内既有 100 个
   同类目录 / 144.7 MB）⇒ `_run_joern_query` / `_generate_cpg` 显式传 `cwd=<joern 缓存目录>`（T2.11 断言）。
3. **sink 未定位与"无路径"数值同形**（都是 0）⇒ 必返回 `verified=None`，绝不静默当作 `False`（AC-5）。
4. **首次使用** Joern 数据流包 `io.joern.dataflowengineoss.language._`（随 CLI 分发，非 pip 依赖）。

### 验收结果

- TDD：`py -m pytest scripts/test_v30_taint_consistency.py` → **41 passed**（0 failed）。
- 零回归：`test_v24` 153 / `test_v27` 68 / `test_v28` 25 / `test_e2e_v24_integration` 全通过。
  > **实测修正（Step 9）**: `test_v24` / `test_v27` / `test_e2e_v24_integration` 是**脚本式**套件
  > （模块级 `sys.exit`），必须以 `python <script>` 直接运行；`py -m pytest` 会触发 pytest INTERNALERROR。
- 向后兼容：`ADD_TAINT_DISABLE=1` ⇒ 全链路关闭，全量裁决与 v2.8 逐位一致（AC-9）。
- 层级数值域：`verification_level ∈ {1,2,3,4}`，**不引入 5**（ADR-027 / AC-11）。

### 决策记录

- [ADR-026](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L578)：L5 = 语义/调度层（在 L4 内新增 `taint` 分支，不新建并行管线，不引入 level 5）。
- [ADR-027](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L615)：taint 默认 `downgrade`、`TAINT_CWE_SET` 8 项、字段约束。

### 已知局限（Phase 2 触发条件不变）

- 精确 source 通道在 MVP **仅预留**（两个 SAST 转换器均未保留 taint 路径；CodeQL 需 `path-problem` 规则、Semgrep 需 Pro）。
- 结构化通道 A 在现存 882 条 benchmark 语料上命中为 **0**（`evidence.cwe` 零出现）⇒ 收益待 T12 引入 SAST 转换器语料。
- `analysis_kind` 子条件在 `scripts/**` **零生产者**（Phase 2 预留接入点，不删）。

---

## 2026-08-12 · 文档体系补齐 (架构/决策/流程规范)

### 补齐背景

v2.8 完成 + v3.0+ 路线重新评估后，梳理发现缺失 3 个关键文档：
- 架构文档（架构信息分散在 SKILL.md + ROADMAP.md）
- 关键决策记录（决策分散在 DEVLOG.md + v3-roadmap-reassessment.md）
- spec 规范流程（流程隐式存在于各版本实践中，未文档化）

### 新增文档

| 文档 | 内容 | 来源 |
|------|------|------|
| [ARCHITECTURE.md](file:///f:/Coding/audit-driven-development/docs/ARCHITECTURE.md) | 系统定位、5-Phase 管线、4-Level 验证门、6 步知识闭环、48 脚本层级、数据流、设计约束、Gap 闭合状态 | 整合 SKILL.md + ROADMAP.md + DEVLOG.md |
| [DECISIONS.md](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md) | 25 条 ADR (ADR-001~025) + 4 个待决策事项，覆盖战略定位、路线调整、技术选型、工程约束 | 整合 DEVLOG.md (D1-D4) + v3-roadmap-reassessment.md (D1-D10) + project_memory.md (ADR-018~025) |
| [DEVELOPMENT_WORKFLOW.md](file:///f:/Coding/audit-driven-development/docs/DEVELOPMENT_WORKFLOW.md) | 10 步开发流程规范、幻觉排除方法论、文档一致性检查、版本发布检查、流程适配规则 | 基于 v2.8 实践经验提炼 |

### 关键决策

#### D5: 文档补齐采用并行策略

**决策**: 同时创建 3 个文档，最大化效率。

**理由**: 3 个文档内容相对独立（架构描述、决策索引、流程规范），无强依赖关系，可并行编写。

#### D6: 决策记录采用 ADR 格式

**决策**: 关键决策记录采用 ADR (Architecture Decision Record) 格式，每条含 Status/Context/Decision/Consequences。

**理由**: ADR 格式是业界标准，支持决策追溯和历史演化。维护规则为追加新记录，不修改历史记录（superseded 状态除外）。

#### D7: 开发流程规范为硬性规范

**决策**: DEVELOPMENT_WORKFLOW.md 定义的 10 步流程为硬性规范，所有任务必须遵循。跳步需在 DEVLOG.md 记录原因和影响评估。Step 9 (TDD) 和 Step 10 (验收) 不可跳过。

**理由**: v2.8 实践验证 10 步流程有效（126/126 验收通过），文档化为规范确保后续任务一致执行。

---

## 2026-08-12 · v2.8 Release + v3.0+ Roadmap Reassessment

### v2.8 完成摘要

**6 个短期改进任务 (T1-T6) + 3 个 P3 修复**

| 任务 | 交付物 | 状态 |
|------|--------|------|
| T1: RL threshold 闭环 | `verify_findings.py` `_threshold_to_min_keywords()` 映射 (0.85→2 严格, 0.55→1 宽松) | ✅ |
| T2: GitHub Actions CI | `.github/workflows/add-audit.yml` (Semgrep→ADD verification) | ✅ |
| T3: Semgrep 转换器 | `scripts/semgrep_to_findings.py` | ✅ |
| T4: CodeQL 转换器 | `scripts/codeql_to_findings.py` (SARIF) | ✅ |
| T5: CWE Top 25 映射 | `scripts/cwe_rules.py` + `enrich_finding_with_cwe()` 集成 | ✅ |
| T6: Linux kernel 下载 | `scripts/download_linux_commits.py` (断点续传+重试) | ✅ |
| P3-1: docstring 过时 | `verify_findings.py` docstring 更新 | ✅ |
| P3-2: mock 签名不匹配 | `test_v24_consistency.py` P8C mock lambda `(rr,fp,ln,**kw)` | ✅ |
| P3-3: benchmark 参数透传 | `run_phase8_benchmark.py` `--history-threshold` | ✅ |

**TDD**: 491/491 PASS (v2.4: 153/153, v2.7: 68/68, v2.8: 25/25)
**Benchmark**: P=75.0%, R=85.7%, F1=80.0% (无退化)

### 关键决策

#### D1: ADD 战略定位 = "SAST Findings Validator"（非 SAST Tool）

**背景**: 原框架有 10 个 Gap，其中 G1 (无 Detection) 和 G2 (无 taint) 被标记为致命。

**决策**: v2.8 通过 T3/T4 (Semgrep/CodeQL 转换器) 消费 SAST 工具输出，而非自建 detection 能力。ADD 定位为"SAST findings 的下游验证器"——消费 SAST 输出，用 4-Level 验证门过滤虚假 findings。

**理由**:
1. Semgrep/CodeQL 有 3000+ 条规则，ADD 7 lenses 永远追不上
2. 4-Level 验证门 + Self-evolving rule pipeline 是 ADD 的真正护城河
3. convergence-analysis.md 研究确认：ADD 的价值在"验证"而非"检测"

**影响**: 中期路线取消 T7 (AST pattern detection)，T9 重新定位为"验证 taint"而非"检测 taint"。

#### D2: 中期路线从"补全 Detection"转向"深化 Verification"

**原路线 (v3.0)**: T7 (AST detection) + T8 (自建 import graph) + T9 (检测 taint) + T10 (IDE) + T11 (Java AST CFG) + T12 (benchmark 扩展)

**新路线 (v3.0)**:
- 取消 T7 (违背战略定位)
- T9 重新定位: 检测 taint → 验证 taint (验证 Semgrep/CodeQL 报告的 source→sink 可达性)
- T8 重构: 自建 import graph → 深化 Joern 跨文件验证
- T12 提升优先级: benchmark 规模是验证泛化能力的前提
- T10 降级: IDE 集成非核心护城河

**理由**: v2.8 战略转向后，Detection 不是 ADD 的定位。资源应投入到"如何更精准地过滤虚假 findings"上。

#### D3: 长期路线新增 T17 (Spec-driven Audit) + T18 (Lean4 子集)

**背景**: convergence-analysis.md 研究结论：
- 当前框架在多轮审计下不可达 1 概率收敛 (Rice 定理、Cousot 抽象解释、Fano 不等式)
- 引入 Lean4 后可实现"分层混合收敛"：形式化子集强收敛 (P=R=1, H=0) + 非形式化子集有界收敛
- 用户提供 spec 时，spec 覆盖范围内可达"条件性 1 收敛"

**新增任务**:
- T17: Spec-driven Audit — 用户提供 spec 时，spec 覆盖范围内 P=R=1, H=0
- T18: Lean4 形式化验证子集 — 形式化子集上 P=R=1, H=0

**理由**: convergence-analysis.md 提供了理论支撑，证明这是实现强收敛的唯一路径。

#### D4: T16 (学习闭环 RL) 明确边界

**原定义**: "学习闭环的真实 RL"（无边界，易被理解为模型级 RL）

**新定义**:
- v2.8 T1 已实现"规则级 RL" (threshold→min_keywords 映射驱动 L3 行为)
- "模型级 RL" (调整 LLM 权重) 是远期目标，不在当前框架范围内

**理由**: 避免过度承诺。"规则级 RL"是当前可实现的，"模型级 RL"需要训练基础设施。

### Gap 闭合追踪

| Gap | 原状态 | v2.8 后 | 变化原因 |
|-----|--------|---------|---------|
| G1 无 Detection | 🔴 致命 | ✅ 解决 | T3/T4 消费 SAST 输出 |
| G2 无 taint | 🔴 致命 | 🔴 仍存在 | v3.0 T9' 解决 |
| G3 无 CWE/CVE | 🟠 严重 | 🟡 部分解决 | T5 CWE Top 25 映射 |
| G4 无跨文件 | 🟠 严重 | 🟡 部分缓解 | Joern CPG (Tier 1) |
| G5 语言窄 | 🟠 严重 | 🟡 部分缓解 | v2.7.1 多语言 + v2.8 SAST 多语言 |
| G6 无 IDE | 🟡 中等 | 🟡 仍存在 | v3.0 T10 解决 |
| G7 无 CI/CD | 🟡 中等 | ✅ 解决 | T2 GitHub Actions |
| G8 规则生态 0 | 🟡 中等 | 🟡 仍存在 | v3.5+ T14 解决 |
| G9 Benchmark 小 | 🟡 中等 | 🟡 部分缓解 | T6 Linux kernel + Big-Vul/CVEfixes |
| G10 Loop 展示非决策 | 🟡 中等 | ✅ 解决 | T1 threshold→min_keywords 闭环 |

**总结**: 10 个 Gap 中 4 个已解决，3 个部分缓解，3 个仍存在。致命级 Gap 从 2 个降至 1 个。

### 文档产出

- `docs/RELEASE_NOTES_v2.8.md` — v2.8 发布说明
- `docs/audit-log/2026-08-12-v2.8-acceptance-audit-checklist.md` — 126 项验收清单
- `docs/audit-log/2026-08-12-v2.8-acceptance-audit-report.md` — 验收报告 (126/126 100%)
- `docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md` — 设计 spec
- `docs/superpowers/specs/2026-08-12-v2.8-implementation-spec.md` — 实施 spec
- `docs/audit/2026-08-12-framework-review-and-gap-analysis.md` — 框架 review + Gap 分析
- `docs/research/2026-08-12-convergence-analysis.md` — 1 概率收敛研究 (未推送远程)
- `docs/research/2026-08-12-v3-roadmap-reassessment.md` — v3.0+ 中期/远期改进路线重新评估与风险调研
- `docs/research/2026-08-12-T11-T8prime-feasibility-research.md` — T11 (Java AST CFG) + T8' (Joern 跨文件) 技术可行性调研

### P3 修复的根因发现

**P3-2 根因**: 验收报告原诊断是"Windows Joern 不可用"，实际根因是 mock lambda 签名 `(rr, fp, ln)` 不接受 `language=` 关键字参数，导致 TypeError 被 `except Exception` 捕获，mock 无效。修复为 `(rr, fp, ln, **kw)` 后 v2.4 测试 153/153 PASS。

**教训**: "测试失败"的表面原因 (Windows 平台) 可能掩盖真实根因 (mock 签名)。直接读取代码验证调用链比依赖平台假设更可靠。

---

## 版本历史摘要

| 版本 | 日期 | 核心交付 | TDD |
|------|------|---------|-----|
| v0.1.1 | 2026-07-06 | Iron Law + Spec Gate | — |
| v0.2 | 2026-07-09 | Structured Foundation (JSON schema, spec mining) | — |
| v0.3 | 2026-07-10 | Detection Bootstrap (7 lenses, 94.3% recall) | — |
| v0.4 | 2026-07-11 | Repair Baseline (iterative audit, fix tracking) | — |
| v1.0 | 2026-07-11 | Ecosystem (guards, scoring, cross-project) | 96/96 |
| v2.0 | 2026-07-11 | Knowledge Pipeline (rule_extractor, spec_graph) | — |
| v2.1 | 2026-07-12 | Dual-Track Learning (diff_miner, fix_history) | 29/29 |
| v2.2 | 2026-07-12 | LLM Generalization + Recipe Book | 25/25 |
| v2.3 | 2026-07-12 | External Knowledge + Community | 22/22 |
| v2.4 | 2026-08-05 | CPG Integration (Joern + AST CFG 三层降级) | 66/66 |
| v2.5 | 2026-08-06 | Learning Pipeline Closure (6 步闭环) | — |
| v2.6 | 2026-08-11 | Dataset Integration (687 findings, 3 languages) | — |
| v2.7 | 2026-08-12 | Closure + L4 Multilang (5 断点修复) | — |
| v2.8 | 2026-08-12 | SAST Integration + CWE + RL Threshold | 491/491 |
