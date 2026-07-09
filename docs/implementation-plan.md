# Implementation Plan / 执行方案

> **Target**: v0.3 → v0.4 → v0.5，基于整合后 ROADMAP.md 的 10 项 P2/P3 升级。
> 每项均给出工程实现细节、兼容性分析、可操作性描述。

---

## 1. Overview / 总览

### 1.1 版本-功能矩阵

| Version | Items | 新增文件 | 修改文件 | 新增 Skill 能力 |
|---|---|---|---|---|
| v0.3 | P2.9, P2.8' | `docs/benchmark/`, `scripts/audit_lens.py` | SKILL.md (Lens section) | 基准测试能力 + 透镜分级审查 |
| v0.4 | P2.10, P2.7, P2.11, P2.12 | `scripts/audit_files.py`, `scripts/verify_lines.py`, `scripts/rule_index.py`, `scripts/issues_tracker.py` | SKILL.md (Deterministic, Inter-rater, Iterative, Verify sections) | 确定性辅助 + 双投票 + 迭代审查 + 修复追踪 |
| v0.5 | P3.1, P3.2, P3.3 | `docs/audit/guards.template.yml`, `scripts/merge_guards.py`, `scripts/score_tracker.py` | SKILL.md (Guards, Scoring, Reuse sections) | 语义守卫 + 量化评分 + 跨项目复用 |

### 1.2 依赖图

```
P1.6 (JSON Schema) ──┬──→ P2.9 (benchmark) ──→ Gate: recall >70% (Tier A), avg >60%? ──→ P2.8' (lens)
                     │                                                        │
                     ├──→ P2.10 (deterministic) ←────────────────────────────┘
                     │        │
                     ├──→ P2.12 (fix tracking) ←── P2.11 (iterative)
                     │        │
                     └──→ P2.7 (inter-rater) ──→ depends on P2.8' lens types
                              │
                    P3.1 (guards) ──→ P3.3 (cross-project reuse)
                    P3.2 (scoring) ──→ depends on P2.12 issues.json data
```

**关键门控**: P2.9 (OSS benchmark) 是最高优先级 P2 项。分级阈值：Tier A recall >70% AND 平均 >60% → 通过；Tier A 50-70% OR 平均 40-60% → 暂停优化 prompt 后重测；Tier A <50% → 重新审视方案。见 ROADMAP §Ecosystem Validation Strategy。

---

## 2. v0.3 Implementation / 实施细节

### 2.1 P2.9 — OSS Benchmark

#### 目标
建立 ADD 技能的可量化检出基准。选 3 个已知 bug 历史的 OSS 项目，运行审计，计算 recall/precision。

#### 工程实现

**新增文件**:
```
docs/benchmark/
├── README.md                  (benchmark methodology + results summary)
├── candidates.md              (OSS project candidate pool + selection criteria)
└── <project>-<version>/
    ├── metadata.json          (project info, buggy commit, known bugs list)
    ├── audit-output.json      (AuditReport per P1.6 schema)
    └── benchmark-result.json  (recall/precision/prioritization scores)
```

**metadata.json schema**:
```json
{
  "project": "pillow",
  "repo_url": "https://github.com/python-pillow/Pillow",
  "buggy_commit": "abc1234",
  "language": "python",
  "known_bugs": [
    {"id": "KB-1", "description": "CVE-2022-24303: path traversal in open()", "file": "src/PIL/Image.py", "fixed_in": "9.0.1"},
    {"id": "KB-2", "description": "Heap buffer overflow in TIFF decoder", "file": "src/libImaging/TiffDecode.c", "fixed_in": "9.1.0"}
  ]
}
```

**benchmark-result.json schema**:
```json
{
  "project": "pillow",
  "total_findings": 23,
  "total_known_bugs": 5,
  "true_positives": 4,
  "false_positives": 3,
  "false_negatives": 1,
  "recall": 0.80,
  "precision": 0.57,
  "prioritization_score": {
    "known_bugs_as_p0": 3,
    "known_bugs_as_p1": 1,
    "known_bugs_as_p2_or_lower": 0
  }
}
```

**执行流程**（1 个 Skill 调用 = 1 个 project benchmark）:

```
Step 1: git checkout <buggy_commit> of OSS project
Step 2: Identify spec documents (formal spec, ADRs, ARCHITECTURE.md — see candidate list for Tier A/B classification)
Step 3: Run Phase 0 Spec Quality Gate. Record tier (Tier A or B expected, see candidate pool)
Step 4: Run Phase 1-4 Audit (single round, 5 subagents max)
Step 5: Output AuditReport.json per P1.6 schema
Step 6: Manual classification per TP standard:
  - Exact match: finding file+line overlaps known bug location → TP
  - Close match: finding file matches, same category, claim describes same root cause → TP (tag: "close")
  - Related: same problem, different file/category → FP (do NOT count as TP — must be strict)
  - No match to any known bug → FP
Step 7: Write benchmark-result.json. If Tier B: include audit_mode: "structural"
```

