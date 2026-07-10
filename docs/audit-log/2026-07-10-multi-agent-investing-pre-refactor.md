# Audit Case Log: Multi-Agent Investing — Pre-Refactor Architecture Alignment

> **4th case log.** Second external project audit (third non-self). First full Detection→Repair loop with structured fix_suggestions per v0.2.2.
> v0.2.2 完整 Detection→Repair 循环验证 — Overview/Process/Step5 Verify-FIX/Completion Checklist 首次实战使用。

---

## 1. Metadata / 元数据

| Field | Value |
|---|---|
| Project | Multi-Agent Factor Investing (HMM + Industry Rotation) |
| Version | Pre-refactor (claimed "重构完成" but partial) |
| Audit Date | 2026-07-10 |
| Auditor | Scott Peng Liu (with Trae + 2 parallel subagents) |
| Baseline Commit | N/A (no git) |
| Spec Quality Tier | **A** (5/5) — 6 design docs, 4-layer arch, 15 module contracts |
| Skill Version | v0.2.2 (Detection→Repair duality) |
| Design Docs | 项目优化方案, 模块解耦方案, 行业轮动重组方案, 重构方案分析, 重构完成报告, HMM README |

---

## 2. Spec Inventory / 设计文档清单

| Doc | Version | Status | Role in Audit |
|---|---|---|---|
| 项目优化方案.md | Mar 2026 | draft (corrective items) | Defines 83 duplicate files, 15 packages, archive strategy |
| 重构方案分析.md | Mar 2026 | draft (arch spec) | Defines 4-layer arch, module contracts,接口契约 |
| 重构完成报告.md | Mar 2026 | draft (claims verification) | Claims 15 modules/8000 lines/45 metrics/complete tests |
| 行业轮动重组方案.md | Mar 2026 | draft (module spec) | Defines industry_rotation module structure |
| 模块解耦方案.md | Mar 2026 | draft (contract spec) | Defines layer1 ↔ HMM decoupling, adapter pattern |
| HMM README.md | Mar 2026 | draft (overview) | Module usage guide |

**Audit Dimensions**: Root+src (1 subagent) + HMM module (1 subagent) = 2 parallel subagents

---

## 3. Findings Summary / 发现汇总

| Severity | Count | Key Categories |
|---|---|---|
| P0 Blocker | **10** | Missing files (3 industry_rotation), fake test claim, missing hmmlearn dep, HMM bypass, hidden duplication |
| P1 Critical | **14** | Residual duplication, wrong paths, dead code, coupling violations, naming mismatches |
| P2 Major | **7** | Package count ambiguity, near-duplications, fragile imports, incomplete deps |
| P3 Minor | **4** | Doc contradictions, naming inconsistencies |

### Per-Module

| Module | P0 | P1 | P2 | P3 | Score |
|---|---|---|---|---|---|
| Root + src/ | 4 | 6 | 4 | 2 | **C** |
| HMM core/ | 5 | 8 | 3 | 2 | **C-** |
| **Aggregate** | **10** | **14** | **7** | **4** | **C-** |

---

## 4. P0 Blockers — Structured Fix Suggestions

### DEP-P0-1: Missing hmmlearn dependency

```json
{
  "finding_id": "DEP-P0-1",
  "severity": "P0",
  "category": "behavior",
  "evidence": "layer1_factor_monitor/market_state.py:1 — from hmmlearn import hmm",
  "spec_ref": "项目优化方案 §requirements",
  "claim": "hmmlearn is a hard dependency of market_state.py but not in requirements.txt. Fresh pip install crashes on import.",
  "fix_suggestion": {
    "steps": ["Add 'hmmlearn>=0.3.0' to requirements.txt line 8"],
    "affected_files": ["requirements.txt:7"],
    "regression_risk": "none",
    "verification_command": "pip install -r requirements.txt && python -c 'from hmmlearn import hmm; print(\"OK\")'"
  },
  "impact": "New environment setup fails. Blocks all HMM-related functionality.",
  "mitigation": "None possible — hmmlearn is required."
}
```

### TEST-P0-1: "Complete integration tests" claim is false

