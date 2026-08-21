# KFlow v2 领域模型与重构方案（Approved）

> 状态：已由产品负责人整体批准，可按依赖式路线实施。  
> 版本：Approved 1  
> 前置材料：`KFlow_v2_重构启动指令.md`、`docs/KFlow_v2_首轮审查报告.md`。  
> 本文定义 v2 核心模型、状态算法、持久化契约和实施路线；实施仍按小任务、小改动和阶段审查推进。

## 1. 审查摘要

本方案把 KFlow v2 定义为一个 Git-native 的文档拓扑和影响范围管理器：

- Knowledge Node 管理一个或多个不可分割的项目文件；
- Derivation 作为零个或多个输入到一个或多个输出的完整推导活动；
- 每个 Node 恰好由一个 Derivation 产生，源 Node 统一由零输入 Derivation 产生；
- 文件、推导和直接输入的有效版本共同决定 Node 是否需要检查；
- confirm 只更新一个 Node 的共享确认基线，绝不级联；
- Node、Derivation、Confirmation 进入 Git；索引、扫描缓存和锁可重建且不进入 Git；
- Agent 查询只返回拓扑、状态原因、文件路径和 Derivation 语义，不返回任何正文；
- v1 通过预检和一次性迁移处理，v2 运行时不保留双格式兼容。

本文把此前剩余未决项收敛为实现负责人建议，并已获得产品负责人整体批准。具体命令名仍按阶段 5 的独立审查点处理，不反向改变领域模型。

## 2. 已确认的产品决策

### D1：源 Node 使用零输入 Derivation

- 每个 Node 恰好有一个 producing Derivation。
- 源 Node 不使用额外 `source` 类型或布尔字段。
- `inputs=[]` 是源 Derivation 的唯一结构化标志。
- 一个零输入 Derivation 可以产出一个或多个共同形成的源 Node。

### D2：confirm 固定三部分基线

confirm 记录：

1. 目标 Node 自身文件集合 fingerprint；
2. producing Derivation fingerprint；
3. producing Derivation 的直接输入 Node 有效版本向量。

### D3：Confirmation 是 Git 跟踪的共享事实

- Node、Derivation 和每个 Node 的 Confirmation 进入 Git。
- index、scan cache、临时 observation、锁和事务临时文件不进入 Git。
- 不引入个人确认 overlay、publish 流程、用户身份或审批系统。

## 3. 严格边界

v2 核心不得：

- 返回、缓存为 Agent 上下文或拼装任何文档正文、片段、摘要或 Prompt；
- 创建、编辑、移动或删除用户正文；
- 建立固定关系类型枚举；
- 建立章节、段落、标题或代码片段级 Node；
- 用向量相似度替代显式 Derivation；
- 自动判断某份文档语义正确或错误；
- 自动确认下游或同一 Derivation 的其他输出；
- 引入 event sourcing、全量命令日志、快照数据库或时间旅行引擎；
- 为方案替代建立 `supersedes`/`replaces` 特殊关系；
- 为兼容 v1 牺牲 v2 模型。

## 4. 规范领域模型

以下 YAML 仅用于说明字段；最终持久化使用 UTF-8 JSON。

### 4.1 ProjectManifest

```yaml
kind: kflow-project
schema_version: 2
```

职责：

- 标识 KFlow 项目和 schema 大版本；
- 作为 codec、validate 和 migration 的入口；
- 不保存可从规范分文件重建的计数或索引。

### 4.2 KnowledgeNode

```yaml
kind: node
schema_version: 2
id: nd_opaque_stable_id
name: architecture
files:
  - docs/architecture.md
  - docs/architecture.svg
```

字段语义：

- `id`：不依赖名称或路径的稳定身份；文件重命名、Node 改名后保持不变。
- `name`：面向人和 Agent 的项目内唯一显示名；不是稳定身份。
- `files`：共同构成该知识单元的非空文件集合。

不增加 `type`、`summary`、关系标签或正文摘录字段。Node 的“为何存在”和“如何形成”由 producing Derivation 的语义说明。

