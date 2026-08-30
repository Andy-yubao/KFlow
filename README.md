# KFlow — 项目知识关系的外部记忆

> **KFlow 保存项目重要知识之间的显式关系，让 AI Agent 少扫描无关文件，也让人类看清一次变化可能影响哪里。**

长期项目里的需求、约束、架构、接口、测试和部署方案通常不是彼此孤立的。但“哪个设计来自哪些依据、上游变化后应该检查哪里”往往只存在于某个人的记忆、一次 Agent 对话，或散落在长文档里。换一个对话、维护者或一段时间后，这份理解就需要重新建立。

KFlow（Knowledge Flow）把值得长期保存的关系登记为 Git 可跟踪的项目事实，并根据文件、推导关系和上次确认条件计算当前影响范围。它先告诉人类或 Agent：

- 哪些重要文件值得关注；
- 它们为什么相关；
- 变化可能沿什么路径传播；
- 建议按什么顺序检查。

KFlow 不读取或返回正文，不替人或 Agent 判断内容真伪，也不会自动修改文件。

## 为什么 KFlow 存在

### Agent 不应在每次会话里重新猜测全部关系

当任务是“需求变了，请检查相关实现和文档”时，没有持久关系的 Agent 往往只能重新扫描目录、搜索关键词、读取大量候选文件，再临时猜测依赖。这会扩大上下文，使每次得到的关注范围不稳定，也让人类难以解释 Agent 为什么选择了这些文件。

KFlow 的目标不是承诺固定比例的 Token 节省，而是先提供一个可解释的关注范围，让 Agent 再决定实际读取哪些文件。

### Git 能说明什么变了，但不直接说明知识为何相关

Git 擅长保存内容与历史，回答“哪些文件和内容发生了变化”。它不会直接表达“架构为什么依赖需求和约束”“测试方案为什么可能受架构变化影响”或“为什么应先检查架构，再检查下游方案”。KFlow 补充的是这层知识拓扑与影响语义。

### 目录树也不是知识结构

文件在同一目录，不代表它们存在推导关系；文件位于不同目录，也不代表它们无关。KFlow 管理的是重要知识如何形成、为什么相关、变化可能沿什么路径传播，而不是目录布局本身。

## 一个项目变化的故事

设想一个本地软件项目有六份重要知识：

```text
requirements + constraints
          │
          ▼
     architecture
       ├──────────────┐
       ▼              ▼
   api-design     testing-plan
       │
       ▼
 deployment-plan
```

这些关系同时包含多输入到单输出（N-to-1）、单输入到多输出（1-to-N）和单输入到单输出（1-to-1）。团队明确登记六个知识单元和三次完整推导，实际检查后再逐个确认。此时，KFlow 记录的是“已经检查到哪些条件”，不是对内容做永久正确的认证。

后来 `docs/requirements.md` 新增一条要求：本地界面必须支持导出只读项目摘要。KFlow 比较当前事实与各知识单元的确认基线后，会指出：

| 知识单元 | 原因 |
|---|---|
| `requirements` | 登记文件发生变化（`files_changed`） |
| `architecture` | 直接输入条件发生变化（`input_changed`） |
| `api-design` | 上游输入发生变化（`input_changed`） |
| `testing-plan` | 上游输入发生变化（`input_changed`） |
| `deployment-plan` | 传递而来的输入变化（`input_changed`） |

检查顺序保持上游优先；同层项目使用稳定的 Node ID 排序。人或 Agent 可以先检查 `requirements` 和 `architecture`，再检查接口与测试分支，最后检查依赖接口设计的部署方案。

这里的 `affected` 只表示“可能需要检查”，不表示文件一定错误或一定要修改。KFlow 不读取正文、不自动修复下游，也不自动确认；实际判断完成后，使用者仍需对每个知识单元分别执行 `confirm`。

## 人类和 Agent 从同一份事实出发

Agent 可以通过 `--json` 获得 Node 身份、登记路径、状态、原因、上下游、影响路径和 Review Order，然后只按任务需要读取真实文件。

人类可以通过 `kflow ui` 查看重要知识图、完整的多输入/多输出 Derivation、Inspector、待检查状态、Review Order、登记文件打开入口，以及基于 Git 的结构历史和 Graph Diff。

Human Interface 与 Agent Interface 消费同一个 Core 查询结果和同一套项目事实，不维护两套独立的图、状态或排序逻辑。

