# ADD v2.8 Release Notes — RL 闭环深化 + SAST 集成 + CWE 规则映射

> **版本**: v2.8 | **发布日期**: 2026-08-12 | **前置版本**: v2.7 (学习管道闭环修复 + 数据补全 + L4 多语言扩展)
> **TDD**: 490/490 PASS (v2.7 465 + v2.8 25)
> **Spec**: [2026-08-12-v2.8-short-term-improvements.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md)
> **审计追溯**: [2026-08-12-v2.8-spec-audit-trace.md](file:///f:/Coding/audit-driven-development/docs/audit/2026-08-12-v2.8-spec-audit-trace.md)
> **验收 Checklist**: [2026-08-12-v2.8-acceptance-audit-checklist.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-checklist.md)

---

## 概述

v2.8 是 v2.7 学习管道闭环修复后的短期深化：打通 RL threshold → L3 验证行为的最后一公里、引入 SAST 工具 (Semgrep/CodeQL) 作为上游 Detection、新增 CWE Top 25 规则映射、提供 GitHub Actions CI/CD 模板、补全 Linux kernel 批量下载能力。

**战略定位**:
```
ADD ≠ SAST Tool (非 Semgrep/CodeQL 竞品)
ADD = SAST Findings Validator (SAST 工具下游过滤器)
ADD + Spec-driven Audit (额外提供设计-代码契约对齐)
```

v2.8 不试图补全 Detection 能力 (G1 修复难度高)，而是通过消费 Semgrep/CodeQL 输出间接获得 Detection 能力，同时深化 ADD 独有的 Verification Gate。

**核心变化**:
- **T1**: `_history_threshold` 真正驱动 L3 验证 (min_keywords 映射)，修复 v2.7 "dead parameter" 裂缝
- **T2**: GitHub Actions workflow 模板，集成 Semgrep CE + ADD Verification
- **T3**: `semgrep_to_findings.py` Semgrep JSON → ADD findings 转换器
- **T4**: `codeql_to_findings.py` SARIF → ADD findings 转换器
- **T5**: `cwe_rules.py` CWE Top 25 (2023) 规则映射 + `enrich_finding_with_cwe()` 集成
- **T6**: `download_linux_commits.py` 分批 + 断点续传 + 重试机制

---

## 新功能

### T1 — RL Threshold 闭环 (修复 G10 dead parameter)

#### 问题

v2.7 中 `_history_threshold` 仅写入 finding 字段，不驱动任何验证行为 (代码注释自证):
```python
# verify_findings.py L697-L699 (v2.7)
# history_threshold: ... 不影响 L1-L4 验证逻辑本身; 为后续 RL 闭环准备.
```

#### 修复方案

新增 `_threshold_to_min_keywords()` 映射函数，将 threshold 转为 L3 验证的 `min_keywords` 参数:

| threshold | trend | min_keywords | 行为 |
|-----------|-------|--------------|------|
| 0.85 | declining (R 下降) | 2 | 严格模式: L3 需 ≥2 keywords 匹配 |
| 0.55 | improving (R 上升) | 1 | 宽松模式: L3 需 ≥1 keyword (v2.7 行为) |
| None | 无 history | 1 | 向后兼容 (v2.7 默认) |
| ≥0.75 | 边界 | 2 | 严格模式 |

**调用链**: `verify_single_finding()` → `finding.get("_history_threshold")` → `_threshold_to_min_keywords()` → `verify_l3(min_keywords=N)`

**反幻觉检查 (v2.7.3 教训)**:
- ✅ `min_keywords` 在 `verify_l3()` 函数体内被实际使用 (非 dead parameter)
- ✅ `_history_threshold` 字段被读取消费 (非仅写入)
- ✅ `_threshold_to_min_keywords()` 返回值被传入 `verify_l3()` (非 dead call)

### T3 — Semgrep JSON → ADD Findings 转换器

**新建**: `scripts/semgrep_to_findings.py`

**字段映射**:

| Semgrep 字段 | ADD finding 字段 |
|--------------|-----------------|
| `check_id` | `id` (前缀 SG-) |
| `extra.severity` (ERROR/WARNING/INFO) | `severity` (P0/P1/P2) |
| `path` | `evidence.file` |
| `start.line` | `evidence.line_start` |
| `extra.metadata.cwe` (数组) | `evidence.cwe` (取 [0], 提取 CWE-XX) |
| `extra.metadata.owasp` (数组) | `evidence.owasp` (取 [0]) |
| Claim 模板 | `{check_id}: {message} ({cwe}) — affects {path}:{line}` |

**关键设计**:
- `extra.metadata.cwe` 是数组类型 (非字符串)，正确处理避免 TypeError
- ground_truth 标记为 `real_bug_pending_verification` (待 L1-L4 验证)
- T5 集成: 转换后调用 `enrich_finding_with_cwe()` 增强 `cwe_rank` + `cwe_category`

### T4 — CodeQL SARIF → ADD Findings 转换器

**新建**: `scripts/codeql_to_findings.py`

**字段映射**:

| SARIF 字段 | ADD finding 字段 |
|------------|-----------------|
| `ruleId` | `id` (前缀 QL-) + `evidence.rule_id` |
| `level` (error/warning/note) | `severity` (P0/P1/P2) |
| `locations[0].physicalLocation.artifactLocation.uri` | `evidence.file` |
| `locations[0].physicalLocation.region.startLine` | `evidence.line_start` |
| `tool.driver.rules[i].properties.tags` (含 cwe-XX) | `evidence.cwe` (CWE-XX) |
| Claim 模板 | `{ruleId}: {message_text} ({cwe}) — affects {uri}:{startLine}` |

**关键设计**:
- 预构建 `rules_index` (O(n) 一次)，避免 result × rules O(n²) 查找
- SARIF 2.0.0 fallback: `tool.toolComponents[0].rules`
- `properties.tags` 是 CodeQL 约定 (非 SARIF 强制)，缺失时 cwe 为空字符串
- T5 集成: 转换后调用 `enrich_finding_with_cwe()` 增强

### T5 — CWE Top 25 (2023) 规则映射

**新建**: `scripts/cwe_rules.py`

**数据结构**:
```python
CWE_TOP_25_2023 = {
    "CWE-787": {"name": "Out-of-bounds Write",   "rank": 1,  "category": "memory"},
    "CWE-79":  {"name": "XSS",                   "rank": 2,  "category": "web"},
    "CWE-89":  {"name": "SQL Injection",         "rank": 3,  "category": "injection"},
    "CWE-416": {"name": "Use-After-Free",        "rank": 4,  "category": "memory"},
    "CWE-78":  {"name": "OS Command Injection",  "rank": 5,  "category": "injection"},
    "CWE-20":  {"name": "Input Validation",      "rank": 6,  "category": "validation"},
    "CWE-125": {"name": "Out-of-bounds Read",    "rank": 7,  "category": "memory"},
    "CWE-22":  {"name": "Path Traversal",        "rank": 8,  "category": "fs"},
    "CWE-352": {"name": "CSRF",                  "rank": 9,  "category": "web"},
    # ... 共 25 条 (按 MITRE CWE Top 25 (2023) 官方排名)
}
```

**功能函数**:
1. `enrich_finding_with_cwe(finding)`: 从 claim/evidence 提取 CWE-XX，添加 `cwe_rank` + `cwe_category`
2. `classify_cwe_severity(finding)`: 根据 category 调整 severity (memory/injection→P0)
3. `get_cwe_claim_keywords(cwe_id)`: 返回该 CWE 典型关键词 (供 L3 验证可选调用)

**集成点 (spec §2.4.2)**:
- ✅ `semgrep_to_findings.py` 调用 `enrich_finding_with_cwe()`
- ✅ `codeql_to_findings.py` 调用 `enrich_finding_with_cwe()`
- 可选: `verify_findings.py` 的 `extract_keywords()` 调用 `get_cwe_claim_keywords()` (spec 标注可选)

### T2 — GitHub Actions Workflow 模板

**新建**: `.github/workflows/add-audit.yml`

**Workflow 流程**:
1. `actions/checkout@v4` (fetch-depth: 1, 差分扫描优化)
2. `semgrep/semgrep@v1` (迁移自 deprecated `returntocorp/semgrep-action@v1`)
   - config: p/python + p/owasp-top-ten + p/cwe-top-25
3. `python scripts/semgrep_to_findings.py` (转换)
4. `python scripts/verify_findings.py` (L1-L4 验证)
5. `actions/upload-artifact@v4` (上传 verified.json + hallucination_log.json, retention 30 天)

**触发**: push/PR to [main, master]

### T6 — Linux Kernel 批量下载

**修改**: `scripts/download_linux_commits.py`

**新增 CLI 参数**:
- `--batch-size 50`: 每批 50 个 commit
- `--batch-delay 60`: 批次间隔 60s (避免 GitHub API 限流)
- `--retry 3`: 单个 commit 失败重试 3 次
- `--retry-delay 30`: 重试间隔 30s
- `--progress-file`: 断点续传进度文件

**关键设计**:
- 原子写入: `.tmp` + `replace()` 避免文件损坏
- 断点续传: progress.json 记录已下载 commit hash + status
- TDD 使用 mock (不实际下载 Linux kernel)

---

## TDD 测试

**新增**: `scripts/test_v28_consistency.py` (25 tests)

| 测试组 | 编号 | 测试数 | 覆盖任务 |
|--------|------|--------|---------|
| T1 threshold 闭环 | L8.1.1.1-L8.1.1.5 | 5 | T1 |
| T3 Semgrep 转换 | L8.3.1.1-L8.3.1.6 | 6 | T3 |
| T4 CodeQL 转换 | L8.4.1.1-L8.4.1.6 | 6 | T4 |
| T5 CWE 规则 | L8.5.1.1-L8.5.1.5 | 5 | T5 |
| T6 Linux 批量 | L8.6.1.1-L8.6.1.3 | 3 | T6 |
| **总计** | | **25** | |

**回归**: v2.7 的 465 个测试全部通过，v2.8 新增 25 个 → 全量 490/490 PASS

---

## Benchmark 回归

### 基线 (v2.7)

| Benchmark | Findings | TP | FP | FN | TN | Unknown | P% | R% | F1% |
|-----------|---------|----|----|----|----|---------|----|----|-----|
| ADD self-audit | 8 | 5 | 0 | 2 | 1 | 0 | 100.0 | 71.4 | 83.3 |
| Python stdlib | 9 | 8 | 1 | 0 | 0 | 0 | 88.9 | 100.0 | 94.1 |
| itsdangerous 2.2.0 | 10 | 5 | 0 | 1 | 4 | 0 | 100.0 | 83.3 | 90.9 |
| defects4j | 50 | 0 | 1 | 0 | 49 | 0 | 0.0 | 0.0 | 0.0 |
| bigvul | 584 | 0 | 0 | 0 | 113 | 471 | — | — | — |
| cvefixes | 26 | 0 | 4 | 0 | 8 | 14 | 0.0 | 0.0 | 0.0 |
| **Aggregate** | **687** | **18** | **6** | **3** | **175** | **485** | **75.0** | **85.7** | **80.0** |

### v2.8 回归结果

| 模式 | Threshold | P% | R% | F1% | 变化 |
|------|-----------|-----|-----|-----|------|
| default (向后兼容) | None | 75.0 | 85.7 | 80.0 | 与 v2.7 完全一致 |
| improving | 0.55 | 75.0 | 85.7 | 80.0 | min_keywords=1, 行为不变 |
| declining | 0.85 | (P 上升) | R≥75.7 | — | R 下降 ≤10pp (spec §6 风险容忍) |

**关键验证**:
- ✅ BM1: default/improving 模式无退化 (P=75.0%, R=85.7%, F1=80.0%)
- ✅ BM3: threshold=None 时指标与 v2.7 完全一致 (向后兼容)
- ✅ BM4: T3+T4 转换器不破坏现有 benchmark (无 Semgrep/CodeQL 输入时行为不变)
- ⚠️ BM2: declining threshold 模式 R 下降 ≤10pp (风险缓解: 若 >10pp 则调整映射)

---

## 文件清单

### 新增文件

| 文件 | 用途 |
|------|------|
| `scripts/semgrep_to_findings.py` | T3: Semgrep JSON → ADD findings 转换器 |
| `scripts/codeql_to_findings.py` | T4: SARIF → ADD findings 转换器 |
| `scripts/cwe_rules.py` | T5: CWE Top 25 (2023) 规则映射 |
| `scripts/test_v28_consistency.py` | v2.8 TDD 测试 (25 项) |
| `.github/workflows/add-audit.yml` | T2: GitHub Actions workflow |
| `docs/RELEASE_NOTES_v2.8.md` | 本文件 |
| `docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md` | v2.8 设计 spec |
| `docs/superpowers/specs/2026-08-12-v2.8-implementation-spec.md` | v2.8 实施 spec |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `scripts/verify_findings.py` | T1: `_threshold_to_min_keywords()` + `verify_l3(min_keywords=)` + `verify_single_finding()` 传递 threshold |
| `scripts/download_linux_commits.py` | T6: 分批 + 断点续传 + 重试 |
| `README.md` | 版本 2.7→2.8, TDD 465→490 |

---

## 已知风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| T1 threshold=0.85 导致 recall 大幅下降 | 中 | 高 | A/B 测试, 若 R 下降 >10pp 则调整 `_threshold_to_min_keywords` 映射 |
| T3 Semgrep JSON 格式版本差异 | 低 | 中 | 支持多个 Semgrep 版本的字段 fallback |
| T4 SARIF 版本差异 (2.1.0 vs 2.2.0) | 中 | 中 | 支持 2.0.0+ fallback (toolComponents) |
| T6 Linux kernel 网络限流持续 | 高 | 低 | 分批 + 长延迟 + 断点续传, 不阻塞 v2.8 发布 |
| T2 Semgrep Action 版本升级 | 低 | 低 | 使用 `semgrep/semgrep@v1` 主版本 (非 deprecated 的 returntocorp) |

---

## 验收

- ✅ TDD: 490/490 PASS
- ✅ 反幻觉专项: 12/12 通过 (dead parameter/dead code/字段名/闭环)
- ✅ 文档: README.md 更新, RELEASE_NOTES_v2.8.md 创建
- ✅ Benchmark 回归: default/improving 模式无退化

详见: [v2.8 验收审计 Checklist](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-checklist.md)

---

**Release Notes 结束**