### 4.3 Derivation

```yaml
kind: derivation
schema_version: 2
id: dv_opaque_stable_id
short: 综合需求与约束形成系统设计
detail: 根据功能需求、性能目标和部署约束共同确定系统架构及接口设计。
inputs:
  - node: nd_requirements
    short: 提供功能目标
    detail: 定义必须支持的能力、输入输出和使用场景。
  - node: nd_constraints
    short: 提供实现约束
    detail: 定义性能、资源、兼容性和部署环境限制。
outputs:
  - node: nd_architecture
    short: 形成总体架构
    detail: 确定组件边界、数据流和运行方式。
  - node: nd_api_design
    short: 形成接口方案
    detail: 根据系统边界和场景确定接口及约束。
```

字段语义：

- `short/detail`：描述整次推导。
- `inputs[].short/detail`：描述该输入在本次推导中的角色。
- `outputs[].short/detail`：描述该输出作为本次推导结果的含义。
- `inputs` 可为空；`outputs` 必须非空。

拓扑只由 `inputs[].node` 和 `outputs[].node` 决定。自由文本不触发机器规则。

### 4.4 NodeConfirmation

```yaml
kind: confirmation
schema_version: 2
node: nd_architecture
files:
  - path: docs/architecture.md
    fingerprint:
      algorithm: sha256
      value: "..."
  - path: docs/architecture.svg
    fingerprint:
      algorithm: sha256
      value: "..."
files_fingerprint:
  algorithm: sha256
  value: "..."
producing_derivation:
  id: dv_system_design
  fingerprint:
    algorithm: sha256
    value: "..."
inputs:
  - node: nd_constraints
    effective_version: "..."
  - node: nd_requirements
    effective_version: "..."
effective_version: "..."
```

职责：

- 记录该 Node 最近一次被 Agent 或人检查时的确定性版本基线；
- 提供具体文件变化、Derivation 变化和直接输入变化的可解释对比；
- 为下游 Node 的输入版本向量提供稳定值。

不保存 `confirmed_by`、时间戳或审批结论。Git commit 已提供作者、时间和历史；当前阶段不建立身份/权限模型。

## 5. 全局不变量

### 5.1 Node 与文件归属

1. Node `id` 全局唯一且不可变。
2. Node `name` 在项目内唯一。
3. `files` 至少包含一个路径，集合内不得重复。
4. 路径必须是使用 `/` 的规范仓库相对路径，不得为绝对路径、目录或包含 `..` 越界。
5. 每个规范文件路径恰好归属于零个或一个 Node；同一文件不能属于多个 Node。
6. 注册时文件必须存在且为普通文件；文件后续缺失作为 validation/scan issue 报告。
7. KFlow 不因 Node 新增、更新或删除而改写真实文件。

“零个 Node”表示普通项目文件可不受 KFlow 管理；“进入某个 Node 后”则必须满足唯一归属。

### 5.2 Derivation 与生产者

1. Derivation `id` 全局唯一且不可变。
2. Derivation 的 `short/detail` 均为非空文本。
3. 每个 input/output 的 `short/detail` 均为非空文本。
4. 同一 Derivation 内 input Node 不重复，output Node 不重复。
5. 同一 Node 不得同时成为同一 Derivation 的 input 和 output。
6. 每个 Node 恰好出现在一个 Derivation 的 `outputs` 中。
7. 一个 Node 可出现在任意多个 Derivation 的 `inputs` 中。
8. 所有 input/output Node 必须存在。
9. 将 Derivation 投影为 `每个 input → 每个 output` 后，整个 Node 图必须无环。
10. 零输入 Derivation 是合法且唯一的源知识表达；零输出 Derivation 非法。

### 5.3 Confirmation