## KFlow 与其他工具如何分工

| 工具 | 主要职责 |
|---|---|
| Git | 保存文件内容和版本历史，告诉你哪些内容发生变化 |
| 编辑器 / IDE | 阅读、搜索和修改文件 |
| AI Agent | 理解任务、读取必要文件、判断并执行工作 |
| KFlow | 保存重要知识的显式拓扑，计算影响范围、原因和检查顺序 |

KFlow 不是 RAG：它不保存正文、不建立 embedding、不检索内容片段，也不拼装 Prompt。

KFlow 不是代码依赖扫描器：它不解析 import、不建立调用图，也不会自动登记所有源码。它管理的是用户认为值得长期保存的知识关系。

KFlow 也不是自动知识图谱生成器：它不会根据文件名或正文猜测 Derivation。AI 可以帮助用户声明关系，但经过确认的关系应作为明确、可审查的项目事实保存。

## 什么时候值得使用

KFlow 比较适合：

- 重要文档之间存在稳定、可解释的推导关系；
- 人类与 AI Agent 长期交替维护同一项目；
- 一项上游变化可能影响多个下游知识单元；
- 项目结构无法只靠目录树理解；
- 团队希望减少 Agent 为判断范围进行的重复扫描；
- 人类希望持续掌握项目结构和变化原因。

以下场景收益较小或不适合：

- 只有几个文件的一次性临时任务；
- 希望工具自动管理全部源码；
- 希望工具自动阅读、总结或修改正文；
- 需要自动生成代码调用图；
- 完全不愿维护显式关系；
- 关系变化快到维护成本高于实际收益。

## Quickstart：亲手建立第一张知识图

这个教程从六个普通示例文件开始。辅助脚本只负责快速创建文件；初始化、选择 Node、声明 Derivation 和逐 Node 确认都由你或你的 Agent 明确执行。

### 准备环境

KFlow 需要 Python 3.11 或更高版本。在仓库根目录安装当前代码：

```bash
python -m pip install -e .
kflow --help
```

也可以使用 `pipx install .` 或 `uv tool install .`。

### 1. 生成普通示例文件

在 KFlow 仓库根目录执行：

```bash
python scripts/create_readme_quickstart.py
cd kflow-quickstart
```

PowerShell 可将第二行写为 `Set-Location kflow-quickstart`。也可以指定一个尚不存在的目标目录：

```bash
python scripts/create_readme_quickstart.py "./my KFlow example"
```

脚本默认创建：

```text
kflow-quickstart/
└── docs/
    ├── requirements.md
    ├── constraints.md
    ├── architecture.md
    ├── api-design.md
    ├── testing-plan.md
    └── deployment-plan.md
```

此时只有普通文件：尚未初始化 KFlow，尚未登记任何 Node，也没有 Derivation、Confirmation、`.kflow/` 或 Git 历史。脚本拒绝覆盖任何已存在的目标目录，也不提供 `--force`。

### 2. 初始化 KFlow

```bash
kflow init
```

`init` 只创建 Git-native KFlow 元数据，不扫描项目并自动建图。

### 3. 明确登记六个 Node

```bash
kflow add-node requirements --file docs/requirements.md
kflow add-node constraints --file docs/constraints.md
kflow add-node architecture --file docs/architecture.md
kflow add-node api-design --file docs/api-design.md
kflow add-node testing-plan --file docs/testing-plan.md
kflow add-node deployment-plan --file docs/deployment-plan.md
```

Node 是稳定的知识身份，文件是组成这个知识单元的完整文件。KFlow 不会把目录里的其他文件自动登记进图。

### 4. 显式创建三次 Derivation

以下命令使用单行写法，在 Bash、PowerShell 和 Windows 命令提示符中都可直接执行：

```bash
kflow derive --short "需求与约束形成架构" --input requirements "提供产品目标" --input constraints "提供运行边界" --output architecture "形成系统结构"
kflow derive --short "架构形成接口与测试方案" --input architecture "提供组件边界" --output api-design "形成接口设计" --output testing-plan "形成测试方案"
kflow derive --short "接口设计形成部署方案" --input api-design "提供运行接口" --output deployment-plan "形成部署计划"
```

KFlow 不根据文件名或正文猜测这些关系。每条命令保存一次完整推导，因此多输入和多输出不会退化成若干含义不完整的二元边。

### 5. 查看结构

