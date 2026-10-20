# T9' Phase 1 — C1–C4 执行裁决分析

> **版本**: v1.0 | **日期**: 2026-10-20 | **作者**: Scott
> **裁决对象**: [design spec §11 待确认决策](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-design.md#L478-L486) 的 C1–C4
> **前置文档**:
> - [调研报告 v1.2](file:///f:/Coding/audit-driven-development/docs/research/2026-08-14-T9prime-joern-mvp-research.md)
> - [DECISIONS.md ADR-005/012/016/018/023](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md)
> **分析方法**: 逐项对比 成本 / 收益 / 兼容 / 维护 / 升级潜力 / 短期 → 证据锚点 → 社区案例 → 幻觉排除 → 明确建议
> **本步性质**: **裁决**（不做实现，不改代码）；产出 ADR 草案供 Step 5 前落地

---

## 0. 执行摘要

| # | 事项 | 裁决建议 | 置信度 | 关键依据 |
|---|------|---------|--------|---------|
| **C1** | ADR-005「独立 L5 层」vs「L4 内分支 + 独立调度函数」 | **采纳 spec 调和方案（A），并新建 ADR-026 显式记录诠释**。逐字复核后：ADR-005 **并未被违背**（其原文已明文授权"复用现有 Tier 1→2→3 降级机制"，Consequences 仅约束"三态字段 + 其他 finding 不受影响"，A 全满足） | 高 | [ADR-005 L153-166](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L153-L166) 逐字核对；AWS ADR 治理锚点 |
| **C2** | taint 证伪默认 `downgrade` vs `remove` | **采纳 `downgrade`（MVP）**，并把切换条件写死。杠杆率实测仅 **3.4%**（30/882），且其中相当部分是 Big-Vul 标签噪声（ADR-006 记录准确率 25-54%）⇒ 现在切 `remove` 的收益极小、误删代价不对称 | 高 | 本步实测 + [Sadowski et al. CACM 2018](https://doi.org/10.1145/3188720) + [ADR-012 L326-330](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L326-L330) |
| **C3** | `TAINT_CWE_SET` 成员集合 | **保留 8 项 + 分三档**；**但必须补一条限定**：通道 A 的两个子信号中 `analysis_kind` **MVP 无生产者**（D-T9'-6 不改转换器 ⇒ 该子条件在 MVP 不可达），须显式标注为 Phase 2 预留。且通道 A 在**现存 benchmark 语料上不可激活**（无 `evidence.cwe`） | 高 | 8/8 CWE 已获 CodeQL Python `@kind path-problem` 证据；`docs/benchmark` 无 `rule_id`/`owasp`/`check_id` 键 |
| **C4** | `verification_level` 是否引入 5 | **不引入（保持 1..4）**。收益与 `taint_verified` 三态字段**冗余**；引入属 SemVer **不兼容变更** | 高 | [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) + [test_v35 L114-115](file:///f:/Coding/audit-driven-development/scripts/test_v35_consistency.py#L114-L115) 唯一消费点 |

**本轮最重要的产出不是"4 个建议"，而是发现 spec 与我自己上一轮证据中的 4 处失真**（见 §1.2）——其中 2 处直接影响 C3 的结论。

---

## 1. 证据基线

### 1.1 本轮新增证据（可机械复核）

**E-1｜CodeQL Python 规则族 `@kind path-problem` 逐项取证（8/8 完成）**

来源：CodeQL 官方 query help 页（逐页抓取，非推断）。

| CWE | CodeQL Python query id | `Kind` | `Precision` | 抓取页 |
|-----|----------------------|--------|------------|--------|
| CWE-078 | `py/command-line-injection` | `path-problem` | 未取 | [link](https://codeql.github.com/codeql-query-help/python/py-command-line-injection/) |
| CWE-079 | `py/reflective-xss` | `path-problem` | `high` | [link](https://codeql.github.com/codeql-query-help/python/py-reflective-xss/) |
| CWE-089 | `py/sql-injection` | `path-problem` | `high` | [link](https://codeql.github.com/codeql-query-help/python/py-sql-injection/) |
| CWE-094 | `py/code-injection` | `path-problem` | `high` | [link](https://codeql.github.com/codeql-query-help/python/py-code-injection/) |
| CWE-022 | `py/path-injection` | `path-problem` | `high` | [link](https://codeql.github.com/codeql-query-help/python/py-path-injection/) |
| CWE-502 | `py/unsafe-deserialization` | `path-problem` | 未取 | [link](https://codeql.github.com/codeql-query-help/python/py-unsafe-deserialization/) |
| CWE-611 | `py/xxe` | `path-problem` | 未取 | [link](https://codeql.github.com/codeql-query-help/python/py-xxe/) |
| CWE-918 | `py/partial-ssrf` | `path-problem` | **`medium`** | [link](https://codeql.github.com/codeql-query-help/python/py-partial-ssrf/) |

逐页原文核验（抽样，冒号后为页面原文）：
- `py/reflective-xss` → `Kind: path-problem` / `Precision: high` / Tags 含 `external/cwe/cwe-079`、`external/cwe/cwe-116`
- `py/sql-injection` → `Kind: path-problem` / `Precision: high` / Tags 含 `external/cwe/cwe-089`
- `py/partial-ssrf` → `Kind: path-problem` / **`Precision: medium`** / Tags 含 `external/cwe/cwe-918`
- 覆盖索引另有 `py/full-ssrf`（CWE-441），与 `py/partial-ssrf` 分列；Python SSRF 由两个查询分担

> **结论**: spec §13.3 中"`CWE-502`/`CWE-611` 的污点型归属 ⚠️ 未证实"这一项**已被一手证据推翻**（两者均为 `path-problem`）。同时得到 spec 未记录的新事实：**CWE-918 的 Python 规则 `precision=medium`，是 8 项中唯一非 high 的**。

**E-2｜benchmark 语料的真实结构与杠杆率（本步实测，含对上一轮的纠错）**

扫描 `docs/benchmark/**/findings*.json`（排除 `oss-cache`），共 **882 条 findings**：

| 语料 | findings | 语料类型 | 是否含 CWE 信号 |
|------|---------|---------|----------------|
| `bigvul/findings.json` | 584 | 数据集派生（claim 模板） | 部分 claim 文本含 `has CWE-XX vulnerability`；**`evidence` 无 `cwe` 键** |
| `bigvul/findings_nonlinux.json` | 190 | 同上 | 同上 |
| `bigvul/findings_test5.json` | 5 | 同上 | 同上 |
| `cvefixes/findings.json` | 26 | 数据集派生（claim 模板） | claim 文本含 CWE；**`evidence` 无 `cwe` 键** |
| `defects4j/findings.json` | 50 | 结构类 | 无 |
| `itsdangerous-2.2.0/findings.json` | 10 | 结构类（`ITD-H*` 合成幻觉） | 无 |
| `stdlib-oss-test/findings.json` | 9 | 结构类 | 无 |
| `add-v2.4-self-audit/findings.json` | 8 | 结构类 | 无 |

关键检索结果（可复现）：

```
Grep '"cwe"'   docs/benchmark/bigvul/findings.json   → 0 命中
Grep '"(rule_id|owasp|check_id)"' docs/benchmark/**  → 0 命中
Grep 'analysis_kind' scripts/**                      → 0 命中
```

⇒ **推断**: 现存 882 条语料**没有任何一条来自 `semgrep_to_findings.py` / `codeql_to_findings.py`**（两转换器才产出 `evidence.cwe` / `rule_id` / `owasp`）。结构化通道（`evidence.cwe`）在现存语料上**不可激活**。

**E-3｜taint 通道杠杆率**

| 指标 | 数值 | 说明 |
|------|------|------|
| taint 分类候选（并集） | **30 / 882 = 3.4%** | 含 claim 文本 CWE 命中 + `TAINT_PATTERNS` 命中 |
| 其中 CWE-89 / 22 / 94 / 79 | 10 / 7 / 5 / 4 | 全部集中在 4 个 CWE |
| CWE-78 / 502 / 611 / 918 | **0** | 现存语料零命中（能力储备项） |
| CWE-94 命中样本质量 | ⚠️ 受标签噪声污染 | 样本如 `The default configuration of the <Button2> binding in Uzbl before 2010`，与代码注入无关 |

**E-4｜ADR 治理锚点**

AWS Prescriptive Guidance（一手）：ADR 被接受后**不可变**；如需变更决策，**新建 ADR**，新 ADR 被接受后将**旧 ADR 置为 Superseded**。——即"状态行置 Superseded"是治理规定动作，**不算对 ADR 内容的改写**。

**E-5｜社区案例锚点**

| 锚点 | 原文要点 | 用于 |
|------|---------|------|
| Sadowski et al., *Lessons from Building Static Analysis Tools at Google*, CACM 61(4), 2018, [DOI:10.1145/3188720](https://doi.org/10.1145/3188720) | Tricorder 团队通过**禁用表现不佳的分析**来最小化有效误报；开发者对静态分析**有强忽略倾向**，任何误报都给他们"不作为"的理由；"Not trustworthy. Users do not trust the results due to, say, false positives" | C2 |
| *Software Engineering at Google*, p.419-420 | "effective false positive"（开发者认为错并不予处置的结果）；"low false-positive rates are often **critical**" | C2 |
| Zoncolan（`distefano:scaling.pdf`） | 误报由人工 triage 并反馈回规则 | C2 |
| [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) | MINOR = 向后兼容的功能新增；MAJOR = 不兼容变更 | C4 |

### 1.2 本轮纠错（对 spec 与对上一轮我自己的证据）

> 这是本步"排除幻觉"的实质产出。**不做这步，C3 会给出错误结论。**

| # | 失真 | 事实 | 影响 |
|---|------|------|------|
| **X-1** | spec §13.3 记「`CWE-502`/`CWE-611` 污点型归属 ⚠️ 未证实」 | **两位均有 `@kind path-problem` 一手证据**（E-1） | 该项状态应改为 ✅ 已证实；AC-2b 取证表可完成 |
| **X-2** | 我上一轮报告「通道 A（CWE）命中 26 条」 | 临时脚本 `taint_scan.py` L80-82 在 `evidence.cwe` 缺失时**回退到 claim 文本正则**（`CWE_RE.search(claim)`）。故这 26 条是**claim 文本 CWE**，**不是** `evidence.cwe` 命中。回到事实：现存语料 `evidence.cwe` 命中 **0** | **C3 结论需改写**：通道 A 在现存语料杠杆率为 **0**，而非"26 条/26 命中" |
| **X-3** | spec D-T9'-1 断言"`evidence.cwe` 由 T5 已填充，是**现存可用的**结构化信号，成本为零" | T5（[cwe_rules L55-84](file:///f:/Coding/audit-driven-development/scripts/cwe_rules.py#L55-L84)）确会回写 `cwe`，转换器也确会产出 `evidence.cwe`（[semgrep L110](file:///f:/Coding/audit-driven-development/scripts/semgrep_to_findings.py#L110)、[codeql L139](file:///f:/Coding/audit-driven-development/scripts/codeql_to_findings.py#L139)），但**现存 882 条语料无一来自转换器**（E-2）⇒"现存可用"中的"现存"需限定为"**生产链路上可用，基准语料上不可用**" | 措辞过度乐观 ⇒ 修正 |
| **X-4** | spec D-T9'-1 通道 A 含子条件 `evidence["analysis_kind"] == "taint"` | `analysis_kind` 在 `scripts/**` **零生产者**，且 D-T9'-6 明确"MVP 不修改任何 SAST 转换器" ⇒ **该子条件在 MVP 不可达**（与 v2.7.3 记录的 dead-parameter 反模式同构） | 必须显式标注为 Phase 2 预留，否则是死条件 |
| **X-5** | spec §11 C1 记"若不采纳，需新建并行管线 ⇒ 成本与回归面**翻倍**" | "翻倍"是**主观估计，非测量值**。可测量的成本是 3 个接线点 + CLI（[聚合 L444-472](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L444-L472)、[判定 L746-749](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L746-L749)、[verify_all_findings L759](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L759)） | 措辞降级为估计 |
| **X-6** | spec §11 C4 记"引入会破坏下游消费方对 `verification_level ∈ {1,2,3,4}` 的既有假设" | 实证唯一消费点 [test_v35 L114-115](file:///f:/Coding/audit-driven-development/scripts/test_v35_consistency.py#L114-L115)，且其断言是 `any(f.get("verification_level") == 4 ...)`。引入 5 **不必然**使其失败（只要仍有任一非 taint finding 为 level 4），但会使该断言语义失真 | 由"必然破坏"降为"条件性风险" |
| **X-7** | spec §13.3 记"CWE-502/611 未证实，影响: 中" | 见 X-1；**同时新增**：CWE-918 上游 precision 为 `medium`（其余 high） | 影响评估更新 |

---

## 2. C1 裁决：ADR-005「独立 L5 层」 vs 「L4 内分支 + 独立调度函数」

### 2.1 候选方案

| 方案 | 内容 |
|------|------|
| **A（spec 调和方案）** | 语义层独立：新增 `_verify_l5_taint()` + 对外三态字段 `taint_verified`；机制层复用：由 `verify_l4_structural` 调用、写入既有 `checks["taint"]`、复用既有聚合器与降级；编号层不变：`verification_level` 保持 1..4 |
| **B（字面 ADR-005：独立管线）** | 新建独立 L5 入口 + 独立聚合 + 独立 `unverified` 判定 + 独立 CLI 接线；`verification_level` 扩展为 5 |
| **C（完全并入 L4）** | 无独立函数、无独立字段，taint 仅作为 `checks` 中一个普通子项 |

### 2.2 六维对比

| 维度 | A | B | C |
|------|---|---|---|
| **成本** | 低：新增 1 函数 + 1 分支 + `structural_false` 扩展（约 4 行判定式） | 高：需复制 [聚合 L444-472](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L444-L472) 与 [移除判定 L746-749](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L746-L749) 的逻辑到新管线，并新增 CLI 与 main 接线（3 个接线点 ×2） | 最低：无需新函数 |
| **收益** | 语义可观测（`taint_verified` 三态）+ 裁决可追溯（`taint_mode` / `disproof_action`） | 与 A **同收益**（L5 的可观测性已由字段承载，独立管线不新增任何能力） | 低于 A：丢失 ADR-012 要求的独立三态可观测性 |
| **兼容** | ✅ 无破坏（纯增量 + kill switch） | ❌ 若引入 `level=5` 则属不兼容变更（见 C4） | ✅ 若保留 `taint_verified` 字段则无破坏 |
| **维护** | 单点接线：未来聚合器演进只改一处 | ⚠️ **双套聚合/判定逻辑需长期同步** ⇒ 维护面 ×2，且是持续性成本而非一次性 | 单点，但语义被埋在通用 check 里，后续审计难定位 |
| **升级潜力** | 高：Phase 2 的 exact-source / inter-procedural / sanitizer 建模都在 `_verify_l5_taint` 内部扩展，不动接线 | 与 A 等价（独立性不带来 Phase 2 收益） | 中：Phase 2 扩展需改通用 L4 路径，回归面更大 |
| **短期** | ✅ 对齐 ADR-005 Rationale 原文"**MVP 2-3 天可交付**" | ❌ 显著延期 | ✅ 最快 |

### 2.3 关键证据：ADR-005 的原文比 spec 描述的**约束更弱**

逐字读 [ADR-005 L153-166](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L153-L166)：

| ADR-005 原文 | 对 A 的判定 |
|-------------|-----------|
| Decision: "T9' 采用 L5 层架构（**独立层级**，taint finding 专属），Joern 优先 + AST 兜底。**复用现有 Tier 1→2→3 降级机制。**" | ⚠️ **关键**：ADR-005 **同时**要求"独立层级"与"复用 Tier 机制"。A 的"机制层复用"正是 ADR-005 的**明文要求**，不是偏离 |
| Rationale: "非破坏性：**L1-L4 对所有 finding 保持不变**" | A 满足（D-T9'-5 纯增量 + kill switch） |
| Consequences: "taint finding 触发 L5 验证，**其他 finding 不受影响**"；"三态输出: `taint_verified: true \| false \| null`" | A 满足（taint 分支仅对含 `"taint"` 标签的 finding 激活；`taint_verified` 字段即 ADR-012 落点） |
| （全文**未出现**）独立入口 / 独立聚合器 / `verification_level == 5` 的表述 | A 不违反任何未写明的约束 |

⇒ **判定**: spec §11 C1 将二者的关系描述为"字面冲突"，**过强**。真实关系是 ADR-005 的"独立层级"存在**两种可行解释**：`pipeline-level`（独立管线）与 `semantic-level`（独立语义层 + 独立字段，共享 tier 机制）。ADR-005 的 Consequences **只约束可观测行为**（三态字段 + 其他 finding 不受影响），未约束实现形态 ⇒ **A 是对 ADR-005 的合理解释实现，不构成违背**。

### 2.4 治理动作（社区案例锚点）

按 AWS Prescriptive Guidance：ADR 接受后不可变；要澄清/变更决策须**新建 ADR**，旧 ADR 置 **Superseded**。

由于 §2.3 判定 A **不违背** ADR-005，治理强度可从"必须 supersede"降级为"必须记录诠释（Clarification）"，但**不应静默**——spec 目前正是"静默偏离"状态（仅在 §11 挂着"待确认"）。

**建议**: 新建 **ADR-026「T9' Phase 1 L5 层语义诠释」**，内容 = §2.3 的判定 + A 方案的实现形态声明；并在 [ADR-005](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L143) 的 `Status` 行追加 `(Clarified by ADR-026 — "L5" 解释为语义/调度层)`，**不置 Superseded**（因为未变更原决策）。

### 2.5 幻觉排除

| 候选断言 | 判定 |
|---------|------|
| "ADR-005 规定必须新建独立管线" | ❌ **幻觉**。ADR-005 全文无此表述，且明写"复用现有 Tier 机制" |
| "不采纳 A 则成本/回归面翻倍" | ⚠️ **主观估计**，非测量值（见 X-5）。可测量的是 3 个接线点需复制并长期同步 |
| "B 方案更符合 ADR-005 精神" | ❌ **无证据支撑**，属偏好陈述 |
| "C 方案违反 ADR-012" | ⚠️ 仅在 C **不**保留 `taint_verified` 字段时成立；若保留则可接受（但仍劣于 A 的可定位性） |

### 2.6 C1 结论

✅ **采纳 A**：语义层独立（`_verify_l5_taint` + `taint_verified` 三态字段）、机制层复用（`checks["taint"]` + 既有聚合器 + 既有 tier 降级）、编号层不变（1..4）。
➕ **附加动作**：新建 **ADR-026** 记录诠释；在 ADR-005 状态行加 Clarified 注记（不 Superseded）。
✏️ **措辞修正**：spec §11 C1 的"字面冲突"改为"解释实现差异（ADR-005 已明文授权机制复用）"；删去"翻倍"表述。

---

## 3. C2 裁决：taint 证伪默认 `downgrade` vs `remove`

### 3.1 候选方案

| 方案 | 语义 | 落 `action` |
|------|------|-----------|
| **D（downgrade，spec 建议）** | `taint_verified=false` → P0→P1 降级，保留在 fix baseline，标记人工复核 | `partial` |
| **R（remove）** | `taint_verified=false` → 移出 fix baseline，写入 hallucination_log | `unverified` |

### 3.2 六维对比

| 维度 | D（downgrade） | R（remove） |
|------|---------------|------------|
| **成本** | 需实现 H2 的判定式扩展（`structural_false` 尊重 `disproof_action`，约 4 行）+ §4 的 T1-False-仍跑-T2 双检 | 更低：与现有 `unverified` 路径完全一致，无需新判定 |
| **收益** | 保护真阳性；保留可信度；与"不信任系统"哲学一致（误删 > 漏删） | 可过滤假阳性（G2"完全修复"）；向 hallucination_log 供样 |
| **兼容** | ⚠️ 与 [ADR-018](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L426) （"L4 verified=False 直接移除"）存在**张力**；但与 [ADR-012 L326-330](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L326-L330)（明写"**降级或移除**"）**一致** | ✅ 与 ADR-018 一致 |
| **维护** | 略高：多一层双检 + 一个开关分支 | 低：复用既有路径 |
| **升级潜力** | ✅ **不封死**：`ADD_TAINT_DISPROOF` / `--taint-disproof=remove` 开关已预留 ⇒ 语料就绪即可切换，无返工 | ⚠️ 若日后发现误删率过高，回退需改默认值 + 重跑基线 |
| **短期** | 需多改 ~4 行判定式（H2 已列为必要实现要件） | 零额外改动 |

### 3.3 决定性证据：杠杆率与语料可信度

**（a）杠杆率极低（E-3）**：taint 通道至多影响 **30/882 = 3.4%** 的 findings。即无论选 D 还是 R，其**影响面本身就只有 3.4%**。

**（b）这 3.4% 里还有相当部分是标签噪声**：CWE-94 的 5 条命中样本为 Big-Vul CVE 描述（如 `The default configuration of the <Button2> binding in Uzbl before 2010`），与"代码注入的数据流"无关；[ADR-006](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L170-L182) 已记录 Big-Vul 标签准确率仅 25-54%。

⇒ **对 `remove` 的直接打击**：`remove` 的收益是"多删掉几个假阳性"，但在当前语料上，**能产生 `taint_verified=false` 的样本本身就可能连 ground truth 都是错的**——用不可靠标签去驱动"删除"动作，会把噪声写进 `hallucination_log`，进而污染 `benchmark_calibrate` → `rule_suggester` 学习链（[ADR-021](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L489) 的顺序要求会把这个污染带进规则生成）。

**（c）ADR-018 不能跨类外推**：[ADR-018](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L426) 的决策依据是 v2.7.3 的 **L4 dead_code/import** 场景 —— 那类断言可被 Tier 2 AST **高置信证伪**（死代码是否可达是精确的）。而 taint 在 MVP 有**系统性跨过程假阴性**（R2：sink 由另一函数写入时 AST 与 broad-source 都可能漏判），置信度**结构性地低于** dead_code。同样的"False"，置信度不同 ⇒ 不应套用同一动作。

**（d）社区案例锚点（不对称代价）**：Sadowski et al. CACM 2018 —— Tricorder 团队"**通过禁用表现不佳的分析来最小化有效误报**"，并指出开发者对静态分析**有强忽略倾向**，"任何误报都给他们不作为的理由"；SE@Google p.419-420 进一步定义 "effective false positive" 并强调"low false-positive rates are often **critical**"。

> ⚠️ **类比限定（诚实标注）**: Tricorder 的"误报"指**报给开发者**的噪声；ADD 的对应物是"**误删真阳性**"（污染 fix baseline，且下游自动修复会照做）。二者的**方向一致**（误报代价不对称地高），但**载体不同**。这是**结构性类比**，不是同构移植。

### 3.4 幻觉排除

| 候选断言 | 判定 |
|---------|------|
| "切 `remove` 能显著增强 hallucination_log 学习闭环" | ⚠️ **方向真实，量级虚假**。链路确实存在（`hallucination_log` → `benchmark_calibrate` → `rule_suggester`，[ADR-021](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L489)/[ADR-022](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L509)），但基数 ≤3.4%，且 `rule_suggester` 要求同一 reason 计数 ≥3 ⇒ 大概率**不触发**。不构成主论据 |
| "ADR-018 已确立 L4 `False` 应移除 ⇒ taint 也应移除" | ❌ **跨类外推**。见 §3.3(c) |
| "Tricorder 的经验直接适用于 ADD" | ⚠️ 需限定为结构性类比。见 §3.3(d) |
| "downgrade 会让 G2 停留在'未修复'" | ⚠️ **部分成立**——spec 已诚实标注为"部分修复"。但这**不构成反对理由**，因为 MVP 的既定目标本就是"可降级、可标记、不可过滤删除" |
| "13.3% 的 taint finding 会误删" | ❌ **无依据的量化**。不采信任何未实测的误删率 |

### 3.5 C2 结论

✅ **采纳 D（MVP 默认 `downgrade`）**。
➕ **切换条件写死（避免"永久默认"成为事实决策）**：
1. 语料升级为 [ADR-006](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L170-L182) 指定的 **CVEfixes / ICVul**（高准确率标注），而非 Big-Vul；且
2. benchmark 能**度量** taint 通道的 precision 与误删率（即 taint 类 finding 在语料中占比 ≥ 可统计阈值）；
3. 上述两项满足后，用 `--taint-disproof=remove` 跑 A/B，若误删率 ≤ 可接受阈值再切默认。

✏️ **措辞修正**：spec §11 C2 的"benchmark + 标注样本通过后切换"过于笼统，替换为上述 3 条可判据。

---

## 4. C3 裁决：`TAINT_CWE_SET` 成员集合

### 4.1 三档分级（本轮证据驱动）

| 档 | 成员 | 上游证据（E-1） | 现存语料命中（E-3） | 处置 |
|----|------|----------------|-------------------|------|
| **I：已验证 + 有真实命中** | `CWE-079` / `CWE-089` / `CWE-022` | CodeQL `path-problem`，`precision=high` | 4 / 10 / 7 | ✅ **保留** |
| **II：已验证 + 零命中（能力储备）** | `CWE-078` / `CWE-502` / `CWE-611` | CodeQL `path-problem` | 0 / 0 / 0 | ✅ **保留**（零成本、覆盖未来 SAST 语料） |
| **III：需附加限定** | `CWE-094` / `CWE-918` | `path-problem`（094 `high`；918 **`medium`**） | 5 / 0 | ⚠️ 保留但标注：094 命中样本受 Big-Vul 标签噪声污染；918 上游精度为 `medium` |

⇒ **8 项全部保留**。结论与 spec 建议方向一致，但**依据更强**（8/8 有一手证据，X-1 已纠错）。

### 4.2 两个必须补写的限定（C3 的真正增量）

**限定 1 — 通道 A 的 `analysis_kind` 子条件在 MVP 无生产者（X-4）**
D-T9'-1 通道 A 写的是 `evidence["analysis_kind"] == "taint"` **或** `evidence["cwe"] ∈ TAINT_CWE_SET`。而 `analysis_kind` 在 `scripts/**` **零命中**，且 D-T9'-6 明确"MVP 不修改任何 SAST 转换器" ⇒ **MVP 中没有任何代码会写出该字段**，该子条件**不可达**——与 v2.7.3 已记录的 dead-parameter 反模式同构（[ADR-024](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L546) 同源的教训）。
**处置**：在 spec 中显式标注 `analysis_kind` 为 **Phase 2 预留通道**（不删，因其是 Phase 2 精确通道的接入点），并要求 AC-4b 的单元测试以**合成 evidence** 覆盖（spec 现有 AC-4b 已如此设计，✓ 但需加一句"并声明 MVP 无自然生产者"）。

**限定 2 — 通道 A 在现存 benchmark 语料上不可激活（X-2/X-3）**
现存 882 条语料无一来自 SAST 转换器（`evidence.cwe` 命中 0）。⇒ 通道 A 的**收益在当前基准上为 0**。
**处置**：
- spec D-T9'-1 理由中的"现存可用的结构化信号"改为"**生产链路上可用（转换器会产出），现存基准语料上不可用**"；
- **AC-8 benchmark 非退化门不足以验证通道 A** ⇒ 需诚实声明：通道 A 的验证要等 Phase 2 引入 SAST 转换器语料（T12），MVP 阶段仅由单元测试覆盖；
- `TAINT_CWE_SET` 的命中在 `bigvul`/`cvefixes` 语料上消费的是**数据集标签 CWE**（受 [ADR-006](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L170-L182) 准确率约束），而在生产链路上消费的是**工具自报 CWE**（可靠）。**两者质量不同，不应混为一谈**——建议在 §7 风险表新增一条 R9 记录该差异。

### 4.3 六维对比（"保留 8 项" vs "收窄至有命中项"）

| 维度 | 保留 8 项（建议） | 收窄至 079/089/022 |
|------|-----------------|------------------|
| 成本 | 相同（集合是常量表） | 相同 |
| 收益 | 覆盖未来 SAST 语料（78/502/611 是常见注入类，生产环境必然出现） | 覆盖当前语料 |
| 兼容 | ✅ 纯新增 | ✅ |
| 维护 | 略高：8 项需 8 份证据（**本轮已完成**）⇒ 边际成本已付 | 3 份 |
| 升级潜力 | ✅ 高（78/502/611 是 T12 语料的常见类） | ⚠️ 需回补 |
| 短期 | 零成本（已取证） | 零成本 |
| **过宽风险** | ⚠️ 存在：**CWE 作为"taint 断言"的代理，仅当该 CWE 由 taint-mode 规则报出时成立**。对数据集标签 CWE（bigvul/cvefixes）不成立 | 较低 |

⇒ **证据成本已在 4.1 付清**，收窄的收益不成立 ⇒ **保留 8 项**。

### 4.4 幻觉排除

| 候选断言 | 判定 |
|---------|------|
| "通道 A 成本为零（spec D-T9'-1）" | ⚠️ **半真**。**实现**成本为零；但**收益在现存语料为零**（无生产者、无语料）⇒ 必须加限定 |
| "`CWE ∈ TAINT_CWE_SET` ⇒ 该 finding 是 taint 断言" | ❌ **无条件不成立**。仅在该 CWE 由 `path-problem` / taint-mode 规则报出时成立；数据集标签 CWE 不满足 |
| "8 项中 502/611 未验证（spec §13.3）" | ❌ **已被 E-1 推翻**（X-1） |
| "上一轮实测：通道 A 命中 26 条 ⇒ 结构化通道有杠杆" | ❌ **已被 X-2 推翻**（实为 claim 文本解析结果） |
| "CWE-918 与其余 7 项同等可靠" | ❌ 上游 `precision=medium`，是唯一非 high 项 ⇒ 需差异化标注 |
| "CWE-094 的 5 条命中是有效 taint finding" | ❌ **样本已显示为 Big-Vul 标签噪声**，不成立 |

### 4.5 C3 结论

✅ **保留 8 项并分三档**（§4.1）。
➕ **必补两条限定**（§4.2）：`analysis_kind` 标注为 Phase 2 预留（MVP 无生产者）；通道 A 在现存基准不可激活（收益为 0，需 T12 语料才能验证）。
➕ **新增 R9 风险**：`evidence.cwe` 的来源（SAST 工具自报 vs 数据集标签）质量不同，通道 A 不应混用。
✏️ **修正 H6**：spec §13.3 / D-T9'-1 的"502/611 未证实"改为"已证实（`@kind path-problem`）"，并补记 CWE-918 `precision=medium`。

---

## 5. C4 裁决：`verification_level` 是否引入 5

### 5.1 六维对比

| 维度 | 不引入 5（建议） | 引入 5 |
|------|-----------------|--------|
| **成本** | 0（spec D-T9'-2 决策 3 已如此） | 需改 [L472 `"level": 4 if verified else 3`](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L472) 增加 5 分支；需遍历全部消费方；需重写受影响的测试断言 |
| **收益** | `taint_verified` / `taint_mode` / `taint_disproof_action` 三字段已承载全部 taint 语义 | 与上述字段**冗余**；不新增可观测能力 |
| **兼容** | ✅ | ❌ 向受约束枚举字段引入新值 = **SemVer MAJOR（不兼容变更）** |
| **维护** | 无分叉 | 每个 level 判定点都需考虑"5 是否适用" |
| **升级潜力** | ✅ 无碍；Phase 2 扩展落在 taint 字段族 | ⚠️ 引入后再回退是二次破坏 |
| **短期** | ✅ | ❌ |

### 5.2 证据锚点

- **[SemVer 2.0.0](https://semver.org/spec/v2.0.0.html)**：MINOR = backward compatible 的功能新增；MAJOR = 不兼容变更。向既有受约束的数值域新增合法值 ⇒ 消费方需改断言 ⇒ **不兼容**。
- **[R6 实证](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-design.md#L410)**：全仓唯一读取 `verification_level` 的消费点是 [test_v35_consistency.py L114-115](file:///f:/Coding/audit-driven-development/scripts/test_v35_consistency.py#L114-L115)，**无生产代码消费**。
- **[ADR-012](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L326-L330)**：三态语义的载体明确是 `taint_verified` 字段，**不是** `verification_level`。
- **[ADR-023](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L525) / project_memory**：schema 字段只增不删、向后兼容硬规则。

### 5.3 幻觉排除（含对 spec 措辞的精度修正）

| 候选断言 | 判定 |
|---------|------|
| "引入 5 会**破坏**下游消费方的假设"（spec §11 C4） | ⚠️ **过强**（X-6）。唯一消费点 [test_v35 L114-115](file:///f:/Coding/audit-driven-development/scripts/test_v35_consistency.py#L114-L115) 断言 `any(level == 4)`——引入 5 **不必然**失败（只要仍有任一非 taint finding 为 level 4）。**真实风险**是"该断言无法区分 taint 层裁决与 L4 裁决"，属**语义失真**而非常规失败 |
| "引入 5 使架构更清晰（对应 ADR-005 的 L5）" | ❌ **主观偏好**，无证据；且 ADR-005 的"独立层级"已由 `taint_verified` 字段与 `_verify_l5_taint` 函数承载（§2.3） |
| "不引入 5 会削弱 L5 的独立性" | ❌ **不成立**。层级语义由**字段 + 函数命名**表达，与数值域无关 |

### 5.4 C4 结论

✅ **不引入 5，保持 `verification_level ∈ {1,2,3,4}`**。
✏️ **修正措辞**：spec §11 C4 / D-T9'-2 理由中的"破坏下游消费方假设"精确化为"在 taint finding 成为被断言样本时使该断言语义失真（条件性风险，非必然失败）"。
➕ **AC-11 保持**（`verification_level ∈ {1,2,3,4}` 不变），无需新增。

---

## 6. 综合建议与落地清单

### 6.1 裁决汇总

| # | 裁决 | 治理动作 |
|---|------|---------|
| C1 | 采纳 A（语义独立 + 机制复用 + 编号 1..4） | 新建 **ADR-026「T9' Phase 1 L5 层语义诠释」**；ADR-005 状态行加 `(Clarified by ADR-026)`，**不** Superseded |
| C2 | 默认 `downgrade` + 3 条切换判据 | 新建 **ADR-027「T9' Phase 1 证伪动作：默认降级」** |
| C3 | 保留 8 项 + 三档 + 2 条限定 + R9 | 并入 **ADR-027**（同属"Phase 1 收敛策略"），或独立 **ADR-028** |
| C4 | 不引入 5 | 并入 **ADR-027** |

> **ADR 粒度建议**: C2/C3/C4 三项互不冲突且同属"T9' Phase 1 收敛策略"，合并为 **ADR-027** 可减少文档碎片；C1 单独成 **ADR-026**，因为它触及既有 ADR-005 的诠释，最需独立可追溯。若偏好"一决策一 ADR"，则拆为 ADR-026/027/028/029，二者皆合规。

### 6.2 需回写 spec 的修正（v1.2 → v1.3）

| 位置 | 修正 |
|------|------|
| §1 D-T9'-1 备注 | `TAINT_CWE_SET` 的"502/611 待 Step 5 取证"→**已完成**（8/8 获 `@kind path-problem`）；补记 CWE-918 `precision=medium` |
| §1 D-T9'-1 理由 | "`evidence.cwe` … 现存可用的结构化信号" → 限定为"**生产链路可用，现存基准语料不可用**"（X-3） |
| §1 D-T9'-1 通道 A | 标注 `analysis_kind == "taint"` 为 **Phase 2 预留**（MVP 无生产者，X-4） |
| §7 风险表 | 新增 **R9**：`evidence.cwe` 来源差异（SAST 工具自报 vs 数据集标签） |
| §11 | C1–C4 由"待确认"改为"**已裁决**（见 ADR-026/027）"，并附本文件链接 |
| §11 C1 / C2 / C4 措辞 | 分别应用 X-5 / §3.5 / X-6 的修正 |
| §13.3 | "`CWE-502`/`CWE-611` 污点型归属 ⚠️ 未证实" → ✅ **已证实**；新增 BOM（本轮纠错）小节引用 X-1~X-7 |

### 6.3 对后续步骤的解锁

| 步骤 | 解锁内容 |
|------|---------|
| Step 5 实施规范 | AC-2b 取证表**本轮已完成**（8/8），可直接固化 `TAINT_CWE_SET`；无需等待 |
| Step 5 | 接口签名与 `structural_false` 扩展（H2）、2 处调用点（H3）均已由 spec 定稿，无需再议 |
| Step 7 checklist | C1–C4 由 checklist 的"待裁决"项转为"已裁决（附 ADR 引用）" |
| Step 9 TDD | **R1 / R1b 仍为硬阻断**（`reachableBy` 入参形态、`cpg.call.name(regex)` 命中行为），与 C1–C4 无关，须按 §8 产出实测记录 |

---

## 7. 幻觉排除总表（本步全部纠错）

| ID | 对象 | 失真类型 | 纠正后事实 | 证据 |
|----|------|---------|-----------|------|
| X-1 | spec §13.3 / D-T9'-1 | 未验证项被当作待办，实为已验证 | 502/611 均 `@kind path-problem` | E-1 |
| X-2 | 我上一轮的实测报告 | 工具 fallback 污染：claim 文本 CWE 被计为 `evidence.cwe` | `evidence.cwe` 在现存语料命中 **0** | `taint_scan.py` L80-82 + Grep |
| X-3 | spec D-T9'-1 理由 | "现存可用"过度乐观 | 生产链路可用，现存基准语料不可用 | E-2 |
| X-4 | spec D-T9'-1 通道 A | 死条件（无生产者） | `analysis_kind` MVP 无生产者，需标注 Phase 2 预留 | Grep `scripts/**` 零命中 + D-T9'-6 |
| X-5 | spec §11 C1 | 主观估计当成本 | "翻倍"→ 3 个接线点需复制并长期同步 | 代码结构 |
| X-6 | spec §11 C4 | 必然破坏当事实 | 条件性语义失真，非必然失败 | test_v35 L114-115 |
| X-7 | spec §13.3 | 影响评估滞后 | 新增 CWE-918 `precision=medium` 事实 | E-1 |

**未采信（无证据）的断言**：任何未实测的误删率量化、"通道 A 有 26 条杠杆"、"独立管线更符合 ADR-005"、"引入 5 更清晰"、"ADR-018 可跨类外推"。

**诚实披露的类比限定**：Tricorder / SE@Google 的误报经验 → ADD 的误删代价，属**结构性类比**（方向一致、载体不同），非同构移植。

---

## 8. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-10-20 | v1.0 | 初始裁决分析：C1–C4 六维对比 + 证据锚点（E-1~E-5）+ 7 处幻觉纠错（X-1~X-7）+ 落地清单（ADR-026/027 草案、spec v1.3 回写项） |