**兼容性**: 零冲突。P2.9 是纯数据采集操作，仅消费 P1.6 JSON Schema 输出，不修改任何代码。

**可操作性**: 每个 OSS 项目 1 个独立 Skill 调用。操作者手动 checkout buggy commit → 运行审计 → 按 TP 标准人工匹配发现到已知 bug。结果存入 benchmark-result.json。基准报告由主 Agent 汇总 3 个 `benchmark-result.json` 生成。B 档项目的 recall 与 A 档项目的 recall 在汇总报告中分列，不混合计算。

**候选项目池**:
```
Tier A (formal design spec exists — must include >=1):
1. FastAPI — OpenAPI spec = machine-readable design doc, well-documented route contracts
2. Django REST Framework — extensive BDFL docs, deprecation policy, serializer contracts
3. SQLAlchemy — detailed architecture docs, session/connection lifecycle documented

Tier B (design docs exist, no formal spec):
4. Flask — extension pattern documentation, app context documented
5. Requests — well-documented API contracts via docstrings (not a formal spec)
6. Click — decorator-based CLI framework, command contracts documented

Selection: 1 Tier A + 2 Tier B = 3 projects. Ensures benchmark covers both full audit and structural audit.
```

---

### 2.2 P2.8' — Lens System + Typed Subagent

#### 目标
将审查从「1 个通用 Subagent 审查 5 维度」升级为「5 个专业 Subagent 各审查 1 个透镜」。每个透镜聚焦 1 个类别，避免通用 Subagent 略读 P1 的问题（即 2026-07-04 case log 的 FN-1/FN-2 根因）。

#### 工程实现

**新增文件**:
```
scripts/audit_lens.py          (透镜派发脚本)
SKILL.md                        (新增 §Lens System 章节)
```

**audit_lens.py** — 透镜派发器:
```python
"""
Usage: python scripts/audit_lens.py --module <name> --spec <spec.md> --lenses <lens1,lens2>
Output: Merged ModuleAuditResult from all selected lens subagents.

Lens → Typed Subagent mapping:
  design_align → Design Aligner (signature + behavior)
  contract     → Contract Guardian (contract invariants)
  error_handle → Error Handler (exception coverage)
  boundary     → Boundary Checker (validation, null, edge)
  corrective   → Corrective Tracker (spec fix items)

Core lenses (always on): design_align, contract, error_handle, boundary, corrective
Extension lenses (opt-in): security, architecture
"""
```

**实际执行路径**: 由于 Trae Skill 不能通过 Python 脚本"派发 subagent"，`audit_lens.py` 的角色是**生成 lens-specific prompt**，主 Agent 读取后通过 Task 工具派发。流程：

```
1. 主 Agent 读取 SKILL.md §Lens System → 确定启用的透镜列表
2. 对每个模块 × 每个透镜，主 Agent 调用 Task tool 派发 typed subagent
3. 每个 typed subagent 的 prompt = Appendix A Template 1 变体
   - Design Aligner: 仅检查 DIMENSION 1+2 (signature + behavior)
   - Contract Guardian: 仅检查 DIMENSION 5 (contract)
   - Error Handler: 检查 DIMENSION 2 子集 (try/except coverage, error propagation)
   - Boundary Checker: 检查 DIMENSION 2 子集 (None checks, range validation, edge cases)
   - Corrective Tracker: 仅检查 DIMENSION 3 (corrective items)
4. 每个 typed subagent 输出 ModuleAuditResult JSON（仅覆盖其透镜维度）
5. 主 Agent 合并所有透镜的 ModuleAuditResult → 最终 AuditReport
```

**SKILL.md 新增章节**（Section: Lens System）:
```markdown
## Lens System / 透镜系统

**Added in v0.3 (P2.8')**

### Core Lens（默认开启）

| Lens | Typed Subagent | Focus |
|---|---|---|
| design_align | Design Aligner | Signature + behavior vs spec |
| contract | Contract Guardian | ADR invariants, dependency graph |
| error_handle | Error Handler | Exception coverage, error propagation |
| boundary | Boundary Checker | Input validation, edge cases, null safety |
| corrective | Corrective Tracker | Spec corrective items in code |

### Extension Lens（按需）

| Lens | Enable with | Focus |
|---|---|---|
| security | `--lens security` | XSS, injection, unsafe eval, secrets |
| architecture | `--lens architecture` | Circular deps, layer violations |

### Lens Selection

Default: All 5 core lens enabled. Each lens dispatches 1 typed subagent per module.
Extension lens: Added when user specifies `--lens <name>`.
Total max subagents per module = 5 (core) + 2 (extension max) = 7.
```

**兼容性**: 向后兼容。不指定透镜 → 行为与 v0.2 完全相同（使用通用 Template 1 subagent）。指定 `--lens design_align,contract` → 仅派发指定透镜。默认（无参数）= 全部 5 个核心透镜。所有 subagent 输出均符合 P1.6 JSON Schema。