```bash
kflow overview
kflow ui
```

你应看到六个 Node、三个完整 Derivation，以及 N-to-1、1-to-N、1-to-1 三种形态。`kflow ui` 是前台本地服务，使用 `Ctrl+C` 停止；无图形环境可运行 `kflow ui --no-open`。

### 6. 实际检查后建立确认基线

浏览六个示例文件，确认它们当前与图中关系一致，然后逐个执行：

```bash
kflow confirm requirements
kflow confirm constraints
kflow confirm architecture
kflow confirm api-design
kflow confirm testing-plan
kflow confirm deployment-plan
```

Confirmation 一次只作用于一个 Node，不会级联，也不是永久确认。它记录该 Node 在当前文件、当前 producer 和当前直接输入条件下已完成检查。

### 7. 制造一次真实上游变化

手动编辑 `docs/requirements.md`，在末尾增加：

```text
- The interface must support exporting a read-only project summary.
```

辅助脚本不会预先制造这次变化。

### 8. 观察影响传播

```bash
kflow scan
kflow status
kflow context --affected
kflow review-order
```

预期现象是：`requirements` 因文件变化需要检查；`architecture` 因直接输入变化需要检查；`api-design` 与 `testing-plan` 继续受到上游影响；`deployment-plan` 受到传递影响。KFlow 会给出原因和稳定、上游优先的实际 Review Order，但仍由你或 Agent 判断每个文件是否需要修改。

### 9. 完成检查闭环

按照 `kflow review-order` 的实际输出逐个处理 Node：需要修改时编辑真实文件，不需修改时也完成实际判断；每完成一个 Node，就单独执行 `kflow confirm <node>`。全部处理后验证：

```bash
kflow context --affected
kflow validate
```

当前影响范围应为空，validation issues 也应为空。这套流程展示了 KFlow 的核心取舍：关系必须明确保存，影响可以自动计算，内容判断和确认不能被悄悄代替。

## 三个核心概念

### Knowledge Node

一个值得长期管理的重要知识单元，可以由一个或多个完整文件组成。不是所有文件都应成为 Node；Node 是稳定身份，文件路径是它的组成，不是身份本身。KFlow 不建立目录、章节、段落或代码片段级 Node。

### Derivation

一个或多个输入知识如何形成一个或多个输出知识的显式推导。它支持 N-to-1、1-to-N 和 N-to-M，是第一等实体，不会退化成普通二元边；KFlow 也不会自动猜测关系。

### Confirmation

一个 Node 已在当前文件、当前生产推导和当前直接输入条件下完成检查。一次只确认一个 Node，不级联，也不代表永久正确；文件、producer 或输入条件变化后，它可能再次需要检查。

## Human Interface

在已初始化的项目根目录运行：

```bash
kflow ui
```

服务只监听 `127.0.0.1`，默认使用随机空闲端口并打开浏览器；可以用 `--port 8765` 指定本地端口，或用 `--no-open` 禁止自动打开。界面提供完整知识图、Inspector、搜索与状态筛选、Review Order、受限的登记文件打开入口，以及工作区相对 Git `HEAD` 或近期结构提交的 Graph Diff。

界面保持只读，不修改 Git、KFlow 元数据或项目文件。Git 历史不可用时只降级历史与 Graph Diff，当前项目图仍可使用。完整技术边界见 [Human Interface 架构](docs/human-interface.md)。

README Quickstart 与仓库已有的 [完整 Graph Diff Demo](docs/demo-project.md) 职责不同：Quickstart 只生成普通文件，让新用户亲手建图；完整 Demo 自动构造 Git 历史与结构差异，面向 Human Interface 开发和高级人工验收。

## Agent Interface 与 `--json`

Agent 应使用稳定机器输出，而不是解析人类文本：

```bash
kflow overview --json
kflow context architecture --json
kflow context --affected --json
kflow explain requirements --json
kflow review-order --json
```

结果通过 `schema_version: 2` 标识机器契约，包含登记路径、完整 Derivation、状态、原因、影响路径、检查顺序和 validation issues，不包含正文、片段、自动摘要或 Prompt。

除交互式 `ui` 外，有限的数据和元数据命令都支持 `--json`；参数可放在子命令前或后。Node reference 可以是精确 Node ID、唯一 name 或已登记文件路径。未登记文件不会被自动接受或自动加入图。

## 日常工作流

