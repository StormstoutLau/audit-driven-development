# 开发流程规范 / Development Workflow

> **适用范围**: ADD Framework 所有新功能开发、版本升级、技术调研任务
> **来源**: 基于 v2.8 实践经验提炼，经多轮审计验证有效
> **强制级别**: 硬性规范 — 所有任务必须遵循此流程，跳步需在 DEVLOG.md 记录原因

---

## 1. 流程概览

```
┌─────────────────────────────────────────────────────────────┐
│                    开发流程规范 (10 步)                       │
└─────────────────────────────────────────────────────────────┘

Step 1:  MCP 工具调研         (多种 MCP 工具并行调研)
Step 2:  Review 形成调研文档   (整合调研结果，排除幻觉)
Step 3:  编写设计文档 (spec)   (基于调研文档，定义做什么)
Step 4:  Review 排除幻觉       (审计 spec，追溯断言)
Step 5:  编写实施文档          (基于调研+spec，定义怎么做)
Step 6:  Review 排除幻觉       (审计实施文档，工程细节)
Step 7:  编写验收 checklist    (定义验收标准)
Step 8:  Review 文档一致性     (检查文档间对齐)
Step 9:  TDD 实现             (测试驱动开发)
Step 10: 代码审查验收          (对照 checklist 验收)
```

### 1.1 流程原则

1. **调研先行**: 任何实现前必须有调研文档，禁止"边写边调研"
2. **幻觉排除**: 每个文档产出后必须经过 review，追溯断言，排除幻觉
3. **文档对齐**: 设计文档、实施文档、验收 checklist 必须三者对齐
4. **TDD 强制**: 实现阶段必须先写测试，测试通过后再实现
5. **不跳步**: 跳过任何步骤需在 DEVLOG.md 记录原因和影响评估

### 1.2 文档产出清单

每个任务完成后，必须产出以下文档：

| 文档类型 | 位置 | Step | 内容 |
|---------|------|------|------|
| 调研文档 | `docs/research/YYYY-MM-DD-<task>-research.md` | Step 2 | MCP 调研结果 + 外部引用 |
| 设计 spec | `docs/superpowers/specs/YYYY-MM-DD-<version>-<task>.md` | Step 3 | 任务定义 + 约束 + 验收标准 |
| 实施 spec | `docs/superpowers/specs/YYYY-MM-DD-<version>-implementation.md` | Step 5 | 工程细节 + 接口签名 + 依赖 |
| 验收 checklist | `docs/audit-log/YYYY-MM-DD-<version>-acceptance-audit-checklist.md` | Step 7 | 逐项验收清单 |
| 审计追溯 | `docs/audit/YYYY-MM-DD-<version>-spec-audit-trace.md` | Step 4/6/8 | 幻觉审计记录 |
| 验收报告 | `docs/audit-log/YYYY-MM-DD-<version>-acceptance-audit-report.md` | Step 10 | 验收结果 |

---

## 2. 详细步骤

### Step 1: MCP 工具调研

**目标**: 使用多种 MCP 工具并行调研，收集技术方案、业界实践、学术文献。

**工具选择** (按任务类型):

| 任务类型 | 推荐 MCP 工具 | 用途 |
|---------|-------------|------|
| 技术可行性 | `mcp_paper-search` (arxiv/pubmed/semantic) | 搜索相关论文 |
| 业界方案 | `mcp_english-search` (search_web) | 搜索工具对比、GitHub Issues |
| 学术价值 | `mcp_paper-search` (search_google_scholar) | 评估学术新颖性 |
| 代码示例 | `mcp_stackexchange` (search_questions) | 搜索技术方案讨论 |
| 代码执行验证 | `integrated_code_mode` (Exec) | 验证技术方案可行性 |

**执行规范**:
- 并行启动 3-4 个 subagent，每个负责一个调研维度
- 每个 subagent 必须返回: 调研结果 + 外部引用 URL
- 外部引用必须注明来源（官方文档/GitHub Issue/论文）

**输出**: 调研原始素材（subagent 返回结果）