**可操作性**: 用户无需感知透镜概念即可使用默认全部审查。高级用户可 `--lens design_align,contract` 只审查设计对齐和契约。安全团队可 `--lens security` 追加安全扫描。

**Lens Prompt Templates Overview / 透镜 Prompt 要点**（每个透镜的 SKILL.md prompt 差异 — 完整模板见实施时 SKILL.md §Lens System）:

| Lens | Prompt Differentiator | Key Instructions |
|---|---|---|
| design_align | DIMENSION 1+2 only | "Compare function signatures, params, return types vs spec. Compare behavior (policies, thresholds, invariants) vs spec. Output only signature/behavior category findings." |
| contract | DIMENSION 5 only | "Verify ADR invariants. Check dependency graph acyclicity via grep. Verify unique entry points. Output only contract category findings. MUST trace transitive dependencies (not just direct imports)." |
| error_handle | DIMENSION 2 subset | "Scan for: bare except clauses, missing try/except on I/O calls, error propagation gaps, retry logic absence. Output behavior category findings — tag subcategory: error_handle." |
| boundary | DIMENSION 2 subset | "Scan for: missing None checks, unvalidated inputs, range violations, type safety gaps. Output behavior category findings — tag subcategory: boundary." |
| corrective | DIMENSION 3 only | "Cross-reference spec §corrective items list with code. For each corrective item: confirm presence in code via grep. Output corrective category findings." |

**Lens Overlap Deduplication / 透镜重叠去重**: When aggregating lens results (Step 3), the main agent applies:
1. Same evidence (file + overlapping line range) + same category → check claims
2. Identical claims → keep one, annotate `detected_by: [lens_a, lens_b]`
3. Different claims, same evidence → keep both (independent findings)
4. One claim is subset of another → keep the more specific, annotate `detected_by: [both]`

This is applied BEFORE score calculation (P3.2) to prevent double-counting. Implemented in `audit_lens.py` merge logic.

---

## 3. v0.4 Implementation / 实施细节

### 3.1 P2.10 — Deterministic Assist Layer

#### 目标
在 subagent 派发前，用确定性脚本生成：精确文件列表、规则索引。在 subagent 输出后，用确定性脚本验证行号准确性。

#### 工程实现

**新增文件**:
```
scripts/audit_files.py      (文件选择器)
scripts/verify_lines.py     (行号验证器)
scripts/rule_index.py       (规则索引生成器)
```

**1. audit_files.py** — 文件选择器:

```python
"""
Deterministic file selector for audit scope.

Algorithm:
  1. Parse spec.md → extract module name → find file glob patterns
     - Look for "## Module: <name>" sections
     - Look for file references: `src/<module>/**/*.py` patterns
  2. Resolve globs via pathlib.glob
  3. If --base commit provided: git diff --name-only <base>..HEAD → changed files
     If --base NOT provided: skip git diff, use all glob-matched files as scope
     (First-time audits have no base commit → full glob scope is correct)
  4. If --base provided: Intersection of glob matches + git diff = audit scope
     If --base NOT provided: glob matches = audit scope
  5. Cap at --max-files (default 50). If >50, warn and pick top 50 by git churn.

Usage:
  python scripts/audit_files.py --spec docs/spec.md --module bridge --repo . [--base HEAD~10] [--max-files 50]

Output (stdout): JSON array of file paths
  ["src/bridge/__init__.py", "src/bridge/worker.py", "src/bridge/handler.py"]
"""
```

**2. verify_lines.py** — 行号验证器:

```python
"""
Post-audit line-number verification.

For each finding in an AuditReport JSON:
  1. Read the claimed file
  2. Extract keywords from finding.claim:
     - Identify specific tokens: variable names (snake_case/CamelCase), module names, error types
     - Deprioritize generic keywords: "from", "import", "the", "and", "with", "for"
     - Weight: specific identifiers ×3, generic words ×1
  3. Check if the claimed line content contains at least 1 weighted keyword from tokenized claim
  4. If no keyword match at claimed line:
     - Search ±N lines (default 20) for the nearest semantic match
     - If found: correct the line number, flag as "auto_corrected"
     - If not found: flag as "unverified", confidence = low
  5. Output verified_report.json with line_number_confirmed: true/false per finding

Accuracy note: v0.4 uses regex + keyword matching (estimated ~65-75% precision on line verification).
Full AST-based verification (tree-sitter) is a v0.5+ option if keyword matching accuracy is insufficient.
This script is a cheap pre-filter, not a replacement for human review of evidence pointers.

Usage:
  python scripts/verify_lines.py --report audit-output.json --repo . [--search-radius 20]

Output: verified_audit_output.json (same schema + verified_line field)
"""
```

**3. rule_index.py** — 规则索引生成器:

