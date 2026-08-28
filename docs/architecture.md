# KFlow 正式架构

> 本文定义 KFlow 当前领域模型、状态算法、持久化与接口边界。产品决策首先服从 [核心原则](core-principles.md)，机器字段见 [机器契约](schema.md)。

## 1. 定位

KFlow 是 Git-native 的知识拓扑和影响范围管理器。它维护重要项目文件组成的 Knowledge Node、Node 之间的 Derivation、当前变化状态和逐 Node 的 Confirmation。

KFlow 提供结构、关系、影响、原因和路径；人类或 Agent 负责读取正文、理解问题、决定是否修改并执行修改。

KFlow 不得：

- 创建、编辑、移动或删除用户正文；
- 返回正文、片段、自动摘要或拼装 Prompt；
- 建立目录、章节、段落或代码片段级 Node；
- 用固定关系类型、向量相似度或自动猜测替代显式 Derivation；
- 把“可能受影响”表述为“一定错误”；
- 级联确认下游或同源输出；
- 引入 event sourcing、快照数据库或时间旅行引擎。

## 2. 架构分层

```text
CLI / Human Interface / future adapters
        ↓
application operations and queries
        ↓
domain graph, status and versioning
        ↓
Git-native JSON facts
        ↓
registered project files (read bytes only for fingerprints)
```

- `kflow/cli.py` 提供人类文本与稳定 JSON 两种呈现。
- `kflow/core/operations.py` 提供小型、原子的建图操作。
- `kflow/core/query.py` 提供完整项目图、context、impact 和 affected context。
- `kflow/core/graph.py`、`status.py`、`versioning.py` 实现纯领域规则。
- `kflow/core/storage.py`、`scan.py` 负责规范事实、扫描和确认。
- `kflow/human/` 是本地只读 Human Interface 适配层，只通过公共 Query API 提供 HTTP JSON、受限本地文件打开动作和包内静态资源。
- `ui/` 是 React 前端源代码；布局、选择等 UI 状态不进入领域层。

人类界面和 Agent 接口消费同一套领域事实与排序算法，不维护第二套状态逻辑。
Human Interface 的技术边界、运行流程与演进阶段见 [Human Interface 架构](human-interface.md)。

## 3. 领域模型

### 3.1 ProjectManifest

```yaml
kind: kflow-project
schema_version: 2
```

Manifest 只标识项目和机器契约大版本，不保存可重建索引或计数。

### 3.2 KnowledgeNode

```yaml
kind: node
schema_version: 2
id: nd_opaque_stable_id
name: architecture
files:
  - docs/architecture.md
  - docs/architecture.svg
```

- `id` 是不依赖名称或路径的稳定身份。
- `name` 在项目内唯一。
- `files` 是共同构成一个知识单元的非空完整文件集合。
- 没有 producing Derivation 的 Node 自动视为源 Node；孤立 Node 合法。
- Node 不保存类型、摘要、正文、颜色或 Derivation 反向引用。

### 3.3 Derivation

```yaml
kind: derivation
schema_version: 2
id: dv_opaque_stable_id
short: 综合需求与约束形成系统设计
detail: 根据功能需求和部署约束确定组件边界。
inputs:
  - node: nd_requirements
    short: 提供功能目标
    detail: 定义必须支持的场景。
outputs:
  - node: nd_architecture
    short: 形成总体架构
    detail: 确定组件边界与数据流。
```

Derivation 是一次不可拆分的多输入、多输出推导活动，不是若干独立二元边。

- inputs 和 outputs 均非空。
- 拓扑只由端点 Node 决定。
- Derivation、input、output 三层 `short` 均为非空文本。
- 三层 `detail` 可为空，规范编码为空字符串。
- 同一 Node 不得同时是同一 Derivation 的输入和输出。

### 3.4 NodeConfirmation

Confirmation 保存某个 Node 最近一次完成检查时的版本基线：

- 当时的完整文件集合及 fingerprint；
- 当时的 files fingerprint 与 effective version；
- 派生 Node 当时的 producing Derivation 及 fingerprint；
- 派生 Node 当时的直接输入 effective version 向量。

源 Node 不记录 producer，inputs 为空。Confirmation 不保存确认人、时间戳或审批结论；Git 已提供作者、时间和历史。

## 4. 全局不变量

### Node 与文件

1. Node ID 全局唯一且不可变，name 在项目内唯一。
2. files 至少一个、不得重复，使用规范仓库相对路径。
3. 路径不得是绝对路径、目录或通过 `..` 越界。
4. 同一文件至多属于一个 Node；普通文件可以不受 KFlow 管理。
5. 登记时文件必须存在且为普通文件；后续缺失作为 validation issue。
6. KFlow 元数据操作不得改写真实文件。

### Derivation 与图

1. Derivation ID 全局唯一且不可变。
2. inputs、outputs 均至少一个且各自不得重复。
3. 所有引用的 Node 必须存在。
4. 每个 Node 至多出现在一个 Derivation 的 outputs 中。
5. 一个 Node 可作为任意多个 Derivation 的 input。
6. 将每个 input 投影到每个 output 后，整个 Node 图必须无环。

### Confirmation

1. 每个 Node 至多有一个当前 Confirmation 文件。
2. Confirmation 的 Node 必须存在并与文件名匹配。
3. Confirmation 完整记录确认时的版本条件。
4. confirm 只写目标 Node，绝不级联。

## 5. Fingerprint 与 effective version

文件只以原始字节参与 SHA-256 计算；KFlow 不解析正文。

```text
file_fingerprint = SHA256(raw file bytes)
files_fingerprint = SHA256(canonical [(path, file_fingerprint)])
derivation_fingerprint = SHA256(canonical derivation JSON)
```

