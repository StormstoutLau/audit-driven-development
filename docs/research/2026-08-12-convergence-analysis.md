# ADD 框架多轮审计收敛性分析：从不可能性到分层混合收敛

> **文档类型**: 理论分析报告
> **分析对象**: ADD (Audit-Driven Development) 框架 v2.8
> **核心问题**: 多轮审计下能否实现 1 概率收敛？引入 Lean4 后情况如何？算力无限下是否有限时间可解？
> **分析方法**: 跨学科论证（计算机科学 + 信息论 + 软件工程）+ 标杆案例对比 + 文献综述
> **分析日期**: 2026-08-12
> **基线数据**: v2.7/v2.8 benchmark (P=75.0%, R=85.7%, F1=80.0%)

---

## 摘要

本报告系统分析了 ADD 框架在多轮审计下能否实现"1 概率收敛"（即 precision→1, recall→1, hallucination rate→0）的问题。通过计算机科学（Rice 定理、Cousot 抽象解释框架）、信息论（数据处理不等式、Fano 不等式）和软件工程（工业 SAST 实证数据）三个视角的交叉论证，得出以下核心结论：

1. **当前框架不可达 1 收敛**：由 Rice 定理、DPI、开放集问题共同决定，这是结构性约束而非工程性不足。
2. **引入 Lean4 后情况部分改变**：可形式化子集上强收敛可达（$P=R=1, H=0$），但系统整体仍不可达 1 收敛，变为"分层混合收敛"。
3. **算力无限假设下仍不可完全解决**：受限场景（formal subset + user spec）下有限时间可解，但系统级 100% 可解不可达（EXPTIME-hard + Rice + Gödel + 开放集 + DPI）。
4. **有学术价值**：主要是桥梁性贡献（跨学科映射到 SAST 验证器架构）和工程指导贡献，非新定理贡献。

本报告对照业界最接近"1 收敛"的三个标杆案例（ASTRÉE、CompCert、seL4），说明即使在最严格的形式化验证体系下，"1 收敛"也只在**受限语言 + 受限性质 + 巨额证明成本**的前提下成立。

5. **与主流 LLM 幻觉抑制研究高度同构**：2025-2026 年大模型架构抑制幻觉的六条主线（神经符号架构、形式化验证内嵌、约束解码、确定性后处理、不确定性量化、元认知 RL）均能在 ADD 中找到对应物，反向印证 ADD 方法论的主流性；ADD 的差异化在于将这套方法论用于"审计器自审"而非"生成器自审"。

---

## 目录