```python
"""
Extract all "must" / "must not" / threshold rules from spec + ADRs.

Algorithm:
  1. Read spec.md
     - Extract lines containing: "must", "must not", "shall", "shall not", "禁止"
     - Extract numeric thresholds: regex for "\b\d+(\.\d+)?\s*(ms|MB|%|seconds|requests)"
  2. Read each ADR file
     - Extract "Decision:" sections → invariant statements
     - Extract "Constraint:" sections → explicit constraints
  3. Build keyword→rule index
     - Tokenize each rule → extract significant words (>3 chars, non-stopword)
     - Create mapping: keyword → [list of rule strings]
  4. Output rule_index.json

Usage:
  python scripts/rule_index.py --spec docs/spec.md --adrs docs/adr/ [--output rule_index.json]

Output: rule_index.json
{
  "keywords": {
    "memory": [
      "ADR-001: bridge MUST NOT import from memory module",
      "spec.md §3.1: memory.write() is the only entry point for persistence"
    ],
    "transaction": [...]
  },
  "thresholds": [
    {"constraint": "response time < 200ms", "source": "spec.md §4.2", "value": 200, "unit": "ms"}
  ]
}
```

**SKILL.md 集成**: 在 Step 2 (Audit) 之前插入新步骤:

```
Step 1.5: Deterministic Pre-Processing (v0.4+)
  1. Run scripts/audit_files.py → get exact file list per module
  2. Run scripts/rule_index.py → generate keyword-indexed rule reference
  3. Pass both to subagent prompts as INPUT CONTRACT supplements
  If any script fails or times out (>30s): skip, proceed with audit using full file list
```

在 Step 2 (Audit) 之后插入新步骤:

```
Step 2.5: Deterministic Post-Processing (v0.4+)
  1. Run scripts/verify_lines.py on each subagent's output
  2. Auto-correct line numbers within ±20 line tolerance
  3. Flag unverified line numbers as low-confidence in final report
  If script fails or times out (>30s): skip, proceed with uncorrected output
```

**兼容性**: 纯附加。所有 3 个脚本都是可选的（失败不回退）。v0.2 用户不受影响。

**可操作性**: 主 Agent 自动运行脚本，用户无感。仅在脚本失败时日志提示"确定性辅助不可用"。

---

### 3.2 P2.7 — Inter-Rater Reliability

#### 目标
对同一模块派发 2 个不同透镜的 subagent，在重叠维度上计算一致性。

#### 工程实现

```
Step 2.7: Inter-Rater Dispatch (v0.4+)
  For module X:
    1. Subagent A = Design Aligner + Error Handler (lens: design_align, error_handle)
    2. Subagent B = Boundary Checker + Corrective Tracker (lens: boundary, corrective)
    3. Overlap dimensions: "behavior" (appears in both A via error_handle, and B via boundary)
    4. On overlap dimension "behavior":
       - findings_A = [f for f in A if f.category == "behavior"]
       - findings_B = [f for f in B if f.category == "behavior"]
       - agreement = |findings_A ∩ findings_B| / |findings_A ∪ findings_B|
       - kappa = Cohen's kappa on finding presence per file
    5. If agreement < 0.5: flag module as "low agreement — manual review recommended"
```

**Cohen's kappa 实现** (Python, 在 `scripts/inter_rater.py` 中):
```python
def cohens_kappa(findings_a, findings_b, files):
    """
    Per-file finding presence matrix:
      file_i has finding in A? (0/1)
      file_i has finding in B? (0/1)
    """
    n = len(files)
    a_yes = sum(1 for f in findings_a if f.file in files)
    b_yes = sum(1 for f in findings_b if f.file in files)
    both_yes = sum(1 for fa in findings_a for fb in findings_b
                   if fa.file == fb.file and fa.file in files)
    both_no = n - a_yes - b_yes + both_yes
    
    p_o = (both_yes + both_no) / n  # observed agreement
    p_e = (a_yes/n)*(b_yes/n) + (1-a_yes/n)*(1-b_yes/n)  # expected by chance
    kappa = (p_o - p_e) / (1 - p_e) if p_e != 1 else 1.0
    return kappa
```

**SKILL.md 集成**: 在 Phase 2 (Multi-Dimensional Audit) 末尾添加可选步骤。P2.7 仅在用户显式启用（`--inter-rater`）时触发，因为会增加 1 倍 subagent dispatch 成本。

**兼容性**: 纯可选功能。不启用 = 行为不变。启用 = 额外 dispatch 成本但产出 kappa 指标。

**可操作性**: `audit --inter-rater` 启用。输出中多一个 `inter_rater` 字段：`{"kappa_behavior": 0.72, "agreement_rate": 0.85}`。

**Kappa granularity note / Kappa 粒度说明**: v0.4 实现在 **per-file** 粒度计算 agreement（两个 subagent 是否在同一文件报告 finding）。这是简化假设——per-finding 粒度（是否在同一代码位置发现同一问题）能在更高精度评估一致性，但需要额外证据对齐逻辑。per-file 粒度在 v0.4 范围内是实用的初版实现，per-finding 精度可升级到 v0.5+。

---

