# KFlow — 项目知识关系的外部记忆

> **KFlow 保存项目重要知识之间的显式关系，让 AI Agent 少扫描无关文件，也让人类看清一次变化可能影响哪里。**

需求、约束、架构、接口、测试和实现通常不是孤立文件。KFlow 把值得长期保存的关系登记为 Git 可跟踪的 Knowledge Node、Derivation 和 Confirmation，并依据当前文件事实计算哪些 Node 仍需检查。

KFlow 只提供结构、直接关系、影响范围、原因和检查顺序。它不读取或返回正文，不替人或 Agent 判断内容真伪，也不会自动修改文件。

## 核心概念

### Knowledge Node

一个值得长期管理的重要知识单元，由一个或多个完整文件组成。Node 是稳定身份；文件路径是组成，不是身份。KFlow 不建立章节、段落或代码片段级 Node。

### Derivation

一个或多个输入知识如何形成一个或多个输出知识的显式推导。Derivation 是不可拆分的一等实体，支持 1-to-1、1-to-N、N-to-1 和 N-to-M，不退化成普通二元边。

### Confirmation

一个 Node 已在当前文件、当前 producing Derivation 和当前直接输入条件下完成检查。一次只确认一个 Node，不级联，也不代表永久正确；条件变化后，该 Node 会再次进入 review order。

## 安装

KFlow 需要 Python 3.11 或更高版本，运行时只使用标准库。

```bash
python -m pip install -e .
kflow --help
```

也可以使用 `pipx install .` 或 `uv tool install .`。

## Quickstart

### 1. 创建六个普通示例文件

在 KFlow 仓库根目录运行：

```bash
python scripts/create_readme_quickstart.py
cd kflow-quickstart
```

PowerShell 可将第二行写成 `Set-Location kflow-quickstart`。脚本只创建六个示例文件，不初始化 KFlow、不创建 Git 仓库，也不覆盖已有目录。

### 2. 初始化并登记 Node

```bash
kflow init
kflow add-node requirements --file docs/requirements.md
kflow add-node constraints --file docs/constraints.md
kflow add-node architecture --file docs/architecture.md
kflow add-node api-design --file docs/api-design.md
kflow add-node testing-plan --file docs/testing-plan.md
kflow add-node deployment-plan --file docs/deployment-plan.md
```

### 3. 声明完整 Derivation

```bash
kflow derive --short "需求与约束形成架构" --input requirements "提供产品目标" --input constraints "提供运行边界" --output architecture "形成系统结构"
kflow derive --short "架构形成接口与测试方案" --input architecture "提供组件边界" --output api-design "形成接口设计" --output testing-plan "形成测试方案"
kflow derive --short "接口设计形成部署方案" --input api-design "提供运行接口" --output deployment-plan "形成部署计划"
```

KFlow 不根据文件名或正文猜测关系。每条命令保存一次完整推导，因此多输入和多输出的原子语义不会丢失。

### 4. 查看结构并建立确认基线

```bash
kflow overview
kflow ui
```

实际阅读六个文件并确认关系正确后，逐个建立 Confirmation：

```bash
kflow confirm requirements
kflow confirm constraints
kflow confirm architecture
kflow confirm api-design
kflow confirm testing-plan
kflow confirm deployment-plan
```

### 5. 修改上游并处理 review order

编辑 `docs/requirements.md` 后，无需先运行同步命令，直接查询当前文件事实：

```bash
kflow overview --status
kflow review-order
kflow context requirements
kflow impact requirements
```

`overview --status` 在完整拓扑中标记待检查 Node；`review-order` 只列实际仍需检查的 Node；`context` 展示目标的一跳局部关系；`impact` 展示目标直接进入的 Derivation 和更远下游。

按照 review order 读取和判断真实文件。每完成一个 Node，就单独执行：

```bash
kflow confirm requirements
```

全部完成后验证：

```bash
kflow review-order
kflow validate
```

此时应看到 `Review scope is clear.` 和 `KFlow metadata is valid.`。

## 公开命令

```text
kflow init [PATH]
kflow add-node NAME --file PATH [...]
kflow derive ...

kflow overview [--status]
kflow context NODE
kflow impact NODE
kflow review-order [NODE]

kflow confirm NODE
kflow validate

kflow ui ...
```

四个查询入口各有一个明确职责：

| 命令 | 返回的信息 |
|---|---|
| `kflow overview [--status]` | 完整项目拓扑；可选叠加当前状态 |
| `kflow context NODE` | 目标 Node 的 producing Derivation 和直接 consumer Derivation |
| `kflow impact NODE` | 目标直接进入的完整 Derivation，以及 direct outputs 之后的更远下游 |
| `kflow review-order [NODE]` | 全项目或指定下游子图中当前仍需检查的稳定线性顺序 |