```json
{
  "finding_id": "TEST-P0-1",
  "severity": "P0",
  "category": "behavior",
  "evidence": "tests/unit/ — only 4 files (test_hmm.py, test_factor_data.py, test_portfolio.py, test_agents.py). No conftest.py, no pytest.ini, no CI config.",
  "spec_ref": "重构完成报告 L109-L113",
  "claim": "重构完成报告声称 '测试覆盖: 完整的集成测试验证' 和 '单元测试: 每个模块独立测试' — 实际 tests/unit/ 仅 4 个测试文件，覆盖 <25% 模块。70+ 个根级文件为 debug_*.py 调试脚本而非结构化测试。",
  "fix_suggestion": {
    "steps": [
      "Step 1: Update 重构完成报告 L109 to '基础测试覆盖: 4个核心模块的简单单元测试，完整集成测试待完成'",
      "Step 2: Move debug_*.py from tests/ to debug/ directory (70+ files are调试脚本，not tests)",
      "Step 3: Create conftest.py + pytest.ini for structured test framework (future)"
    ],
    "affected_files": ["HMM/docs/重构完成报告.md:L109-L113", "tests/ (70+ files to move)", "tests/ (new conftest.py)"],
    "regression_risk": "none (doc fix only for Step 1)",
    "verification_command": "grep -c '完整的集成测试验证' HMM/docs/重构完成报告.md | grep 0"
  },
  "impact": "Misleading documentation creates false sense of quality. Engineers making decisions based on 'complete test coverage' are acting on false information.",
  "mitigation": "Apply Step 1 immediately (文档修正). Steps 2-3 can be deferred."
}
```

### ROT-P0-1/2/3: industry_rotation missing 3 critical files

```json
{
  "finding_id": "ROT-P0-1",
  "severity": "P0",
  "category": "corrective",
  "evidence": "industry_rotation/core/ — no models.py exists",
  "spec_ref": "行业轮动重组方案 L39-L44",
  "claim": "方案要求创建 core/models.py (RotationMetrics, IndustryData)，__init__.py 的 from .core.models import 会直接 ImportError",
  "fix_suggestion": {
    "steps": [
      "Create industry_rotation/core/models.py with RotationMetrics and IndustryData dataclasses",
      "Content: @dataclass with fields defined in方案 L39-L44"
    ],
    "affected_files": ["industry_rotation/core/models.py (NEW)", "industry_rotation/core/__init__.py (verify import)"],
    "regression_risk": "none (new file, no existing code depends on it except __init__.py)",
    "verification_command": "python -c 'from industry_rotation.core.models import RotationMetrics, IndustryData; print(\"OK\")'"
  },
  "impact": "industry_rotation module incomplete — any code importing from this module will fail.",
  "mitigation": "None — file simply doesn't exist."
}
```

### ARCH-P0-1: HMM module bypassed — app.py uses market_state.py directly

```json
{
  "finding_id": "ARCH-P0-1",
  "severity": "P0",
  "category": "contract",
  "evidence": "app.py:L35 → src/core/backtest/backtest.py:L11 → layer1_factor_monitor/market_state.py:L1 → hmmlearn (NOT HMM.core.models)",
  "spec_ref": "模块解耦方案 L56-L58 (方案要求 '删除 market_state.py/robust_hmm.py，统一用 HMM.core.models')",
  "claim": "app.py 的整个调用链完全不经过 HMM 核心模块。market_state.py 直接使用 hmmlearn 自建 HMM，与 HMM 模块形成功能重复。hmm_adapter.py 已创建但从未被使用。",
  "fix_suggestion": {
    "steps": [
      "Step 1: Change backtest.py:L11 from 'from layer1_factor_monitor.market_state import HMMMarketState' to 'from layer1_factor_monitor.hmm_adapter import HMMMarketStateAdapter as HMMMarketState'",
      "Step 2: Verify hmm_adapter.py correctly bridges to HMM.core.models",
      "Step 3: Once verified, delete or deprecate market_state.py and robust_hmm.py"
    ],
    "affected_files": ["src/core/backtest/backtest.py:L11", "main.py:L3", "debug/test_integration.py:L26"],
    "regression_risk": "medium — hmm_adapter.py must provide equivalent interface to market_state.py.HMMMarketState",
    "verification_command": "python -c 'from layer1_factor_monitor.hmm_adapter import HMMMarketStateAdapter; print(\"OK\")'"
  },
  "impact": "HMM核心模块是一个孤岛 — 整个应用绕过它直接使用 hmmlearn。15 模块架构中的核心模块实际上未被任何应用代码使用。",
  "mitigation": "hmm_adapter.py 已存在且功能完整 — 仅需切换 import 路径。低风险高收益。"
}
```

### HMM-P0-1: rotation_analyzer.py missing from HMM/business