### 3.3 P2.11 — Iterative Audit

#### 目标
支持最多 5 轮迭代审查，每轮仅审查被修改的文件（增量），P0 清零即停止。

#### 工程实现

**SKILL.md 修改**: Step 2 与 Step 3 之间插入循环逻辑。Human-in-the-loop：每轮 Agent 审计后暂
停，等待人修复并提交，然后读取 git diff 确定增量范围继续。

```
Step 2.x: Iterative Audit Loop (v0.4+, HUMAN-IN-THE-LOOP)

  Parameters:
    round = 1
    max_rounds = min(user_specified or 2, 5)
    stop_when = user_specified or "p0_zero"  # or "p0_p1_zero"
    incremental = user_specified or true
  
  Loop:
    while round <= max_rounds:
      1. Run Step 2 (Audit) on current file scope           # Agent step
         - Round 1: full scope (all module files)
         - Round N>1: only files modified in Round N-1 (if incremental)
      2. Run Step 3 (Aggregate) on current round findings   # Agent step
      3. If stop condition met: break                       # Agent check
         - "p0_zero" → total P0 findings this round == 0
         - "p0_p1_zero" → total P0+P1 findings this round == 0
      4. Report P0 findings to user                         # Agent output
      5. USER fixes all P0 findings + commits               # HUMAN step (Agent WAITS)
      6. Agent reads git diff to determine changed files    # Agent step
      7. round += 1
    
    If round > max_rounds and stop condition not met:
      Output warning: "Iteration stopped at max_rounds. {n_p0} P0, {n_p1} P1 remain."
```

**与 P2.8' 的透镜轮换集成**:

```
Round 1: All 5 core lens → broad coverage
Round 2: design_align + contract only → deep focus (most P0s are in these categories)
Round 3: error_handle + boundary + corrective → coverage of remaining categories
Round 4-5: Same as round 1, but on incremental scope only
```

**SKILL.md 新增参数段**:

```
## Iterative Audit Configuration (v0.4+)

| Parameter | Default | Max | Description |
|---|---|---|---|
| `--max_rounds` | 2 | 5 | Maximum audit-fix cycles |
| `--stop_condition` | p0_zero | — | Stop when: "p0_zero" or "p0_p1_zero" |
| `--no_incremental` | false | — | Disable incremental (always audit full scope) |
```

**兼容性**: 向后兼容。不指定参数 → 行为与 v0.2 完全相同（单轮）。指定 `--max_rounds 1` → 明确单轮。

**可操作性**: 
- `audit` → 默认 2 轮迭代（新默认行为，因为 2 轮成本可控）
- `audit --max_rounds 1` → 恢复单轮行为（v0.2 兼容模式）
- `audit --max_rounds 5 --stop_condition p0_p1_zero` → 激进模式

**成本**: 经验估算值（实际取决于 P0 密度）。无 P0 → 停止在第 1 轮，成本 = 1.0×。中等 P0 密度（5-8 个 P0，分散在 3-5 个文件）→ 2 轮，成本 ≈ 1.3-1.5×（增量范围缩小第二轮）。高 P0 密度（15+ P0，分散在 10+ 文件）→ 3+ 轮，成本 ≈ 1.8-2.5×。最大硬上限：5 轮。

---

### 3.4 P2.12 — Fix Tracking JSON + --verify

#### 目标
将 Phase 4 的 Markdown 跟踪表替换为结构化 `issues.json`，支持增量验证。

#### 工程实现

**新增文件**:
```
scripts/issues_tracker.py     (issues.json CRUD + verify logic)
```

**issues_tracker.py**:
```python
"""
issues.json state machine: open → in_progress → fixed → verified

Commands:
  python scripts/issues_tracker.py init <audit_report.json>
    → Generate issues.json from AuditReport findings
    → All issues start as status="open"

  python scripts/issues_tracker.py status --id <finding_id> --to <status>
    → Transition an issue: open/in_progress/fixed/verified

  python scripts/issues_tracker.py verify --file <file_path> [--report <audit_output.json>]
    → Re-audit the specified file against its spec section (from issues.json's spec_ref field)
    → Each open issue in issues.json includes spec_ref for this purpose
    → Compare new findings with existing issues.json
    → If previously-open issue NOT in new findings → status → "verified"
    → If previously-open issue STILL in new findings → status remains, warn user

  python scripts/issues_tracker.py summary
    → Print: open=X, in_progress=Y, fixed=Z, verified=W
```

**SKILL.md 集成**: 替换 Phase 4 中的 Markdown 跟踪表:

```
Phase 4: Fix Baseline + Tracking (v0.4+ updated)

1. Write audit report: docs/audit/YYYY-MM-DD-code-quality-audit.md (unchanged)
2. Generate issues.json: python scripts/issues_tracker.py init <report.json>
3. Fix tracking:
   - After fixing an issue: python scripts/issues_tracker.py status --id <id> --to fixed
   - After PR review: python scripts/issues_tracker.py status --id <id> --to verified
4. Verify mode:
   - After fixing all P0s: audit --verify --files <changed_files>
   - Re-audits only the fixed files, updates issues.json status
   - Generates verify report: docs/audit/verify-YYYY-MM-DD.md
```