Node reference 可以是精确 Node ID、唯一名称或已登记文件路径。未登记文件不会自动进入图。

默认文本面向人和直接阅读终端的 Agent，使用 Node 名称，不展示随机内部 ID。详细文本语义和 golden outputs 见 [CLI 信息架构](docs/cli-information-architecture.md)。

## 机器接口与 `--json`

直接操作终端的 Agent 使用上面的默认文本闭环。MCP、IDE、自动化脚本和其他程序化消费者应使用 JSON，不解析默认文本：

```bash
kflow overview --json
kflow overview --status --json
kflow context architecture --json
kflow impact requirements --json
kflow review-order --json
kflow review-order architecture --json
```

完整项目图保持 `schema_version: 2`，供程序化 Agent 适配器和 Human Interface 共享。按任务拆分的 `context`、`impact`、`review-order` 以及 CLI operation envelope 使用 query schema v3。Git 跟踪的 metadata schema 仍为 v2。具体字段见 [机器契约](docs/schema.md)。

JSON 只包含登记路径、Node、完整 Derivation、状态、原因、顺序和 validation issues，不包含正文、片段、自动摘要或 Prompt。除前台交互式 `ui` 外，其他公开命令支持把 `--json` 放在子命令前或后。

## Human Interface

在已初始化的项目根目录运行：

```bash
kflow ui
kflow ui status
kflow ui stop
```

`kflow ui` 是 `kflow ui start` 的常用简写：它在后台启动当前项目的实例并打开浏览器；已有健康实例时直接复用，因此同一项目不会重复启动。命令启动成功后立即返回。不同项目拥有彼此独立的实例；`status` 显示当前项目的 URL、PID 与启动时间，`stop` 只关闭当前项目。可用 `start --port 8765` 指定端口、`start --no-open` 禁止打开浏览器，或用 `start --foreground` 附着终端调试。

服务只监听 `127.0.0.1`。运行记录位于用户级本机状态目录（Windows 为 `%LOCALAPPDATA%\KFlow\ui`，Linux/macOS 遵循 XDG state 目录或 `~/.local/state/kflow/ui`），按规范化项目根目录隔离；这些 PID、端口、随机实例身份和控制 token 不写入 `.kflow`，也不进入 Git。

界面保持只读，并通过轻量 revision polling 自动感知已登记正文、KFlow 元数据、Confirmation 与 Git HEAD/结构历史变化；只有 token 变化时才安静刷新实际数据。手动 Reload 会忽略当前 revision 基线并强制完整同步，两种方式都保留合理的筛选、选择、历史基准和 viewport。

Knowledge Node 主体视觉表达可重建的结构角色：Source（无 producer、有 consumer）、Intermediate（两者都有）、Terminal（有 producer、无 consumer）和 Isolated（两者都无）。Source/Isolated 为 L0；派生 Node 的 Layer 等于 producing Derivation 全部输入 Node 的最大 Layer 加一。Current、Needs review、Unknown 状态改由小面积文字 badge 表达，与结构颜色分离。当前领域模型没有 Knowledge Category，界面不会根据路径或文件名猜测类别。

界面还展示 Inspector、Review Order、登记文件打开入口和基于 Git 的结构历史与 Graph Diff。它与 CLI 共用 `query_project_graph` 和 `query_review_order`，不复制图、状态或排序算法。技术边界见 [Human Interface 架构](docs/human-interface.md)。

## KFlow 与其他工具的分工

| 工具 | 主要职责 |
|---|---|
| Git | 保存文件内容和版本历史 |
| 编辑器 / IDE | 阅读、搜索和修改文件 |
| AI Agent | 理解任务、判断并执行工作 |
| KFlow | 保存重要知识拓扑，计算当前影响原因和检查顺序 |

KFlow 不是 RAG、代码依赖扫描器或自动知识图谱生成器。它不保存 embedding、不解析 import、不自动登记全部源码，也不根据正文猜测关系。

## 文档

- [核心原则](docs/core-principles.md)
- [正式架构](docs/architecture.md)
- [CLI 信息架构](docs/cli-information-architecture.md)
- [Agent 工作流](docs/agent-workflow.md)
- [Agent 集成](docs/agent-integration.md)
- [KFlow Agent Skill](docs/kflow_skills.md)
- [机器契约](docs/schema.md)
- [Human Interface 架构](docs/human-interface.md)
- [Human Interface Demo](docs/demo-project.md)

## 开发

```bash
pytest -q
ruff check .
ruff format --check .
```

仓库开发约束见 [AGENTS.md](AGENTS.md)。

## License

[Apache License 2.0](LICENSE)