1. 每个 Node 至多一个当前 Confirmation 文件。
2. Confirmation 的 `node` 必须存在，并与文件名匹配。
3. Confirmation 的 producing Derivation ID 必须是该 Node 的唯一生产者。
4. Confirmation 的文件路径集合必须等于当时 Node 的文件集合。
5. Confirmation 输入集合必须等于当时 producing Derivation 的输入集合。
6. confirm 只写目标 Node 的 Confirmation，不写任何其他 Node。
7. Confirmation 不是真伪证明，只表示已在记录的版本条件下完成检查。

## 6. 规范化、fingerprint 与有效版本

### 6.1 规范序列化

- JSON 使用 UTF-8、LF 换行、固定缩进和稳定 key 顺序。
- `files` 按规范路径排序。
- Derivation inputs/outputs 在领域语义上是集合，持久化和 fingerprint 按 Node ID 排序。
- Confirmation files 按路径排序，inputs 按 Node ID 排序。
- 自由文本保留原字符，不做语义归一化。

这样同一事实只产生一种规范序列化，便于 Git diff 和跨版本比较。

### 6.2 文件 fingerprint

首版使用带算法标签的 SHA-256：

```text
file_fingerprint = SHA256(raw file bytes)
files_fingerprint = SHA256(canonical [(normalized_path, file_fingerprint)])
```

路径被纳入集合 fingerprint，因此文件重命名会被识别为 Node 变化，但不会改变 Node ID。原始字节变化包括格式和换行变化；KFlow 只报告变化，不判断语义重要性，Agent 可以检查后直接 confirm。

算法名称随值保存，未来可以显式迁移，不能静默改变算法。

### 6.3 Derivation fingerprint

```text
derivation_fingerprint = SHA256(canonical derivation JSON)
```

包括：

- Derivation ID、short/detail；
- 全部 input Node ID 及 short/detail；
- 全部 output Node ID 及 short/detail；
- schema version。

任一拓扑或语义变化都会使该 Derivation 的所有输出需要重新检查。这是保守且可解释的行为，符合“修改输出时必须检查 producing Derivation 和同源输出”的要求。

### 6.4 Node 当前有效版本

按 DAG 拓扑顺序递归计算：

```text
effective_version(node) = SHA256(canonical [
  node.id,
  current_files_fingerprint(node),
  current_derivation_fingerprint(producer(node)),
  sorted [(input.node_id, effective_version(input))]
])
```

源 Node 的输入向量为空。计算不读取 Confirmation，因此 confirm 不会改变任何 Node 的当前有效版本，只会记录目标 Node 已经检查到该版本。

该定义保证：

- 上游内容、路径、推导语义或拓扑发生变化时，下游有效版本逐层变化；
- 确认 B 不会让 C 自动恢复，因为 C 的旧 Confirmation 仍记录旧的 B 有效版本；
- 如果内容精确恢复到旧版本，effective version 也恢复，KFlow 按当前事实判断而不保留临时变化事件；这符合“不引入事件溯源”的边界。

## 7. 状态与 confirm 语义

### 7.1 状态是派生结果，不是颜色字段

对每个 Node 比较当前事实与 Confirmation，返回可并存的 reason：

```text
unconfirmed          没有 Confirmation
files_changed        文件集合、路径或内容 fingerprint 不同
derivation_changed   producing Derivation ID 或 fingerprint 不同
input_changed        一个或多个直接输入 effective version 不同
```

派生字段：

```text
needs_review = reasons 非空
current = reasons 为空
```

validation issue（文件缺失、图非法、schema 损坏）与 review state 分开返回，不能伪装成红色状态。

### 7.2 confirm

`confirm(node)` 的业务语义：

> Agent 或人已经检查目标 Node 的当前文件、producing Derivation 和当前直接输入条件，认为该 Node 仍成立或已完成必要修改。

执行规则：

1. 先要求规范图和目标文件可读取；存在阻断性 validation error 时拒绝。
2. 计算目标 Node 当前三部分基线和 effective version。
3. 原子写入或替换该 Node 的 Confirmation 文件。
4. 不写任何其他 Confirmation。
5. 返回目标状态、此前 reasons 和仍待检查的下游摘要。

不存在 `--cascade`。同一 Derivation 的多个输出必须分别 confirm。

