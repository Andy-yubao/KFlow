# KFlow v2 领域模型与重构方案

> 状态：当前设计基线（2026-08-22）。
>
> 上位约束：`KFlow_核心原则.md`。
>
> 行为验收：`KFlow_v2_使用场景清单.md`。
>
> 实现状态：领域内核已按本文修正，并已实现 schema v2 最小持久化、scan/status、单 Node confirm、Agent-oriented context、impact explanation、`review_order` 与正式 CLI workflow 验证。`v2` 继续作为内部模块与 schema 版本，不再是用户命令层级；按文件定位、直接 neighborhood、剩余影响查询与事务恢复仍待后续阶段。

## 1. 定位与边界

KFlow 是 Git-native 的知识拓扑和影响范围管理器。它管理重要文件组成的 Knowledge Node、Node 之间的 Derivation、变化状态和必要的确认历史。

KFlow 只告诉 Agent 应关注哪些文件、为什么相关、哪些位置可能受影响；是否读取、如何理解和是否修改仍由 Agent 决定。人类界面与 Agent 接口必须消费同一套事实。

KFlow 不得：

- 创建、编辑、移动或删除用户正文；
- 向 Agent 返回正文、片段、自动摘要或拼装 Prompt；
- 建立章节、段落、标题或代码片段级 Node；
- 用固定关系类型、向量相似度或自动猜测替代显式 Derivation；
- 自动判断文档真伪，或把“可能受影响”说成“必须修改”；
- 级联确认下游或同源输出；
- 引入 event sourcing、快照数据库、时间旅行引擎或替代方案特殊关系；
- 为兼容 v1 改变 v2 领域模型。

## 2. 当前产品决策

### D1：源 Node 没有 producing Derivation

- Node 可以先独立创建，再参与 Derivation。
- 没有 producing Derivation 的 Node 自动视为源 Node，不保存额外 `source` 字段。
- Derivation 必须至少有一个输入和一个输出；零输入 Derivation 已取消。
- 每个 Node 至多由一个 Derivation 产生，而不是恰好一个。
- 源 Node 不在 KFlow 中保存“为什么存在”的推导语义。

本决策取代此前“所有 Node 都由零输入或普通 Derivation 产生”的模型。

### D2：confirm 保存可解释的版本基线

- 源 Node：保存自身文件集合 fingerprint 和 effective version。
- 派生 Node：另保存 producing Derivation fingerprint 与直接输入 Node 的 effective version 向量。
- confirm 只写目标 Node 的 Confirmation，绝不级联。

### D3：Confirmation 是 Git 跟踪的共享事实

- Node、Derivation、Confirmation 进入 Git。
- index、scan cache、临时 observation、锁和事务临时文件不进入 Git。
- 不引入个人确认 overlay、publish 流程、用户身份或审批系统。

## 3. 规范领域模型

以下 YAML 仅说明字段；持久化格式为 UTF-8 JSON。

### 3.1 ProjectManifest

```yaml
kind: kflow-project
schema_version: 2
```

Manifest 只标识项目与 schema 大版本，不保存可重建的索引或计数。

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

- `id` 是稳定身份，不依赖名称或路径。
- `name` 是项目内唯一显示名。
- `files` 是共同构成一个知识单元的非空文件集合。
- Node 不保存类型、摘要、正文、状态颜色或 Derivation 反向引用。

### 3.3 Derivation

```yaml
kind: derivation
schema_version: 2
id: dv_opaque_stable_id
short: 综合需求与约束形成系统设计
detail: 根据功能需求和部署约束确定系统架构及接口。
inputs:
  - node: nd_requirements
    short: 提供功能目标
    detail: 定义必须支持的能力和使用场景。
  - node: nd_constraints
    short: 提供实现约束
    detail: 定义性能、兼容性和部署限制。
outputs:
  - node: nd_architecture
    short: 形成总体架构
    detail: 确定组件边界和数据流。
  - node: nd_api_design
    short: 形成接口方案
    detail: 确定接口及约束。
```