```text
查看项目结构与状态
→ 获取受影响范围和原因
→ 按需读取真实文件
→ 判断并在必要时修改
→ scan
→ 按 Review Order 逐 Node 检查
→ 对每个已完成检查的 Node 单独 confirm
→ 再次检查 affected 范围并 validate
```

常用命令：

```bash
kflow overview
kflow status
kflow context --affected
kflow review-order
kflow scan
kflow explain requirements
kflow confirm requirements
kflow validate
```

完整的 Agent 闭环见 [Agent 工作流](docs/agent-workflow.md) 和 [KFlow 使用指南](docs/kflow_skills.md)。

## 设计边界

- KFlow 只管理值得长期记住来源与影响的重要完整文件，不管理所有源码。
- 普通文件可以不属于任何 Node；没有 producer 的 Node 也是合法源 Node。
- KFlow 只保存显式关系，不从正文、文件名或相似性自动猜测 Derivation。
- 每个 Node 至多由一个 Derivation 产生，整个 Node 图必须无环。
- `affected` 表示可能需要检查，不表示一定错误或必须修改。
- KFlow 不创建、编辑、移动、删除、返回或总结用户正文。
- `confirm` 只确认一个已实际检查的 Node，绝不级联。
- Node、Derivation 和 Confirmation 是 Git 跟踪的共享事实；cache 和 runtime 可重建或丢弃。
- Git 提供内容与历史；KFlow 不建立 event sourcing、快照数据库或平行历史引擎。

详细的 fingerprint、effective version、状态算法、literal Git pathspec、历史限制、Graph Diff schema、Reload 隔离和前端请求生命周期分别保留在 [正式架构](docs/architecture.md)、[机器契约](docs/schema.md) 与 [Human Interface 架构](docs/human-interface.md)，不在产品首页重复展开。

## 正式命令索引

| 命令 | 用途 |
|---|---|
| `kflow init [path]` | 初始化 Git-native 元数据，不扫描项目建图 |
| `kflow add-node <name> --file <path>` | 将一个或多个已有完整文件登记为 Node |
| `kflow derive ...` | 用显式 Derivation 连接已有 Node |
| `kflow overview` | 查看完整项目结构、全部 Node 与完整 Derivation |
| `kflow status` | 展示项目状态、待检查 Node、原因和问题 |
| `kflow scan` | 观察受管文件变化并刷新可重建本地缓存 |
| `kflow confirm <node>` | 记录一个 Node 已在当前条件下完成检查 |
| `kflow validate` | 校验元数据、文件引用与图不变量 |
| `kflow context <node>` | 查看一个 Node 的路径、状态、关系和影响 |
| `kflow context --affected` | 查看当前受影响范围与检查顺序 |
| `kflow explain <node>` | 解释指定 Node 的直接和传递影响 |
| `kflow review-order` | 展示当前变化对应的稳定检查顺序 |
| `kflow ui [--port PORT] [--no-open]` | 启动本地只读浏览器界面 |

正式 CLI 保持原子操作；`scripts/create_readme_quickstart.py` 只是仓库内 onboarding helper，不是新的 KFlow 子命令，也不会代替上述命令。

## 深入文档

- [核心原则](docs/core-principles.md)：产品使命、北极星原则与边界
- [正式架构](docs/architecture.md)：领域模型、图不变量、状态与持久化
- [KFlow 使用指南](docs/kflow_skills.md)：Agent 调用顺序与维护边界
- [Agent 工作流](docs/agent-workflow.md)：一次变化的端到端检查闭环
- [机器契约](docs/schema.md)：稳定 JSON schema
- [Human Interface 架构](docs/human-interface.md)：本地只读界面与 Git-backed history/diff
- [适配层说明](docs/agent-integration.md)：Agent 集成方式
- [完整 Graph Diff Demo](docs/demo-project.md)：高级界面人工验收

`docs/history/` 只保存历史设计材料，不定义当前产品行为。

## 开发

Python 运行时只依赖标准库。开发检查：

```bash
pytest -q
ruff check .
ruff format --check .
```

前端开发使用 `ui/.nvmrc` 指定的 Node.js 版本：

```bash
cd ui
npm ci
npm run typecheck
npm run test
npm run build
```

production build 写入 `kflow/human/static/` 并随 Python 包分发；最终用户运行 `kflow ui` 不需要 Node.js。

## 许可证

MIT