### 7.3 同源输出

对于 `A,B → C,D`：

- A/B 或 Derivation 变化会使 C/D 都需要检查；
- C 自身文件变化不会自动宣称 D 受影响；
- 查询 C 时必须展示 producing Derivation 和 sibling output D，提醒 Agent 判断推导是否也需更新；
- 若 Agent 更新了 Derivation，Derivation fingerprint 变化会使 C/D 都需要检查；
- confirm C 永远不修改 D。

## 8. 变化检测与影响传播

### 8.1 scan

scan 是只读计算：

1. 加载并 validate 规范元数据；
2. 读取 Node 文件并计算当前 fingerprint；
3. 按拓扑序计算 Derivation fingerprint 和 Node effective version；
4. 与 Confirmation 对比得到 reasons；
5. 可选更新本地可重建 cache，但不改变共享状态。

不再依赖人工 `modify`。首版不需要文件 watcher、hook 或常驻服务。

### 8.2 影响传播

- 当前存在 `files_changed` 或 `derivation_changed` 的 Node 作为尚未确认的变化根；未确认 Node 单独列出，不默认视作变化事件。
- 沿 Node 作为 input 的 Derivation，传播到该 Derivation 的全部 outputs。
- `depth=1` 为直接输出，后续为传递影响。
- 多根影响合并时保留每个目标的最小深度、全部直接来源和可解释路径。
- review order 是所有 `needs_review` Node 构成子图的稳定拓扑序；同层无依赖 Node 按 ID 排序。
- KFlow 只报告“可能受影响”，不声明必须改写。

上游 Node confirm 后，它不再是“当前变化根”，但下游 Confirmation 仍保存旧输入有效版本，因此下游继续保持 `input_changed`。此时状态结果以发生版本不匹配的直接输入作为 `causes`，无需永久保存最初变化事件。显式 `affect <node>` 查询则始终从指定 Node 做拓扑遍历，不依赖该 Node 当前是否已 confirm。

`input_changed` 可由有效版本直接判断；影响遍历用于生成层级、路径和处理顺序，两者必须得到一致结果。

## 9. Agent 查询契约

### 9.1 基础影响结果

```yaml
schema_version: 2
changed_nodes:
  - node: nd_requirements
    name: requirements
    files: [docs/requirements.md]
    changed_files: [docs/requirements.md]
    reasons: [files_changed]
affected_nodes:
  - node: nd_architecture
    name: architecture
    files: [docs/architecture.md, docs/architecture.svg]
    depth: 1
    reasons: [input_changed]
    via_derivations: [dv_system_design]
    roots: [nd_requirements]
review_order:
  - nd_architecture
  - nd_api_design
issues: []
```

基础结果必须优先包含：

- 变化 Node；
- Node 的全部文件路径及发生变化的具体路径；
- 直接/传递层级；
- 稳定拓扑检查顺序；
- 状态 reasons；
- 阻断性 validation issues。

### 9.2 可选展开

调用方可按需请求：

- 涉及的 Derivation ID；
- Derivation short/detail；
- input/output short/detail；
- 影响路径；
- producing Derivation 的 sibling outputs；
- Confirmation 中的 fingerprint/version 差异。

任何模式都禁止返回文档正文、片段、摘要或 Prompt。

### 9.3 修改前查询

提供独立可组合方向：

- upstream：目标的前提 Node、文件路径和 Derivation；
- downstream：目标可能影响的 Node、路径和层级；
- neighborhood：目标 producing Derivation 的 inputs、outputs 和语义；
- status/impact：当前变化与待检查状态。

不强制 Agent 使用单一工作流，也不自动打开文件。

## 10. Git 持久化布局

推荐布局：

```text
.kflow/
├── project.json                         # tracked
├── .gitignore                           # tracked，仅忽略本地子目录
├── nodes/                               # tracked
│   └── nd_<id>.json
├── derivations/                         # tracked
│   └── dv_<id>.json
├── confirmations/                       # tracked
│   └── nd_<id>.json
├── cache/                               # ignored，可重建
│   ├── index.json
│   └── observations.json
└── runtime/                             # ignored，可删除
    ├── lock
    └── transactions/
```