Derivation 是一次不可拆分的多输入、多输出推导活动，不是若干独立二元关系。

- `inputs` 和 `outputs` 均非空。
- 拓扑只由 `inputs[].node` 与 `outputs[].node` 决定。
- `short/detail` 描述整次推导；input/output 的 `short/detail` 描述各 Node 在本次推导中的角色。
- Derivation、input 和 output 的 `short` 均为非空文本，用于提供最小可解释语义。
- 三层 `detail` 均为可选文本；缺省统一编码为空字符串，不支持缺失字段与 `null` 等多种等价表示。

### 3.4 NodeConfirmation

派生 Node 的确认记录：

```yaml
kind: confirmation
schema_version: 2
node: nd_architecture
files:
  - path: docs/architecture.md
    fingerprint: {algorithm: sha256, value: "..."}
files_fingerprint: {algorithm: sha256, value: "..."}
producing_derivation:
  id: dv_system_design
  fingerprint: {algorithm: sha256, value: "..."}
inputs:
  - node: nd_requirements
    effective_version: "..."
effective_version: "..."
```

源 Node 的 Confirmation 没有 `producing_derivation`，`inputs` 为空。最终 codec 应使用单一、明确的缺省表示，不能同时支持多种等价编码。

Confirmation 不保存确认人、时间戳或审批结论。Git 已提供作者、时间和历史。

Confirmation 是确认时事实的版本基线，不要求其中记录的 producer 和 input 标识在后续拓扑编辑后仍指向当前对象。目标 Node 仍必须存在；当前事实与旧基线不同由 review reason 表达，而不是把合法变化报成 schema 损坏。

## 4. 全局不变量

### 4.1 Node 与文件

1. Node `id` 全局唯一且不可变，`name` 在项目内唯一。
2. `files` 至少一个、不得重复，使用 `/` 分隔的规范仓库相对路径。
3. 路径不得是绝对路径、目录或通过 `..` 越界。
4. 同一文件至多属于一个 Node；普通项目文件可以不受 KFlow 管理。
5. 注册时文件必须存在且为普通文件；后续缺失作为 validation issue 报告。
6. KFlow 的任何元数据操作都不得改写真实文件。

### 4.2 Derivation 与图

1. Derivation `id` 全局唯一且不可变。
2. inputs、outputs 均至少一个；同一列表内不得重复。
3. 同一 Node 不得同时是同一 Derivation 的 input 和 output。
4. 所有引用的 Node 必须存在。
5. 每个 Node 至多出现在一个 Derivation 的 outputs 中。
6. 一个 Node 可作为任意多个 Derivation 的 input。
7. 将每个 input 投影到每个 output 后，整个 Node 图必须无环。
8. 无生产者 Node 合法，并自动视为源 Node；孤立 Node 也合法。

### 4.3 Confirmation

1. 每个 Node 至多有一个当前 Confirmation 文件。
2. Confirmation 的 `node` 必须存在并与文件名匹配。
3. `files` 完整记录确认时 Node 的文件集合与各文件 fingerprint。
4. 确认时为派生 Node，则 producer 与 inputs 完整记录当时的生产推导和直接输入版本；确认时为源 Node，则没有这两部分。
5. confirm 只写目标 Node 的 Confirmation。
6. Confirmation 只表示“已在记录的版本条件下完成检查”，不是真伪证明。

## 5. 规范化、fingerprint 与有效版本

### 5.1 规范化

- JSON 使用 UTF-8、LF、固定缩进与稳定 key 顺序。
- `files` 按规范路径排序；Derivation inputs/outputs 与 Confirmation inputs 按 Node ID 排序。
- 自由文本保留原字符，不做语义归一化。

### 5.2 Fingerprint

首版使用带算法标签的 SHA-256：