**v2.8 案例参考**: [framework-review-and-gap-analysis.md](file:///f:/Coding/audit-driven-development/docs/audit/2026-08-12-framework-review-and-gap-analysis.md) 使用 4 个并行 subagent 调研 10 个 Gap

---

### Step 2: Review 形成调研文档

**目标**: 整合调研素材，形成结构化调研文档，排除幻觉。

**Review 检查项**:
1. **断言追溯**: 每个关键断言必须有外部引用 URL 或代码引用
2. **数字验证**: 所有数字（规模、准确率、成本）必须有来源
3. **工具状态**: 工具的"活跃/停更"状态必须通过 GitHub 仓库最后提交时间验证
4. **版本号**: 工具版本号必须通过官方文档或 changelog 验证
5. **幻觉模式检查**:
   - 编造的 Issue 编号（格式正确但不存在）
   - 编造的 API 名称（看似合理但实际不存在）
   - 编造的性能数字（无来源的准确率/延迟）

**文档结构**:
```markdown
# <任务名> 调研报告

## 0. 执行摘要
## 1. 背景
## 2. 方案对比矩阵 (含外部引用)
## 3. 技术可行性分析
## 4. 风险矩阵
## 5. 实施建议
## 6. 参考文献 (URL 列表)
```

**输出**: `docs/research/YYYY-MM-DD-<task>-research.md`

**v3.0+ 案例参考**: [v3-roadmap-reassessment.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md) (1022 行，6 任务风险评估)

---

### Step 3: 编写设计文档 (spec)

**目标**: 基于调研文档，定义任务"做什么"（What），不定义"怎么做"（How）。

**设计文档结构**:
```markdown
# <版本> <任务名> 设计 spec

## 1. 背景与动机
## 2. 任务定义
   - 2.1 输入契约
   - 2.2 输出契约
   - 2.3 约束条件
## 3. 验收标准 (可测试)
## 4. 与现有架构的关系
## 5. 风险与缓解
```

**编写规范**:
- 验收标准必须可测试（"T1 测试数量 = 5" 而非"增加测试"）
- 约束条件必须具体（"Python ≥ 3.9" 而非"兼容性好"）
- 输入/输出契约必须含 JSON schema 示例

**输出**: `docs/superpowers/specs/YYYY-MM-DD-<version>-<task>.md`

**v2.8 案例参考**: [v2.8-short-term-improvements.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md)

---

### Step 4: Review 排除幻觉 (设计文档审计)

**目标**: 审计设计文档，追溯每个断言，排除幻觉。

**审计方法**:
1. **逐句追溯**: 每个事实性断言必须可追溯到调研文档或代码
2. **数字核对**: spec 中的数字与调研文档一致
3. **引用验证**: spec 引用的外部文档/工具状态与调研文档一致
4. **API 验证**: spec 中提到的 API 必须通过官方文档验证存在

**常见幻觉模式** (v2.8 实际发现):
| 幻觉类型 | 示例 | 检测方法 |
|---------|------|---------|
| 编造排名 | "CWE Top 25 第 1 名是 X" | 核对官方 CWE Top 25 列表 |
| 编造状态 | "Semgrep Action v1 已 deprecated" | 核对 GitHub 仓库 |
| 编造计数 | "TDD 465 测试" | 实际运行 `pytest --co -q | wc -l` |
| 编造 API | "Joern 的 `reachableBy` API" | 核对 Joern 官方文档 |

**输出**: `docs/audit/YYYY-MM-DD-<version>-spec-audit-trace.md`

**v2.8 案例参考**: [v2.8-spec-audit-trace.md](file:///f:/Coding/audit-driven-development/docs/audit/2026-08-12-v2.8-spec-audit-trace.md) (发现并修正 7 处幻觉)

---

### Step 5: 编写实施文档

**目标**: 基于调研文档 + 设计 spec，定义"怎么做"（How），考虑工程细节。

**工程细节检查清单**:
- [ ] **算法性能**: 时间复杂度、空间复杂度分析
- [ ] **版本依赖**: 依赖库的最低版本要求
- [ ] **兼容性**: 向后兼容（`threshold=None` 等价旧行为）
- [ ] **接口签名**: 函数签名、参数类型、返回值类型
- [ ] **错误处理**: 异常捕获、降级策略
- [ ] **并发安全**: async/await 规范
- [ ] **原子操作**: 文件写入使用 `.tmp + replace()`
- [ ] **低效操作排除**:
  - [ ] 无函数内 `import re`（移至模块级 + 预编译）
  - [ ] 无 O(n²) 查找（预构建 O(n) 索引）
  - [ ] 无重复计算（缓存结果）
  - [ ] 无不必要的全量扫描（增量处理）

**实施文档结构**:
```markdown
# <版本> <任务名> 实施 spec

## 1. 实施概览
## 2. 文件变更清单
## 3. 每个文件的详细变更
   - 3.x <file>.py
     - 新增函数: 签名 + 参数说明 + 返回值
     - 修改函数: 变更内容 + 向后兼容策略
     - 性能分析: 时间/空间复杂度
## 4. 依赖变更
## 5. TDD 测试计划
## 6. 回归风险
```

**输出**: `docs/superpowers/specs/YYYY-MM-DD-<version>-implementation.md`

**v2.8 案例参考**: [v2.8-implementation-spec.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-implementation-spec.md)

---

### Step 6: Review 排除幻觉 (实施文档审计)

**目标**: 审计实施文档，确保正确执行设计意图，无额外错误引入。

**审计检查项**:
1. **设计意图对齐**: 实施文档是否正确实现 spec 的每个要求
2. **工程细节验证**:
   - 函数签名是否与 spec 一致
   - 依赖版本是否合理
   - 性能分析是否准确
3. **低效操作检查**: 逐条检查工程细节检查清单
4. **向后兼容验证**: 新参数是否有默认值，旧行为是否保持

**输出**: 追加到 `docs/audit/YYYY-MM-DD-<version>-spec-audit-trace.md`

---

### Step 7: 编写验收 checklist

**目标**: 定义逐项验收标准，确保实现满足设计意图。

**checklist 编写规范**:
- 每项必须可机械验证（"运行 `pytest test_v28_consistency.py` 返回 0" 而非"测试通过"）
- 每项必须标注严重度（P0/P1/P2）
- 覆盖范围: 功能验收 + 文档验收 + 回归验收 + 性能验收

**checklist 结构**:
```markdown
# <版本> 验收审计 checklist

## 1. 功能验收 (T1-T6)
### T1: <任务名>
- [P0] T1.1: <可验证项> → 验证方法: <命令>
- [P1] T1.2: <可验证项> → 验证方法: <命令>

## 2. 文档验收
- [P0] D1: README.md 版本号更新 → 验证方法: grep

## 3. 回归验收
- [P0] R1: v2.7 测试全通过 → 验证方法: pytest test_v27_consistency.py

## 4. 性能验收
- [P1] P1: benchmark 无退化 → 验证方法: run_phase8_benchmark.py
```

**输出**: `docs/audit-log/YYYY-MM-DD-<version>-acceptance-audit-checklist.md`

**v2.8 案例参考**: [v2.8-acceptance-audit-checklist.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-checklist.md) (126 项)

---

### Step 8: Review 文档一致性

**目标**: 检查设计文档、实施文档、验收 checklist 三者对齐。

**一致性检查项**:
1. **任务覆盖**: checklist 覆盖 spec 中的所有任务
2. **验收标准对齐**: checklist 的验收项与 spec 的验收标准一致
3. **数字一致**: 三份文档中的数字（测试数量、文件数量）一致
4. **引用一致**: 三份文档对 ADR 的引用一致
5. **幻觉排查**:
   - checklist 中的 TDD 编号是否与实际测试文件匹配
   - checklist 中的文件路径是否实际存在
   - checklist 中的命令是否可执行

**v2.8 教训**: checklist review 发现 20 项问题（5 幻觉 + 8 误判 + 3 遗漏 + 4 计数错误）

**输出**: 追加到审计追溯文档

---

### Step 9: TDD 实现

**目标**: 测试驱动开发，先写测试，测试通过后再实现。

**TDD 流程**:
```
RED:   编写测试 → 运行失败 → 确认测试有效
GREEN: 编写最小实现 → 运行通过
REFACTOR: 重构 → 确保测试仍通过
```

**实现规范**:
1. **测试文件命名**: `test_v<version>_consistency.py` (如 `test_v28_consistency.py`)
2. **测试覆盖**: 每个任务 (T1-T6) 至少 3 个测试（正常 + 边界 + 异常）
3. **回归测试**: 每次实现后运行全量回归测试
4. **Benchmark 验证**: 实现后运行 benchmark，确认无退化

**命令规范**:
```bash
# 单元测试
python -m pytest scripts/test_v<version>_consistency.py -v

# 回归测试
python -m pytest scripts/test_v24_consistency.py scripts/test_v27_consistency.py -v

# Benchmark
python scripts/run_phase8_benchmark.py --baseline v2.7

# E2E 集成测试
python -m pytest scripts/test_e2e_v24_integration.py -v
```

**输出**: 测试文件 + 代码实现

**v2.8 案例参考**: [test_v28_consistency.py](file:///f:/Coding/audit-driven-development/scripts/test_v28_consistency.py) (25 测试, 491/491 PASS)

---

### Step 10: 代码审查验收

**目标**: 对照验收 checklist 逐项验收，生成验收报告。

**验收流程**:
1. 逐项执行 checklist 中的验证命令
2. 记录每项的 PASS/FAIL
3. FAIL 项需记录根因和修复方案
4. 全部 PASS 后生成验收报告

**验收报告结构**:
```markdown
# <版本> 验收审计报告

## 验收摘要
- 总项数: 126
- PASS: 126
- FAIL: 0
- 通过率: 100%

## 逐项验收结果
| ID | 严重度 | 验收项 | 结果 | 证据 |
|----|--------|--------|------|------|
| T1.1 | P0 | ... | ✅ PASS | pytest 输出 |

## 根因分析 (如有 FAIL)
## 修复记录
## 结论
```

**输出**: `docs/audit-log/YYYY-MM-DD-<version>-acceptance-audit-report.md`

**v2.8 案例参考**: [v2.8-acceptance-audit-report.md](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-08-12-v2.8-acceptance-audit-report.md) (126/126 100%)

---

## 3. 幻觉排除方法论

### 3.1 幻觉类型分类

| 类型 | 描述 | 检测方法 | v2.8 实例数 |
|------|------|---------|------------|
| **编造排名** | 编造的排名/优先级 | 核对官方列表 | 2 |
| **编造状态** | 工具/库的虚假状态 | 核对 GitHub 仓库 | 2 |
| **编造计数** | 虚假的测试/文件数量 | 实际运行命令 | 1 |
| **编造 API** | 不存在的 API 名称 | 核对官方文档 | 1 |
| **编造引用** | 格式正确但不存在的 Issue | 访问 URL 验证 | 1 |

### 3.2 排除流程

```
每个断言
    │
    ├─ 有外部引用 URL? 
    │   ├─ YES → 访问 URL 验证内容匹配
    │   └─ NO → 标记为潜在幻觉，需补充引用
    │
    ├─ 是数字?
    │   ├─ YES → 运行命令验证（pytest --co, wc -l, grep -c）
    │   └─ NO → 跳过
    │
    ├─ 是工具状态?
    │   ├─ YES → 检查 GitHub 仓库最后提交时间
    │   └─ NO → 跳过
    │
    └─ 是 API/函数?
        ├─ YES → 核对官方文档或源码
        └─ NO → 跳过
```

### 3.3 反模式 (v2.7.3 教训)

| 反模式 | 描述 | 对策 |
|--------|------|------|
| **Dead code/Dead parameter** | 函数签名声明修复了断点，但函数体内未真正调用 | TDD 测试需覆盖"消费端"而非仅"存在性" |
| **字段名不匹配** | 脚本 A 输出字段名 X，脚本 B 读取字段名 Y | 闭环字段名必须跨脚本对齐 |
| **步骤顺序错误** | 消费者在生产者之前运行 | 保证"生产者先于消费者" |
| **PowerShell LF 陷阱** | `Get-Content -TotalCount` 对 LF 文件解析异常 | 使用 `[System.IO.File]::ReadAllLines()` 验证行数 |

---

## 4. 文档一致性检查

### 4.1 三文档对齐矩阵

| 检查项 | 设计 spec | 实施 spec | 验收 checklist |
|--------|----------|----------|---------------|
| 任务数量 | T1-T6 (6 个) | T1-T6 (6 个) | T1-T6 (6 个) |
| TDD 测试数 | 25 | 25 | 25 |
| 文件变更数 | N | N | N |
| ADR 引用 | ADR-001 | ADR-001 | ADR-001 |
| Benchmark 指标 | P≥75%, R≥85% | P≥75%, R≥85% | P=75%, R=85.7% |

### 4.2 检查命令

```bash
# 检查 TDD 测试数量一致性
grep -c "def test_" scripts/test_v<version>_consistency.py

# 检查文件引用一致性
grep "scripts/" docs/superpowers/specs/*<version>*.md

# 检查 ADR 引用一致性
grep "ADR-" docs/superpowers/specs/*<version>*.md docs/audit-log/*<version>*.md

# 检查 benchmark 指标一致性
grep "P=\|R=\|F1=" docs/superpowers/specs/*<version>*.md docs/audit-log/*<version>*.md
```

---

## 5. 版本发布检查

### 5.1 发布前检查清单

- [ ] 所有 TDD 测试通过 (491/491)
- [ ] E2E 集成测试通过 (22/22)
- [ ] Benchmark 无退化 (P=75.0%, R=85.7%, F1=80.0%)
- [ ] README.md 版本号已更新
- [ ] RELEASE_NOTES_v<version>.md 已创建
- [ ] ROADMAP.md 已更新
- [ ] DEVLOG.md 已记录
- [ ] DECISIONS.md 已追加新 ADR
- [ ] ARCHITECTURE.md 已同步（如架构变更）

### 5.2 Git 提交规范

```bash
# 提交顺序
git add scripts/ docs/superpowers/ docs/audit/ docs/audit-log/
git commit -m "v<version>: <简要描述>

- T1: <任务描述>
- T2: <任务描述>
...
- TDD: <数量>/<数量> PASS
- Benchmark: P=xx%, R=xx%, F1=xx%"

# Tag
git tag v<version>
```

---

## 6. 流程适配

### 6.1 任务规模适配

| 任务规模 | 调研深度 | 文档产出 | Review 强度 |
|---------|---------|---------|------------|
| **大型** (新版本, 1+ 周) | 4 subagent 并行 | 全部 6 份文档 | 3 轮 review |
| **中型** (新功能, 2-5 天) | 2 subagent | 调研 + spec + checklist | 2 轮 review |
| **小型** (bugfix, <1 天) | 直接代码验证 | DEVLOG 记录 | 1 轮 review |
| **紧急** (hotfix) | 跳过调研 | DEVLOG 记录跳步原因 | 事后补 review |

### 6.2 跳步规则

- **允许跳步**: 紧急 hotfix 可跳过 Step 1-8，但必须在 DEVLOG.md 记录：
  - 跳过的步骤
  - 跳步原因
  - 风险评估
  - 事后补全计划
- **禁止跳步**: Step 9 (TDD) 和 Step 10 (验收) 不可跳过

---

## 7. 参考案例

### 7.1 v2.8 完整流程执行

| Step | 文档 | 状态 |
|------|------|------|
| 1 | 4 subagent 调研 10 个 Gap | ✅ |
| 2 | framework-review-and-gap-analysis.md | ✅ |
| 3 | v2.8-short-term-improvements.md (设计 spec) | ✅ |
| 4 | v2.8-spec-audit-trace.md (修正 7 处幻觉) | ✅ |
| 5 | v2.8-implementation-spec.md (实施 spec) | ✅ |
| 6 | implementation-spec 审计 | ✅ |
| 7 | v2.8-acceptance-audit-checklist.md (126 项) | ✅ |
| 8 | checklist review (修正 20 项问题) | ✅ |
| 9 | test_v28_consistency.py (25 测试, 491/491 PASS) | ✅ |
| 10 | v2.8-acceptance-audit-report.md (126/126 100%) | ✅ |

### 7.2 v3.0+ 调研阶段执行

| Step | 文档 | 状态 |
|------|------|------|
| 1 | 4 subagent 调研 T9'/T12/T17/T18/T11/T8' | ✅ |
| 2 | v3-roadmap-reassessment.md + T11-T8prime-feasibility-research.md | ✅ |
| 3-10 | 待 T9' Phase 1 启动时执行 | ⏳ |

---

## 8. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-12 | v1.0 | 初版创建。基于 v2.8 实践经验提炼 10 步流程规范，含幻觉排除方法论、文档一致性检查、版本发布检查、流程适配规则。 |

---

**文档结束**