`.kflow/.gitignore`：

```gitignore
/cache/
/runtime/
```

仓库根 `.gitignore` 必须删除现有的 `.kflow/` 整体忽略规则。规范元数据不得与缓存混在同一忽略边界。

### 10.1 真相源

- Node/Derivation/Confirmation 分文件是规范真相源。
- index、反向引用、邻接表、状态和 review order 均为派生数据。
- Node 文件不持久化消费者/生产者反向引用，消除 v1 的双向事实不一致。

### 10.2 安全写入

- 单文件更新使用同目录临时文件、flush/fsync 和原子 replace。
- 涉及多个规范文件的图编辑使用 `.kflow/runtime/transactions/` 中的临时事务清单；完成后删除，失败时可回滚或继续。
- 临时事务只用于崩溃恢复，不进入 Git，不构成事件历史。
- 同一工作区首版采用单写者文件锁；不承诺并发写入合并。

### 10.3 Git 历史边界

- Git 保存正文、Node、Derivation 和 Confirmation 历史。
- checkout 任意 commit 后可从该版本规范文件重建图和确认基线。
- 未来拓扑历史比较按稳定 ID 对 Node/Derivation 做 added/removed/modified diff。
- 当前阶段不实现历史 UI、快照或重放引擎。

## 11. 生命周期操作原则

### 11.1 注册源知识

由于 Node 不能脱离生产者存在，“创建源 Node”是一个原子领域操作：

```text
绑定一个或多个已存在文件
+ 创建零输入 Derivation
+ 创建其一个或多个输出 Node
```

KFlow 不创建 Markdown 占位文件。缺失 `short/detail` 时拒绝写入。

### 11.2 创建普通推导

一个原子操作创建 Derivation 及其一个或多个新输出 Node。若要改变现有 Node 的生产者，必须使用显式 rewire/update 操作，在单个事务中移除旧生产者关系并建立新关系，过程中不能提交非法中间图。

### 11.3 修改元数据

- Node 改名：保持 ID；不影响有效版本。
- Node 文件路径/成员变化：保持 ID；files fingerprint 改变，目标及下游需要检查。
- Derivation 文本或拓扑变化：fingerprint 改变，其全部输出及下游需要检查。
- 纯缓存重建：不影响任何 Confirmation。

### 11.4 删除

- 默认只删除 KFlow 元数据，绝不删除用户文件。
- 有下游消费者的 Node 默认拒绝删除，必须先显式 rewire 或确认级联移除的元数据范围。
- 从多输出 Derivation 移除一个 output 会改变该 Derivation fingerprint，使其他 outputs 需要检查。
- 删除最后一个 output 时同时删除 Derivation。
- 删除 Node 时删除其 Confirmation；保留原文件不受管理。

## 12. v1 一次性迁移策略

### 12.1 决策

采用“只读预检 → 人工补全映射 → 生成独立 v2 数据 → validate → 显式切换”的一次性迁移。不在 v2 运行时读取或写回 v1 schema。

### 12.2 可机械迁移

- 保留现有 Node/Derivation ID，避免破坏身份引用；新 ID 使用更大随机空间。
- `file` 包装成 `files: [file]`。
- `summary → Derivation.short`。
- `role/role_detail → input.short/detail`。
- `method/method_detail → output.short/detail`。
- 单 output 包装成 `outputs: [output]`。
- 从 Derivation 文件重建全部生产者和消费者索引，不信任 v1 Node 双向引用。

### 12.3 必须人工处理

- `file=null` 的 Node：必须绑定至少一个真实文件或从迁移范围删除。
- v1 Derivation 缺少独立 `detail`：映射文件必须补全，迁移器不得虚构。
- v1 源 Node 缺少零输入 Derivation：必须为每组源 Node 提供 Derivation short/detail 和每个 output short/detail。
- 多条 v1 单输出 Derivation 是否应合并为一个多输出 Derivation：默认不自动合并；只按用户显式映射合并。
- 双向引用、重复生产者、路径冲突或缺失文件：作为阻断项报告。