**兼容性**: Markdown 跟踪表保留作为人类可读形式。issues.json 是机器可读的并行格式。Phase 4 同时生成两种格式。

**可操作性**:
- `audit` → 生成 issues.json（自动）
- `python scripts/issues_tracker.py status --id BRIDGE-P0-1 --to fixed` → 手动标记修复
- `audit --verify --file bridge/__init__.py` → 验证单文件修复

---

## 4. v0.5 Implementation / 实施细节

### 4.1 P3.1 — Semantic Guards Engine

#### 目标
支持用户编写 YAML 守卫规则，AI 检查合规。

#### 工程实现

**新增文件**:
```
docs/audit/guards.template.yml    (模板 + 初始守卫库)
SKILL.md                            (新增 §Semantic Guards 章节)
```

**guards.template.yml** — 初始模板（10 条通用守卫）:
```yaml
# Semantic Guards — Template
# Copy to docs/audit/guards.yml and customize.
# AI checks compliance. NEVER auto-generates guards.
version: "1.0"

guards:
  # --- API Documentation ---
  - id: "TEMPLATE-01"
    description: "Public API functions MUST have docstrings"
    scope: "src/api/**/*.py"
    severity: "warning"
    check: "Every public function (no _ prefix) in scope files has a docstring"

  # --- Error Handling ---
  - id: "TEMPLATE-02"
    description: "External I/O calls MUST include error handling"
    scope: "**/*.py"
    severity: "critical"
    check: "Every file I/O, network call, or database query is wrapped in try/except or returns a Result type"

  # --- Transaction Safety ---
  - id: "TEMPLATE-03"
    description: "Database write operations MUST execute within a transaction"
    scope: "src/repository/**/*.py"
    severity: "blocker"
    check: "INSERT/UPDATE/DELETE operations are wrapped in transaction context managers"

  # --- Input Validation ---
  - id: "TEMPLATE-04"
    description: "All user input MUST be validated before processing"
    scope: "src/api/**/*.py"
    severity: "critical"
    check: "Request body/params are validated via Pydantic schema or explicit type checks"

  # --- Secrets ---
  - id: "TEMPLATE-05"
    description: "No hardcoded secrets in source code"
    scope: "**/*.py"
    severity: "blocker"
    check: "No API keys, passwords, tokens, or private keys in source files"
```

**SKILL.md 新增章节**: 在 Phase 0（Spec Quality Gate）之后，Phase 1（Spec Inventory）之前，作为新的可选层：

```
## Guard Check (Phase 0.5, v0.5+)

If docs/audit/guards.yml exists:
  1. Parse guards.yml
  2. For each guard, resolve scope glob → get file list (via scripts/audit_files.py)
  3. Dispatch 1 Guard Check Subagent per guard group
     - Group guards by scope overlap to minimize subagent count
     - Max 3 Guard Check Subagents per audit
  4. Each Guard Check Subagent:
     - Input: guard list + scope files
     - Output: ModuleAuditResult where category = "guard"
     - Severity: blocker→P0, critical→P1, warning→P2
  5. Merge guard findings into AuditReport as a separate finding category

If guards.yml does not exist: skip (no error, no warning).
```

**与新透镜的集成**: Guard Check 作为第 3 个 Extension Lens（`--lens guard`），或在 guards.yml 存在时自动启用。

**兼容性**: guards.yml 不存在 → 零影响。存在 → 自动附加检查层。不影响现有 Phase 0-4 流程。

**可操作性**:
1. 首次使用：`cp docs/audit/guards.template.yml docs/audit/guards.yml`
2. 编辑 guards.yml 添加项目特有规则
3. 运行 `audit` → 自动加载 guards.yml 并执行 Guard Check

---

### 4.2 P3.2 — Numeric Scoring + Trend Tracking

#### 工程实现

**新增文件**:
```
scripts/score_tracker.py     (评分计算 + scores.json 管理 + Mermaid 生成)
```

**score_tracker.py**:
```python
"""
Score calculator and trend tracker.

Commands:
  python scripts/score_tracker.py compute <audit_report.json>
    → Calculate 0-100 score: 100 - (P0*20 + P1*8 + P2*3 + P3*1)
    → Append to docs/audit/scores.json
    → Output: {"score": 82, "grade": "A-", "date": "2026-07-09"}

  python scripts/score_tracker.py trend
    → Read docs/audit/scores.json
    → Generate Mermaid xychart
    → Output to stdout
```

**SKILL.md 集成**: 在 Phase 3 (Fix Priority Matrix) 末尾追加评分行。在 Audit Report 模板末尾追加趋势图。

**兼容性**: scores.json 不存在 → 自动创建。现有 Find 数量来自 AuditReport JSON（P1.6 已就绪）。

