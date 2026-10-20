# T9' Phase 1 · T0 前置阻断门 — Joern 数据流 API 实测记录

> **版本**: **v1.2**（v1.0 + **2026-10-20 追补 ①: ⑦ codeFlows 次序**（§2⑦ / M-9）+ **②: Joern 精确版本实证 = 4.0.595**（§0 / M-10）） | **日期**: 2026-10-20 | **作者**: Scott
> **关联文档**: 设计 spec §8（阻断项 R1/R1b/R1c/R1d）· 实施规范 §8.1（T0 门）· 验收 checklist §1（T0.1~T0.10）
> **上游决议**: [ADR-026](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L578)（L5 语义诠释）· [ADR-027](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md#L615)（C2–C4 收敛策略）
> **实测方法**: 真实环境（Windows 宿主机 → WSL2 Ubuntu-24.04）中构造 4 文件夹具 → `joern-parse` 生成 CPG → 8 个 bare-REPL Scala 脚本逐项探测；**调用形态与 ADD 现有代码一致**（[joern_cpg.py `_build_wsl_bash_command` L469-494](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L469-L494) / `_build_joern_parse_command` L497-531 / `_build_joern_query_command` L536-571）
> **探针脚本**（临时，**位于仓库外**，非交付物）: `C:\Users\Peng\AppData\Local\Temp\t0_probe\run.sh` · `run2.sh`
> **门禁结论**: ✅ **R1 / R1b / R1c / R1d 全部闭合** ⇒ **不触发**"MVP 退化为 Tier 2+Tier 3、新建 ADR supersede ADR-026"分支；**AC-16 满足**

---

## 0. 环境前提（实测）

| 项 | 状态 | 实测证据 |
|---|---|---|
| **WSL2** | ✅ | `wsl -l -v` → `Ubuntu-24.04  VERSION 2`（另有 `docker-desktop` V2）；内核 `5.15.167.4-microsoft-standard-WSL2`；WSL `2.4.13.0`；`systeminfo` → "A hypervisor has been detected" |
| **JDK** | ✅ Temurin **21.0.12+8-LTS** | `/home/pengliu2026/jdk/bin/java -version` → `openjdk version "21.0.12" 2026-07-21 LTS`；**正是** [joern_cpg.py L167-169](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L167-L169) 写死的 `candidate_java` 路径 |
| **Joern CLI** | ✅ | `/home/pengliu2026/bin/joern/joern-cli/`（`joern-parse` / `joern` / `frontends/pysrc2cpg` 均在）；**正是** [L159-161](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L159-L161) 写死的 `candidate_joern` 路径 |
| **ADD 自身探测** | ✅ 打通 | `is_available() == True`；`_find_joern_binary() == /home/pengliu2026/bin/joern/joern-cli/joern-parse`；`_detect_wsl_from_windows() == {'joern_path': '…/joern-parse', 'java_home': '/home/pengliu2026/jdk'}` |
| **`joern` 启动器** | ✅ | `joern --help` 正常，含 `--script <value>` + 位置参数 `[<cpg.bin>]` ⇒ 与 ADD Phase 7 的调用形态一致 |
| **宿主 → GitHub:443** | ✅ | `Test-NetConnection github.com -Port 443` = True |
| **WSL → GitHub** | ❌ 超时 | `curl -m 20 https://github.com/…` → `http_code=000`（DNS 正常 `20.205.243.166`）—— **不影响本门**（Joern 无需下载） |
| **WSL → apt 源** | ✅ | `archive.ubuntu.com` = 200；`mirrors.aliyun.com` = 301 |
| **资源** | ✅ | WSL 根分区 **952 GB 可用**；**16 核** |

**环境差异说明（非阻塞）**: `java` 不在 PATH、`JAVA_HOME` 未设 ⇒ 直接执行 `joern-parse` 报 `No java installations was detected.`。**ADD 不受影响**：`_build_wsl_bash_command` 会主动注入 `export JAVA_HOME='…' && export PATH="$JAVA_HOME/bin:/usr/bin:/bin"`（实测加 env 后 JVM 正常启动）。

**✅ 已实证项（2026-10-20 追补闭合，原为 ⚠️ 未证实）— Joern 精确版本与安装日期**:

| 项 | 实测值 | 证据（可复现命令 / 输出） |
|---|---|---|
| **Joern 版本** | **4.0.595** | `ls -1 /home/pengliu2026/bin/joern/joern-cli/lib \| grep '^io\.joern\.'` → **11 个** `io.joern.*-4.0.595.jar`（含 `io.joern.joern-cli-4.0.595.jar` · `io.joern.console-4.0.595.jar` · `io.joern.semanticcpg-4.0.595.jar` · `io.joern.x2cpg-4.0.595.jar` …） |
| **安装日期** | **2026-08-05 12:31** | `ls -l --time-style=long-iso …/joern-cli/lib/io.joern.joern-cli-4.0.595.jar` → `2026-08-05 12:31`；安装根 `…/bin/joern/` 亦为 `Aug 5 12:31` ⇒ 与源码注释 "P1-5 verified APIs (Joern v4.0.595, 2026-08-05)" **逐字一致**（原"推断"升级为**实证**） |
| **CPG schema 版本** | **1.7.70** | `cat …/joern-cli/schema-extender/cpg-version`（= `io.joern.flatgraph*` 系列版本，**与 Joern 版本是不同产物**，仅供 CPG 兼容性参考） |
| **`dataflowengineoss` 包存在性** | ✅ 存在于发行包 | `io.joern.dataflowengineoss-4.0.595.jar`（873,744 B）⇒ **③/M-2 的"该包随 CLI 分发、非 pip 依赖"获得直接文件证据**（此前仅有"脚本可跑通"的间接证据） |

**为何此前未取到（根因，本版已确认）**: 本发行包的**两个 CLI 均不提供版本旗标** —— `joern-parse --help` 仅列 `--help`/`--language` 等（无 version）；`joern --version` → `Warning: Unknown option --version`；`joern-cli/` 顶层与 `bin/` 下条目均为**工具名**（`joern` / `joern-parse` / `repl-bridge` / `pysrc2cpg` …）；`conf/` 仅含 `log4j2.xml` / `log4j-ghidra.xml`（**无** `version` 文件）。⇒ **可判定版本的唯一确定性来源是发行包 `lib/` 的可执行 jar 文件名**（本版据此实证）。

**与 `JOERN_VERSION_MIN` 的关系（精确化）**: [joern_cpg.py L41](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L41) 的 `JOERN_VERSION_MIN = "4.0"` 是**最低兼容声明（floor）**，**不等于实测环境版本**（实测 = 4.0.595）。本轮实证仅证明"**当前环境 = 4.0.595**"，**未**独立验证 4.0.x 区间内更低版本（如调研报告提及的 4.0.325）是否可用 ⇒ `"4.0"` 作为 floor 的**保守性未被推翻，维持不变**。

**⚠️ 字段语义留痕（新登记 L-7，非缺陷）**: `verify_dead_code` / `verify_taint_flow` 成功路径返回的 `"joern_version"` 取值来自 `JOERN_VERSION_MIN`（即 `"4.0"`），**语义上是"最低兼容 floor"而非"实测版本"**。MVP 不做运行时版本探测（避免为每个 finding 引入额外 WSL 子进程开销，且 ADR-023 要求零新增依赖），故字段**命名与语义存在轻微落差** —— 已在[验收报告 §10](file:///f:/Coding/audit-driven-development/docs/audit-log/2026-10-20-v3.0-T9prime-taint-acceptance-audit-report.md) 登记为观察项。若后续确需"实测版本"，应按上表方法从 `lib/` jar 文件名探测（一次性或缓存）。

---

## 1. 测试夹具与探针

**夹具（`/tmp/add_t0/repo/`，4 文件，CPG = 101,700 bytes）**:

```
a.py                    b.py                    c.py                    d.py
1  import os            1  import os            1  import os            1  import os
2  def fa(x):           2  def fb():            2  def fc():            2  cmd = input()
3      os.system(x)     3      os.system("ls")   3      v = os.getenv("X")3  os.system(cmd)
                                                4      os.system(v)
```

设计意图：`a.py:3` 参数污染（**正向**）· `b.py:3` 常量实参（**负向**）· `c.py:3→4` 输入 API 赋值的**跨行**精确通道（`R1d`）· `d.py:2→3` **模块级**输入（宽来源集）· **4 个文件的第 3 行都存在**（`R1c` 串号风险 + ② 多节点行为）。

探针执行要点（**对结论正确性至关重要**）:
- 探针**自身**在两个地方出过 bug（`cpg.call…file.head.name.l` 类型错误；Round-1 未 `cd` 导致在仓库 CWD 建 `workspace/`）⇒ Round-2 修正后重跑，**下述结论均取自修正后的数据**。
- Round-2 起 `cd /tmp/add_t0` 执行，避免污染仓库工作目录。
- 参阅: `cpg.method.parameter` 在夹具中 = **12** 个（含 `self`? 本夹具无类；含 `x`/`fb`/`fc` 等）· `cpg.call` = **25** · `cpg.method` = **12**。

---

## 2. 逐项实测结论

### ① `reachableBy` 入参形态（Traversal vs List）— ✅ **PASS**

实测 4 组合（`sinkA` = `a.py:3` 的 call，`sources` = `cpg.method.parameter`）:

| 组合（sink × source） | 结果 |
|---|---|
| `sinkList.reachableBy(srcList)` | **1** ✅ |
| `sinkList.reachableBy(srcTraversal)` | **1** ✅ |
| `sinkTraversal.reachableBy(srcList)` | **1** ✅ |
| `sinkTraversal.reachableBy(srcTraversal)` | **0** ❌ |

**并且**直接以**设计 spec §3.2 的脚本形态**验证（`sinkList.exists(s => s.reachableBy(sources).size > 0)`，其中 `sources = (…) ++ cpg.method.parameter).l`）：
`design_a_positive = true` · `design_c_positive = true` · `design_b_negative = false` ✅

⇒ **结论**: 设计脚本**按原样可用**。**入参以 `.l`（List）为安全形态**；`Traversal.reachableBy(Traversal)` 返回 0 ⇒ 实施时必须保证 sink 与 source **至少一侧为 List**（设计脚本两者均为 `.l`，已满足）。
⇒ 另: `reachableByFlows(…)` 亦可用（`RB_flowsA=1`），但 MVP 不消费（D-T9'-6）。

### ② 对多节点 traversal 的行为 — ✅ **PASS**

`cpg.call.lineNumber(3)`（**裸**，无文件过滤）在夹具中命中 **9** 个 call，跨 **4** 个文件（`line3_files = a.py|b.py|c.py|d.py`）。`sinkList.reachableBy(srcList)` 返回**可达 sink 的个数**（此处 1），语义定义良好 ⇒ 无需逐节点展开。

⚠️ **同时暴露 E-1 的量化风险**：裸 `lineNumber(N)` 得到的是**全 repo 同号行**的 call 集合（9 个），而非目标文件的 sink —— 印证 **R1c 必须闭合**。

### ③ `import io.joern.dataflowengineoss.language._` 在 bare REPL 下是否生效 — ⚠️ **PASS，但结论需修正**

- 含该 import 的脚本（p3/p4/q3/q4）**全部编译通过并执行成功** ⇒ 该 import **在 bare REPL 下合法且有效** ✅
- **对照实验 P6（无 import）**: `no_import_reachableBy = 1` ⇒ **不加 import 也能用 `reachableBy`**（Joern 在加载 CPG 时已应用 `dataflowOss` overlay，日志可见 "Overlay dataflowOss already exists"）。

⇒ **修正**: 设计 spec §3.2 把它列为"**必需的 import**"——应改为"**显式声明（无害、保留；但实测证明非必需）**"。保留该行不影响正确性，只是不再是必要条件。

### ④ `cpg.call.lineNumber(N)` 与 `cpg.method.parameter` 的实际节点数 — ✅ **PASS**

| 量 | 值 |
|---|---|
| `cpg.call.size` | 25 |
| `cpg.method.size` | 12 |
| `cpg.method.parameter.size` | 12 |
| `cpg.call.lineNumber(3).size` | 9 |
| `cpg.call.lineNumber(4).filter(file=="c.py").size` | 2 |
| `cpg.call.lineNumber(3).filter(file=="c.py").size` | 3 |

⇒ 均 ≥ 1 且可读；**注意**: 单行内存在**多个** call 节点（`os.system(x)` 产生 `system` + 一个 `<operator>.fieldAccess` 伪调用）⇒ `sink_nodes` 计数会大于"逻辑 sink 个数"，属正常，不影响 `exists(…)` 语义。

### ⑤ 正/负向样本 — ✅ **PASS**

| 样本 | 语义 | 实测 |
|---|---|---|
| `a.py:3` `os.system(x)`，`x` 为参数 | 正向（参数污染） | 有流 ✅ |
| `c.py:4` `os.system(v)`，`v = os.getenv("X")` | 正向（输入 API） | 参数集=**0**；参数集∪输入API=**1** ✅ |
| `d.py:3` `os.system(cmd)`，`cmd = input()`（模块级） | 正向（模块级输入） | 参数集=0；`cpg.call.name("^input$")`=**1**；并集=**1** ✅ |
| `b.py:3` `os.system("ls")`（常量） | **负向** | `design_b_negative = false`（无任何流） ✅ |

⇒ **证伪语义成立**：常量实参的 sink 在"参数 ∪ 输入 API"宽来源集下**无路径可达** ⇒ 支撑 D-T9'-3 的 `verified=False`（结构性证伪）。
⇒ **并直接验证 D-T9'-3 的必要性**：`c.py` 若**只用参数**会得 0（漏判），**加入输入 API 调用名后**才得 1 ⇒ **`cpg.call.name(INPUT_API_REGEX)` 是必需的补充来源集**。

### ⑥ `cpg.call.name(regex)` 对 `INPUT_API_REGEX` 的命中（**R1b**）— ✅ **PASS，正则需定稿修正**

**全 call 名 dump**（夹具）:
```
<operator>.assignment | <operator>.fieldAccess | getenv | import | input | system
```

| 候选 | 命中数 | 判定 |
|---|---|---|
| `^getenv$` | **1** | ✅ 命中 `os.getenv(...)` |
| `^input$` | **1** | ✅ 命中内置 `input()` |
| `^system$` | 4 | （sink 侧，非来源） |
| `^raw_input$` / `^getpass$` / `^get$` / `^getlist$` / `^loads$` / `^load$` | 0 | 夹具中不存在，**未能实证** |
| 候选正则 `^(input\|raw_input\|getenv\|getpass\|get\|getlist\|loads\|load)$` | **2** | 即 `input` + `getenv` |

**🔑 关键语义发现（决定正则定稿）**: 点分调用被 pysrc2cpg 渲染为**末段名字** —— `os.getenv` → call name **`getenv`**，`os.system` → **`system`**（**不是** `os.getenv` / `os.system`）。据此：

- `request.args.get(...)` / `os.environ.get(...)` 将渲染为 **`get`** ⇒ `^get$` **有依据**（此前只能推测）
- `request.args.getlist(...)` → **`getlist`** ⇒ `^getlist$` 有依据
- `pickle.loads` / `yaml.load` → `loads` / `load` ⇒ **但这两个是 sink 侧（反序列化）而非输入源**，列进来源集语义错误

⇒ **正则定稿（据实修正）**:
```
INPUT_API_REGEX = ^(input|raw_input|getenv|getpass|get|getlist)$
```
即 **删除 `loads|load`**（无实证依据 + 语义错位），**保留 `input|getenv`（已实证）**，**保留 `raw_input|getpass`（py2/冷门，零成本）**，**新增 `get|getlist`（由末段渲染语义推出）**。
⇒ 已知过近似：`^get$` 会匹配任意 `.get()` 调用 ⇒ 来源集偏大 ⇒ `verified=False` 更难出现 ⇒ **方向安全**（D-T9'-3 已声明接受）。
⇒ `<operator>.*` 伪调用不会命中该正则 ⇒ 无噪声。

### ⑦ CodeQL `codeFlows` 的 source/sink 次序（H5，信息性）— ✅ **PASS（2026-10-20 补充实测）**

**本夹具不经 SARIF 路径**（T0 探针为 Joern CPG 夹具，非 SARIF 产物），且本机**无 CodeQL CLI**（T0 §0 实测：WSL2 内仅安装 Joern；WSL→GitHub 超时）⇒ 改为「**权威样例 artifact 观测 + 一手查询语义交叉**」四条证据：

| # | 证据 | 内容 | 来源 |
|---|---|---|---|
| **A** | **具体 SARIF 观测（次序）** | `codeFlows[0].threadFlows[0].locations[]`（长度 2，同一 `threadFlow` 内）：**首项** = `src/handler.py:38`，snippet `command = request.json['command']`，message **"User input received: …"** ⇒ **source**；**末项** = `src/handler.py:42`，snippet `subprocess.run(command, shell=True, …)`，message **"Unsanitized value passed to subprocess.run(…)"** ⇒ **sink**。⇒ **次序 = source（首）→ sink（末）** | [Microsoft SARIF SDK · docs/ai/example.sarif](https://raw.githubusercontent.com/microsoft/sarif-sdk/HEAD/docs/ai/example.sarif) |
| **B** | **同一 artifact 的主位置** | `result.locations[0].physicalLocation.region.startLine = 42` = **sink 行**（该 `location` 另带 `logicalLocations` = `execute_job` 函数，`kind: "function"`）⇒ **主位置 = sink** | 同上 |
| **C** | **一手查询语义（端点角色）** | CodeQL 路径查询 `select` 为**四列** `select element, source, sink, string`（`element` = 告警位置，`source`/`sink` = 路径列）；官方模板与内置 [`py/command-line-injection`](https://codeql.github.com/codeql-query-help/python/py-command-line-injection/)（`Kind: path-problem`、`Precision: high`）**均以 `sink.getNode()` 作首列** ⇒ **主位置由查询作者选择**，CodeQL 路径规则**惯例取 sink**；官方原文亦明确"可把告警显示在 `source` 或 `sink`，取决于判断" | [Creating path queries](https://codeql.github.com/docs/writing-codeql-queries/creating-path-queries/) · [CommandInjection.ql](https://raw.githubusercontent.com/github/codeql/main/python/ql/src/Security/CWE-078/CommandInjection.ql) |
| **D** | **生成条件（复核）** | `codeFlows` **仅当**规则为 `@kind path-problem` 时**可能**生成（非必然） | [GitHub Docs · CodeQL CLI SARIF output](https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-cli/sarif-output)（Step 4 已逐字复核） |

**结论**:

1. **`codeFlows[].threadFlows[].locations[]` 按 source → sink 排列**（A 实测观测与 C 的 `flowPath(source, sink)` 方向一致）。
2. **`result.locations[0]`（主位置）不是规范强制的 sink**，而是 query `select` 的**首列**；CodeQL 路径规则**惯例取 sink**（B + C 一致）。⇒ 设计 spec GAP-1 括号内原表述"主位置=**通常**是 sink"应精确化为"**主位置 = select 首列（CodeQL 路径规则取 sink）**"。
3. **规范层面未强制端点角色**：SARIF 官方规范 `codeFlows` 正文（§3.27.18）因页面体积**未能完整取回**，GitHub 一手文档亦**未声明**端点次序 ⇒ **ADD 不得依赖该次序**。MVP 不消费（D-T9'-6）⇒ **风险 = 无**。
4. **Phase 2 若消费**（T12 数据链），须以本表 A/B 观测 + 上游实现为准，并在转换器内**显式校验**（首项=source / 末项=sink），**不得静默假定**。

> **证据强度声明（诚实披露）**: 证据 A/B 取自 **SARIF SDK 维护方（Microsoft，SARIF TC 编辑方）随文档发布的样例 artifact** —— 属**权威样例，但非 CodeQL 产出物**；本机无 CodeQL CLI 无法端到端复现。故本条为 **"样例观测 + 规范语义交叉"** 级证据，**不等于** CodeQL 实机实测。因 MVP 不消费该字段，该强度**足够闭合 T0.7**。

### ⑧ 按 `sink_file` 的文件过滤（**R1c**，E-1）— ✅ **PASS（且风险被量化证实）**

| 查询 | 结果 |
|---|---|
| `cpg.call.lineNumber(3).size`（**裸**） | **9**（跨 4 文件） |
| `.filter(_.file.head.name == "a.py")` | **2** |
| `.filter(_.file.head.name == "b.py")` | **2** |
| `.filter(_.file.head.name == "c.py")` | **3** |
| `.filter(_.file.head.name == "d.py")` | **2** |
| 合计 | **2+2+3+2 = 9** ✅ 与裸查询一致 |

⇒ **过滤器生效**（`_.file.head.name` 可比较，形态取自既有已实测模式 `imp.file.head.name`）。
⇒ **E-1 风险定量**: 若无过滤，ADD 会把**另外 3 个文件**的 7 个 call 当作 sink ⇒ `verified=False` 将基于**错误节点**得出。**R1c 必须闭合**，实测已完成。

### ⑨ exact 变体（**R1d**，G-2）— ✅ **PASS**

| 查询（`c.py` 内 line3→line4） | 结果 |
|---|---|
| `sinkC` = `line4 ∧ file=c.py` | 2 节点 |
| `srcC` = `line3 ∧ file=c.py` | 3 节点 |
| `sinkC.reachableBy(srcC).size` | **1** ✅ |
| `sinkC.reachableBy(cpg.method.parameter).size` | **0** |
| `sinkC.reachableBy((输入API调用名) ++ cpg.method.parameter).size` | **1** ✅ |

⇒ **exact 变体可用**（`cpg.call.lineNumber(sourceLine).filter(file)` 能定位来源调用，且 `reachableBy` 行为正确）⇒ **`taint_mode="exact"` 有实现依据**，`source_line` **不再是死参数**（G-2 闭合）。
⇒ 若 R1d 曾失败，按 G-2 契约应降级为"仅记录、不改变查询"——**该降级分支不触发**。

### 边界（补充）— `sink_nodes == 0` 的保护得到支撑

| 查询 | 结果 |
|---|---|
| `cpg.call.lineNumber(999).size` | **0** |
| `cpg.call.lineNumber(999).reachableBy(cpg.method.parameter).size` | **0** |

⇒ sink 未定位与"无路径"在数值上**同形**（都是 0）⇒ **证实 D-T9'-3 关键保护的必要性**：必须以 `sink_nodes == 0` 判定为 `verified=None`，**不得**判为 `verified=False`。

---

## 3. 新发现问题（N-1）：`joern --script` 在 CWD 生成 `workspace/` 副本

**现象**: `joern --script <script.sc> <cpg.bin>` 会在**当前工作目录**下创建 `workspace/<cpg基名>/` 项目目录（内含 CPG 副本），并在退出时保存。

**实测证据**:
- 我 Round-1 探针的 CWD = 仓库根 ⇒ 生成 `f:\Coding\audit-driven-development\workspace\cpg.bin\`（**3 文件 / 0.2 MB**，时间戳 2026-10-20 15:18）。**已删除**（见 §5）。
- 仓库内既有 **100 个**同类目录（创建时间 **2026-08-05 ~ 2026-08-12**，属 v2.4/v2.7/v2.8 开发期同类副作用），累计 **303 文件 / 144.7 MB**。
- `.gitignore` **第 26 行** `workspace/` 与 **第 27 行** `scripts/workspace/` 已忽略 ⇒ **该副作用是已知的**，但**每执行一次新留一份 CPG 副本** ⇒ 磁盘**无界增长**（100 次 ≈ 145 MB）。

**影响**: [joern_cpg.py `_run_joern_query` L712-748](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L712-L748) 调 `subprocess.run(cmd, env=env, …)` **未传 `cwd=`** ⇒ 工作目录继承调用者（运行 `verify_findings.py` 时的 CWD）⇒ 在仓库根持续生成 `workspace/`。

**处置建议（列入 T2 实施）**: `_run_joern_query`（及 `_generate_cpg` 若同样受影响）**显式传 `cwd=_get_cache_dir()`**（`%TEMP%\add_joern_cache` / `/tmp/add_joern_cache`，已被 `.gitignore` L14 覆盖），使 joern 的工作区落在缓存目录内、随缓存一起失效。**不采用**"扩展 `.gitignore`"作为唯一方案 —— 那只是掩盖磁盘增长。

> **是否阻断**: **不阻断 T0**（T0 结论不受影响）。**应作为 T2 的实施要求 + 新增验收项**（见 §4 修正 M-6）。

---

## 4. 据实修正（T0 触发的文档修正）

| ID | 修正对象 | 原内容 | 修正为 |
|---|---|---|---|
| **M-1** | design D-T9'-3 + §3.2 + impl §4.2.1 | `INPUT_API_REGEX = ^(input\|raw_input\|getenv\|getpass\|get\|getlist\|loads\|load)$`（impl）/ 更早版本含属性访问 | **`^(input\|raw_input\|getenv\|getpass\|get\|getlist)$`** —— 删 `loads\|load`（无依据 + 语义属 sink 侧）；`get\|getlist` 由**末段渲染语义**实证推出 |
| **M-2** | design §3.2 约定第 4 条 + impl §4.2.3 | "**必需的 import**"`io.joern.dataflowengineoss.language._` | "**显式声明（无害保留；实测证明非必需** —— 对照无 import 亦可）" |
| **M-3** | design §7 R1d + §8 ⑨ + impl §7 R-E + §8.1 ⑨ | 阻断项（未实测） | **✅ 已闭合**（exact 变体可用，`taint_mode="exact"` 有依据） |
| **M-4** | design §7 R1 + §8 ① + impl §3.2 脚本注 | 阻断项（未实测） | **✅ 已闭合**；**入参形态须满足"至少一侧为 List"**（`Traversal.reachableBy(Traversal)`=0） |
| **M-5** | design §7 R1c + §8 ⑧ + impl §8.1 ⑧ | 阻断项（未实测） | **✅ 已闭合**；并附**量化证据**（裸查询 9 个跨 4 文件 vs 过滤后 2+2+3+2） |
| **M-6** | impl §4.2.4 / §0.4 / §7 / §8.1 | （无） | **新增 N-1 处置**: `_run_joern_query` 须传 `cwd=_get_cache_dir()`；新增验收项（T2 组） |
| **M-7** | impl §8.1 ①②③④⑤⑦ | 实测项（未执行） | **①-⑥⑧⑨ 已执行 PASS**；**⑦ 未取**（信息性，MVP 不消费） |
| **M-8** | 三文档的"Joern 版本"表述 + 本文 §0 未证实项 | "版本号未取到 / 仍属假设" | **✅ 2026-10-20 追补实证闭合**（见 **M-10**）：版本 = **4.0.595**、安装日期 **2026-08-05 12:31**；根因 = 两个 CLI 均无版本旗标 |
| **M-9** | design §0.4 事实表 + §13.3 + GAP-1 括号 | "codeFlows 次序 ⚠️ **未验证**" / "主位置=**通常**是 sink" | **✅ 2026-10-20 补充实测闭合**: 次序 = **source→sink**；**主位置 = query `select` 首列**（CodeQL 路径规则**惯例取 sink**，非规范强制）⇒ 消解 §13.3 的"未证实"项，并修正 GAP-1 表述（详见 §2⑦） |
| **M-10** | 本文 §0（未证实项）+ design/impl 的 Joern 版本表述 | 隐式视为 v4.0.595（推断） | **✅ 实证**: 发行包 `lib/` 含 **11 个 `io.joern.*-4.0.595.jar`** ⇒ **版本 = 4.0.595**、安装 **2026-08-05 12:31**（与 P1-5 注释同源一致）；另 `schema-extender/cpg-version` = **1.7.70**（CPG schema，非 Joern 版本）；`io.joern.dataflowengineoss-4.0.595.jar` 实体存在 ⇒ ③ 的"随 CLI 分发"获**直接文件证据**。`JOERN_VERSION_MIN="4.0"` 语义精确化为**最低兼容 floor**（≠ 实测版本），**维持不变**；新登记 **L-7**（`joern_version` 字段语义 = floor 而非实测版本，MVP 不做运行时探测） |

---

## 5. 环境清理记录（谨慎操作）

| 对象 | 来源 | 处置 |
|---|---|---|
| `f:\Coding\audit-driven-development\workspace\cpg.bin\`（3 文件 / 0.2 MB） | **本次 Round-1 探针**（时间戳 2026-10-20 15:18，名称与 P3 日志 "Creating project `cpg.bin`" 一致） | ✅ **已删除**（仅此一个） |
| `workspace/` 下其余 **100 个**目录（303 文件 / 144.7 MB，2026-08-05 ~ 2026-08-12） | **既有**（v2.4/v2.7/v2.8 开发期），已被 `.gitignore` 第 26 行忽略 | ⚪ **未触碰** —— 先分析来源，不擅自清理；如要清理请另行确认（它们不对 git 状态产生影响） |
| `C:\Users\Peng\AppData\Local\Temp\t0_probe\*.sh` | 本次探针脚本（**仓库外**） | 保留（可复现；如需清理请告知） |

---

## 6. 门禁结论

| 阻断项 | 状态 | 依据 |
|---|---|---|
| **R1**（`reachableBy` 入参形态/多节点行为） | ✅ **闭合** | ① 4 组合实测 + ② 多节点行为定义良好；设计脚本形态直接验证通过 |
| **R1b**（`cpg.call.name(regex)` 命中） | ✅ **闭合** | ⑥ 全名 dump + 末段渲染语义 ⇒ 正则定稿（M-1） |
| **R1c**（文件过滤） | ✅ **闭合** | ⑧ 过滤生效且串号风险被量化 |
| **R1d**（exact 变体） | ✅ **闭合** | ⑨ exact 通道返回 1 |

**⇒ 不触发**设计 spec §8 的降级分支（Tier 1 退化为常态 `verified=None`、MVP 退化为 Tier 2+Tier 3、新建 ADR supersede ADR-026）。**Tier 1 保留，MVP 三段式（T1→T2→T3）不变。**
**⇒ AC-16 满足**（实测记录存在，四项结论明确）。
**⇒ 可进入 Step 9 TDD 实现**（T0 为前置硬门，现已闭合）。

**信息项 ⑦（codeFlows 次序）— ✅ 2026-10-20 补充实测闭合**（Step 10 追补）：结论 = 次序 **source→sink**；主位置 = `select` 首列（CodeQL 惯例取 sink）。证据强度 = "权威样例 artifact 观测 + 一手查询语义交叉"（非 CodeQL 实机实测；本机无 CodeQL CLI）⇒ 因 MVP 不消费该字段（D-T9'-6），风险 = **无**。详见 §2⑦。

**T0 遗留**（不阻塞，列入 Step 10 复核或后续）:
1. ~~**Joern 版本号未取**（M-8）~~ → ✅ **已实证闭合（2026-10-20）**: **4.0.595**（`lib/` 11 个 `io.joern.*-4.0.595.jar` 一致），安装日期 **2026-08-05 12:31**。**注**: `joern-cli/conf/version` **不存在**、两个 CLI 均**无**版本旗标 ⇒ 唯一确定性来源为 **jar 文件名**（详见 §0 已实证项块 + M-10）。**遗留子项**: `joern_version` 字段语义（= floor 非实测版本）登记为 **L-7**；
2. ~~⑦ codeFlows 次序未取~~ → ✅ **已闭合**（见 §2⑦）；
3. **N-1 的 `cwd=` 修正**须在 T2 落地并有验收项（**已在 T2 落地，T2.11 断言通过**）；
4. `raw_input` / `getpass` 未在夹具中实证命中（保留零成本，风险可忽略）。

---

## 7. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-10-20 | v1.0 | 初始记录：环境前提实测（WSL2/JDK/Joern/网络）+ 4 文件夹具 + ①-⑨ 逐项实测结论（R1/R1b/R1c/R1d **全部闭合**）+ 新发现 **N-1**（joern `--script` 在 CWD 生成 `workspace/` 副本）+ 8 项据实修正（M-1~M-8）+ 清理记录（仅删除本次产生的 1 个 artifact） |
| 2026-10-20 | **v1.1** | **Step 10 追补：⑦ codeFlows 次序闭合**。原 v1.0 标"⚪ 未取"（T0 探针非 SARIF 路径）。本版以 **4 条证据**闭合：A/B = 权威样例 SARIF artifact 观测（`codeFlows[0].threadFlows[0].locations[]` 次序 = **source→sink**；`result.locations[0]` = **sink** 行）；C = CodeQL 路径查询 `select element, source, sink, string` + 内置 `py/command-line-injection`（`@kind path-problem`）取 `sink.getNode()` 作首列 ⇒ **主位置由查询作者选择**；D = `codeFlows` 生成条件复核。**新增 M-9**（同步修正 design §0.4 / §13.3 / GAP-1）。**证据强度诚实声明**：样例 artifact（非 CodeQL 产出）+ 本机无 CodeQL CLI ⇒ 非实机复现；MVP 不消费该字段（D-T9'-6），风险 = 无 |
| 2026-10-20 | **v1.2** | **Step 10 追补：Joern 精确版本号闭合**（原 §0 标"⚠️ 未证实"）。**实证**: `lib/` 含 **11 个 `io.joern.*-4.0.595.jar`** ⇒ 版本 = **4.0.595**、安装 **2026-08-05 12:31**（与源码 P1-5 注释**逐字一致**，推断升级为实证）；`schema-extender/cpg-version` = **1.7.70**；`io.joern.dataflowengineoss-4.0.595.jar` 实体存在 ⇒ ③ 的"随 CLI 分发"获直接文件证据。**根因认定**: 两个 CLI 均无版本旗标（`joern-parse --help` 无 version；`joern --version` → Unknown option）、`conf/` 无 version 文件 ⇒ 唯一确定性来源 = jar 文件名。**语义精确化**: `JOERN_VERSION_MIN="4.0"` = 最低兼容 floor（≠ 实测版本），维持不变。**新增 M-10** + 新登记 **L-7**（`joern_version` 字段语义为 floor，MVP 不做运行时探测） |

**T0 实测记录结束**