### 12.4 不迁移

- v1 `green/yellow/red` 状态；它缺少版本依据，不能可信映射。
- `confirm --cascade` 的结果。
- `index.json`；由 v2 规范文件重建。

迁移后的 Node 初始为 `unconfirmed`，需要 scan 和逐 Node confirm。

### 12.5 安全要求

- 预检不写文件。
- 不原地覆盖 v1 `.kflow/`；输出到显式目标并生成计数对账。
- 永不改写、移动或删除正文。
- 只有全部阻断项解决且 v2 validate 通过后，才允许用户显式切换。

## 13. 依赖式实施路线

不按时间估算组织；每一阶段均以前一阶段的审查结果为输入。

### 阶段 0：冻结 v1 基线

- 目标：保护可运行参考。
- 输入：当前 98 项测试、README、v1 schema。
- 输出：行为基线清单和可复现测试命令；是否打 tag/建分支由用户另行授权。
- 验收：98 tests passed，ruff clean，工作树中用户文档不被改动。
- 风险：把冲突的 v1 行为误当作 v2 兼容要求。
- 审查点：明确“参考测试”与“v2 必须通过的业务测试”。

### 阶段 1：领域契约与纯图内核

- 目标：不依赖文件系统/CLI 实现批准后的对象和不变量。
- 输入：本文批准版。
- 输出：Node、Derivation、图索引、validate rules、有效版本纯函数接口。
- 验收：零/多输入、多输出、恰好一个生产者、文件唯一归属和 DAG 全部可验证。
- 风险：把 Derivation 拆成普通二元关系；把输入/输出顺序误当业务语义。
- 测试：模型构造、生产者冲突、环、`A,B → C,D`、零输入多输出。
- 审查点：领域层不得导入 CLI、Git 或具体 JSON 路径。

### 阶段 2：versioned codec、规范存储与缓存

- 目标：实现 Git-friendly 真相源和可恢复写入。
- 输入：阶段 1 稳定模型。
- 输出：project/node/derivation/confirmation codec、原子写入、事务恢复、index/reindex、v2 validate。
- 验收：规范序列化确定；缓存删除后完全重建；故障不留下不可恢复半图。
- 风险：Windows replace/fsync、跨文件事务、路径越界。
- 测试：golden JSON、round-trip、故障注入、路径规范化、损坏缓存恢复。
- 审查点：确认 tracked/ignored 清单和 schema diff 可读性。

### 阶段 3：fingerprint、有效版本与 confirm

- 目标：完成无需红黄绿字段的状态闭环。
- 输入：阶段 2 存储与已批准 D2/D3。
- 输出：scan、fingerprint、effective version、reasons、单 Node confirm。
- 验收：自身/Derivation/输入变化原因可区分；confirm 不级联；工作树未提交修改可处理。
- 风险：大文件 hashing 成本、换行变化噪声、深 DAG 计算。
- 测试：多文件 Node、路径重命名、多输入、多输出、链式确认、内容恢复旧版本。
- 审查点：状态必须可从规范事实重建，不得新增事件日志。

### 阶段 4：影响与 Agent 查询

- 目标：向 Agent 返回最小、充分、可解释的元数据结果。
- 输入：阶段 3 状态引擎。
- 输出：upstream/downstream/neighborhood/status/impact 领域查询与 JSON 契约。
- 验收：返回变化路径、层级、拓扑序、Derivation 路径和 sibling outputs；零正文泄漏。
- 风险：响应过大、重复路径、把“可能影响”表述成“必须修改”。
- 测试：JSON golden、多个变化根、共享下游、深度限制、正文泄漏防护。
- 审查点：先稳定领域结果，不同时引入 MCP/UI。

### 阶段 5：薄 CLI 与 dogfood