```text
file_fingerprint = SHA256(raw file bytes)
files_fingerprint = SHA256(canonical [(normalized_path, file_fingerprint)])
derivation_fingerprint = SHA256(canonical derivation JSON)
```

路径属于 files fingerprint，因此重命名会被识别为变化，但不改变 Node ID。Derivation 的 ID、语义、inputs、outputs 任一变化都会改变其 fingerprint。

### 5.3 Effective version

按 DAG 拓扑序计算：

```text
source_version(node) = SHA256(canonical [
  node.id,
  current_files_fingerprint(node)
])

derived_version(node) = SHA256(canonical [
  node.id,
  current_files_fingerprint(node),
  current_derivation_fingerprint(producer(node)),
  sorted [(input.node_id, effective_version(input))]
])
```

计算不读取 Confirmation，因此 confirm 不改变当前 effective version，只记录“已检查到哪个版本”。内容精确恢复时版本也恢复；KFlow 不保存临时变化事件。

## 6. 状态、scan 与 confirm

### 6.1 状态

状态由当前事实与 Confirmation 比较得到，不持久化红黄绿字段：

```text
unconfirmed          没有 Confirmation
files_changed        文件集合、路径或内容不同
derivation_changed   当前生产者或其 fingerprint 与确认基线不同
input_changed        一个或多个直接输入 effective version 不同
```

- `needs_review = reasons 非空`；`current = reasons 为空`。
- 源 Node 通常只会出现 `unconfirmed` 或 `files_changed`。
- producer 的增加、移除或替换不删除旧 Confirmation；当前 producer 形态或 fingerprint 与基线不同时产生 `derivation_changed`。因此输出 Node 的 effective version 改变，其下游按直接输入版本产生 `input_changed`。
- 文件缺失、非法图和 schema 损坏是 validation issue，不是 review reason。

### 6.2 scan

scan 是只读计算：加载并校验元数据，读取 Node 文件计算 fingerprint，按拓扑序计算版本，与 Confirmation 比较得到 reasons。它可以更新可重建本地 cache，但不改变共享状态。

首版不依赖人工 `modify`，也不需要 watcher、hook 或常驻服务。

### 6.3 confirm

`confirm(node)` 表示 Agent 或人已经检查目标 Node 的当前文件；若它有生产者，也检查了生产推导和当前直接输入条件，并认为该 Node 仍成立或已完成必要修改。

执行时必须：

1. 校验图和目标文件可读；有阻断错误时拒绝。
2. 计算并原子写入目标 Node 的当前基线。
3. 不写任何其他 Confirmation。
4. 返回确认前 reasons 和仍待检查的下游摘要。

不存在级联确认；同一 Derivation 的多个输出必须分别确认。

## 7. 影响传播与查询

### 7.1 影响传播

- `files_changed` 或 `derivation_changed` 的 Node 是自动检测到的当前变化根；`unconfirmed` 单独列出，不自动解释为一次内容变化。
- 从 Node 作为 input 的 Derivation 向其全部 outputs 传播。
- `depth=1` 表示直接输出，后续为传递影响。
- 多根合并时保留目标的最小深度、来源根和可解释路径。
- `review_order` 是一次影响查询结果中相关 `needs_review` 子图的稳定拓扑序；上游先于下游，同层按稳定 ID 排序。它必须随 impact 一起返回。用户界面可以提供专用视图，但必须复用同一 impact 结果，不得另造排序领域能力。
- 显式指定 Node 的影响查询始终从该 Node 遍历，不依赖其当前状态。

上游确认不会修改下游 Confirmation；下游仍可通过旧输入版本基线保持 `input_changed`。

### 7.2 Agent 查询

基础影响结果至少包含：

```yaml
schema_version: 2
changed_nodes: []
affected_nodes: []
review_order: []
issues: []
```

每个结果项按需包含 Node ID、名称、全部文件路径、具体变化路径、reasons、depth、经过的 Derivation 与来源根。

独立可组合的查询方向：