---

### 4.3 P3.3 — Cross-Project Guard Reuse

#### 工程实现

**新增文件**:
```
scripts/merge_guards.py      (外部引用解析 + 合并)
```

**merge_guards.py**:
```python
"""
Resolve guards.yml 'extends' directive and merge with project guards.

Usage:
  python scripts/merge_guards.py --project docs/audit/guards.project.yml
    → If extends field present:
      - Resolve path (local file or git URL)
      - Load base guards
      - Merge by id: project guards with same id as base → project override base (WARNING logged)
        - If same id but different description → WARNING: "G001 in project overrides base G001 with different description — verify this is intentional"
        - If same id and same description → INFO: "G001: project confirms base guard"
      - If no id conflict: concatenate (base guards first, then project guards)
    → Output: docs/audit/guards.effective.yml
"""
```

**extends 解析**:
```
supports:
  local relative path: "../shared-rules/guards.base.yml"
  local absolute path: "/home/team/audit-rules/guards.base.yml"
  git URL (simple): "https://raw.githubusercontent.com/org/audit-rules/main/guards.base.yml"
```

**兼容性**: guards.project.yml 无 extends → merge_guards.py 是 no-op（直接复制到 effective）。guards.project.yml 不存在 → 不执行任何检查。

---

## 5. Compatibility Matrix / 兼容性矩阵

### 5.1 向后兼容

| 升级项 | v0.2 用户迁移成本 | 破坏性变更 |
|---|---|---|
| P2.9 (benchmark) | 零 — 新目录，不影响现有功能 | 无 |
| P2.8' (lens) | 零 — 默认行为相同（核心透镜 = 原有 5 维度） | 无 |
| P2.10 (deterministic) | 零 — 脚本可选，失败回退 | 无 |
| P2.7 (inter-rater) | 零 — 默认关闭 | 无 |
| P2.11 (iterative) | **轻微** — 默认从 1 轮变为 2 轮（成本增加 ~50%） | 可通过 `--max_rounds 1` 恢复 |
| P2.12 (fix tracking) | 零 — 新增 issues.json，Markdown 表保留 | 无 |
| P3.1 (guards) | 零 — guards.yml 不存在时跳过 | 无 |
| P3.2 (scoring) | 零 — 新增 0-100 分，A+~F 保留 | 无 |
| P3.3 (cross-project) | 零 — 无外部引用时 no-op | 无 |

### 5.2 并行启用矩阵

```
                    P2.9  P2.8' P2.10 P2.7  P2.11 P2.12 P3.1  P3.2  P3.3
P2.9  (benchmark)    —     ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓
P2.8' (lens)         ✓     —     ✓     ✓*    ✓     ✓     ✓     ✓     ✓
P2.10 (deterministic) ✓     ✓     —     ✓     ✓     ✓     ✓     ✓     ✓
P2.7  (inter-rater)  ✓     ✓*    ✓     —     ✓     ✓     ✓     ✓     ✓
P2.11 (iterative)    ✓     ✓     ✓     ✓     —     ✓     ✓     ✓     ✓
P2.12 (fix tracking) ✓     ✓     ✓     ✓     ✓     —     ✓     ✓     ✓
P3.1  (guards)       ✓     ✓     ✓     ✓     ✓     ✓     —     ✓     ✓
P3.2  (scoring)      ✓     ✓     ✓     ✓     ✓     ✓     ✓     —     ✓
P3.3  (cross-project)✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓     —
```
✓ = 兼容，可同时启用
✓* = P2.7 依赖 P2.8'（需要透镜类型化才有意义）

### 5.3 JSON Schema 兼容性

所有新增输出字段均为 **optional**（按 JSON Schema Draft-07 标准），不违反现有 `schemas/audit-finding.schema.json`。

| 新增字段 | 所属实体 | 引入版本 |
|---|---|---|
| `status` | AuditFinding | v0.4 (P2.12) |
| `verified_line` | EvidencePointer | v0.4 (P2.10) |
| `score` (0-100) | AuditReport.summary | v0.5 (P3.2) |
| `inter_rater` | AuditReport | v0.4 (P2.7) |
| `guard_findings` | AuditReport | v0.5 (P3.1) |

---

## 6. File Structure After Full Implementation / 实施后文件结构