```json
{
  "finding_id": "HMM-P0-1",
  "severity": "P0",
  "category": "corrective",
  "evidence": "HMM/business/ — only performance_calculator.py + risk_metrics.py (no rotation_analyzer.py)",
  "spec_ref": "重构完成报告 L18 — lists rotation_analyzer.py as completed in Phase 2",
  "claim": "重构报告第二阶段声称 rotation_analyzer.py 已完成，但实际文件不存在。轮动分析 + 综合分析功能将崩溃。",
  "fix_suggestion": {
    "steps": [
      "Option A (if rotation logic moved to industry_rotation): Update 重构完成报告 to remove rotation_analyzer.py from claimed deliverables, note 'moved to industry_rotation/core/analyzer.py'",
      "Option B (if still needed): Create stub rotation_analyzer.py that delegates to industry_rotation.core.analyzer"
    ],
    "affected_files": ["HMM/docs/重构完成报告.md:L18 (option A)", "HMM/business/rotation_analyzer.py (option B, NEW)"],
    "regression_risk": "none (file doesn't exist — adding doc fix or stub is safe)",
    "verification_command": "grep -c 'rotation_analyzer.py' HMM/docs/重构完成报告.md"
  },
  "impact": "重构完成报告与代码状态不一致 — 声称完成但缺失核心模块。约 60% 完成度，非 100%.",
  "mitigation": "Option A is preferred — documentation should reflect reality."
}
```

---

## 5. Architectural Health Assessment / 架构健康评估

**重构完成率: ~55%** (not the claimed 100%)

```
✅ COMPLETED:
  - _legacy/ archive (200+ files moved)
  - HMM 4-layer structure (config/data/business/service/ui all present)
  - industry_rotation module skeleton (core/data/service/ui/api directories)
  - hmm_adapter.py (fully implemented but unused)
  - config.yaml externalization

🟡 PARTIALLY:
  - industry_rotation: skeleton exists but 3 files missing (models/industry_mapping/endpoints)
  - Test infrastructure: 4 test files (not the claimed "complete integration tests")
  - Duplicate removal: main.py deduplicated but src/core/backtest/backtest.py is functional duplicate

❌ NOT STARTED:
  - market_state.py/robust_hmm.py NOT deleted (module 解耦方案 §56-58 explicit requirement)
  - app.py import chain NOT updated to use hmm_adapter (still using market_state.py)
  - HMM/ui/pages/ 仍有重复轮动 UI (should be removed after migration)
  - 6+ 个实验性脚本散布在 HMM/ 根目录 (not in重构报告 listed modules)
  - analyzer.py 混杂 BayesianFactorMonitor (unrelated class in industry_rotation module)
```

---

## 6. Detection Quality / 检出质量

| Metric | Value | Comparison |
|---|---|---|
| Subagent Count | 2 parallel | Code_Hub: 5, Factor_Miner: 6 |
| Wall-clock Time | ~15 min | Code_Hub: 25 min, Factor_Miner: 120 min |
| Total Findings | 35 (after dedup) | Code_Hub: 23, Factor_Miner: 21 |
| P0 Findings | 10 | Code_Hub: 9, Factor_Miner: 5 |
| P1 Findings | 14 | Code_Hub: 8, Factor_Miner: 8 |

**Key observation**: P0 density is higher than Code_Hub (10 vs 9 on a smaller codebase) — the partial refactoring created more broken contracts than the untouched codebase.

---

## 7. Skill Improvement Notes / Skill 改进记录

- **DIMENSION 6 in action**: 两个 Subagent 均正确检测到 pyproject.toml 缺失和 hmmlearn 依赖缺失 — v0.2.1 的 DIMENSION 6 有效
- **Fixed suggestion quality**: 结构化 fix_suggestion 格式（steps + affected_files + regression_risk + verification_command）首次在 Subagent 输出中自然产生 — P2.13 的概念提前验证
- **Repair priority heuristic**: "1-line fix for broken dependency" (DEP-P0-1) correctly ranked highest in Tier 1 — P0 修复排序启发式验证有效

---

## 8。Lessons Learned / 经验教训

- **Lesson 1**: 声称"重构完成"的项目是最理想的审计目标 — 声明与实际的差距直接转化为 P0 发现。Code_Hub 的 ADR "决策"与代码差距是 P0，MAI 的"重构完成报告"与实际差距也是 P0。模式成立。

- **Lesson 2**: 部分重构比不重构更容易产生隐蔽的架构问题 — market_state.py 未删除 + hmm_adapter 已创建但未使用 = 两个并行实现，新人不知道该用哪个。这是重构反模式。

- **Lesson 3**: DIMENSION 6 直接产生 2 个 P0 (hmmlearn 依赖 + pyproject 缺失) — 构建配置审计维度的 ROI 已验证。
