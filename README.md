# KFlow — Knowledge Flow CLI

KFlow 是面向人类与 AI Agent 协同开发的知识拓扑与影响范围管理工具。它记录重要项目文件组成的 Knowledge Node、显式 Derivation 和逐 Node 的 Confirmation，帮助使用者回答：

- 当前项目是否健康；
- 哪些重要知识发生了变化；
- 哪些 Node 可能需要检查；
- 为什么需要检查，以及建议按什么顺序检查。

KFlow 不保存或返回文档正文，不分析内容，不自动修改文件，也不替 Agent 或人类做判断。

## 安装

需要 Python 3.11 或更高版本。

```bash
pip install -e .
```

也可以使用 pipx 或 uv：

```bash
pipx install .
# 或
uv tool install .
```

安装后可直接查看正式命令：

```bash
kflow --help
```

## 五分钟快速开始

假设项目中已有 `docs/requirements.md` 和 `docs/architecture.md`：

```bash
kflow init

kflow add-node requirements --file docs/requirements.md
kflow add-node architecture --file docs/architecture.md

kflow derive \
  --short "根据需求形成架构" \
  --input requirements "提供产品目标" \
  --output architecture "形成系统设计"
```

首次查看状态：

```bash
kflow status
```

未确认的 Node 会显示为需要关注。实际检查每个 Node 后分别确认：

```bash
kflow confirm requirements
kflow confirm architecture
```

之后如果 `docs/requirements.md` 发生变化，`kflow status` 会指出：

- `requirements` 的受管文件发生了变化；
- `architecture` 的直接输入条件发生了变化；
- 下一步可以运行 `kflow context --affected` 查看影响范围与建议检查顺序。

## 日常工作流

```text
查看状态
→ 获取受影响范围
→ 按需读取和检查真实文件
→ 必要时修改文件
→ 重新扫描
→ 对每个已检查 Node 单独确认
→ 验证本次影响范围闭合
```

对应命令：

```bash
kflow overview
kflow status
kflow context --affected
kflow review-order

# 人或 Agent 检查、按需修改文件
kflow scan
kflow explain requirements

kflow confirm requirements
kflow confirm architecture
kflow validate
```

`affected` 表示“可能需要检查”，不表示 KFlow 已判断文件错误或要求修改。

## 正式命令

| 命令 | 用途 |
|---|---|
| `kflow init [path]` | 初始化 Git-native 元数据，不扫描项目建图 |
| `kflow add-node <name> --file <path>` | 将一个或多个已有完整文件登记为 Node |
| `kflow derive ...` | 用显式 Derivation 连接已有 Node |
| `kflow overview` | 查看完整项目结构、全部 Node 与完整 Derivation |
| `kflow status` | 展示项目状态、待关注 Node、原因和问题 |
| `kflow scan` | 观察受管文件变化并刷新可重建本地缓存 |
| `kflow context <node>` | 查看一个 Node 的路径、状态、关系和影响 |
| `kflow context --affected` | 查看当前受影响范围与检查顺序 |
| `kflow explain <node>` | 解释指定 Node 的直接和传递影响 |
| `kflow review-order` | 展示当前变化对应的稳定检查顺序 |
| `kflow confirm <node>` | 记录一个 Node 已在当前条件下完成检查 |
| `kflow validate` | 校验元数据、文件引用与图不变量 |

所有命令都支持 `--json`。机器结果只包含路径、拓扑、显式语义、状态、影响和校验问题，不包含正文、片段、自动摘要或拼装 Prompt。

命令职责有所区分：`overview` 建立完整项目全貌；`context <node>` 查看一个 Node 的相关上下文；`context --affected` 查看当前变化对应的待检查范围；`explain <node>` 解释指定变化根的下游影响；`review-order` 只展示当前变化对应的稳定检查顺序。

`context`、`explain` 和 `confirm` 的目标始终是 Node；其中的 Node reference 可以使用精确的 Node ID、唯一 Node name 或该 Node 已登记的文件路径。查询路径允许仓库相对路径、开头单个 `./` 和 Windows `\` 分隔符的等价写法；未登记或越出仓库的路径不会被自动接受。

Node name 应使用简短、稳定、面向人类的名称，不建议使用 `docs/example.md` 一类相对路径作为 Node name；文件路径通过 Node 的 `files` 字段表达。这是命名建议，不改变 Node reference 的解析行为。

### 多文件 Node

一个 Node 可以由多个完整文件共同构成：

```bash
kflow add-node architecture \
  --file docs/architecture.md \
  --file docs/architecture.svg
```

KFlow 不建立目录、章节、段落或代码片段级 Node。

### 多输入、多输出 Derivation

```bash
kflow derive \
  --short "综合需求与约束形成设计" \
  --detail "确定组件边界和接口。" \
  --input requirements "提供功能目标" \
  --input constraints "提供部署限制" \
  --output architecture "形成总体架构" \
  --output api-design "形成接口方案"
```

Derivation 的输入和输出均至少一个；每个 Node 至多有一个 producer；整个图必须保持无环。

### Confirmation

`confirm` 只作用于一个 Node。它表示该 Node 已在当前文件、当前生产推导和当前直接输入条件下完成检查：

```bash
kflow confirm architecture
```

它不会级联确认 sibling outputs 或下游，也不是审批、真伪证明或永久绿色状态。

## 人类输出与机器输出

不带 `--json` 的输出面向人类，`kflow status` 会汇总项目状态、待检查数量、具体 Node、原因、相关路径和 validation issues。

带 `--json` 的输出面向 Agent 与未来适配层：

```bash
kflow overview --json
kflow context --affected --json
```

机器契约通过结果中的 `schema_version: 2` 标识兼容大版本。产品名称、命令层级和 Python 包不带版本号。

## 元数据

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

Node、Derivation 和 Confirmation 是 Git 跟踪的共享事实；cache、runtime、锁和临时 observation 不是。

## 设计边界

- KFlow 只管理值得长期记住来源与影响的重要文件，不管理所有源码。
- KFlow 只保存显式关系，不根据正文、文件名或相似性自动猜测 Derivation。
- KFlow 只提示可能受影响的位置，不判断正文真伪，不自动修改下游。
- Git 管理正文和历史；编辑器、Agent 或人类负责阅读与修改；KFlow 管理知识拓扑和影响范围。
- Human Interface 与 Agent Interface 消费同一个完整项目图公共查询；未来历史与差异视图从 Git 获取，不建立第二套历史引擎。

## 文档

- [核心原则](docs/core-principles.md)
- [正式架构](docs/architecture.md)
- [机器契约](docs/schema.md)
- [Agent 工作流](docs/agent-workflow.md)
- [KFlow 使用指南](docs/kflow_skills.md)
- [适配层说明](docs/agent-integration.md)

历史设计材料集中在 `docs/history/`，仅用于追溯，不定义当前产品行为。

## 开发

```bash
pytest -q
ruff check .
ruff format --check .
```

项目没有第三方运行时依赖；pytest 与 Ruff 仅用于开发。

## 许可证

MIT
