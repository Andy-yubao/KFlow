# KFlow — Knowledge Flow CLI

KFlow 是面向人类与 AI Agent 协同开发的知识拓扑和影响范围管理工具。它维护重要项目文件组成的 Knowledge Node、显式 Derivation、变化状态与确认基线，帮助使用者判断应该检查哪些文件以及为什么。

KFlow 不保存或返回文档正文，也不会创建、编辑、移动或删除用户正文。

## 安装

需要 Python 3.11 或更高版本。

```bash
pip install -e .
```

也可以通过 pipx 或 uv 安装：

```bash
pipx install .
# 或
uv tool install .
```

## 快速开始

当前正式 CLI 已采用 schema v2 架构。`v2` 是内部实现版本，不是用户命令层级；用户直接调用 `kflow <command>`。

先准备两个需要纳入 KFlow 的已有文件，例如 `docs/a.md` 和 `docs/b.md`，然后执行：

```bash
kflow init
kflow add-node a --file docs/a.md
kflow add-node b --file docs/b.md

kflow derive \
  --short "由 A 形成 B" \
  --input a "使用 A" \
  --output b "形成 B"

kflow status
kflow context b
kflow explain a
kflow review-order
kflow confirm a
kflow confirm b
kflow validate
```

Node 可以绑定多个完整文件，只需重复 `--file`。Derivation 支持多输入、多输出，只需重复 `--input` 或 `--output`。

## 正式命令

### `kflow init [path]`

初始化 schema v2 元数据目录。它不会扫描项目建立图谱，也不会创建用户正文。

```bash
kflow init
kflow init /path/to/project
```

### `kflow add-node <name> --file <path>`

把一个或多个已存在的项目相对路径登记为 Node。文件必须存在，且同一文件不能属于多个 Node。

```bash
kflow add-node requirements --file docs/requirements.md
kflow add-node architecture \
  --file docs/architecture.md \
  --file docs/architecture.svg
```

没有 producing Derivation 的 Node 自动视为源 Node，孤立 Node 也是合法的。

### `kflow derive`

用一个不可拆分的 Derivation 连接已有 Node。输入和输出至少各一个，每个输出 Node 至多有一个 producer，整个图必须保持无环。

```bash
kflow derive \
  --short "综合需求与约束形成设计" \
  --detail "根据功能目标与部署限制确定系统设计。" \
  --input requirements "提供功能目标" \
  --input constraints "提供部署限制" \
  --output architecture "形成系统架构" \
  --output api-design "形成接口方案"
```

### `kflow status`

只读扫描当前项目，计算 Node 状态、可解释的 review reasons 和独立的 validation issues。

```bash
kflow status
kflow status --json
```

粗粒度状态包括：

- `valid`：尚无确认基线；
- `affected`：当前事实与确认基线不同；
- `confirmed`：当前事实与确认基线一致。

规范原因包括 `unconfirmed`、`files_changed`、`derivation_changed` 和 `input_changed`。缺失文件、非法图或损坏的 schema 属于 validation issue，不会伪装成普通 review reason。

### `kflow context <node>`

只读查询一个 Node 当前最值得关注的结构信息：自身文件与状态、全部上游、全部下游，以及这些路径涉及的 Derivation 和显式作用描述。

```bash
kflow context architecture
kflow context architecture --json
```

Context 只返回登记的文件路径和元数据，不读取或返回文件正文。

### `kflow explain <node>`

以指定 Node 为变化根解释下游影响。显式查询不依赖该 Node 当前是否已经出现 review reason；结果区分直接与间接影响，并在 JSON 中给出影响深度、来源根、经过的 Node/Derivation 路径、当前状态原因和稳定 `review_order`。

```bash
kflow explain architecture
kflow explain architecture --json
```

`affected` 只表示可能需要检查，不表示 KFlow 已判断文件错误或要求修改。

### `kflow review-order`

从当前扫描中自动选择具有 `files_changed` 或 `derivation_changed` 的变化根，并按上游优先的稳定拓扑顺序展示仍需检查的相关 Node。

```bash
kflow review-order
kflow review-order --json
```

该命令复用与 `explain` 相同的 impact 结果和排序语义；它不保存顺序，也不引入独立状态机。尚未确认的 Node 会保留 `unconfirmed`，但不会仅因未确认就自动成为变化根。

### `kflow confirm <node>`

确认一个已经实际检查过的 Node，记录它在当前文件、生产推导和直接输入条件下的版本基线。

```bash
kflow confirm architecture
```

一次只确认一个 Node，不会级联确认 sibling outputs 或下游，也不代表 KFlow 证明正文绝对正确。

### `kflow validate`

校验 schema v2 元数据、文件引用和图不变量，只报告问题，不修改用户正文。

```bash
kflow validate
kflow validate --json
```

所有正式命令都支持 `--json`，机器结果只包含路径、拓扑、状态和校验信息，不包含正文、片段、自动摘要或拼装 Prompt。

## 旧 v1 命令

旧实现仍保留为行为基线，但不再是默认接口。需要显式使用 legacy 命令组：

```bash
kflow legacy --help
kflow legacy init
kflow legacy create architecture
```

KFlow 不会自动迁移或转换旧 v1 项目。请不要在同一项目中混用正式 schema v2 命令和 legacy 命令。

## 元数据结构

正式 CLI 使用 Git-native 的 schema v2 事实：

```text
.kflow/
├── project.json
├── .gitignore
├── nodes/
├── derivations/
├── confirmations/
├── cache/          # 可重建，不进 Git
└── runtime/        # 临时数据，不进 Git
```

Node、Derivation 和 Confirmation 应由 Git 跟踪；cache、runtime 与其他可重建数据不进入 Git。

内部领域代码继续位于 `kflow/v2/`。这个目录名用于隔离领域实现和 schema 版本，不构成用户可见的 CLI 层级。

## 设计边界

- Node 只管理一个或多个完整文件，不管理目录、章节、段落或代码片段。
- KFlow 只维护显式 Derivation，不根据正文、文件名或主题相似性自动猜测关系。
- KFlow 只提示哪些位置可能受影响，不判断正文真伪，也不自动修改下游。
- Confirmation 是版本检查基线，不是审批、真伪证明或永久绿色状态。
- Git 管理正文和历史，编辑器或 Agent 负责读取与修改，KFlow 负责知识拓扑和影响范围。

## 开发

```bash
pytest -q
ruff check .
ruff format --check .
```

项目当前零第三方运行时依赖；pytest 与 Ruff 仅用于开发。

## 许可证

MIT