路径属于 files fingerprint，因此重命名会被识别为变化，但不改变 Node ID。

effective version 按 DAG 拓扑序计算：

```text
source_version(node) = SHA256(node.id, files_fingerprint)

derived_version(node) = SHA256(
  node.id,
  files_fingerprint,
  producer_fingerprint,
  sorted direct input effective versions
)
```

计算不读取 Confirmation。confirm 不改变当前 effective version，只记录已经检查到哪个版本条件；内容精确恢复时版本也恢复。

## 6. 状态、scan 与 confirm

状态由当前事实与 Confirmation 即时比较，不持久化颜色：

| reason | 含义 |
|---|---|
| `unconfirmed` | 尚无确认基线 |
| `files_changed` | 文件集合、路径或内容不同 |
| `derivation_changed` | 当前 producer 或其 fingerprint 不同 |
| `input_changed` | 一个或多个直接输入 effective version 不同 |

`needs_review` 等价于 reasons 非空；`current` 等价于 reasons 为空。同一 Node 可以同时具有多个 reason。

文件缺失、非法图和损坏的机器数据是 validation issue，不是普通 review reason。

### scan

scan 加载并校验元数据，读取受管文件字节计算 fingerprint，按拓扑序计算版本并比较 Confirmation。它只可更新可重建、被 Git 忽略的本地 cache，不修改共享事实或用户正文。

### confirm

confirm 表示人或 Agent 已实际检查目标 Node 的当前文件；若它有 producer，也检查了当前生产推导和直接输入条件。

执行时必须：

1. 校验图和目标文件可读；有阻断问题时拒绝。
2. 原子写入目标 Node 的当前基线。
3. 不写任何其他 Confirmation。
4. 返回确认前原因、确认后状态和剩余待检查摘要。

## 7. 影响与查询

当前自动变化根是具有 `files_changed` 或 `derivation_changed` 的 Node。`unconfirmed` 单独展示，不自动解释为一次内容变化。

影响从 input Node 沿 Derivation 传播到全部 outputs：

- `depth=1` 是直接影响，更深层是传递影响；
- 多根合并时保留最小深度、所有来源根和可解释路径；
- `review_order` 是相关 needs-review 子图的稳定拓扑序，上游先于下游；
- 显式 impact 查询始终从指定 Node 遍历，不依赖其当前状态。

公共查询：

- `query_project_graph(root)`：全部 Node、完整 Derivation、当前状态、validation issues 与稳定拓扑顺序；
- `query_context(root, reference)`：一个 Node 的状态、上下游和相关 Derivation；
- `query_impact(root, reference=None)`：显式或自动变化根的下游影响；
- `query_affected_context(root)`：当前变化范围内仍待检查的项目上下文。

查询可以按 Node ID、name 或已登记文件路径定位，操作目标仍是 Node。查询路径可将开头单个 `./` 和 Windows `\` 分隔符规范化为仓库相对 POSIX 路径；绝对路径、drive path 和包含 `..` 的路径不会匹配。未登记文件返回 `unknown_node` 查询错误，但不构成图校验错误，也不触发自动登记。

`query_project_graph` 是 Human Interface 与 Agent Interface 的共同基础。它直接复用 scan 状态、图拓扑和统一 Derivation presenter；Derivation 作为完整多输入、多输出实体返回。展示层不得把投影邻接边误作规范 Derivation 事实，也不得加入坐标、颜色、折叠或选择状态等 UI 私有数据。

## 8. 持久化

```text
.kflow/
├── project.json             # tracked
├── .gitignore               # tracked
├── nodes/                   # tracked
├── derivations/             # tracked
├── confirmations/           # tracked
├── cache/                   # ignored, rebuildable
└── runtime/                 # ignored, disposable
```

Node、Derivation 和 Confirmation 分文件保存，是规范真相源。索引、反向引用、邻接、状态与 review order 均为派生数据。

当前可靠性范围是单工作区、单写者。切换到任意 Git commit 后，应能仅凭该版本的规范元数据和项目文件重建拓扑与确认基线。

未来历史与图差异查询以 Git ref/commit 为数据源，不新增 KFlow event sourcing 或快照数据库；当前阶段不实现按 Git ref 查询或图差异。

## 9. 接口冻结

- 用户命令固定为顶层 `kflow <command>`，没有版本命令组。
- 正式 Python 领域入口位于 `kflow.core`。
- JSON 结果通过 `schema_version` 管理机器兼容性。
- 人类输出可以改善措辞与布局，但必须复用同一事实、reasons、impact 和 review order。
- Agent 适配层不得复制影响传播或排序算法。
- Human Interface 必须调用完整项目图公共查询，不得直接读取 `.kflow` JSON 后复制领域、状态、Derivation 序列化或排序逻辑。
- `kflow/human/` 和 `ui/` 不属于领域层，不得把画布坐标、选择或加载状态写入 Core。
- Human Interface 不修改 KFlow 元数据和项目文件。它允许有限的本地只读辅助动作，例如打开已经登记、真实存在且解析后仍位于项目根目录内的普通文件；不得接受任意路径、程序、命令或 shell 参数。

## 10. 当前明确排除

- 正文分析、LLM 总结或 Prompt 拼装；
- 自动创建、编辑、移动或删除用户正文；
- 自动关系推断与全项目文件登记；
- 章节、段落、代码片段级 Node；
- 固定关系类型枚举；
- 级联确认；
- 自动修改下游；
- 远程 Web 服务、MCP Server、watcher 或后台常驻服务；
- event sourcing、快照数据库或时间旅行引擎。

未来集成必须建立在当前稳定事实、查询和机器契约之上，不得改变这些核心边界。