- 目标：以通用 CLI + JSON 完成真实闭环。
- 输入：稳定领域 API。
- 输出：init/register/derive/scan/status/context/affect/confirm/validate/reindex 等薄适配；最终命令名在该阶段审查。
- 验收：KFlow 自身可建图并完成“文件变化 → 影响查询 → 逐 Node confirm”。
- 风险：为兼容 v1 参数污染领域层；CLI 隐式创建或删除正文。
- 测试：临时 Git 仓库端到端、退出码、机器/人类输出。
- 审查点：用真实 Agent 会话验证是否减少无关文件扫描。

### 阶段 6：v1 迁移器（有真实数据需求时）

- 目标：安全转换有价值的 v1 元数据。
- 输入：稳定 v2 codec 和真实只读样本。
- 输出：preflight、补全映射模板、一次性转换、对账和回滚说明。
- 验收：ID 保留、正文零写入、缺失语义不虚构、v2 validate 通过。
- 风险：坏引用、无文件 Node、全部旧 Derivation 缺少 detail。
- 测试：合法/损坏/冲突/中断样本。
- 审查点：转换结果逐项目人工审查后切换。

### 阶段 7：人类图谱与 Git 版本比较（后续立项）

- 前提：核心模型经过 dogfood 稳定。
- 只消费相同规范模型，不增加第二套关系。
- 先做只读当前图和按 Git ref 的拓扑 diff；Web UI、MCP 和更深 Agent 集成分别审查。

## 14. v2 验收矩阵

| 场景 | 必须结果 |
|---|---|
| 多文件 Node 任一文件变化 | 同一 Node `files_changed`，返回具体路径 |
| 文件重命名并更新 Node | ID 不变，路径变化可见，目标及下游待检查 |
| `A,B → C,D` 中 A 变化 | C/D 均为直接影响，顺序稳定 |
| confirm C | D 和所有传递下游 Confirmation 不变 |
| `A → B → C` 中 A 变化后 confirm B | C 仍待检查 |
| Derivation short/detail 变化 | 其全部输出和下游待检查 |
| C 自身文件变化且与 D 同源 | 展示 D 为 sibling output，不自动判定 D 已受影响 |
| 删除 Node 元数据 | 用户文件保持原样 |
| 删除 cache/index | 可从 tracked 规范文件完整重建 |
| checkout 历史 commit | 可重建该版本拓扑和确认基线 |
| Agent 基础查询 | 只含元数据/路径，不含正文或摘要 |
| v1 迁移缺失 detail | 明确阻断，不生成虚构文本 |

## 15. 主要风险与控制

- **Confirmation Git 噪声**：按 Node 分文件，限制冲突范围；不保存时间戳等非确定字段。
- **递归版本计算成本**：按拓扑序单次计算并使用本地 cache；cache 永远不是事实源。
- **大文件 hashing**：先正确实现，可基于 stat + cache 优化；缓存命中不能跳过明确要求的强制重扫。
- **Derivation 全量 fingerprint 过于保守**：优先保证可解释正确性；实际 dogfood 后再评估是否需要更细粒度，但不提前引入 impact policy。
- **多文件事务失败**：使用忽略的临时事务和显式恢复，不用永久事件日志。
- **Git 合并产生非法图**：validate 在读操作和写操作前后检查；提供报告，不静默猜测修复。
- **v1 迁移语义缺失**：人工补全映射是硬门槛，不以兼容为由放宽 v2 schema。
- **KFlow 越界为编辑器**：所有生命周期测试必须断言用户文件字节不变。

## 16. 整体审查项

请整体审查以下方案：

1. 第 4～7 节的 schema、fingerprint、effective version 和 confirm 语义；
2. 第 8～9 节的影响传播与 Agent 输出；
3. 第 10 节的 Git tracked/ignored 边界；
4. 第 11～12 节的生命周期与一次性迁移；
5. 第 13 节按依赖组织的实施路线。

方案已整体批准。下一步从“阶段 0 基线确认 + 阶段 1 契约测试”开始，以小任务和小改动推进；v1 实现保持隔离，直到 v2 对应能力具备独立验收基线。