```
audit-driven-development/
├── SKILL.md                         (主 Skill 定义, v0.5)
├── README.md
├── LICENSE
├── adapters/                        (7 files, 始终同步)
├── schemas/
│   ├── audit-finding.schema.json    (v0.2, 不变)
│   └── example-audit-report.json    (v0.2, 不变)
├── scripts/
│   ├── sync_adapters.py             (v0.2)
│   ├── audit_files.py               (v0.4, P2.10)
│   ├── verify_lines.py              (v0.4, P2.10)
│   ├── rule_index.py                (v0.4, P2.10)
│   ├── issues_tracker.py            (v0.4, P2.12)
│   ├── audit_lens.py                (v0.3, P2.8')
│   ├── inter_rater.py               (v0.4, P2.7)
│   ├── score_tracker.py             (v0.5, P3.2)
│   └── merge_guards.py              (v0.5, P3.3)
├── docs/
│   ├── ROADMAP.md                   (当前文档)
│   ├── implementation-plan.md       (本文档)
│   ├── audit/
│   │   ├── guards.template.yml      (v0.5, P3.1)
│   │   ├── guards.yml               (用户编写)
│   │   └── scores.json              (v0.5, P3.2, 自动追加)
│   ├── audit-log/
│   │   ├── TEMPLATE.md
│   │   ├── 2026-07-04-factor-miner-v0.1.0.md
│   │   └── ...                      (持续追加)
│   └── benchmark/                   (v0.3, P2.9)
│       ├── README.md
│       ├── candidates.md
│       └── <project>-<version>/
│           ├── metadata.json
│           ├── audit-output.json
│           └── benchmark-result.json
```

---

## 7. Milestone Plan / 里程碑计划

### Milestone 1: v0.3 — Core Verification（业余 1.5 months）

| Week | Tasks | Deliverable | Notes |
|---|---|---|---|
| 1 | P2.9: Select 3 OSS candidates (1 Tier A + 2 Tier B). Write metadata.json templates. Define TP/FP/FN classification standard in benchmark README. | candidates.md + TP标准文档 | — |
| 2 | P2.9: Benchmark Tier A project (e.g., FastAPI), manual TP/FP classification. Calculate recall/precision. | 1st benchmark-result.json | ~3-4 hours |
| 3 | P2.9: Benchmark Tier B projects (2×). | 3 benchmark results | ~3-4 hours each |
| 4 | P2.9: Write aggregated benchmark report. **Gate check**: apply tiered thresholds (recall >70% Tier A, avg >60%). If pass: begin P2.8' design. If soft-fail: optimize prompts, retry. | benchmark README | Gate timing: Week 4, NOT after Week 3 |
| 5-6 | P2.8': Design lens SKILL.md section + write 5 typed subagent prompts (see §2.2 Lens Prompt Templates). Implement audit_lens.py merge logic with deduplication. | SKILL.md lens section + audit_lens.py | Can start design in Week 4, code in Week 5-6 |

**Gate check at end of M1**: Apply tiered thresholds:
- Gate pass (proceed to P2.8'): Recall >70% Tier A AND average >60%
- Soft-fail (fix prompts, retry): Recall 50-70% Tier A or avg 40-60%
- Hard-fail (re-scope): Recall <50% Tier A or avg <40%

### Milestone 2: v0.4 — Pragmatic Enhancement（业余 1 month）

| Week | Tasks | Deliverable |
|---|---|---|
| 5 | P2.10: Implement audit_files.py + verify_lines.py + rule_index.py | 3 scripts |
| 6 | P2.10: Integrate into SKILL.md. P2.12: Implement issues_tracker.py | SKILL.md update + issues_tracker.py |
| 7 | P2.7: Implement inter_rater.py. P2.11: Add iterative audit loop to SKILL.md Step 2.x | inter_rater.py + SKILL.md iterative section |
| 8 | Integration testing + adapters sync + release v0.4 | Tag v0.4 |

### Milestone 3: v0.5 — Rules + Scoring Ecosystem（业余 1.5 month）

| Week | Tasks | Deliverable |
|---|---|---|
| 9 | P3.1: Write guards.template.yml (10 guards). SKILL.md Guard Check section | template + SKILL.md section |
| 10 | P3.2: Implement score_tracker.py. SKILL.md scoring section | score_tracker.py |
| 11 | P3.3: Implement merge_guards.py. Integration testing | merge_guards.py |
| 12 | Full integration test. Adapters sync. Release v0.5 | Tag v0.5 |

**Total**: ~14 weeks full-time ≈ **4–5 calendar months** at hobby-project pace. Each version is independently shippable.

---

## 8. Risk Register / 风险登记

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OSS benchmark recall below gate threshold | 中 | 高 — 阻塞所有后续开发 | P2.9 作为门控，分级阈值（70%/60%）。若 soft-fail：回退优化 subagent prompt 后重测。若 hard-fail：重新审视 subagent 方案在未知代码库审计中的可行性。 |
| 透镜 Subagent 产出质量下降（专业但过窄） | 低 | 中 — 漏报增加 | 每个透镜 Subagent 仍覆盖 2 个紧耦合维度，不完全割裂。lens overlap dedup 防止重复发现影响 scoring |
| 确定性脚本维护成本 | 低 | 低 — 脚本简单（<200 行/个） | 脚本纯 Python stdlib，无外部依赖 |
| guards.yml 模板无人使用 | 中 | 低 — 不影响核心功能 | guards.yml 完全可选。模板提供默认值降低编写成本 |
| 版本迭代过快，用户无所适从 | 低 | 低 | 每版本向后兼容。v0.2→v0.3 默认行为不变 |