- upstream：目标的前提 Node、文件路径和 Derivation；
- downstream：目标可能影响的 Node、路径和层级；
- neighborhood：与目标直接相连的 Derivation、inputs、outputs 和 sibling outputs；
- status/impact：当前变化与待检查状态。

调用方可展开 Derivation short/detail、input/output short/detail、影响路径和确认差异。任何模式都不得返回正文、片段、摘要或 Prompt。

按文件路径定位 Node 是 Agent 工作流的入口查询：返回是否受管、所属 Node 的稳定 ID、名称与全部文件路径。未受管文件返回明确的“未登记”结果，不作为错误，也不触发自动登记。

## 8. Git 持久化

```text
.kflow/
├── project.json             # tracked
├── .gitignore               # tracked
├── nodes/                   # tracked
├── derivations/             # tracked
├── confirmations/           # tracked
├── cache/                   # ignored，可重建
└── runtime/                 # ignored，可删除
```

- Node、Derivation、Confirmation 分文件是规范真相源。
- index、反向引用、邻接、状态和 review order 都是派生数据。
- 单文件更新使用临时文件和原子替换；多文件图编辑使用忽略的临时事务清单恢复。
- 首版同一工作区采用单写者文件锁，不承诺并发写合并。
- checkout 任意 commit 后，应能仅凭该版本规范元数据和文件重建拓扑与确认基线。
- 历史比较只做稳定 ID 的 added/removed/modified diff；当前不实现历史 UI、快照或重放。

## 9. 生命周期原则

用户可见操作保持简单、原子、可组合；每次操作涉及的全部元数据写入必须由内部事务保证一致，失败时不得暴露半完成状态。

### 9.1 初始化与 Node

- 初始化只建立 KFlow 规范元数据结构和忽略规则，不读取正文建图。
- 新建 Node 只绑定已有文件并创建孤立 Node，不同时创建 Derivation。
- Node 改名保持 ID，不影响 effective version；文件集合变化会影响目标及下游。
- 删除 Node 仅在它不属于任何 Derivation 的 inputs 或 outputs 时允许；操作原子删除 Node 及其 Confirmation，用户文件保持不变。否则拒绝并返回关联 Derivation。

### 9.2 Derivation

- 新建 Derivation 连接已有 Node；inputs、outputs 均非空，outputs 必须当前没有生产者。
- 修改 Derivation 可以改变语义、input/output 角色或拓扑；提交后的对象必须满足全部图不变量，语义或拓扑变化会影响其 outputs 及下游。
- 删除 Derivation 只删除该 Derivation；其 outputs 保留并自动成为无生产者源 Node。旧 Confirmation 保留为检查基线，outputs 产生 `derivation_changed`，下游按版本变化产生 `input_changed`。
- 删除或修改操作必须返回失去 producer 的 outputs、受影响下游及不再匹配当前事实的确认基线。

### 9.3 producer 变化

producer 变化通过修改或删除相关 Derivation，再修改目标 Derivation 来组合完成，不提供独立 `rewire` 用户概念。无 producer 的中间 Node 是合法源 Node，因此每一步都能形成合法、可恢复的状态。

单次修改仍必须原子写入该操作涉及的所有对象；若未来某个界面把多步组合封装为一次请求，该请求也必须以一个内部事务提交或整体失败。用户接口的简单性不能以牺牲持久化一致性为代价。

所有生命周期操作只处理 KFlow 元数据，不创建、编辑、移动或删除用户文件。

## 10. v1 迁移

采用“只读预检 → 必要人工补全 → 生成独立 v2 数据 → validate → 显式切换”的一次性迁移，不在 v2 运行时兼容两套 schema。

可机械迁移：

- 保留 Node/Derivation ID；
- `file → files[]`；
- `summary → derivation.short`；
- `role/role_detail → input.short/detail`；
- `method/method_detail → output.short/detail`；
- 从 Derivation 重建生产者和消费者索引。