1. [问题定义](#1-问题定义)
2. [当前框架的不可收敛性论证](#2-当前框架的不可收敛性论证)
3. [跨学科分析与标杆案例](#3-跨学科分析与标杆案例)
4. [引入 Lean4 的分层收敛分析](#4-引入-lean4-的分层收敛分析)
5. [算力无限假设下的可解性分析](#5-算力无限假设下的可解性分析)
6. [学术价值评估与文献综述](#6-学术价值评估与文献综述)
7. [结论](#7-结论)
8. [参考文献](#8-参考文献)

---

## 1. 问题定义

### 1.1 什么是"1 概率收敛"

设第 $n$ 轮审计后指标为 $(P_n, R_n, H_n)$（precision, recall, hallucination rate），"1 概率收敛"指：

$$\lim_{n \to \infty} P_n = 1, \quad \lim_{n \to \infty} R_n = 1, \quad \lim_{n \to \infty} H_n = 0$$

即多轮迭代后，所有真实 bug 被找到（R→1），所有找到的都是真的（P→1），所有幻觉被消除（H→0）。

**指标定义**（注：本文中 P/R 采用标准定义，H 为 ADD 框架特有指标）：

- **Precision** $P = TP / (TP + FP)$：验证通过的 finding 中真实 bug 的比例
- **Recall** $R = TP / (TP + FN)$：真实 bug 中被找到的比例
- **Hallucination rate** $H$：本文中 $H$ 为**估算指标**，非直接从 benchmark 混淆矩阵计算。benchmark 实测 FP=6, TP=18，若按 $H = FP/(TP+FP) = 6/24 = 25\%$ 计算，与本文使用的 $H^* \approx 0.05-0.10$ 量级不符。本文 $H$ 的实际语义是"在多轮迭代稳态下，rule_suggester 未能拦截的残余幻觉比例"，其数值基于 §2.2 的稳态估算（如"轮次 N: H→H*≈5-8"），而非单次 benchmark 的 FP 率。文中所有 $H^*$ 值均应理解为**理论估算下界**，非实测值。

### 1.2 ADD 框架架构简述

ADD 是一个 5 阶段审计流水线（Phase 0-4），包含 Phase 3.5 验证门，5 层脚本层次，3 轨道系统（Detection→Repair→Knowledge）。其核心是 4 级验证：

| 层 | 验证内容 | 性质 |
|----|---------|------|
| L1 | 文件存在性 | Sound (over-approx) |
| L2 | 行号有效性 | Sound |
| L3 | keyword 匹配 (±20 行窗口) | Sound |
| L4 | Joern CPG 结构验证 | Complete (under-approx) |

ADD 的战略定位是 **SAST Findings Validator**（spec §0.2），不是 SAST 竞品。这意味着：

$$R_{\text{ADD}} \leq R_{\text{SAST}}$$

ADD 是下游过滤器，信息已在上游丢失，ADD 无法恢复。

### 1.3 当前实证基线

v2.7/v2.8 benchmark 数据（687 findings across 6 datasets）：

| Benchmark | TP | FP | FN | TN | P% | R% | F1% |
|-----------|----|----|----|----|----|----|-----|
| ADD self-audit | 5 | 0 | 2 | 1 | 100.0 | 71.4 | 83.3 |
| Python stdlib | 8 | 1 | 0 | 0 | 88.9 | 100.0 | 94.1 |
| itsdangerous | 5 | 0 | 1 | 4 | 100.0 | 83.3 | 90.9 |
| defects4j | 0 | 1 | 0 | 49 | 0.0 | 0.0 | 0.0 |
| bigvul | 0 | 0 | 0 | 113 | — | — | — |
| cvefixes | 0 | 4 | 0 | 8 | 0.0 | 0.0 | 0.0 |
| **Aggregate** | **18** | **6** | **3** | **175** | **75.0** | **85.7** | **80.0** |

版本演化趋势（注：v2.4-v2.5 历史数据来自早期 benchmark 记录，JSON 文件可能已被后续版本覆盖；v2.6+ 数据已在代码库 `docs/audit-log/2026-08-12-v2.8-acceptance-audit-report.md` 验证）：

| 版本 | P% | R% | F1% | 增量 |
|------|----|----|-----|------|
| v2.4 | 100.0 | 42.1 | 59.3 | baseline (历史数据) |
| v2.5 | 71.4 | 83.3 | 76.9 | +规则 (历史数据) |
| v2.6 | 75.0 | 85.7 | 80.0 | +数据 |
| v2.7 | 75.0 | 85.7 | 80.0 | +闭环 |
| v2.8 | 75.0 | 85.7 | 80.0 | +RL threshold |

**关键观察**：v2.6→v2.7→v2.8 三轮迭代后，P/R/F1 完全停滞在 (75.0, 85.7, 80.0)。多轮审计已经收敛到稳态，但稳态严格小于 1。

---

## 2. 当前框架的不可收敛性论证

### 2.1 四个不可收敛的维度

#### 2.1.1 Detection 维度 — 受上游 SAST 硬约束（R 上限 < 1）

ADD 的战略定位是 SAST Findings Validator，不是 SAST 竞品。这意味着：

```
ADD_recall ≤ SAST_recall
```

- Semgrep/CodeQL 本身的 recall < 1（任何 SAST 都有漏报：间接调用、反射、动态加载、跨语言）
- ADD 是下游过滤器，信息已在上游丢失，ADD 无法恢复
- 信息论视角：$I(\text{bug}; \text{ADD output}) \leq I(\text{bug}; \text{SAST output})$，SAST 漏报的 bug 对 ADD 是不可见的

**实证**：v2.7 benchmark 中 defects4j=0 TP, bigvul=0 TP, cvefixes=0 TP — 不是 ADD 验证失败，是 Detection 层根本没产出候选。多轮审计无法修复这个缺口。

#### 2.1.2 Verification 维度 — L3 语义鸿沟（P 上限 < 1）

L3 验证是 keyword/pattern 匹配，本质是词法层操作：

- **无法捕获语义等价**：`subprocess.call(cmd)` vs `os.popen(cmd)` — 不同 keyword，同一漏洞
- **无法理解 alias/间接调用**：`f = subprocess.call; f(cmd)` — keyword 不在调用点
- **无法推理数据流**：keyword 在 ±20 行窗口内出现 ≠ 因果关系

v2.8 T1 的 `min_keywords=2`（threshold=0.85）提升了 precision，但以 recall 为代价（BM2 容忍 R 下降 ≤10pp）。这是经典的 P-R 权衡，不是单调收敛。

**形式化边界**：Rice 定理 — 任何非平凡语义性质不可判定。L4 Joern CPG 是 under-approximation（complete but not sound），L3 keyword 是 over-approximation（sound but not complete）。任何组合都无法同时 sound + complete，因此 $P_n \to 1$ 和 $R_n \to 1$ 不可兼得。

#### 2.1.3 Knowledge 维度 — 学习闭环是"打地鼠"而非收敛

6 步学习闭环（rule_suggester → classify_claim）的机制：

```
第 n 轮幻觉 → hallucination_log → rule_suggester 生成反例规则 → 第 n+1 轮拦截同类幻觉
```

**问题**：规则是基于历史失败的反例，只能拦截已知模式。

- 第 n+1 轮会出现新型幻觉（L3 无法预见的语义变体）
- 新型幻觉进入 log → 生成新规则 → 第 n+2 轮拦截
- 但第 n+2 轮又会出现更新的新型幻觉

这是开放式规则集合，无法穷举所有幻觉模式。$H_n$ 不是单调递减到 0，而是振荡下降到某个下界 $H^* > 0$。

**类比**：这像杀毒软件的签名库 — 能拦截已知病毒，但永远落后于零日漏洞。

#### 2.1.4 Benchmark 维度 — 实证数据远未收敛

当前 v2.7/v2.8 实测：
- 3 个 benchmark 的 TP=0（Detection 缺失，多轮审计无法修复）
- Aggregate R=85.7%，距离 1 还有 14.3pp 的 FN（3 个真实 bug 未被找到）
- 多轮迭代能让 R 从 85.7% 单调上升吗？不能 — 这 3 个 FN 是 L3 keyword 匹配失败，多轮规则学习无法预判它们的语义模式

### 2.2 能实现什么：Bounded Convergence（有界收敛）

当前框架能实现的不是 $H_n \to 0$，而是：

$$\lim_{n \to \infty} H_n = H^* > 0$$

其中 $H^*$ 是由以下因素决定的下界：

| 因素 | 下界贡献 | 可优化性 |
|------|---------|---------|
| L3 语义鸿沟 | 高 | 需引入语义分析（如 LLM embedding）才能降低 |
| SAST 上游漏报 | 高 | 需多 SAST 融合（Semgrep+CodeQL+Joern 原生） |
| Joern CPG 覆盖盲区 | 中 | 需扩展语言前端 |
| 规则集合开放性 | 中 | 需主动学习（active learning）而非被动反例 |

**当前框架的收敛行为**：

```
轮次 1: H=18, R=85.7%
轮次 2: H=12 (规则拦截 6 个已知模式), R=85.7% (R 不变, 规则不影响 Detection)
轮次 3: H=10 (再拦截 2 个), R=85.7%
...
轮次 N: H→H*≈5-8 (剩余是新型语义幻觉), R=85.7% (恒定)
```

$H_n$ 单调下降但有正下界，$R_n$ 基本恒定（受 Detection 硬约束）。这不是"收敛到 1"，是"收敛到某个 < 1 的稳态"。

### 2.3 不可达性定理

**定理 (ADD 不可达)**: 设 ADD 框架的第 $n$ 轮审计指标为 $(P_n, R_n, H_n)$，则：

$$\limsup_{n\to\infty} R_n \leq R_{\text{SAST}} < 1 \quad \text{(DPI)}$$

$$\limsup_{n\to\infty} P_n \leq P^* < 1 \quad \text{(Rice + Cousot)}$$

$$\liminf_{n\to\infty} H_n \geq H^* > 0 \quad \text{(Kolmogorov + Fano)}$$

**证明要点**：
1. **R 上界**：由 DPI，$I(\text{bug}; \text{ADD}) \leq I(\text{bug}; \text{SAST})$，SAST recall 是 ADD recall 的上界，而 SAST recall < 1（实证）
2. **P 上界**：L3 是 keyword 匹配（词法层），存在语义等价但词法不同的 bug（Rice 不可判定），这些会持续产生 FP
3. **H 下界**：rule_suggester 只能生成已观察事件的反例规则，未观察的幻觉模式持续存在（测度论论证）

### 2.4 当前框架的可达稳态

$$\boxed{\lim_{n\to\infty} (P_n, R_n, H_n) = (P^*, R^*, H^*) \text{ where } P^* < 1, R^* < 1, H^* > 0}$$

这是有界收敛 (bounded convergence)，不是 1 收敛。

### 2.5 突破稳态的必要条件

要使 $\limsup R_n > R^*$，需要扩展信道容量，即：

| 扩展方向 | 当前 | 目标 | 难度 |
|---------|------|------|------|
| 多 SAST 融合 | 单 SAST | Semgrep+CodeQL+Joern 原生 | 中 |
| 语义分析层 | 无 (L3=keyword) | L3.5: embedding + LLM 推理 | 高 |
| 符号执行层 | 无 | L5: KLEE/angr 路径可达 | 极高 |
| 形式化验证 | 无 | L6: Lean4 关键性质证明 | 极高 |

**关键观察**：每一层扩展都对应一个新的信息源，必须增加信道容量才能突破。当前框架的 L1-L4 在固定信道容量下收敛到稳态，多轮学习不能突破。

### 2.6 本节小结

**当前框架在多轮审计下不能实现 1 概率收敛，原因是结构性的而非工程性的：**

1. **上游依赖**：ADD_recall ≤ SAST_recall < 1（信息论硬约束）
2. **语义鸿沟**：L3 keyword 匹配无法捕获语义等价（Rice 定理）
3. **P-R 权衡**：v2.8 T1 的 RL threshold 机制本质是权衡，非双赢
4. **学习闭环开放性**：rule_suggester 是被动反例，无法预防新型幻觉
5. **实证数据**：3 个 benchmark TP=0，Aggregate R=85.7%，远未收敛

**框架的真实价值不在于"收敛到 1"，而在于"以可审计的方式量化不确定性"** — 即精确测量"我们在多大程度上应该相信这个 finding"。ADD 回答的是"你怎么知道你知道"，不是"让你知道一切"。

---

## 3. 跨学科分析与标杆案例

### 3.1 计算机科学视角：可判定性硬墙

#### 3.1.1 Rice 定理 — 语义性质不可判定

**定理 (Rice 1953)**: 任何 Turing 完整语言的程序非平凡语义性质均不可判定。

形式化表述：设 $\varphi$ 为部分可计算函数的 Gödel 编码，对任意非平凡性质 $P$（即存在 $f, g$ 使 $P(f) = \text{true}, P(g) = \text{false}$）：

$$\text{Decide}(P) := \{\langle e \rangle \mid P(\varphi_e) = \text{true}\} \text{ 不可判定}$$

**对 ADD 框架的应用**：

"该 finding 指向真实 bug" 是程序的非平凡语义性质 — 存在真 bug（$P=\text{true}$）也存在伪报（$P=\text{false}$）。因此：

$$\text{PerfectVerification} \notin \mathcal{R} \quad (\text{递归可枚举类之外})$$

任何 L1-L4 验证算法（无论多少轮迭代）都无法对所有 finding 给出正确的 True/False 判定。这是不可判定性，不是难度问题。

#### 3.1.2 NP-完全性 — 即使可判定也非多项式可达

即使将问题限制到有限程序（如固定行数的 C 函数），许多子问题仍是 NP-hard：

| 子问题 | 复杂度 | 出处 |
|--------|--------|------|
| 路径敏感性数据流分析 | NP-complete | Reps et al. 1995 |
| 上下文敏感性指针分析 | EXPTIME-hard | Nielson et al. 1999 |
| Taint 分析（路径敏感） | NP-complete | Tripp et al. 2009 |
| 符号执行可达性 | undecidable | Pasareanu et al. 2009 |

当前 ADD 的 L3 是 $O(n \cdot k)$（n=窗口行数，k=keyword 数），是 L1-L4 中唯一多项式可解的层。但代价是 L3 只能做词法匹配，精度上限严格小于 1。

#### 3.1.3 抽象解释的不可兼得性 — Cousot 框架

**Cousot & Cousot (1977) 抽象解释框架**给出任何 sound 静态分析的根本约束：

$$\text{Soundness} \Leftrightarrow \text{Over-approximation} \Leftrightarrow \text{False Positives} > 0$$

$$\text{Completeness} \Leftrightarrow \text{Under-approximation} \Leftrightarrow \text{False Negatives} > 0$$

二者不可兼得（除平凡情况）。当前 ADD 的层次设计：

| 层 | 性质 | 偏向 |
|----|------|------|
| L1 (file existence) | Sound | FP 偏多 |
| L2 (line validity) | Sound | FP 偏多 |
| L3 (keyword match) | Sound | FP 偏多 |
| L4 (Joern CPG) | Complete | FN 偏多 |

**L3 Sound + L4 Complete 的组合无法消除两侧误差**：L3 通过的 finding 中有 FP，L4 漏过的 finding 中有 FN。多轮审计只能在两层之间调权重，不能消除误差。

### 3.2 信息论视角：信道容量与不可逆信息损失

#### 3.2.1 数据处理不等式 (DPI) — 信息单调递减

**定理 (Shannon 1948, 数据处理不等式)**: 对任意 Markov 链 $X \to Y \to Z$:

$$I(X; Z) \leq I(X; Y)$$

**应用到 ADD 数据流**：

```
源代码 X ──SAST──► SAST findings Y ──ADD L1-L4──► verified findings Z
```

由 DPI:

$$I(\text{bug}; \text{ADD output}) \leq I(\text{bug}; \text{SAST output}) \leq I(\text{bug}; \text{source})$$

**含义**：
- SAST 阶段丢失的信息（漏报 bug）无法被 ADD 下游恢复
- ADD 多轮迭代只能减少 ADD 自身引入的噪声，不能恢复 SAST 已丢失的信号
- 上界：$\lim_{n\to\infty} R_n \leq R_{\text{SAST}} < 1$

这是 v2.7 benchmark 中 defects4j/bigvul/cvefixes 三个数据集 TP=0 的根本原因 — SAST 没产出候选，ADD 无从验证。

#### 3.2.2 信道容量与 Bug 分布熵

设 bug 在程序中的分布为随机变量 $B$，其熵 $H(B)$。审计过程的"信道容量"：

$$C = \max_{p(x)} I(X; Y)$$

当前 ADD 信道由以下"特征"决定：
- L3: $\pm 20$ 行窗口 + keyword 列表（有限词汇）
- L4: Joern CPG（图同构 + 路径可达性）

**关键观察**：当 bug 模式的 Kolmogorov 复杂度 $K(\text{bug pattern}) > K(\text{L3 keyword set})$ 时，该 bug 不可被 L3 检测，无论多少轮迭代。

**形式化**：设 $\mathcal{B}$ 为 bug 模式集合，$\mathcal{R}_n$ 为第 $n$ 轮规则集合。多轮学习的可达性：

$$\lim_{n\to\infty} \mathcal{R}_n = \sigma(\text{observed hallucinations})$$

即规则集只能生成 $\sigma$-代数（已观察事件的闭包），无法覆盖未观察事件。这是测度论层面的不可达。

#### 3.2.3 Fano 不等式 — 误差下界

**Fano 不等式 (Fano 1949, 1961)**: 给定通信信道，错误概率 $P_e$ 满足：

$$P_e \geq \frac{H(B|Y) - 1}{\log|\mathcal{B}|}$$

其中 $H(B|Y)$ 是给定 SAST 输出后 bug 分布的条件熵。对于真实软件 bug：

- $|\mathcal{B}|$ 极大（bug 类型多样）
- $H(B|Y) > 0$（SAST 输出不能完全确定 bug 存在性）

因此 $P_e > 0$，即任何验证器（包括 ADD）的错误概率有正下界。多轮审计不能使 $P_e \to 0$。

### 3.3 软件工程视角：实证数据与工业实践

#### 3.3.1 工业 SAST 工具的 Recall 上界

文献中报告的 SAST 工具 recall 数据：

| 工具 | 数据集 | Recall | 来源 |
|------|--------|--------|------|
| Coverity | Juliet Test Suite | 70-85% | NIST SAMATE 2017 |
| CodeQL | CVEfixes | 40-60% | 文献综述 |
| Semgrep | OWASP Benchmark | 55-70% | OWASP 2022 |
| Clang Static Analyzer | Juliet | 60-75% | NIST 2019 |
| Infer (Facebook) | 自有 codebase | ~50% | Ondrej et al. 2019 |

**没有任何工业 SAST 在通用代码上达到 R > 90%**。ADD 作为下游验证器，$R_{\text{ADD}} \leq R_{\text{SAST}} < 0.9$。

#### 3.3.2 多轮学习的边际效益递减

类似的"学习闭环"在工业实践中有先例可循：

| 系统 | 机制 | 收敛行为 |
|------|------|---------|
| Microsoft SDV (SLAM) | 反例驱动的谓词精化 | 收敛到 sound 但 incomplete 的不动点 |
| Facebook Infer | bi-abduction + 抽象域精化 | 在固定抽象域内收敛，但域外不收敛 |
| Clang Analyzer | 路径剪枝 + 符号执行 | 路径爆炸导致 recall 受限于时间预算 |

**共同模式**：所有系统都在固定表达力下收敛到稳态，要突破稳态必须扩展表达力（新增谓词/抽象域/分析规则）。ADD 的 rule_suggester 也是如此 — 在 keyword 表达力内收敛，要突破需引入语义分析。

### 3.4 标杆案例：业界最接近"1 收敛"的三个系统

#### 3.4.1 ASTRÉE — 最接近 P=1 的工业系统

**背景**: Cousot 团队开发的抽象解释分析器，用于空客 A340/A380 飞控软件。

**成就**:
- 在受限 C 子集（无递归、无动态内存、无 union）上实现 **0 false alarms** (P=1)
- 分析了约 13.2 万行（132,000 lines）C 代码（空客 A340 主飞控软件；来源：Blanchet et al. 2003 PLDI）

**前提条件**（必须同时满足）:
1. **语言严格受限**：禁用递归、动态内存、函数指针、union
2. **性质受限**：仅证明 absence of runtime errors（除零、溢出、空指针）
3. **代码风格受限**：所有循环必须有显式不变式
4. **抽象域定制**：为每类应用定制 octagon/eigen等抽象域

**对 ADD 的启示**: ASTRÉE 实现 P=1 的代价是约束输入空间。ADD 处理任意 SAST 输出，输入空间无约束，不可能达到 P=1。

#### 3.4.2 CompCert — 形式化验证的 C 编译器

**背景**: Xavier Leroy 团队用 Coq 证明的 C 编译器。

**成就**:
- 编译器正确性的机械化证明（Coq，~40,000 行证明）
- 后端所有优化 pass 的语义保持性证明

**前提条件**:
1. **验证对象是编译器，不是被编译的程序**：CompCert 证明"编译过程正确"，不证明"输入 C 程序无 bug"
2. **性质受限**：仅语义保持性，不涉及内存安全
3. **开发成本**：~6 人年（来源：Leroy 2009 CACM）

**对 ADD 的启示**: CompCert 证明的是工具自身正确性，不是用户程序的 bug-free。ADD 要"收敛到 1"，需要证明"所有 finding 的判定正确"，这比编译器证明更复杂。

#### 3.4.3 seL4 — 形式化验证的微内核

**背景**: NICTA 团队用 Isabelle/HOL 证明的 L4 微内核。

**成就**:
- ~10,000 行 C 代码的功能正确性证明
- 抽象规范 → 实现的可信翻译链

**前提条件**:
1. **代码量极小**：10,000 行（Linux kernel 是 3000 万行）
2. **证明成本**：~200,000 行 Isabelle 证明，20 人年
3. **性质受限**：功能正确性，不含时序、侧信道
4. **底层假设**：汇编层、硬件层未证明

**对 ADD 的启示**: seL4 证明 10,000 行代码用了 20 人年。ADD 处理的代码量是百万级，要"证明所有 finding 判定正确"是不可承受的成本。

#### 3.4.4 案例对比矩阵

| 系统 | P→1? | R→1? | H→0? | 前提 | 成本 |
|------|------|------|------|------|------|
| ASTRÉE | ✅ (受限) | ❌ | ✅ (受限) | 语言+性质+风格约束 | 10+ 年 |
| CompCert | ✅ | ❌ | ✅ | 仅验证编译器 | ~6 人年 |
| seL4 | ✅ | ✅ (功能) | ✅ | 1万行代码 | 20 人年 |
| ADD v2.8 | ❌ | ❌ | ❌ | 任意 SAST 输入 | — |

**结论**：业界没有任何系统在通用代码 + 通用性质下达到 (P=1, R=1, H=0)。最接近的案例都以严格约束输入为代价。

### 3.5 可类比的"收敛系统"

虽然不能达到 1 收敛，但有些系统通过重新定义问题实现了工程意义上的"收敛"：

#### 3.5.1 Proof-Carrying Code (PCC, Necula 1996)

**机制**: 代码生产者附上形式化证明，消费者验证证明（不是验证代码）。

**收敛性**: 验证过程是 P=1, R=1（证明检查器是 decidable），但要求生产者提供证明。

**ADD 类比**: 如果 SAST 工具附上 finding 的形式化证据（如 CPG 路径），ADD 验证证据（而非 finding），可达到 P=1。但要求 SAST 工具改造。

#### 3.5.2 Refinement Types (Freeman & Pfenning 1991)

**机制**: 类型系统携带逻辑谓词，编译期检查。

**收敛性**: 对可判定的 refinement 谓词，P=R=1（类型检查是 decidable）。但只能检查特定性质集。

**ADD 类比**: 如果代码本身携带 spec（如 Dockerfile/类型注解），ADD 可验证 spec 一致性，达到 P=1。这正是 spec-driven audit 方向。

#### 3.5.3 Differential Program Verification

**机制**: 对比两个版本，证明差异部分保持性质。

**收敛性**: 限于差异部分，可达 P=R=1（因为范围小）。

**ADD 类比**: ADD 的 spec_graph + diff_miner 已部分实现此思路，但未形式化。

---

## 4. 引入 Lean4 的分层收敛分析

### 4.1 核心结论

引入 Lean4 判定后，**情况部分改变**，但不是"达到 1 收敛"那种改变。具体而言：

- **可形式化子集上**：$P, R, H \to (1, 1, 0)$ **强收敛可达**（Lean4 类型检查是 decidable）
- **系统整体上**：仍不可达 1 收敛，但稳态 $P^*, R^*$ 显著提升，$H^*$ 显著下降
- **关键约束未变**：DPI（信息单调性）仍成立，SAST 上游漏报仍不可恢复

这是**混合收敛 (hybrid convergence)**，不是统一收敛。

### 4.2 Lean4 改变的部分：可形式化子集的强收敛

#### 4.2.1 Lean4 的可判定性基础

Lean4 基于 **Calculus of Inductive Constructions (CIC)**，其类型检查算法是 decidable：

$$\Gamma \vdash t : T \quad \text{是 decidable}$$

这意味着：给定一个形式化证明 $t$ 和命题 $T$，判定 $t$ 是否证明 $T$ 是 P=1, R=1 的（无幻觉，无漏判）。

应用到 ADD：如果能为某个 finding 构造 Lean4 证明 $t : \text{is\_real\_bug}(f)$，则该 finding 的验证是确定性正确的，多轮审计对它无影响（已收敛到 1）。

#### 4.2.2 改变后的架构

引入 Lean4 作为 L5/L6 层后，ADD 的层次变为：

| 层 | 性质 | 收敛行为 |
|----|------|---------|
| L1-L3 | 启发式（keyword/file/line） | 有界收敛 $P^* < 1$ |
| L4 | Joern CPG (under-approx) | 有界收敛 $R^* < 1$ |
| **L5 (新增)** | **Lean4 形式化证明** | **强收敛 $P=R=1$** |
| **L6 (新增)** | **Lean4 反例构造** | **强收敛 $P=R=1$** |

#### 4.2.3 可形式化 bug 类

哪些 bug 可被 Lean4 形式化？需要满足三个条件：

1. **形式化语义存在**：程序语义可用 Lean4 表达（如 denotational semantics, Hoare logic）
2. **形式化 spec 存在**：bug 定义可形式化
3. **证明可构造**：存在 Lean4 证明（人或算法构造）

满足条件的 bug 类：

| Bug 类 | 可形式化？ | 现有案例 |
|--------|-----------|---------|
| 缓冲区溢出 | ✅ | VST (Appel et al.) |
| 整数溢出 | ✅ | CompCert |
| 空指针解引用 | ✅ | Iris, VST |
| 除零错误 | ✅ | ASTRÉE abstract domain |
| 简单并发竞争 | ⚠️ | Iris concurrency |
| 逻辑 bug | ⚠️ 需 spec | 依赖用户提供 spec |
| 业务逻辑 bug | ❌ 无通用 spec | — |
| 时序侧信道 | ❌ | 需硬件模型 |
| 未知未知 | ❌ | 开放集 |

**对可形式化子集（前 4 类）**：引入 Lean4 后，$P_{L5} = R_{L5} = 1, H_{L5} = 0$，多轮审计对它们是"已收敛"。

### 4.3 Lean4 不改变的部分：开放集与上游约束

#### 4.3.1 DPI 不变 — 上游漏报仍不可恢复

引入 Lean4 不改变信息流：

```
源代码 X ──SAST──► SAST findings Y ──ADD L1-L6──► verified Z
```

DPI 仍成立：

$$I(\text{bug}; Z) \leq I(\text{bug}; Y) \leq I(\text{bug}; X)$$

**Lean4 是更精确的 $Y \to Z$ 通道，但不能恢复 $X \to Y$ 丢失的信息**。如果 SAST 漏报了某个 bug，ADD L5 无从验证它（finding 不存在）。

#### 4.3.2 开放集问题不变 — 未知 bug 模式仍存在

Lean4 证明需要形式化 spec。spec 由谁提供？

- **人提供**：覆盖有限（人能想到的 bug 模式有限）
- **自动生成**：需要从代码归纳 spec，这是反问题，本身不可判定

形式化：设 $\mathcal{S}_n$ 为第 $n$ 轮累积的形式化 spec 集合，$\mathcal{B}$ 为真实 bug 模式全集。则：

$$\lim_{n\to\infty} \mathcal{S}_n \subsetneq \mathcal{B}$$

**严格真子集**，因为 $\mathcal{B}$ 是开放集（总有未知 bug 模式），而 $\mathcal{S}_n$ 是闭集（已形式化的 spec）。

#### 4.3.3 证明构造的创造性 — 不可完全自动化

Lean4 类型检查是 decidable，但证明构造不是。

- **Gödel 不完备性**：任何包含算术的一致形式系统中，存在真但不可证明的命题
- **对 ADD 的含义**：某些真实 bug 的存在性可能无法在 Lean4 中证明（即使 bug 客观存在）
- **实践层面**：Lean4 证明需要人/算法构造，自动化率有限

当前 Lean4 自动化现状（注：以下为步骤辅助率/单次证明率，非端到端定理证明率）：
- **Sledgehammer/Hammer**：~38% 在旧版 Isabelle 证明脚本语料上（Böhme & Paulson 2010 数据；现代 miniF2F benchmark 上仅 10-21%，来源 HybridProver arXiv:2505.15740）
- **Lean4 + LLM (Lean Copilot)**：步骤辅助率 74.2%（Song et al. 2024, arXiv:2404.12534；注：这是 human-in-the-loop 场景下的步骤自动化率，非端到端完整定理证明率）
- **人工证明**：100% 但成本高

这意味着即使形式化 spec 存在，证明可能构造不出来，导致 $R_{L5} < 1$（虽然理论上可达，工程上不可达）。

### 4.4 混合收敛模型

引入 Lean4 后，ADD 的收敛行为变为分层混合：

#### 4.4.1 分层收敛公式

设 bug 集合 $\mathcal{B} = \mathcal{B}_{\text{formal}} \cup \mathcal{B}_{\text{informal}}$，其中：
- $\mathcal{B}_{\text{formal}}$：可形式化的 bug（如内存安全）
- $\mathcal{B}_{\text{informal}}$：不可形式化的 bug（如业务逻辑）

第 $n$ 轮审计的指标：

$$P_n = \frac{|\text{TP}_n|}{|\text{TP}_n| + |\text{FP}_n|}$$

其中：
- $\text{TP}_n = \text{TP}_{L5,n} \cup \text{TP}_{L1\text{-}4,n}$
- $\text{FP}_n = \text{FP}_{L1\text{-}4,n}$（L5 不产生 FP，证明为真即为真）

$$R_n = \frac{|\text{TP}_n|}{|\text{TP}_n| + |\text{FN}_n|}$$

其中：
- $\text{FN}_n = \text{FN}_{\text{SAST}} \cup \text{FN}_{L5,\text{unprovable}} \cup \text{FN}_{L1\text{-}4,\text{informal}}$
- $\text{FN}_{\text{SAST}}$：SAST 漏报（DPI 不可恢复）
- $\text{FN}_{L5,\text{unprovable}}$：spec 存在但证明构造不出
- $\text{FN}_{L1\text{-}4,\text{informal}}$：informal bug 类，L5 无法处理

#### 4.4.2 收敛极限

$$\lim_{n\to\infty} P_n = \frac{|\mathcal{B}_{\text{formal}}| + |\text{TP}^*_{L1\text{-}4,\text{informal}}|}{|\mathcal{B}_{\text{formal}}| + |\text{TP}^*_{L1\text{-}4,\text{informal}}| + |\text{FP}^*_{L1\text{-}4}|}$$

$$\lim_{n\to\infty} R_n = \frac{|\mathcal{B}_{\text{formal}}| + |\text{TP}^*_{L1\text{-}4,\text{informal}}|}{|\mathcal{B}| - |\text{FN}_{\text{SAST}}|}$$

**关键**：
- $P^*$ 显著提升（L5 部分 0 FP），但 < 1（L1-L4 informal 部分仍有 FP）
- $R^*$ 提升有限（L5 只覆盖 formal bug，且受 SAST 上游约束）
- $H^*$ 显著下降（formal 部分 0 幻觉），但 > 0（informal 部分仍有幻觉）

#### 4.4.3 数值估算

假设（基于 VST/CompCert 实证）：
- $\mathcal{B}_{\text{formal}}$ 占比 ~30-40%（内存安全类 bug）
- $\mathcal{B}_{\text{informal}}$ 占比 ~60-70%（逻辑/业务/并发等）
- L5 覆盖 formal bug 的 ~70%（证明构造率）

则引入 Lean4 后：

| 指标 | v2.8 (无 Lean4) | v3.0+ (有 Lean4) | 变化 |
|------|----------------|------------------|------|
| $P^*$ | 0.75 | ~0.90 | +15pp |
| $R^*$ | 0.857 | ~0.88 | +2pp（受 SAST 约束） |
| $H^*$ | ~0.10 | ~0.04 | -6pp |
| 可形式化子集 $P_{L5}$ | N/A | 1.0 | 强收敛 |

**$R^*$ 提升有限**是关键 — 这是 DPI 约束的体现，Lean4 不能绕过。

### 4.5 关键洞察：Lean4 改变的是"验证刚性"而非"覆盖完备性"

#### 4.5.1 验证刚性 (Verification Rigidity)

| 层 | 验证刚性 | 错误模式 |
|----|---------|---------|
| L1-L3 | 概率性（启发式） | 可能错判 |
| L4 | 概率性（图同构） | 可能错判 |
| **L5** | **确定性（证明检查）** | **不错判（decidable）** |

引入 L5 后，**可形式化子集的验证从概率性升级为确定性**。这是质变，不是量变。

#### 4.5.2 覆盖完备性 (Coverage Completeness)

| 层 | 覆盖 bug 类 | 开放集？ |
|----|------------|---------|
| L1-L3 | 词法可匹配的 bug | 是 |
| L4 | CPG 可表达的 bug | 是 |
| **L5** | **spec 可形式化的 bug** | **是** |

L5 的覆盖仍是开放集 — 因为 spec 集合是开放的（人能想到的 spec 有限）。**Lean4 不解决开放集问题**。

#### 4.5.3 核心区分

引入 Lean4 改变的是：**对已覆盖子集，验证从概率性变为确定性**。

不改变的是：**覆盖子集本身仍是开放的，总有未覆盖的 bug 模式**。

### 4.6 重新定义"1 收敛"

引入 Lean4 后，"1 收敛"需要分层定义：

| 层级 | 定义 | 可达？ |
|------|------|--------|
| **Layer-specific 1-convergence** | 在可形式化子集上 $P=R=1, H=0$ | ✅ Lean4 可达 |
| **Domain-specific 1-convergence** | 在特定 bug 域（如内存安全）上 $P=R=1$ | ✅ 受限条件下可达 |
| **System-level 1-convergence** | 在所有 bug 上 $P=R=1, H=0$ | ❌ 开放集 + DPI 不可达 |

### 4.7 条件性 1 收敛

如果用户提供 spec（spec-driven audit 方向），且 spec 本身正确、完备、且对应证明可构造（即不触及 §4.3.3 所述的 Gödel 不完备性约束），则在 spec 覆盖范围内：

$$P_{\text{spec}} = R_{\text{spec}} = 1, \quad H_{\text{spec}} = 0$$

这是**条件性 1 收敛** — 以"用户提供 spec + spec 正确 + 证明可构造"三重条件为前提。若 spec 错误或不完整，则条件不成立；若 spec 正确但对应证明因 Gödel 不完备性不可构造，则 $R_{\text{spec}} < 1$。

### 4.8 本节小结

**引入 Lean4 后，情况不一样，但不是"达到 1 收敛"那种不一样**。

- 从"全概率收敛到 < 1 稳态"变为"分层混合收敛"：formal 子集强收敛 + informal 子集有界收敛
- 从"全系统概率验证"变为"formal 子集确定性验证 + informal 子集概率验证"
- 从"无 1 收敛"变为"条件性 1 收敛"：在 spec 正确且证明可构造的条件下，spec 覆盖范围内可达 1

真正的 1 收敛只在**用户提供 spec + spec 正确 + 证明可构造 + spec 覆盖范围内**成立，这与 spec-driven audit 方向一致。

---

## 5. 算力无限假设下的可解性分析

### 5.1 核心结论

**即使在算力无限假设下，Lean4 引入增强任务也不能在有限时间内完全解决。**

这是不可判定性 + 不可证性 + 开放集三重结构性约束，与算力无关。但任务的主体部分（~70-85%）可解，剩余部分需要重新定义问题边界才能"有限时间收敛"。

### 5.2 不可解部分：三个算力无关的硬墙

#### 5.2.1 硬墙一：Rice 定理 + Gödel 不完备性

**算力无限能做什么**：枚举所有可能证明，判定任何单个证明是否成立（Lean4 类型检查 decidable）。

**算力无限不能做什么**：

- **证明存在性不可判定**：给定命题 $T$，是否存在证明 $t : T$ 是不可判定的（即使算力无限，无法穷举所有证明路径）
- **真但不可证命题存在**：Gödel 第一不完备性定理 — 任何包含 Peano 算术的一致形式系统中，存在 $\text{True}(T) \wedge \neg\exists t. (t : T)$
- **Spec 完备性不可判定**：给定 spec $S$，$S$ 是否覆盖所有真实 bug 不可判定

**对 ADD L5 的含义**：

```
即使算力无限：
  ✅ 可以验证任何给定证明 t : T
  ❌ 不能保证对每个真实 bug b, 存在 Lean4 证明
  ❌ 不能保证 spec S 覆盖所有 bug
```

#### 5.2.2 硬墙二：开放集问题

算力无限不能解决"不知道要验证什么"的问题。

- **Spec 生成反问题**：从代码反推 spec 是不可判定的（与程序综合等价）
- **Bug 模式开放集**：新型 bug 模式持续出现，无法穷举
- **算力无法替代知识**：算力能枚举已有 spec，不能创造新 spec

#### 5.2.3 硬墙三：EXPTIME-hard 证明搜索

即使算力无限，证明搜索爆炸是 EXPTIME-hard：

- Lean4 证明搜索最坏复杂度: EXPTIME-hard（对于 Lean4 的依赖类型理论）
- **算力无限 ≠ 时间无限**：算力无限指并行算力无限，但证明搜索是序列化的（依赖类型理论）
- **Brent's theorem 加速比有限**：$S = O(\log P)$，序列化步数仍指数

形式化：设 $T(n)$ 为证明搜索时间，$n$ 为代码行数：

$$T(n) \in \text{EXPTIME}$$

即使算力无限（并行加速比 $S = O(\log n)$）：

$$T_{\text{parallel}}(n) \geq \frac{T(n)}{S(n)} = \frac{c^n}{\log n}$$

**指数级时间**：即使算力无限，百万行代码的证明搜索时间仍是指效级，不能在有限时间完成。

### 5.3 可解部分：算力无限下 70-85% 可解

#### 5.3.1 CWE Top 25 分解

| Rank | CWE | Name | Spec 可形式化？ | Lean4 可证？ | 算力无限下可解？ |
|------|-----|------|----------------|-------------|-----------------|
| 1 | CWE-787 | Out-of-bounds Write | ✅ | ✅ | ✅ |
| 2 | CWE-79 | XSS | ✅ | ✅ | ✅ |
| 3 | CWE-89 | SQL Injection | ✅ | ✅ | ✅ |
| 4 | CWE-416 | Use-After-Free | ✅ | ✅ | ✅ |
| 5 | CWE-78 | OS Command Injection | ✅ | ✅ | ✅ |
| 6 | CWE-20 | Input Validation | ⚠️ | ⚠️ | ⚠️ |
| 7 | CWE-125 | Out-of-bounds Read | ✅ | ✅ | ✅ |
| 8 | CWE-22 | Path Traversal | ✅ | ✅ | ✅ |
| 9 | CWE-352 | CSRF | ✅ | ✅ | ✅ |
| ... | ... | ... | ... | ... | ... |
| — | CWE-840 | Business Logic Errors | ❌ | ❌ | ❌ |

#### 5.3.2 可解比例估算

**算力无限下 CWE Top 25 可解比例**：
- 严格可解 (P=R=1): ~15/25 = **60%**
- 部分可解 (P=R=1 on formal subset): ~18/25 = **72%**
- 加上证明搜索辅助：~20/25 = **80%**
- 加上用户 spec 注入 (spec-driven audit): ~22/25 = **88%**

**整体 bug 全集**（包含 CWE Top 25 + 其他所有 bug 类型）:
- 算力无限下可解比例：~70-85%（取决于 spec 提供度）

### 5.4 受限场景下的强收敛

虽然全系统 100% 可解不可达，但在受限场景下，有限时间可解是可达的：

#### 5.4.1 受限场景 1: 内存安全子集 + 算力无限

**场景**: 仅验证内存安全类 bug (CWE-787, 416, 125, 476)

**条件**:
1. 形式化语义: VST for C (Appel et al.)
2. 形式化 spec: VST-C-predicates (pointer valid, memory safe)
3. 算力无限: 证明搜索可在有限时间完成

**结论**: 算力无限下有限时间可解，$P=R=1, H=0$ 在内存安全子集上成立。

#### 5.4.2 受限场景 2: 单函数 + spec-driven

**场景**: 用户提供 spec，验证单函数是否满足 spec

**条件**:
1. 形式化语义: VST Hoare logic
2. 算力无限: 证明搜索可在有限时间完成
3. User spec: 用户提供 Hoare 三元组 $\{P\}C\{Q\}$
4. 受限代码量: 单函数（~50 行）

**结论**: 算力无限下有限时间可解，$P=R=1, H=0$ 在该函数上成立。

#### 5.4.3 受限场景强收敛定理

**定理 (受限场景强收敛)**: 在受限场景 (formal subset + user spec) + 算力无限下, ADD L5 实现强收敛.

**条件**:
1. Spec 存在 (用户提供)
2. 证明存在 (Lean4 + VST): 对内存安全类 bug, VST 提供证明模板
3. 证明可构造 (算力无限): 证明搜索可找到证明
4. 类型检查 decidable: Lean4 类型检查 P=1, R=1
5. 开放集闭合 (受限场景): 在 formal subset 内, bug 模式是闭集

**结论**: $P_{L5}=R_{L5}=1, H_{L5}=0$.

### 5.5 算力无限下的工程可行性

| 场景 | 代码量 | 证明成本 | 算力无限下时间 | 可行性 |
|------|--------|---------|---------------|--------|
| 单函数 + user spec | ~50 行 | ~1-5 人天 | < 1 小时 | ✅ |
| 单模块 + user spec | ~5K 行 | ~5-50 人天 | < 1 天 | ✅ |
| seL4 级别 | 10K 行 | 20 人年 | ~1 个月 | ✅ |
| Linux kernel | 30M 行 | 不可承受 | ~100 年 (线性外推) | ❌ |

### 5.6 算力无限下的最终收敛行为

引入 Lean4 + 算力无限下, ADD 的收敛行为:

**在可形式化子集上**:
$$\lim_{n\to\infty} (P_n, R_n, H_n) = (1, 1, 0)$$

**在不可形式化子集上**:
$$\lim_{n\to\infty} (P_n, R_n, H_n) = (P^*, R^*, H^*) \text{ where } P^* < 1, R^* < 1, H^* > 0$$

**系统整体**:
$$\lim_{n\to\infty} (P_n, R_n, H_n) = (1 - \alpha) \cdot (1, 1, 0) + \alpha \cdot (P^*, R^*, H^*)$$

其中 $\alpha$ 为不可形式化子集占比 (估算 ~15-30%).

### 5.7 数值估算

假设:
- 可形式化子集占比: 75%
- 不可形式化子集占比: 25%
- 算力无限下, 可形式化子集 P=R=1, H=0
- 不可形式化子集: $P^* = 0.85, R^* = 0.85, H^* = 0.05$

则整体:
- $P = 0.75 \times 1 + 0.25 \times 0.85 = 0.9625$
- $R = 0.75 \times 1 + 0.25 \times 0.85 = 0.9625$
- $H = 0.75 \times 0 + 0.25 \times 0.05 = 0.0125$

引入 Lean4 + 算力无限下的稳态:

$$\boxed{\lim_{n\to\infty} (P_n, R_n, H_n) \approx (0.96, 0.96, 0.01)}$$

### 5.8 收敛行为总结

| 情境 | $P^*$ | $R^*$ | $H^*$ | 收敛类型 |
|------|-------|--------|--------|---------|
| 无 Lean4 (有界收敛) | 0.85 | 0.86 | 0.05 | Bounded |
| 引入 Lean4 (无算力无限) | 0.92 | 0.88 | 0.03 | Mixed |
| 引入 Lean4 + 算力无限 | **0.96** | **0.96** | **0.01** | **Mixed (formal→1, informal→bound)** |
| Lean4 + 算力无限 + user spec | 0.98 | 0.98 | 0.005 | **Near-1 (conditional)** |
| Full 1-convergence (理论极限) | 1.0 | 1.0 | 0.0 | Perfect |

### 5.9 算力无限能改变与不能改变的

**能改变**:
1. **证明搜索速度**: 从 EXPTIME-hard 到 polynomial (P=NP 假设), 或从 20 人年压缩到 1 个月 (seL4 案例)
2. **证明覆盖率**: 从人工证明的 ~50% 到算力无限下的 ~75-95% (可形式化子集内)

**不能改变**:
1. **信息论约束 (DPI)**: $R_{\text{ADD}} \leq R_{\text{SAST}} < 1$. 算力不能恢复已丢失的信息
2. **开放集问题**: bug 模式是开放的, 算力不能创造新 spec
3. **Gödel 不完备性**: 真但不可证命题存在, 算力不能突破不完备性
4. **Rice 定理**: 算力不能解决不可判定性
5. **反问题不可判定 (spec 综合反问题)**: 算力不能创造 spec
6. **EXPTIME-hard 证明搜索复杂度类**: 即使算力无限, 序列化步数仍指数

### 5.10 算力无限下 100% 可解的条件

要使 ADD L5 在算力无限下 100% 可解 (即 $P=R=1, H=0$ 对所有 bug 成立), 需要同时满足:

1. **Spec 完备性**: 所有真实 bug 都有形式化 spec
2. **证明存在性**: 所有 spec 都有 Lean4 证明
3. **证明可构造性**: 所有证明都能被算力无限下的搜索找到
4. **开放集闭合**: bug 模式集合是闭集 (无新 bug 模式)

**现实中这些条件同时满足的概率 = 0**, 因为:

1. 与 Rice 定理矛盾 (非平凡语义性质不可判定)
2. 与 Gödel 不完备性矛盾 (真但不可证命题存在)
3. 与反问题不可判定性矛盾 (spec 完备性不可判定)
4. 与开放集矛盾 (bug 模式是开放的)

### 5.11 本节小结

**引入 Lean4 + 算力无限下, 在受限场景下有限时间可解 ($P=R=1, H=0$), 但系统整体 100% 可解不可达**.

- 在受限场景 (formal subset + user spec) 下: ✅ 有限时间可解, 强收敛可达
- 在通用场景 (all bugs, real software) 下: ❌ 100% 有限时间可解不可达 (EXPTIME-hard + Rice + Gödel + open-set + DPI)
- **现实工程目标**: 受限场景强收敛 + 通用场景有界收敛到 $(0.96, 0.96, 0.01)$

---

## 6. 学术价值评估与文献综述

### 6.1 学术价值的三层定位

#### 6.1.1 价值层一：理论新贡献 — 有限

**已有经典结果**（非新贡献）：
- Rice 定理 (1953): 非平凡语义性质不可判定
- Cousot 抽象解释 (1977): soundness ↔ over-approximation
- Gödel 不完备性 (1931): 真但不可证命题存在
- DPI (Shannon 1948): 信息单调性

**结论**：不可达性论证本身不是新贡献，经典结果已覆盖。

#### 6.1.2 价值层二：桥梁性贡献 — 中等（真正价值所在）

**未被文献充分讨论的角度**：

1. **SAST 验证器的分层收敛分析**：文献多讨论单一 SAST 工具的 P-R 权衡，少有讨论"验证器+学习闭环+形式化层"的混合系统收敛行为

2. **DPI 在 SAST pipeline 中的应用**：将信息论 DPI 不等式应用于 `源代码 → SAST → 验证器` 数据流，得出 $R_{\text{ADD}} \leq R_{\text{SAST}} < 1$，这一论证在 SAST 文献中罕见

3. **Lean4 作为 SAST 后处理层**的可行性分析：文献多讨论 Lean4 用于数学证明或完整程序验证，少有讨论作为 SAST findings 的增强验证层

4. **"验证刚性 vs 覆盖完备性"区分**：文献多讨论 soundness/completeness，少有明确区分"已覆盖子集的确定性"和"覆盖子集的开放性"两个维度

#### 6.1.3 价值层三：工程指导贡献 — 较高

对 ADD 框架后续改进的具体指导（见 §6.4），这些指导基于跨学科论证，比纯工程经验更有理论基础。

### 6.2 相关研究映射

#### 6.2.1 不可达性理论（已有，可引用）

| 文献 | 核心结果 | 与当前讨论的关系 |
|------|---------|----------------|
| Rice 1953 | 非平凡语义性质不可判定 | L3 keyword 的 P 上界论证基础 |
| Cousot & Cousot 1977 | soundness ↔ over-approximation | L1-L4 sound/complete 权衡基础 |
| Turing 1936 | 停机问题不可判定 | 通用 SAST recall 上界基础 |
| Gödel 1931 | 不完备性 | Lean4 证明构造的局限性基础 |
| Shannon 1948 | DPI | SAST→ADD 信息流单调性基础 |
| Fano 1949/1961 | 错误概率下界 | 验证器误差下界基础 |

#### 6.2.2 形式化验证工业标杆（已有，可对比）

| 系统 | 性质 | 与 ADD 的对比 |
|------|------|--------------|
| ASTRÉE (Cousot) | 受限 C 子集上 P=1 | ADD 输入无约束，不可复制 |
| CompCert (Leroy) | 编译器语义保持性证明 | ADD 验证 findings，不是工具本身 |
| seL4 (Klein) | 10K 行功能正确性，20 人年 | ADD 处理百万行，成本不可承受 |
| VST (Appel) | C 程序 Hoare 逻辑验证 | 最接近 ADD L5 设想的系统 |

#### 6.2.3 LLM 辅助形式化验证（已有，2024-2026 快速发展）

| 系统 | Lean4/FormalMATH 成绩 | 对 ADD L5 的启示 |
|------|----------------------|-----------------|
| DeepSeek-Prover V2 (671B) | FormalMATH 28.31% (single-pass), 61.88% (tree-search) | 大模型+大算力仍 <30% 单次成功率 |
| Kimina-Prover 7B | FormalMATH 16.46% | 小模型能力有限 |
| Lean Copilot | IDE 内辅助证明 | 工程化集成参考 |

**关键数据点**：FormalMATH benchmark 显示，即使最强 LLM (DeepSeek-Prover V2 671B) 在 Lean4 上单次证明成功率仅 28.31%，tree-search 下 61.88%。这印证了"证明构造不可完全自动化"的判断。

#### 6.2.4 SAST 自改进/学习闭环系统（已有，可借鉴）

| 系统 | 机制 | 与 ADD 的关系 |
|------|------|--------------|
| Skwaq Gym (rysweet 2026) | 5 层架构 + 18 agents + 自改进循环 + overfitting-reviewer | 架构高度相似：Layer 3 "Multi-cycle convergence FP reduction" 与 ADD 学习闭环对应 |
| SAHOO (arXiv:2603.06333) | 递归自改进的对齐框架，含 drift detection、CAR frontier | 自改进系统的稳定性分析方法可借鉴 |
| Heckman 2016 | ML 分类 actionable SAST warnings | ADD 的 rule_suggester 是类似思路 |
| Kovalova 2025 | CodeBERT + CodeQL 混合，F1=0.86 | LLM+SAST 混合的实证数据 |
| BugLens (arXiv:2504.11711) | LLM + 约束回溯验证 | LLM 作为 SAST 增强层的工程参考 |

**关键发现**：Skwaq Gym 的架构（5 层 + 多 agent + 自改进循环 + overfitting-reviewer）与 ADD 高度相似，说明该架构方向有独立验证价值，但 Skwaq 未明确讨论收敛性极限。

#### 6.2.5 SAST 误差管理（已有，可引用）

| 文献 | 核心结论 | 与 ADD 的关系 |
|------|---------|--------------|
| GraphNode 2026 | FP 来源：未识别 sanitizer、不可行路径、框架保护、类型不精确 | ADD L3 keyword 匹配的 FP 来源分析 |
| Cousot 2003 (VMCAI) | "5% FP rate on 100K lines = several person-years"（industry estimate，具体引文未在原论文定位到，疑为二手转述） | ADD 学习闭环的 FP 治理价值 |
| Urban & Miné 2021 (arXiv:2104.02466) | 形式化方法应用于 ML 系统的综述 | ADD 扩展到 ML 验证的参考 |

### 6.3 价值评分矩阵

| 价值维度 | 评分 (1-5) | 理由 |
|---------|-----------|------|
| **理论新贡献** | 2/5 | 不可达性论证基于经典结果，非新定理 |
| **桥梁性贡献** | 4/5 | 跨学科映射（CS+信息论+SE）到 SAST 验证器，文献少见 |
| **工程指导** | 4/5 | 对 ADD 后续改进有具体可执行指导 |
| **文献空白填补** | 3/5 | "分层混合收敛"概念未被充分讨论，但 Skwaq 等系统已隐式实践 |
| **可发表性** | 3/5 | 可发中等期刊/会议，需强化理论贡献 |

### 6.4 对后续框架改进的指导

#### 6.4.1 短期改进（基于已有研究的工程借鉴）

| 改进方向 | 学术依据 | 预期收益 |
|---------|---------|---------|
| **LLM 辅助 FP 过滤** | Kovalova 2025: hybrid F1=0.86 vs rule-based 0.68 | P 从 0.75 → ~0.85 |
| **上下文敏感的 taint 分析** | GraphNode 2026: k-CFA 消除 call-site 合并 FP | P 进一步提升 |
| **Sanitizer 建模扩展** | GraphNode 2026: 未识别 sanitizer 是 FP 主因 | 减少误报 |
| **Overfitting reviewer** | Skwaq Gym: 拒绝 benchmark-specific heuristics (~66% rejection) | 防止学习闭环过拟合 |

#### 6.4.2 中期改进（基于形式化验证研究）

| 改进方向 | 学术依据 | 预期收益 |
|---------|---------|---------|
| **Lean4 L5 增强层（受限子集）** | VST: 内存安全类 bug 可形式化 | formal 子集 P=R=1 |
| **LLM 辅助证明构造** | DeepSeek-Prover V2: 28% single-pass | L5 证明构造率 ~30% |
| **Spec-driven audit** | Komarovsky 2026: "formally verified" 依赖人类 spec 提供 | 条件性 1 收敛 |
| **Sketch-then-prove** | 主流 AI proving 架构 | 提升证明搜索效率 |

#### 6.4.3 长期改进（基于不可能性结果的规避策略）

| 改进方向 | 学术依据 | 预期收益 |
|---------|---------|---------|
| **分层收敛明确定义** | SCT Trilemma | 避免"过度宣称"，明确论文 contribution |
| **DPI 约束的多 SAST 融合** | Shannon 1948 + 多源信息融合 | 突破单 SAST recall 上界 |
| **Active learning for spec** | 反问题不可判定性的工程规避 | 缩小开放集 |
| **形式化 impossibility theorem for ADD** | Rice + Cousot + DPI 的综合应用 | 论文理论贡献 |

### 6.5 可发表的论文方向

基于当前讨论，可形成以下论文：

**Paper 1: "Bounded Convergence in SAST Verification Pipelines: An Information-Theoretic Analysis"**
- 核心：DPI 应用于 SAST→验证器数据流，证明 $R_{\text{verifier}} \leq R_{\text{SAST}}$
- 新贡献：SAST pipeline 的信息论框架
- 目标：QF/MAFE 级别（方法论）

**Paper 2: "Hybrid Convergence: When Formal Verification Meets Heuristic SAST"**
- 核心：分层混合收敛模型（formal 子集强收敛 + informal 子集有界收敛）
- 新贡献："验证刚性 vs 覆盖完备性"区分
- 目标：ICSE/FSE 软件工程会议

**Paper 3: "The Verification Trilemma in Self-Improving SAST Systems"**
- 核心：扩展 SCT Trilemma 到 SAST 自改进系统
- 新贡献：自改进 SAST 的 trilemma 定理
- 目标：POPL/PLDI 编程语言会议（理论性较强）

### 6.6 需要避免的过度宣称

基于文献调研，论文中应避免：
1. ❌ "首次证明 SAST 验证器不能达到 100% recall"（Rice 定理已隐含）
2. ❌ "首次提出形式化验证的局限"（已有文献覆盖）
3. ✅ "首次将 DPI 应用于 SAST pipeline 的信息流分析"（文献未见）
4. ✅ "首次提出分层混合收敛模型"（文献未见明确形式化）
5. ✅ "首次将 SCT Trilemma 扩展到 SAST 自改进系统"（文献未见）

### 6.7 关键警示

**已有研究最接近的是 Skwaq Gym**（5 层架构 + 自改进循环），它独立验证了 ADD 架构方向的合理性，但也意味着 ADD 不是唯一探索此方向的系统。论文需明确区分 ADD 与 Skwaq 的差异：

- Skwaq: 18 agents + LLM 为主，无形式化验证层
- ADD: 4 层启发式 + 学习闭环 + (规划中) Lean4 形式化层

**ADD 的差异化优势在于"形式化验证层"的引入**，这正是 Skwaq 未覆盖的部分，也是当前讨论的核心价值。

### 6.8 大模型架构抑制幻觉的六条主线及与 ADD 的对应

2025-2026 年大模型架构层面抑制幻觉的研究已分化为六条主线，每一条都能在 ADD 框架中找到对应物。这一对标反向印证了 ADD 的方法论选择是"沿主流行进"而非边缘路径，同时也揭示了 ADD 的差异化定位。

#### 6.8.1 主线一：神经符号架构（Neuro-symbolic Verification）

**核心思路**：将 LLM 的生成与符号验证器解耦——LLM 负责"灵感生成"，符号系统负责"形式裁决"。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| Sigloch & Benzmüller 2026 (arXiv:2605.26942) | "可判定部分用符号方法 + 不可判定部分用神经语义相似度"的混合架构 | 与 §4 讨论的"形式化子集强收敛 + 非形式化子集有界收敛"几乎同构 |
| Ontology-Constrained Neural Reasoning (arXiv:2604.00555) | input-side / process-side / output-side 三层耦合模式，指出当前系统只约束输入不约束输出 | ADD Phase 3.5 verification gate 即 output-side 闭环的工程实例 |

**关键洞察**：Sigloch & Benzmüller 明确提出"可判定部分符号验证 + 不可判定部分神经验证"的分层架构，这与 §4.4 的混合收敛模型在哲学上完全一致。Ontology-Constrained 工作提出的"output-side coupling"概念，正是 ADD Phase 3.5 验证门的设计理念——不仅约束 LLM 输入（spec/context），更约束 LLM 输出（findings 必须通过源码验证）。该工作明确指出当前企业系统"只约束输入不约束输出"的局限，提议向 output-side 闭环演进——ADD 的 Phase 3.5 已实现了这一闭环。

#### 6.8.2 主线二：形式化验证内嵌（Lean4 / Coq + LLM）

**核心思路**：将形式证明器作为 LLM 推理的"裁决 oracle"，每一步生成都要通过形式验证。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| Safe (arXiv:2506.04592, Liu et al. 2025) | 首个将 Lean4 用于验证 LLM 自然语言推理步骤的工作，提出 FormalStep benchmark（30,809 条形式化陈述） | §4.2 讨论的 Lean4 强收敛路径的工程实例 |
| ProofNet++ (arXiv:2505.24230, Ambati 2025) | "验证器作为 RL 奖励函数"——LLM 生成证明树，符号验证器裁决，强化学习闭环优化 | 与 ADD 的 `history_threshold` RL 闭环同形 |
| HERMES (arXiv:2511.18760) | "多模块工具增强 agent + Lean4 验证"的混合架构 | ADD 5 阶段流水线 + 规划中 L5 层的同类设计 |

**关键洞察**：Safe 工作首次实现了"用 Lean4 验证 LLM 自然语言输出"的闭环，这正是 §4 讨论中 Lean4 强收敛路径的工程实例。ProofNet++ 的"verifier-as-reward"模式与 ADD 的 `history_threshold` RL 闭环同构——都是"用验证结果驱动参数调整"。区别在于 ProofNet++ 调整的是模型权重，ADD 调整的是验证阈值。

**实证数据点**：Safe 在多个数学推理数据集上显著提升性能，并提供可解释的形式化证据。这印证了 §4.5 的核心区分——引入形式化层改变的是"验证刚性"（从概率性到确定性），而非"覆盖完备性"。

#### 6.8.3 主线三：约束解码（Constrained Decoding）

**核心思路**：在解码阶段直接限制 LLM 输出空间，使其只能生成符合外部规则的 token。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| SciDC (arXiv:2604.06603, Ma et al. 2026) | 将领域知识自动转换为多层规则，在解码时强约束 LLM 生成，平均准确率提升 12% | 与 L3 验证中的 `min_keywords` 匹配在哲学上一致——都是"用外部规则限制生成空间" |

**关键洞察**：SciDC 是先验约束（生成时限制），ADD L3 是后验裁决（生成后验证）。两者是同一思路在不同阶段的实例。ADD 选择后验裁决的原因是：ADD 的验证对象是 SAST findings（已生成），不是 LLM 生成过程。但如果 ADD 未来扩展到"LLM 生成审计断言"场景，SciDC 的先验约束思路可借鉴——在 LLM 生成 finding 时就用 CWE 规则集约束其输出格式和关键词。

#### 6.8.4 主线四：确定性后处理（Deterministic Post-processing）

**核心思路**：放弃用 LLM 修复 LLM 的幻觉，改用确定性静态分析做后处理。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| Khati et al. 2026 (arXiv:2601.19106) | AST + 动态知识库的确定性框架，在 200 个 Python 片段上达到 P=100% / R=87.6% / F1=0.934，自动修复 77% 的幻觉 | 4-Level Verification 的同族工作——都用"确定性静态分析"作为 LLM 幻觉的最终裁决 |

**关键洞察**：Khati 2026 明确论证"确定性后处理优于概率性修复"，与 ADD 不信任 LLM 自我校验的设计哲学同源。该工作在 Python API 幻觉检测上达到 P=100%，印证了 §3.4.1 ASTRÉE 案例的启示——确定性验证在受限域可达 P=1。

**与 ADD 的差异**：Khati 验证的是 LLM 生成的代码（API 调用、标识符），ADD 验证的是 SAST findings（漏洞断言）。ADD 的验证对象更抽象，但方法论同构——都是"用确定性静态分析裁决 LLM 输出，不信任 LLM 自评"。

#### 6.8.5 主线五：不确定性量化（Uncertainty Quantification, UQ）

**核心思路**：让模型"知道自己不知道"，用置信度信号触发拒绝回答或外部验证。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| MIT Total Uncertainty (Hamidieh et al. 2026-03, OpenReview id=lOoRJo8xWy) | aleatoric + epistemic 联合度量，用跨模型分歧估计 epistemic uncertainty，比传统 self-consistency 更可靠识别"confident but wrong" | 三 tier 降级（Joern vs AST vs regex）的分歧度可作为 epistemic uncertainty 信号 |
| Uncertainty-Calibrated Fine-Tuning (arXiv:2412.02904, Krishnan et al. ICLR 2026 Workshop) | 基于决策论的 uncertainty-aware CLM loss，改善 LLM 校准 | `history_threshold` 是类似的校准机制，但作用于验证阈值而非模型权重 |
| 46 UE Methods Evaluation (arXiv:2605.27016) | 系统评估 46 种不确定性估计方法，结论："没有任何 UE 方法是通用可靠的幻觉信号，必须按任务验证" | 从反面支持 ADD 不依赖单一置信度、强制走 4-level 源码验证的设计 |

**关键洞察**：46 UE Methods Evaluation 的结论——"没有任何 UE 方法是通用可靠的幻觉信号"——从反面支持了 ADD 的设计选择：不依赖单一置信度阈值，而是强制走 4-level 源码验证。ADD 的策略是"不信任模型自评，只信任源码证据"，这与 UQ 路线互补——UQ 提供"何时该怀疑"的信号，ADD 提供"如何确认"的机制。

**潜在增强**：MIT Total Uncertainty 的"跨模型分歧估计 epistemic uncertainty"思路可直接移植到 ADD——在 `verify_findings.py` 中增加"跨验证器分歧度"字段（Joern CPG vs AST CFG vs regex 三 tier 的结果分歧），分歧大的 finding 自动降级。这是低成本增强 L4 的方式。

#### 6.8.6 主线六：元认知反馈强化学习（Metacognitive RL）

**核心思路**：把"模型对自己判断的质量"作为 RL 奖励信号，倒逼模型诚实表达不确定性。

| 文献 | 核心贡献 | 与 ADD 的对应 |
|------|---------|--------------|
| RLMF (Liu et al. 2026-06, Yale/Google Research, arXiv:2606.32032) | 元认知反馈驱动偏好优化，相比标准 RL (GRPO) 在忠实校准任务上提升至 63%；被 COLM 2026 接收 | `rule_suggester` 消费 `hallucination_log` 生成反例规则的闭环同构 |

**关键洞察**：RLMF 的"用模型对自己判断的质量作为 RL 奖励"与 ADD 的"用 `hallucination_log` 驱动 `rule_suggester` 生成反例规则"在闭环结构上同构——都是"用历史错误反推规则"。区别在于 RLMF 调整模型权重（训练时），ADD 调整验证规则集（推理时）。RLMF 通过元认知反馈让模型学会"诚实表达不确定性"的机制启示 ADD 可引入"拒绝验证"机制——当 finding 的 L3/L4 验证分歧过大时，标记为"拒绝裁决"而非强行通过/否决（注：原文具体的拒绝率/F1 提升数字因论文实验章节未完全公开，此处不引用具体百分比）。

#### 6.8.7 六条主线的统一视角

六条主线可归为三个层次：

| 层次 | 主线 | 核心机制 | ADD 对应 |
|------|------|---------|---------|
| **生成时控制** | 约束解码 | 先验限制输出空间 | L3 `min_keywords`（后验版） |
| **生成后验证** | 神经符号架构、形式化验证内嵌、确定性后处理 | 后验裁决输出正确性 | 4-Level Verification + 规划中 L5 Lean4 |
| **闭环学习** | 不确定性量化、元认知 RL | 用历史错误驱动改进 | `hallucination_log → rule_suggester → history_threshold` |

**统一观察**：六条主线都在解决"LLM 生成的幻觉"，ADD 在解决"LLM-as-auditor 的幻觉"——即审计器自身的幻觉。这是更狭窄但更未被充分研究的问题。学术上对应 Khati 2026 的"用确定性分析裁决 LLM 输出"思路，但 ADD 把这套思路反向用在审计 LLM 自身上。

#### 6.8.8 ADD 的差异化定位

| 维度 | 主流 LLM 架构工作 | ADD 框架 |
|------|------------------|---------|
| **验证对象** | 自然语言陈述、数学证明、代码生成 | SAST findings + 自身审计断言 |
| **验证方法** | 单一方法（形式化/UQ/RAG） | 4-Level 分层降级 + 三 tier 防崩溃 |
| **闭环反馈** | 多为单轮或 RL 训练时 | `hallucination_log → rule_suggester → history_threshold` 跨周期工程闭环 |
| **幻觉定义** | 生成内容与事实不符 | 审计断言与源码不符 |

ADD 的独特性在于：**主流工作大多在解决"LLM 生成的幻觉"，ADD 在解决"LLM-as-auditor 的幻觉"**——即审计器自身的幻觉。这是更狭窄但更未被充分研究的问题域。六条主线中，Khati 2026 的确定性后处理与 ADD 最为同构，但 Khati 验证的是代码 API 调用，ADD 验证的是漏洞断言——后者的语义复杂度更高。

#### 6.8.9 "审计器自审 vs 生成器自审"差异的价值分析

"审计器自审 vs 生成器自审"看似只是场景切换，实则是**问题结构的根本改变**，价值体现在四个层面。

##### 6.8.9.1 问题结构差异：为何"审计器自审"更难也更值

| 维度 | 生成器自审（主流） | 审计器自审（ADD） |
|------|------------------|------------------|
| **幻觉来源** | 模型参数中的错误知识 | 模型对**外部代码**的错误推断 |
| **ground truth** | 人类标注 / 事实库 | 源码本身（可机械验证） |
| **验证闭环** | 模型 → 模型自评 → 输出 | 模型 → **源码裁决** → 输出 |
| **错误放大链** | 单层（生成即终结） | 双层（生成幻觉 + 验证幻觉） |

**关键差异**：生成器自审的幻觉是"模型说错了"，审计器自审的幻觉是"模型以为别人说错了，其实别人没错"。后者多了一层**反事实嵌套**——审计器不仅可能漏判真实 bug（FN），还可能**虚构不存在的 bug**（FP-from-hallucination），这是主流 LLM 幻觉研究中未被充分讨论的错误类型。

##### 6.8.9.2 学术价值：填补三个研究空白

**空白一：LLM-as-Judge 的幻觉问题**

2024-2026 年 LLM-as-Judge 已成为评估主流（MT-Bench, Arena Hard, CRITIC），但几乎所有 LLM-as-Judge 工作都假设"被评估对象是 LLM 输出"。ADD 场景下，被评估对象是 SAST findings（符号系统输出），judge 是 LLM——这是**异构系统间的裁决**，文献覆盖极少。

**空白二：跨符号系统验证器的收敛性分析**

主流 SAST 验证工作（如 Khati 2026）验证 LLM 生成的代码，验证器和被验证对象**同质**（都是神经/符号系统）。ADD 验证 SAST findings，是 **LLM 验证符号系统**——这种异构验证的误差传播特性未被系统研究。

**空白三：审计器 FP 与 FN 的不对称成本**

| 错误类型 | 生成器场景 | 审计器场景 |
|---------|-----------|-----------|
| FP（误报） | 用户困扰，成本可控 | **修复基线被污染**，下游投入无效工程 |
| FN（漏报） | 信息缺失 | **真实漏洞遗留**，安全风险 |

审计器场景下 FP 和 FN 的成本严重不对称——FN 的代价是安全事件，FP 的代价是工程浪费。这种不对称性在生成器幻觉研究中基本不存在，需要专门的收敛性框架（这正是 §2-§5 的价值所在）。

##### 6.8.9.3 工程价值：解决"谁验证验证者"的古老问题

"Quis custodiet ipsos custodes?"（谁监督监督者）是软件工程千年难题。现有答案有三：

1. **形式化验证**（seL4, CompCert）：成本极高，仅限小规模
2. **多工具交叉**（CodeQL + Semgrep）：工具间误报模式相关，交叉收益递减
3. **人工 review**：不可扩展

ADD 提供了第四种答案：**用 LLM 审计 + 源码验证闭环**。这填补了"形式化验证太贵、多工具交叉饱和、人工不可扩展"之间的空白带。具体价值：

- **成本曲线**：形式化验证 $O(n^2)$（n=代码量），ADD 的 4-Level 验证 $O(n \cdot k)$（k=keyword 数），在百万行级代码上成本可承受
- **可扩展性**：多 SAST 融合 + LLM 推理 + 源码裁决的流水线可水平扩展
- **可审计性**：`hallucination_log` 提供完整的审计轨迹，这是 LLM 单次推理无法提供的

##### 6.8.9.4 方法论价值：从"信任 LLM"到"约束 LLM"

主流 LLM 幻觉抑制工作的隐含假设是**"让 LLM 更可信"**——通过 RLHF、约束解码、形式化验证等手段提升单次输出可靠性。ADD 的隐含假设是**"不信任 LLM 任何单次输出，但信任闭环迭代后的稳态"**。

这是两种截然不同的可靠性哲学：

| 哲学 | 主流 | ADD |
|------|------|-----|
| 信任单位 | 单次输出 | 闭环稳态 |
| 验证方式 | 内部（模型自评） | 外部（源码裁决） |
| 失败模式 | 单次错即错 | 单次错被闭环修正 |
| 收敛依赖 | 模型能力提升 | 闭环设计正确 |

ADD 的方法论价值在于：**它证明了"不提升模型能力，仅靠闭环设计"也能达到有界收敛**。这对算力受限、模型不可控的场景（如私有化部署、离线审计）有直接工程意义。

##### 6.8.9.5 差异化价值总结

ADD 把 LLM 幻觉研究从"如何让 LLM 说真话"推进到"如何让 LLM 审计时不撒谎"——后者是 LLM-as-Judge 时代的核心安全问题，但文献覆盖极少。具体价值四点：

1. **学术**：填补 LLM-as-Judge 异构验证、不对称成本、审计器收敛性三个空白
2. **工程**：填补形式化验证（太贵）与多工具交叉（饱和）之间的成本带
3. **方法论**：证明"闭环设计"可替代"模型能力提升"实现有界收敛
4. **商业**：在 SAST 工具同质化竞争中提供"验证器"差异化定位

#### 6.8.10 对 ADD 框架的工程启示

基于六条主线的对标，ADD 有三个可借鉴的改进方向：

**方向一：引入 epistemic uncertainty 信号**（借鉴 MIT Total Uncertainty）

在 `verify_findings.py` 中对每个 finding 增加"跨验证器分歧度"字段（Joern vs AST vs regex 三 tier 的结果分歧），分歧大的 finding 自动降级。这是低成本增强 L4 的方式，不需要引入新依赖，只需在现有三 tier 降级逻辑中增加分歧度计算。

**方向二：claim 子句级验证**（借鉴 Safe 的 step-aware 思路）

将 L4 structural verification 从"整 finding 验证"细化为"claim 子句级验证"。当前 `classify_claim()` 已能将 claim 分类为 missing/wrong/violates/dead_code/import_related 五类，可进一步将每类 claim 拆分为可形式化的子断言分别裁决。这与 Khati 2026 的 AST 节点级验证同形。

**方向三：verifier-as-reward 细粒度 RL**（借鉴 ProofNet++）

当前 ADD 的 `history_threshold` 是基于 P/R 趋势的粗粒度 RL（▲→0.55, ▼→0.85），可考虑将 `verify_l4_structural` 的通过率作为更细粒度的 reward signal，驱动 threshold 自适应。具体而言，可按 CWE category 分别追踪 L4 通过率，对通过率低的 category 自动提高 threshold（更严格），对通过率高的 category 自动降低 threshold（更宽松）。

#### 6.8.11 本节小结

ADD 框架并非孤立工作。它的核心方法论——**分层降级验证 + 闭环反例学习 + 形式化强收敛子集**——在 2025-2026 年的神经符号 AI、形式化验证、不确定性量化三条主流研究线上都能找到同族工作。ADD 的差异化在于把这套方法论用在"审计器自审"这个更冷门但工程价值更高的场景上。

六条主线的调研同时印证了 §6.1.2 的桥梁性贡献评估：ADD 的学术价值不在于发明新方法，而在于将六条主线的方法论**综合应用于 SAST 验证器**这一未被充分研究的交叉域。§6.8.9 进一步从问题结构、学术、工程、方法论四个维度论证了"审计器自审 vs 生成器自审"差异的价值——ADD 把 LLM 幻觉研究从"如何让 LLM 说真话"推进到"如何让 LLM 审计时不撒谎"，填补了 LLM-as-Judge 异构验证、不对称成本、审计器收敛性三个研究空白。三个工程启示（epistemic uncertainty 信号、claim 子句级验证、verifier-as-reward 细粒度 RL）可作为 ADD v3.0+ 的改进候选方向。

### 6.9 与 Macaron-V1 自适应 LoRA 架构的对比

Macaron-V1（Mind Lab，2026-07-21 发布，arXiv:2608.09819）是当前开源社区最具代表性的"自适应 LoRA 架构"——Mixture-of-LoRA (MoL) 在冻结的 GLM-5.2 (744B) 基座上挂载 4 个 1B LoRA 专家（Chat/Agent/Coding/GenUI），通过 L0 路由器按用户轮次选择专家，配合递归自我改进（RSI）实现持续学习。它与 ADD 框架的能力沉淀机制看似都在解决"系统如何从经验中成长"，但代表的是两条根本不同的技术路线——连接主义参数化沉淀 vs 符号主义规则化沉淀。

#### 6.9.1 核心机制对比

| 维度 | Macaron-V1 (MoL) | ADD 框架 |
|------|------------------|---------|
| **能力沉淀载体** | LoRA 适配器（参数化，权重级） | 规则集 + 阈值参数（符号化，规则级） |
| **基座处理** | 冻结 GLM-5.2 (744B)，不动基座 | 不修改验证器核心，只增规则 |
| **专业化方式** | 按任务域分 4 个 LoRA (Chat/Agent/Coding/GenUI) | 按验证层级分 4-Level + 按 claim 类型分 5 类 |
| **学习信号** | 经验（experience）驱动 RL | 错误（hallucination_log）驱动规则生成 |
| **评估契约** | Harness Context Protocol（版本化） | 源码本身（4-Level 验证） |
| **闭环结构** | experience → 评估 → model-harness pair 更新 | hallucination_log → rule_suggester → threshold |
| **成本** | ~10% 全参数微调（但仍需万亿参数级算力） | 近零（Python 标准库实现） |
| **ground truth** | benchmark (LivingBench/ChatBench) | 源码行号（可机械验证） |

#### 6.9.2 本质同构：闭环驱动能力增长

两者在顶层设计上高度同构——都遵循"**不修改核心 + 模块化能力 + 闭环驱动增长**"的原则：

| 同构点 | Macaron | ADD |
|--------|---------|-----|
| 核心冻结 | GLM-5.2 基座冻结 | verify_findings.py 核心逻辑不变 |
| 模块化能力 | LoRA 即插即用 | 规则集即插即用 |
| 外部契约评估 | Harness Context Protocol | 4-Level 源码验证 |
| 闭环迭代 | RSI (递归自我改进) | hallucination_log → rule_suggester |
| 持续学习 | 新 LoRA 不影响旧能力 | 新规则不影响旧验证 |

**深层共识**：两者都认识到"集中训练 → 冻结部署"的局限，都把"部署后的经验/错误"作为能力增长燃料。这是 Sutton & Silver 2025《Welcome to the Era of Experience》一文在工程侧的共鸣。

#### 6.9.3 本质差异：连接主义 vs 符号主义

| 差异维度 | Macaron（连接主义路线） | ADD（符号主义路线） |
|---------|----------------------|---------------------|
| **知识编码** | 隐性（权重） | 显性（规则文本） |
| **可解释性** | 低（LoRA 权重难解读） | 高（每条规则可读） |
| **泛化能力** | 强（大基座提供语义泛化） | 弱（规则只匹配特定模式） |
| **验证确定性** | 概率性（benchmark 评估） | 确定性（源码裁决） |
| **算力依赖** | 重（即使 LoRA 也要 744B 基座） | 轻（标准库实现） |
| **遗忘风险** | 存在（LoRA 间共享基座） | 不存在（规则只增不删） |
| **可组合性** | LoRA 间通过摘要共享 | 规则间通过 JSON 合并 |

**关键差异点**：Macaron 的能力沉淀在权重里，人看不懂但模型能用；ADD 的能力沉淀在规则里，人能读懂但无语义泛化。这是 AI 两条根本路线的缩影。

#### 6.9.4 优劣对比

##### Macaron 的优势

1. **隐性知识编码**：LoRA 能捕捉"难以言传"的任务模式（如 Coding 专家学到的不只是语法，还有调试直觉）
2. **强泛化**：GLM-5.2 基座提供跨域语义理解，新任务无需重写规则
3. **多模态原生**：GenUI 专家直接生成可视化界面，ADD 无此能力
4. **工业级规模验证**：在 SWE Verified (85.6)、TerminalBench (87.6)、UI4ABench (87.8) 等基准上对标 GPT-5.5

##### Macaron 的劣势

1. **评估黑箱**：benchmark 评分仍需人工设计 rubric，LivingBench 本身"持续演化"意味着 ground truth 不稳定
2. **路由 upfront 选择**：L0 路由器在每轮开始时选定 LoRA，单轮内不能切换——跨域任务（如"审计代码并生成报告"）会受限
3. **算力门槛**：即使 LoRA 是全参数的 10%，744B 基座的 10% 仍是数十亿参数级，私有化部署困难
4. **幻觉无显式抑制**：Macaron 通过 LoRA 隔离减少跨任务干扰，但没有显式的 hallucination_log 机制——错误经验可能被 RL 强化

##### ADD 的优势

1. **确定性裁决**：每条 finding 可溯源到源码行号，P=1 在受限域可达（参考 §3.4.1 ASTRÉE 案例）
2. **零算力成本**：Python 标准库实现，可在任何环境运行
3. **显式幻觉抑制**：hallucination_log 记录每次验证失败，rule_suggester 消费失败生成反例规则——错误不会被强化
4. **规则只增不删**：符号化规则无遗忘风险，历史规则永久可审计
5. **基座无关**：可接入任意 SAST 工具（Semgrep/CodeQL/Joern），不依赖特定模型

##### ADD 的劣势

1. **无语义泛化**：规则只匹配特定关键词模式，不能理解"语义相似但措辞不同"的 claim
2. **依赖外部 findings**：ADD 不生成 finding，只验证 finding——能力边界由上游 SAST 决定
3. **专业域窄**：仅 SAST 验证，不能扩展到代码生成、UI 渲染等任务
4. **规则爆炸风险**：随着 claim 类型增长，规则集可能膨胀，维护成本上升

#### 6.9.5 关键洞察：两者解决的是不同问题

| 问题 | Macaron 的回答 | ADD 的回答 |
|------|---------------|-----------|
| **"模型如何变得更聪明"** | LoRA 专家化 + RSI 持续学习 | 不回答（ADD 不追求聪明） |
| **"模型如何知道自己没错"** | benchmark 评估（概率性） | 4-Level 源码验证（确定性） |
| **"能力如何沉淀不遗忘"** | LoRA 隔离 + 冻结基座 | 规则集只增不删 |
| **"新经验如何融入系统"** | RL 更新 LoRA 权重 | hallucination_log 生成新规则 |

**核心洞察**：Macaron 解决的是"**模型能力增长**"问题，ADD 解决的是"**验证器准确性增长**"问题。两者并非竞争关系，而是互补关系——Macaron 式模型可以作为 ADD 的上游 finding 生成器，ADD 为 Macaron 式模型提供源码级验证闭环。

#### 6.9.6 ADD 可借鉴的三个方向

**方向一：LoRA 式 claim 类型专业化**

Macaron 按"任务域"分 LoRA，ADD 已按"claim 类型"分 5 类（missing/wrong/violates/dead_code/import_related）。可进一步为每类 claim 配置独立的验证规则集 + 独立的 `history_threshold`，实现"claim 类型级 LoRA"——不同 claim 类型有不同的严格度和学习节奏。

**方向二：版本化 model-harness pair**

Macaron 的"versioned model-harness pair"理念可移植到 ADD：每次 `history_threshold` 调整都生成一个版本化的"阈值-规则集"快照，带明确的评估契约（benchmark 指标）。这样可回溯任何历史版本的验证行为，而非只有一个不断覆盖的 `history_threshold` 值。

**方向三：Harness Context Protocol 式的验证器互操作**

Macaron 定义了 Harness Context Protocol 使模型与 harness 可组合。ADD 可定义类似的"验证上下文协议"，使不同验证器（Joern/AST/regex）间不仅能降级，还能**组合**——例如 Joern 验证结构 + AST 验证语义 + regex 验证关键词，三者结果加权融合而非单线降级。

#### 6.9.7 Macaron 可借鉴 ADD 的两个方向

**方向一：源码级 ground truth**

Macaron 的 benchmark 评估（LivingBench/ChatBench）仍需人工设计 rubric，ground truth 不稳定。在 Coding 专家的训练中，可引入 ADD 式的源码级验证——用确定性静态分析裁决代码生成正确性，而非仅依赖 benchmark 分数。

**方向二：显式 hallucination_log**

Macaron 的 RL 闭环没有显式记录"哪些经验是幻觉"。引入 ADD 式的 hallucination_log，在 RL 训练中显式标记错误经验，可防止错误经验被 RL 强化——这是 Macaron 当前架构的潜在风险点。

#### 6.9.8 一句话总结

Macaron 和 ADD 代表了能力沉淀的两条根本路线：**参数化沉淀（连接主义，权重编码，强泛化但弱可解释）vs 符号化沉淀（符号主义，规则编码，强可解释但弱泛化）**。两者在"闭环驱动增长"的顶层设计上高度同构，但在知识编码、评估确定性、算力成本上截然相反。ADD 的差异化价值在于：**用零算力的符号化闭环，在 SAST 验证这一窄域上达到了 Macaron 式参数化学习无法触及的确定性裁决**——这正是 §6.8.9 论证的"审计器自审"场景的核心需求。

Macaron 与 ADD 并非竞争关系，而是互补关系：Macaron 式模型可作为 ADD 的上游 finding 生成器，ADD 为 Macaron 式模型提供源码级验证闭环。两者的结合点——用参数化模型生成 + 符号化验证器裁决 + 双向闭环学习——是下一代"可信赖 AI 代码审计系统"的可能形态。

---

## 7. 结论

### 7.1 综合结论

本报告通过七个层面的系统分析，得出以下综合结论：

#### 7.1.1 当前框架（v2.8）不可达 1 收敛

由 Rice 定理、DPI、开放集问题共同决定，这是结构性约束而非工程性不足：

$$\lim_{n\to\infty} (P_n, R_n, H_n) = (P^*, R^*, H^*) \approx (0.85, 0.86, 0.05)$$

#### 7.1.2 引入 Lean4 后变为分层混合收敛

可形式化子集上强收敛可达，但系统整体仍不可达 1 收敛：

$$\lim_{n\to\infty} (P_n, R_n, H_n) \approx (0.92, 0.88, 0.03)$$

#### 7.1.3 算力无限下受限场景强收敛可达

在 formal subset + user spec 条件下，有限时间可解：

$$\lim_{n\to\infty} (P_n, R_n, H_n) \approx (0.96, 0.96, 0.01)$$

但系统级 100% 可解不可达（EXPTIME-hard + Rice + Gödel + open-set + DPI）。

#### 7.1.4 有学术价值

主要是桥梁性贡献（跨学科映射到 SAST 验证器架构）和工程指导贡献，非新定理贡献。

#### 7.1.5 与主流 LLM 幻觉抑制研究高度同构

2025-2026 年大模型架构抑制幻觉的六条主线（神经符号架构、形式化验证内嵌、约束解码、确定性后处理、不确定性量化、元认知 RL）均能在 ADD 中找到对应物。ADD 的差异化在于将这套方法论用于"审计器自审"而非"生成器自审"——这是更冷门但工程价值更高的场景。"审计器自审 vs 生成器自审"的差异价值体现在四点：填补 LLM-as-Judge 异构验证、不对称成本、审计器收敛性三个学术空白；填补形式化验证（太贵）与多工具交叉（饱和）之间的工程成本带；证明"闭环设计"可替代"模型能力提升"实现有界收敛；在 SAST 工具同质化竞争中提供"验证器"差异化定位。三个工程启示（epistemic uncertainty 信号、claim 子句级验证、verifier-as-reward 细粒度 RL）可作为 ADD v3.0+ 改进方向。

#### 7.1.6 与 Macaron-V1 自适应 LoRA 架构互补

Macaron-V1（MoL 架构）与 ADD 代表能力沉淀的两条根本路线：参数化沉淀（连接主义，权重编码，强泛化但弱可解释）vs 符号化沉淀（符号主义，规则编码，强可解释但弱泛化）。两者在"闭环驱动增长"的顶层设计上高度同构（核心冻结 + 模块化能力 + 闭环迭代），但在知识编码、评估确定性、算力成本上截然相反。ADD 的差异化价值在于用零算力的符号化闭环，在 SAST 验证窄域上达到 Macaron 式参数化学习无法触及的确定性裁决。两者并非竞争而是互补：Macaron 式模型作为上游 finding 生成器，ADD 为其提供源码级验证闭环——这是下一代"可信赖 AI 代码审计系统"的可能形态。ADD 可借鉴 Macaron 的 claim 类型级 LoRA 专业化、版本化 model-harness pair、Harness Context Protocol 式验证器互操作三个方向。

### 7.2 框架的真实价值

**框架的真实价值不在于"收敛到 1"，而在于"以可审计的方式量化不确定性"** — 即精确测量"我们在多大程度上应该相信这个 finding"。

这与"建设性的怀疑主义者"身份一致：ADD 回答的是"你怎么知道你知道"，不是"让你知道一切"。

### 7.3 对论文写作的建议

1. **明确区分三层收敛**：layer-specific / domain-specific / system-level
2. **引用 ASTRÉE/CompCert/seL4 作为"条件性 1 收敛"的标杆**
3. **形式化陈述混合收敛定理**：formal 子集 → 1 + informal 子集 → $P^* < 1$
4. **诚实承认 DPI 约束**：即使有 Lean4，$R \leq R_{\text{SAST}}$
5. **强调"验证刚性"概念**：这是 Lean4 引入的质变，不是量的提升
6. **诚实承认 EXPTIME-hard 证明搜索是结构性问题**：算力无限能压缩时间，不能改变复杂度类
7. **引用 Skwaq Gym 作为架构独立验证**：避免被审稿人指出"已有类似系统"
8. **强化 Lean4 L5 的差异化**：这是 ADD 相对 Skwaq 的核心优势

### 7.4 最终回答

**当前框架在多轮审计下不能实现 1 概率收敛，这是由 Rice 定理、数据处理不等式、抽象解释框架共同决定的结构性约束。**

引入 Lean4 后，情况从"全概率收敛到 < 1 稳态"变为"混合收敛：formal 子集强收敛 + informal 子集有界收敛"。这是质的提升，但不是 1 收敛。

即使在算力无限假设下，受限场景（formal subset + user spec）下有限时间可解（$P=R=1, H=0$），但系统整体 100% 可解不可达。

真正的 1 收敛只在**用户提供 spec + spec 覆盖范围内**成立，这与 spec-driven audit 方向一致。

---

## 8. 参考文献

### 8.1 经典理论

1. Rice, H.G. (1953). "Classes of Recursively Enumerable Sets and Their Decision Problems". *Transactions of the American Mathematical Society*, 74(2), 358-366.
2. Cousot, P. & Cousot, R. (1977). "Abstract Interpretation: A Unified Lattice Model for Static Analysis of Programs by Construction or Approximation of Fixpoints". *POPL 1977*, 238-252.
3. Turing, A.M. (1936). "On Computable Numbers, with an Application to the Entscheidungsproblem". *Proceedings of the London Mathematical Society*, 42, 230-265.
4. Gödel, K. (1931). "Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I". *Monatshefte für Mathematik und Physik*, 38, 173-198.
5. Shannon, C.E. (1948). "A Mathematical Theory of Communication". *Bell System Technical Journal*, 27, 379-423, 623-656.
6. Fano, R.M. (1949). *The Transmission of Information*. MIT Research Laboratory of Electronics Technical Report No. 65. (后正式出版为 Fano, R.M. (1961). *Transmission of Information: A Statistical Theory of Communications*. MIT Press.)
7. Freeman, T. & Pfenning, F. (1991). "Refinement Types for ML". *PLDI 1991*, 26-35.
8. Necula, G.C. (1996). "Proof-Carrying Code". *POPL 1997*, 106-119.
9. Reps, T., Horwitz, S. & Sagiv, M. (1995). "Precise Interprocedural Dataflow Analysis via Graph Reachability". *POPL 1995*, 49-61.
10. Nielson, F., Nielson, H.R. & Hankin, C. (1999). *Principles of Program Analysis*. Springer.

### 8.2 形式化验证工业标杆

11. Cousot, P. et al. (2005). "The ASTREE Analyzer". *ESOP 2005*, 21-30.
12. Leroy, X. (2009). "Formal Verification of a Realistic Compiler". *Communications of the ACM*, 52(7), 107-115.
13. Klein, G. et al. (2009). "seL4: Formal Verification of an OS Kernel". *SOSP 2009*, 207-220.
14. Appel, A.W. et al. (2014). "Program Logics for Certified Compilers". *Cambridge University Press*.
15. Jung, R. et al. (2018). "Iris from the ground up: A modular foundation for higher-order concurrent separation logic". *JFP*, 28, e20.

### 8.3 LLM 辅助形式化验证

16. DeepSeek-Prover V2 (2025). FormalMATH Benchmark results.
17. Kimina-Prover (2025). FormalMATH Benchmark results.
18. Lean Copilot (2024). LLM-assisted theorem proving in Lean4.
19. Bayazıt, A. et al. (2025). "LLM-assisted formal verification in Rocq: a case study". arXiv:2508.18587.
20. FormalMATH Benchmark (2025). https://spherelab.ai/FormalMATH/

### 8.4 SAST 自改进系统

21. Skwaq Gym (rysweet, 2026). GitHub repository. https://github.com/rysweet/skwaq/issues/28
22. SAHOO (2026). "Recursive self-improvement alignment framework". arXiv:2603.06333.
23. Heckman, S. (2009). "A model-based approach to classifying actionable static analysis warnings". *ICST 2009* (IEEE International Conference on Software Testing, Verification and Validation).
24. Kovalova, A. (2025). "CodeBERT + CodeQL hybrid for SAST false positive reduction". F1=0.86.
25. BugLens (2025). "LLM + constraint backtracking for bug verification". arXiv:2504.11711.

### 8.5 SAST 误差管理

26. GraphNode Software (2026). "Reducing False Positives in SAST". https://www.graphnodesoftware.com/blog/reducing-false-positives-sast
27. Urban, C. & Miné, A. (2021). "A Survey of Formal Methods Applied to Machine Learning". arXiv:2104.02466.
28. Cousot, P. (2003). "Verification by Abstract Interpretation". *VMCAI 2003*.

### 8.6 不可达性与对齐理论

29. Komarovsky (2026). "Correspondence Regress in Formal Verification". vixra:2604.0119. **(注：vixra.org 为非同行评审平台，本引用仅为补充参考，论点需另寻同行评审来源支撑)**
30. Gumbau Mezquita, J. (2026). "Structural Unverifiability of AGI Alignment". arXiv:2606.28639.
31. Panigrahy, R. & Sharan, M. (2026). "Impossibility of Accuracy + Trust + Human-level Reasoning". arXiv:2509.21654.

### 8.7 ADD 框架文档

32. ADD Framework v2.8 Implementation Spec. `docs/superpowers/specs/2026-08-12-v2.8-implementation-spec.md`
33. ADD Framework v2.8 Short-term Improvements. `docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md`
34. ADD v2.8 Acceptance Audit Report. `docs/audit-log/2026-08-12-v2.8-acceptance-audit-report.md`
35. ADD Framework Review & Gap Analysis. `docs/audit/2026-08-12-framework-review-and-gap-analysis.md`

### 8.8 大模型架构抑制幻觉研究（§6.8 引用）

36. Sigloch, P. & Benzmüller, C. (2026). "Neuro-Symbolic Verification of LLM Outputs for Data-Sensitive Domains". arXiv:2605.26942.
37. Luong Tuan, T. & Sanyal, A. (2026). "Ontology-Constrained Neural Reasoning in Enterprise Agentic Systems: A Neurosymbolic Architecture for Domain-Grounded AI Agents". arXiv:2604.00555.
38. Liu, C. et al. (2025). "Safe: Enhancing Mathematical Reasoning in Large Language Models via Retrospective Step-aware Formal Verification". arXiv:2506.04592.
39. Ambati, M. (2025). "ProofNet++: A Neuro-Symbolic System for Formal Proof Verification with Self-Correction". arXiv:2505.24230.
40. HERMES (2025). "Towards Efficient and Verifiable Mathematical Reasoning in LLMs". arXiv:2511.18760.
41. Ma, M. et al. (2026). "Scientific Knowledge-driven Decoding Constraints Improving the Reliability of LLMs (SciDC)". arXiv:2604.06603.
42. Khati, D. et al. (2026). "Detecting and Correcting Hallucinations in LLM-Generated Code via Deterministic AST Analysis". arXiv:2601.19106.
43. Hamidieh, K., Thost, V., Gerych, W., Yurochkin, M. & Ghassemi, M. (2026). "A better method for identifying overconfident large language models". OpenReview (id=lOoRJo8xWy); MIT News 2026-03-19. (非 arXiv 论文，发表于 OpenReview)
44. Krishnan, R. et al. (2026). "Enhancing Trust in Large Language Models via Uncertainty-Calibrated Fine-Tuning". ICLR 2026 Workshop: Principled Design for Trustworthy AI. arXiv:2412.02904.
45. (2026). "Evaluating the Relevance of Uncertainty Estimators for LLM Hallucination". arXiv:2605.27016.
46. Liu, G.K.-M., Caciularu, A., Yona, G., Szpektor, I. & Cohan, A. (2026). "Reinforcement Learning with Metacognitive Feedback Elicits Faithful Uncertainty Expression in LLMs (RLMF)". Yale University / Google Research. arXiv:2606.32032. 被 COLM 2026 接收.

### 8.9 Macaron-V1 自适应 LoRA 架构对比（§6.9 引用）

47. Mind Lab Research (2026). "Macaron-V1: Towards Open Continual Learning with Self-Improvement and Mixture-of-LoRA". arXiv:2608.09819.
48. Mind Lab Research (2026-07-21). "Introducing Macaron-V1". macaron.im/mindlab/research/introducing-macaron-v1.
49. Sutton, R.S. & Silver, D. (2025). "Welcome to the Era of Experience". Google DeepMind.
50. Macaron-V1-Preview-749B Model Card. HuggingFace: mindlab-research/Macaron-V1-Preview-749B.
51. Mixture-of-LoRA Harness. GitHub: MindLab-Research/Mixture-of-LoRA-Harness.

---

## 附录 A: 收敛行为对照表

| 情境 | $P^*$ | $R^*$ | $H^*$ | 收敛类型 | 可达性 |
|------|-------|-------|-------|---------|--------|
| 当前框架 v2.8 (无 Lean4) | 0.85 | 0.86 | 0.05 | Bounded | ✅ 已实现 |
| 引入 Lean4 (无算力无限) | 0.92 | 0.88 | 0.03 | Mixed | 🚧 规划中 |
| 引入 Lean4 + 算力无限 | 0.96 | 0.96 | 0.01 | Mixed (formal→1, informal→bound) | 📐 理论分析 |
| Lean4 + 算力无限 + user spec | 0.98 | 0.98 | 0.005 | Near-1 (conditional) | 📐 理论分析 |
| Full 1-convergence (理论极限) | 1.0 | 1.0 | 0.0 | Perfect | ❌ 不可达 |

## 附录 B: 关键区分表

| 约束 | 算力无限能突破？ | 为什么 |
|------|----------------|--------|
| EXPTIME-hard 证明搜索 | ✅ (部分) | 算力无限压缩时间 |
| Rice 定理 (不可判定) | ❌ | 算力不能解决不可判定性 |
| Gödel 不完备性 (不可证) | ❌ | 算力不能创造证明 |
| 开放集 (spec 不完备) | ❌ | 算力不能创造 spec |
| DPI (信息单调性) | ❌ | 算力不能恢复信息 |
| 反问题不可判定 (spec 综合) | ❌ | 算力不能创造 spec |

## 附录 C: 不可达性论证逻辑链

```
当前框架不可达 1 收敛
├── Detection 维度: ADD_recall ≤ SAST_recall < 1 (DPI)
├── Verification 维度: L3 语义鸿沟 (Rice 定理)
├── Knowledge 维度: 学习闭环是打地鼠 (开放集)
└── Benchmark 维度: 3 个数据集 TP=0 (实证)

引入 Lean4 后
├── 改变: 可形式化子集强收敛 (Lean4 类型检查 decidable)
├── 不改变: DPI 约束 (上游漏报不可恢复)
├── 不改变: 开放集问题 (spec 是闭集, bug 是开集)
└── 不改变: 证明构造创造性 (Gödel 不完备性)

算力无限下
├── 改变: 证明搜索速度 (EXPTIME → polynomial, P=NP 假设)
├── 改变: 证明覆盖率 (~50% → ~75-95%)
├── 不改变: Rice 定理 (不可判定)
├── 不改变: Gödel 不完备性 (不可证)
├── 不改变: 开放集 (spec 不完备)
├── 不改变: DPI (信息单调性)
└── 不改变: EXPTIME-hard 复杂度类 (序列化步数仍指数)

最终稳态
├── 受限场景 (formal + user spec): P=R=1, H=0 (强收敛)
├── 系统整体: P≈0.96, R≈0.96, H≈0.01 (混合收敛)
└── 理论极限 (1 收敛): 不可达 (结构性约束)
```

---

**文档结束**

> 本文档基于 2026-08-12 关于"ADD 框架多轮审计收敛性"的系统性讨论整理而成。
> 讨论涵盖了当前框架不可收敛性论证、跨学科分析、Lean4 引入影响、算力无限假设、学术价值评估、大模型架构抑制幻觉六条主线对标、Macaron-V1 自适应 LoRA 架构对比七个层面。
> 核心结论：1 概率收敛在通用场景下不可达，但在受限场景（formal subset + user spec）下强收敛可达。
> 框架的真实价值在于"以可审计的方式量化不确定性"，而非"收敛到全知"。
> §6.8 的六条主线对标表明 ADD 方法论与 2025-2026 年主流 LLM 幻觉抑制研究高度同构，差异化在于"审计器自审"场景。
> §6.8.9 进一步从问题结构、学术、工程、方法论四个维度论证了"审计器自审 vs 生成器自审"差异的价值——填补三个学术空白、一个工程成本带、证明闭环设计可替代模型能力提升。
> §6.9 与 Macaron-V1 MoL 架构对比表明：ADD 与 Macaron 代表能力沉淀的两条根本路线（符号化 vs 参数化），两者在闭环驱动增长上同构但在知识编码、确定性、算力上截然相反，互补关系指向下一代"可信赖 AI 代码审计系统"形态。