必须报告或人工处理：

- `file=null`、路径冲突、缺失文件、重复生产者或坏引用；
- v1 Derivation 缺少独立 `detail` 时使用规范空字符串，不阻塞迁移；缺失的必填 `short` 仍须人工补全；
- 是否把多条单输出 Derivation 合并为多输出，默认不自动判断。

v1 无生产者的源 Node 可直接迁移为 v2 源 Node，不再补建零输入 Derivation。不迁移红黄绿状态、级联确认结果和 `index.json`；迁移后 Node 初始为 `unconfirmed`。

迁移不得原地覆盖 v1 元数据，也不得改写正文。

## 11. 实施边界与依赖顺序

v2 当前已推进到 Agent 查询基础阶段。后续继续按依赖顺序推进，每阶段单独审查：

1. **修正纯领域内核**：落实无生产者源 Node、Derivation 非空输入、至多一个生产者、源 Node effective version 和可空 detail。
2. **最小规范读写**：仅支撑首切片所需的 project、Node、Derivation、Confirmation 加载、校验与原子确认写入。
3. **状态闭环**：fingerprint、scan、reasons、单 Node confirm。
4. **Agent 查询与薄适配层**：项目启用判断、按文件定位、upstream/neighborhood、impact（含 `review_order`）和剩余影响查询；提供稳定机器契约并验证零正文泄漏。
5. **真实项目 dogfood**：只验证正式使用场景 Section A 的黄金流程，并在闭环成立后停止首切片。

完整建图 CLI、完整删除策略、v1 迁移、人类图谱、Git 历史比较、MCP、Web UI、watcher 和自动候选文件发现均不进入首切片。详细阶段与停止点见 `KFlow_v2_首个垂直切片实施计划.md`。

## 12. 核心验收矩阵

| 场景 | 必须结果 |
|---|---|
| 新建 Node | 可独立存在，无生产者即源 |
| 创建零输入 Derivation | 拒绝 |
| 三层 `detail` 为空 | 接受并规范编码为空字符串；三层 `short` 仍必填 |
| 多文件 Node 任一文件变化 | 同一 Node `files_changed`，返回具体路径 |
| 文件重命名并更新 Node | ID 不变，路径变化可见，目标及下游待检查 |
| `A,B → C,D` 中 A 变化 | C/D 均为直接影响，顺序稳定 |
| confirm C | D 和所有下游 Confirmation 不变 |
| `A → B → C` 中 A 变化后 confirm B | C 仍待检查 |
| Derivation 语义或拓扑变化 | outputs 及下游待检查 |
| 删除 producing Derivation | outputs 成为源并为 `derivation_changed`；旧 Confirmation 保留 |
| C 自身变化且与 D 同源 | 展示 D 为 sibling，不自动判定 D 已变化 |
| 按文件路径定位 | 返回所属 Node 与全部路径；未登记不是错误 |
| impact 查询 | 同时返回稳定 `review_order`；专用 CLI 视图复用同一结果，不存在独立排序领域操作 |
| 删除元数据 | 用户文件字节不变 |
| 删除 cache/index | 可从 tracked 规范文件完整重建 |
| checkout 历史 commit | 可重建该版本拓扑和确认基线 |
| Agent 查询 | 只含元数据与路径，不含正文或摘要 |

## 13. 本轮收敛结论

- 无生产者 Node 与孤立 Node 合法，自动视为源 Node。
- Derivation 两端均非空，每个 Node 至多一个 producer。
- 三层 `short` 必填，三层 `detail` 可为空。
- producer 变化由 Derivation 操作组合表达，不提供独立 `rewire`。
- producer 增删或替换时保留旧 Confirmation，以 `derivation_changed` 表达基线差异。
- confirm 只写一个 Node；`review_order` 只由 impact 查询计算，专用展示不得另造排序语义。
- 首切片只验证 Agent 黄金流程；其余能力按正式使用场景 Section D 或排除清单处理。
