# KFlow v2 首轮审查报告（Approved Baseline）

> 状态：首轮基线已批准；后续实现以 `KFlow_v2_领域模型与重构方案.md` 的 Approved 1 为准。  
> 依据：`KFlow_v2_重构启动指令.md`、当前仓库实现、现有设计文档、98 项测试与 Git 历史。  
> 边界：本报告不批准 schema，不修改 v1 行为，不启动大规模重构。

## 1. 审查结论

KFlow v1 是一个可运行、测试完整的“文档 DAG + 手工状态传播”概念验证。它已经证明了 Node、Derivation、上下游查询、环检测、索引重建和 CLI/JSON 双输出的可行性，但其领域模型被以下假设锁定：一个 Node 最多对应一个 Markdown 文件、一个 Derivation 只能有一个输出、状态是持久化的红黄绿单字段、变化依赖人工 `modify`、确认允许向下游级联、整个 `.kflow/` 不进入 Git。

这些假设与 v2 的核心产品定义直接冲突。v2 不适合在现有 dataclass 和存储 JSON 上逐字段扩展；应保留算法与工程经验，重新定义领域对象、状态事实和持久化边界，再以兼容性适配或一次性迁移读取 v1 数据。

产品负责人已决定：**Q1 采用方案 A，所有 Knowledge Node 都由且仅由一个 Derivation 产生，源知识统一使用零输入 Derivation；Q2 采用方案 B，confirm 固定目标文件、producing Derivation 和直接输入有效版本三部分基线；Q3 采用方案 A，Confirmation 是进入 Git 的共享项目事实**。其余架构项不再逐项追问，由实现负责人形成最佳方案后整体提交审查。

## 2. 审查范围与基线

已检查：

- `README.md`、`CLAUDE.md`、启动指令和 `docs/` 下现有设计/计划；仓库没有 `AGENTS.md`。
- `kflow/models.py`、`store.py`、`graph.py`、`status.py`、`output.py`、CLI 入口和全部命令。
- `tests/` 下全部 98 项测试。
- `.gitignore`、`pyproject.toml` 和最近的重要提交。

验证结果：

- `pytest -q -p no:cacheprovider --basetemp ...`：98 passed。
- `ruff check .`：通过。
- 当前工作树已有两个用户提供的未跟踪文档：v2 启动指令和旧重构计划书；本轮未修改它们。
- 最近实现历史显示 v1 按模型、存储、图算法、状态、CLI、12 个命令、输出和测试依次构建；最新重要集成提交宣称并实际保有 98 项测试。

注意：沙箱内默认 pytest 临时目录不可访问，首次运行出现的 57 个错误均发生在 `tmp_path` 夹具建立阶段；在获批的沙箱外工作区临时目录重跑后全部通过，不是代码失败。

## 3. KFlow v1 的实际领域模型

### 3.1 Node

`Node` 持久化以下事实：

```text
id
name
file: string | null
status: green | yellow | red
derivations_as_input: derivation ids
derivations_as_output: derivation ids
```

实际语义：

- `file` 最多一个，默认固定创建为 `knowledge/<name>.md`；`--no-file` 允许无文件 Node。
- `id` 是随机 6 位十六进制标识，重命名理论上可以保持 ID，但 v1 没有重命名/重新绑定文件命令。
- Node 同时保存作为 Derivation 输入和输出的反向引用，因此拓扑事实与 Derivation 重复存储。
- `derivations_as_output` 命名表示“该 Node 是这些 Derivation 的输出”，正常 CLI 只会放入一个 ID，但模型和校验器没有直接声明生产者唯一性。
- 状态是 Node 当前记录上的单一可变字段，没有“由哪个上游版本触发”“基于什么 fingerprint 确认”等事实。

### 3.2 Derivation

```text
id
summary
inputs[]:
  node
  role
  role_detail
output:
  node
  method
  method_detail
```

实际语义是“一到多输入 → 单输出”。`summary` 近似 v2 的 Derivation `short`；输入 `role/role_detail` 近似 input `short/detail`；输出 `method/method_detail` 近似 output `short/detail`。v1 没有 Derivation 自身独立的 `detail`，也没有 outputs 列表。

### 3.3 图与状态

- 图按 Node 之间的投影边遍历：每个 Derivation 的每个 input 都投影为 `input Node → output Node`。
- `bfs_upstream` 返回上游子图的 Node 拓扑序；`bfs_downstream` 返回 Node 到深度的映射。
- Kahn 算法检查环；新增 Derivation 前通过可达性判断是否成环。
- `modify X` 把 X 置绿，并把全部传递下游置黄。
- `remove X --force` 删除与 X 关联的 Derivation，把被删除输入所产出的下游置红，并默认删除用户 Markdown。
- `confirm X` 仅把 X 置绿；`confirm X --cascade` 无条件把 X 和全部下游置绿，即使其他输入仍为红色。现有测试明确固化了这一危险行为。

### 3.4 存储

```text
.kflow/index.json
.kflow/nodes/<node-id>.json
.kflow/derivations/<derivation-id>.json
knowledge/<name>.md
```

- Node/Derivation 分文件被视作真相源，`index.json` 是可重建聚合索引。
- `index.json` 只保留 short 层信息；detail 只在 Derivation 分文件中。
- 只有索引写入使用临时文件加 `os.replace`；Node 和 Derivation 写入以及跨文件命令不是原子的。
- `.gitignore` 忽略整个 `.kflow/`，因此 Node/Derivation 元数据也不会被 Git 保存。
- 没有 schema version、迁移入口、fingerprint、路径归属索引或写入锁。

### 3.5 主要工作流

```text
init
→ create 源 Node / derive 新的单输出 Node
→ 人或 Agent 编辑 knowledge/*.md
→ 人工调用 modify
→ affect/context 查询上下游
→ 人或 Agent 复查
→ confirm（可级联）
→ validate / reindex
```

KFlow v1 的 `context` 返回路径、状态和简短 Derivation 元数据，不返回 Markdown 正文；这一点符合 v2 的硬边界。

## 4. v1 与 v2 的关键冲突

| 主题 | v1 | v2 要求 | 判断 |
|---|---|---|---|
| Node 文件归属 | 0 或 1 个文件，默认 `knowledge/*.md` | 1 个或多个文件；文件全局唯一归属；不限 Markdown 专用目录 | 重写模型与创建/绑定流程 |
| Derivation 输出 | 单输出对象 | 0..n 输入、1..n 输出（包括零输入多输出） | 重写模型、图投影和命令 |
| Derivation 语义 | `summary` + input role + output method | Derivation/input/output 均有 `short/detail` | schema 不兼容，需映射迁移 |
| 拓扑事实 | Node 与 Derivation 双向持久化 | 应共享单一核心事实模型 | 推荐 Derivation 单向引用为真相，反向索引派生 |
| 生产者唯一性 | 命令路径间接保证；校验不足 | 已决定每个 Node 恰好一个 producing Derivation，源 Node 使用零输入 Derivation | 领域层和校验器必须强制 |
| 变化发现 | 必须手工 `modify` | 通过文件 hash 或 Git 识别变化 | 重写变化检测 |
| 状态 | 持久化 `green/yellow/red` | 不预设单字段足够，应保留触发与确认语义 | 重写状态模型 |
| confirm | 可 `--cascade` 全部置绿 | 严格 Node 级，不能自动确认下游/同源其他输出 | 删除级联语义，保留单 Node 动作 |
| 删除 | KFlow 默认删除用户正文 | KFlow 不是编辑器，不接管用户文件 | 拆分“移除元数据”与文件生命周期；默认绝不删正文 |
| Git | 整个 `.kflow/` 忽略 | Node/Derivation 元数据历史由 Git 保存 | 重写目录和 ignore 策略 |
| Agent 输出 | JSON 含路径和元数据 | 基础影响结果还需变化 Node、文件路径、层级、拓扑顺序，可选完整关系语义 | 扩充契约，但继续禁止正文 |
| 历史 | 无 | 当前只保证可做 Git 版本间图比较 | schema 需稳定、确定、可 diff；不引入 event sourcing |
| 查询 | context/affect 主要按 Node 展示 | 需显示经过哪些多输入多输出 Derivation | 重写结果结构，复用遍历方向 |
| 完整性校验 | 6 项，适配单文件/单输出 | 还需文件唯一归属、多输出生产者唯一性、完整 backlink/路径/schema 校验 | 保留框架，重写规则 |

旧重构计划书中提出的章节级对象、固定 Relation 类型、ContextBundle 正文分级、event sourcing、Snapshot、`supersedes`、Web UI/MCP 首期实现等内容，均已被启动指令明确取代或推迟，不能作为 v2 当前约束。

## 5. 可复用资产

### 5.1 可直接复用思想、需要适配实现

- 稳定随机 ID 与按 ID 分文件的方向；ID 长度和冲突策略可在 schema 审查时调整。
- Derivation 作为超边而不是普通二元关系的核心抽象。
- short/detail 两层语义的产品经验。
- 上游 `context`、下游 `affect` 两个可组合查询方向。
- 从 Derivation 投影 Node 邻接关系的遍历方式。
- Kahn 拓扑排序、环检测和深度限制的算法思路。
- 分文件真相源 + 可重建索引的存储原则。
- UTF-8 JSON、人类输出与机器 JSON 分离、明确错误类型的 CLI 工程框架。
- `validate` 只报告不静默修复，以及 `reindex` 可恢复缓存的运维思路。
- 零外部运行时依赖可以继续作为偏好，但不应压过正确性。

### 5.2 可作为回归参考、不能原样继承

- `graph.py`：算法可移植，但所有 `dv.output` 假设必须改为 `dv.outputs`，且查询需要保留 Derivation 层信息。
- `store.py`：文件布局和重建思路可用，但 schema、写入原子性、Git tracked/cache 分界必须重写。
- `output.py` 与错误类：结构可用，字段契约和状态展示需重写。
- argparse 分发：可保留为薄适配层；命令名称和参数先不承诺兼容。
- 现有测试：大部分是 v1 行为证据，应挑选业务不变量转写成 v2 测试，而不是让 v2 通过全部旧断言。

## 6. 必须重写的模块

1. **领域模型 `models.py`**：文件集合、多输出、统一 short/detail、生产者规则、状态事实与 schema version 都改变。
2. **状态 `status.py`**：三色突变和级联确认不满足 v2；应从“文件变化事实 + 影响传播 + Node 确认基线”推导当前状态。
3. **存储 `store.py`**：需将可 Git 跟踪的规范元数据与派生缓存分开，支持 schema version、确定序列化和跨文件安全写入。
4. **创建/推导命令**：不能再隐式创建/编辑 Markdown；需支持绑定已有多个文件和多输出 Derivation。
5. **modify/scan 工作流**：从人工通知改为确定性的文件/Git 变化检测；是否保留手工 override 以后决定。
6. **confirm 命令**：只确认一个 Node，记录它针对当前输入/文件版本的检查事实；删除 `--cascade`。
7. **remove 命令**：只管理元数据，默认不删除用户文件；删除后的拓扑与受影响状态需重新定义。
8. **context/affect 输出契约**：返回文件集合、直接/传递层级、拓扑顺序、所经 Derivation 和可选语义，绝不返回正文。
9. **validate**：按 v2 不变量重建，包括文件唯一归属、生产者唯一性、多输出和 Git-friendly schema。

## 7. 可延后问题

- Web UI、MCP、IDE 插件和任何远程服务。
- Git 版本间图谱比较的用户界面；首期只保证元数据可被 Git 正确比较。
- 历史时间线、快照、事件溯源、命令日志和身份/审批系统。
- 向量检索、自动关系发现和章节/代码片段级 Node。
- 固定关系类型、替代关系、强弱影响策略和语义真伪判断。
- 大规模性能优化、并发多写者和跨仓库 Node。
- v1 CLI 的完整兼容层；先决定是否只提供一次性迁移工具。

## 8. 数据迁移风险

### 高风险

- v1 单输出 Derivation 到 v2 多输出 Derivation 无法自动判断哪些 v1 Derivation 原本是同一次推导而应合并；默认逐条迁移最安全，但会保留较碎的拓扑。
- v1 的 `green/yellow/red` 没有触发版本和确认基线，无法无损迁移成新的状态事实。建议迁移结构，不信任旧颜色；迁移后执行一次 scan，并要求受影响 Node 重新确认。
- `.kflow/` 当前完全未进 Git。用户本地 v1 元数据可能没有历史备份，迁移必须先复制/备份并做只读预检。
- Node 的单 `file` 到 `files[]` 可机械包装，但 `file=null` 与 v2“Node 至少一个文件”的硬规则冲突。无文件 Node 必须由用户绑定文件、删除，或在迁移报告中阻塞。

### 中风险

- `summary → short`、`role → input.short`、`role_detail → input.detail`、`method → output.short`、`method_detail → output.detail` 可机械映射，但 Derivation 自身 `detail` 在 v1 缺失，不能虚构；需标记待补。
- 双向引用可能已经不一致；迁移应只信任完整 Derivation 文件并重建反向索引，同时报告冲突。
- v1 名称和默认文件路径耦合；迁移必须保留 Node ID，不得以路径重新生成身份。
- 6 位随机 ID 理论碰撞空间较小；当前数据可保留，新增 ID 策略可以升级，但不可静默改写旧 ID。

### 迁移安全原则

- 迁移器先只读分析，输出阻塞项和预期变更。
- 不原地覆盖 v1；生成独立 v2 目录或备份后原子替换。
- 不删除、移动或改写任何用户正文。
- 迁移后必须通过 v2 validate，并给出 Node/Derivation/文件归属计数对账。

## 9. 可作为 v2 验收基线的现有测试

### 保留业务意图并改写

- `test_graph.py`：上游/下游遍历、深度、DAG 环检测、拓扑顺序。
- `test_store.py`：分文件 round-trip、索引缺失/损坏后重建、原子缓存写入。
- `test_cli_context.py`、`test_cli_affect.py`：两个查询方向和深度语义。
- `test_cli_validate.py`：悬挂引用、缺失/未注册文件、只报告不修复。
- `test_json_output.py`：机器输出为稳定 JSON、错误和人类输出分离。
- `test_errors.py`：预期错误有明确类型和非零退出。
- 创建重复名称、引用不存在 Node、成环拒绝、删除有下游时保护等安全意图。

### 明确废弃或改写断言

- 所有 `output` 单对象断言改为 `outputs[]`。
- `file=None` 和自动创建 `knowledge/<name>.md` 的断言不进入 v2。
- 红黄绿字段的直接突变断言不进入 v2。
- `confirm --cascade` 及其“忽略其他红色上游”的测试必须被反向安全测试替代。
- `remove` 默认删除 Markdown 的断言必须废弃，新增“任何元数据删除都不改写正文”的测试。
- 手工 `modify` 触发变化的测试改为 fingerprint/Git scan 场景。

建议 v2 第一批端到端验收场景：

1. 一个 Node 绑定两个文件，任一文件变化都识别为同一 Node 变化。
2. `A,B → C,D`，A 变化后 C/D 均受影响；确认 C 不确认 D。
3. `A → B → C`，确认 B 不确认 C。
4. 文件重命名并更新 locator 后 Node ID 保持不变。
5. 查询只返回 Node/Derivation 元数据和路径，不出现正文。
6. 删除/解绑 Node 不删除真实文件。
7. 元数据提交到 Git 后，可在两个 commit 间确定性比较拓扑。

## 10. 未决架构问题（按优先级）

### Q1：源 Node 的唯一表达方式（已决定）

背景：启动指令既要求支持零输入 Derivation，又列出“无 producing Derivation”和“零输入 Derivation”两个候选，并明确禁止长期保留重叠语义。

影响：改变生产者不变量、Node/Derivation schema、创建流程、多输出源知识的表达、校验规则和 v1 `create` 迁移。

决定：采用方案 A。所有 Node 都由且仅由一个 Derivation 产生；源知识使用零输入 Derivation。v1 中无 producing Derivation 的源 Node 在迁移时必须创建零输入 Derivation，缺失的语义文本不能由迁移器静默编造。

### Q2：confirm 所固定的基线是什么（已决定）

背景：多文件 Node 与多输入 Derivation 下，单一颜色无法说明“针对哪些文件内容和哪些上游版本已检查”。

候选：仅保存 Node 自身文件 fingerprint；保存自身 fingerprint + producing Derivation 输入 Node 的确认/内容版本向量；或仅以 Git commit 为统一基线。

决定：采用方案 B。保存 Node 自身文件集合 fingerprint、producing Derivation fingerprint，并保存产生它的各直接输入 Node 的“有效版本”摘要；状态由当前值与确认基线比较得到。Node 有效版本按稳定顺序由这三部分确定性计算，源 Node 的输入版本向量为空。

### Q3：规范元数据与本地运行状态的 Git 边界（已决定）

背景：Node/Derivation 必须进 Git，但文件扫描缓存、未提交变更和个人确认状态是否进 Git 尚未明确。

决定：采用方案 A。规范 Node、Derivation 和每个 Node 的 Confirmation 进入 Git；可重建 index、锁、临时扫描缓存和 observation 不进 Git。不引入个人确认 overlay、发布命令或用户身份。

### Q4：v1 迁移是一次性工具还是运行时兼容（实现负责人建议）

背景：当前 schema 与 v2 多处不兼容，双格式运行会扩大所有命令和校验复杂度。

最佳方案：提供只读预检 + 显式补全映射 + 一次性迁移，不在 v2 领域层长期兼容 v1。迁移器是否进入首个开发里程碑取决于真实 v1 数据样本，但 v2 schema 和运行时不为双格式兼容让步。

## 11. v2 领域模型草案

本节是概念草案，不是已批准 schema；字段名和文件布局可以在不改变语义的情况下调整。

### 11.1 Knowledge Node

```yaml
id: nd_stable_id
name: architecture
files:
  - docs/architecture.md
  - docs/architecture.svg
```

不变量：

- `id` 是稳定身份；重命名和文件路径变化不改变 ID。
- `files` 是非空、去重、使用仓库相对规范路径的列表。
- 同一规范路径只能属于一个 Node。
- 目录、章节、段落、标题和代码片段不能作为 locator。
- Node 不保存 Derivation 反向引用；生产者和消费者从 Derivation 集合构建索引。
- Node 不保存正文、摘要正文或 Prompt。
- Node 当前状态不应压缩为规范元数据里的单个颜色字段。

### 11.2 Derivation

```yaml
id: dv_stable_id
short: 综合需求与约束形成系统设计
detail: 根据功能需求、性能目标和部署约束共同确定系统设计。
inputs:
  - node: nd_requirements
    short: 提供功能目标
    detail: 定义必须支持的能力和场景。
outputs:
  - node: nd_architecture
    short: 形成总体架构
    detail: 确定组件边界和数据流。
  - node: nd_api_design
    short: 形成接口方案
    detail: 确定接口及约束。
```

不变量：

- `inputs` 可为空；`outputs` 必须非空。
- 一个 Derivation 内 input Node 不重复，output Node 不重复，且 input/output 不应交叉导致自环。
- 每个 input/output 都必须有非空 `short/detail`；Derivation 自身也必须有非空 `short/detail`。
- 每个 Node 恰好出现在一个 Derivation 的 outputs 中；零输入 Derivation 是源 Node 的唯一生产方式。
- 图必须无环。多输出 Derivation 作为一个不可拆分的事实对象保存，遍历时才投影成 Node 邻接。
- 不增加固定关系类型；语义由拓扑和自由文本表达。

### 11.3 变化与确认事实（概念）

```text
FileObservation
  node_id
  files_fingerprint

NodeConfirmation
  node_id
  confirmed_files_fingerprint
  producing_derivation_fingerprint
  observed_input_versions[]
```

- scan 读取文件/Git 信息并计算 fingerprint，但不输出正文。
- Node 自身文件与确认 fingerprint 不同，表示该 Node 已变化。
- 上游观察版本晚于该 Node 的确认基线，表示该 Node 可能受影响。
- 影响从变化 Node 经 Derivation outputs 向下游传播，返回最短层级和稳定拓扑顺序。
- confirm 仅更新目标 Node 的确认基线；不更新同一 Derivation 的其他输出，也不更新传递下游。
- 删除上游或 Derivation 是拓扑变化，应使相关下游进入需检查状态，但不自动宣称其内容错误。
- 状态展示可派生为易懂标签，但标签不是唯一事实源。

Q2 已确定上述确认基线；确认记录的持久化位置仍取决于 Q3，因此本节尚不能固化为最终 schema。

### 11.4 Agent 基础查询结果

```yaml
changed_nodes:
  - node: nd_requirements
    files: [docs/requirements.md]
affected_nodes:
  - node: nd_architecture
    files: [docs/architecture.md, docs/architecture.svg]
    depth: 1
    via_derivations: [dv_system_design]
review_order: [nd_architecture, nd_api_design, nd_test_plan]
```

可选展开字段：

- Node 当前派生状态；
- Derivation `short/detail`；
- input/output `short/detail`；
- 直接影响与传递影响路径。

结果禁止包含文件正文、片段、自动摘要或拼装 Prompt。

### 11.5 Git 持久化原则

- Node 和 Derivation 规范分文件进入 Git，序列化顺序稳定、diff 可读、带 schema version。
- index、邻接表、锁和可重建缓存不进入 Git。
- 文档内容历史只由 Git 保存，KFlow 不复制正文。
- 当前阶段不引入数据库、event sourcing、全量命令日志或快照引擎。
- 任意 Git 版本 checkout 后，应能仅从该版本规范元数据重建同版本图谱。

## 12. 按依赖组织的重构路线

### 阶段 A：决策与契约冻结

- 输入：启动指令、本报告、已决定的 Q1，以及用户对 Q2/Q3/Q4 的逐项回答。
- 输出：批准的领域模型、术语、不变量、查询契约和 Git 边界。
- 验收：用源 Node、多文件 Node、`A,B → C,D`、链式确认四个样例无歧义演算。
- 风险：过早把状态实现细节写进 schema。
- 测试：先写模型示例/契约测试，不写 CLI。
- 审查点：产品负责人明确批准后才进入代码阶段。

### 阶段 B：纯领域内核

- 输入：批准的 schema 和不变量。
- 输出：Node/Derivation 值对象、图索引构建、生产者唯一性、环检测、上下游和拓扑排序。
- 验收：支持零/多输入和多输出；所有非法图被拒绝；算法不依赖 CLI/文件系统。
- 风险：把多输出 Derivation 错拆成普通边而丢失语义。
- 测试：迁移 v1 图算法测试并新增多输出、文件归属、生产者唯一性测试。
- 审查点：只审领域行为，不同时审存储和 CLI。

### 阶段 C：Git-friendly 规范存储

- 输入：领域内核与持久化契约。
- 输出：versioned codec、规范分文件、原子写入/恢复、派生 index 和 validate。
- 验收：checkout 任意元数据版本可重建同一图；破坏缓存可恢复；中途写失败不损坏规范数据。
- 风险：多文件事务和 Windows 原子替换行为。
- 测试：round-trip、golden files、故障注入、确定性 diff、路径规范化。
- 审查点：确认 tracked/untracked 文件清单和 `.gitignore` 变化。

### 阶段 D：变化检测与 Node 级确认

- 输入：已批准的 Q2 状态基线和待批准的 Q3 Git 持久化边界。
- 输出：scan、fingerprint、影响传播、confirm、状态派生。
- 验收：多文件任一变化可识别；直接/传递深度正确；确认不级联；不读取输出正文。
- 风险：Git 未提交状态、重命名、文件缺失和换行变化。
- 测试：真实临时 Git 仓库端到端场景和多输入/多输出确认矩阵。
- 审查点：确认状态事实足够解释“为何受影响”，但没有事件溯源膨胀。

### 阶段 E：Agent 查询与薄 CLI

- 输入：稳定领域 API、存储和状态查询。
- 输出：可组合 context/affect/impact/status/confirm JSON 契约及人类 CLI 展示。
- 验收：基础结果含变化 Node、文件路径、层级和拓扑顺序；可选展开 Derivation 语义；任何输出不含正文。
- 风险：为兼容 v1 命令污染领域 API。
- 测试：JSON schema/golden output、错误码、正文泄漏防护。
- 审查点：先 dogfood CLI + JSON，不引入 MCP/UI。

### 阶段 F：v1 迁移（仅在确认需要后）

- 输入：真实 v1 数据样本和稳定 v2 codec。
- 输出：只读预检、迁移报告、一次性转换器、回滚/备份说明。
- 验收：计数对账、ID 保留、正文零改写、缺失 detail 和无文件 Node 明确阻塞。
- 风险：不一致双向引用、无历史元数据和错误颜色继承。
- 测试：合法、损坏、部分缺失和重复生产者样本。
- 审查点：迁移结果必须人工审查后才替换使用。

### 阶段 G：人类图谱与历史比较（后续）

- 依赖：前述核心契约经真实项目验证稳定。
- 仅消费相同核心事实模型；先设计只读图谱/版本比较，不改变内核关系语义。
- Web UI、MCP 和更深 Agent 集成分别立项，不与核心重构捆绑。

## 13. 架构决策与当前结构化追问

### Q1 决策记录：源 Node 的表达

### 发现

v2 明确要求支持“零输入 → 单/多输出”Derivation，同时把源 Node 的表达列为二选一：

1. 源 Node 没有 producing Derivation；
2. 源 Node 由零输入 Derivation 产生。

如果两者都长期存在，同一种“源知识”将有两套表示，查询、校验、创建和迁移都会产生分支语义。

### 为什么影响架构

该选择决定 Node 的生产者约束究竟是“最多一个”还是“恰好一个”，并直接改变 schema、`create`/`derive` 工作流、零输入多输出的用途、source 展示、完整性校验和 v1 源 Node 的迁移方式。

### 选项

**A. 所有源 Node 都由零输入 Derivation 产生（推荐）**

- 优点：所有 Node 统一为恰好一个生产者；真正落实零输入到多输出；源知识的形成说明也有 Derivation/input/output 同一套语义；查询和校验无双轨分支。
- 缺点：创建任何源 Node 都要同时创建 Derivation；必须提供有意义的 `short/detail`，元数据录入成本更高；v1 源 Node 迁移时缺少这些说明，不能自动编造。

**B. 源 Node 不拥有 producing Derivation，零输入 Derivation 仅用于显式声明的特殊生成活动**

- 优点：普通源 Node 简单，v1 迁移直接；用户可以先登记文件，之后再补关系。
- 缺点：“普通源”与“零输入推导源”边界难以稳定定义；生产者规则和查询必须支持两种语义，容易长期重叠。

**C. 源 Node 不拥有 producing Derivation，并从 v2 当前范围删除零输入 Derivation**

- 优点：模型最简，迁移最容易。
- 缺点：直接违反启动指令中零输入 Derivation 的硬性能力要求，除非产品负责人明确修改该要求，因此不推荐。

### 推荐

推荐 **A**。它是唯一同时满足“必须支持零输入 Derivation”和“不保留重叠源语义”的方案，并把生产者规则收敛为最容易验证的单一不变量。其代价应通过创建流程和迁移报告解决，而不是让核心模型永久保留歧义。

### 决定

产品负责人选择 **A：所有 Knowledge Node（包括源 Node）都由且仅由一个 Derivation 产生，源知识统一使用零输入 Derivation**。

由此确定：

- Node 生产者不变量是“恰好一个”，不是“最多一个”。
- `inputs=[]` 是源 Derivation 的结构化标志，不再额外设置 `source` 类型或布尔字段。
- 一个零输入 Derivation 可以产出一个或多个共同形成的源 Node。
- v1 源 Node 迁移时需要补建零输入 Derivation；缺失的 `short/detail` 必须显式待补，迁移器不得虚构产品语义。

### Q2：confirm 固定哪一组版本基线（已决定）

#### 发现

v2 的一个 Node 可以包含多个文件，一个 Derivation 也可以有多个输入。Node 在确认之后，可能因为自身文件再次变化、producing Derivation 的语义或拓扑发生变化，或任一上游 Node 变化而重新受到影响。v1 的单一 `green/yellow/red` 无法说明“这次确认检查的是哪个自身版本、依据哪次推导、基于哪些上游版本”。

#### 为什么影响架构

该选择决定确认记录和状态派生的 schema、fingerprint 粒度、影响传播能否解释原因、Git 中需要保存哪些共享事实，以及多输入/多输出场景下是否会错误清除风险。选错后会迫使状态和存储层一起返工。

#### 选项

**A. 只确认 Node 自身文件 fingerprint**

- 含义：confirm 只记录目标 Node 当前 `files[]` 的聚合 fingerprint。
- 优点：schema 最简单，确认记录小。
- 缺点：无法证明确认时采用了哪些上游版本；同一 Node 文件未变化但上游再次变化时，只能依赖额外的易丢失状态标志，难以从持久化事实重建“为何受影响”。

**B. 确认自身 fingerprint + producing Derivation fingerprint + 直接输入版本向量（推荐）**

- 含义：confirm 记录目标 Node 当前文件集合 fingerprint、producing Derivation 的规范 fingerprint，以及每个直接输入 Node 当时的稳定有效版本摘要。Node 的有效版本由这三部分按稳定顺序确定性计算。
- 优点：可以确定性回答“目标内容是否变了”“推导依据是否变了”和“它是否基于当前直接前提检查过”；传递影响可逐层推导；适配多输入/多输出且不需要事件溯源。即使 B 的文件未变，B 在新上游条件下确认后，其有效版本也能让 C 保持待检查，而不会被 B 的确认级联清除。
- 缺点：确认记录更大；必须定义稳定的 Node 有效版本、Derivation fingerprint 和输入排序；Derivation 的语义或输入/输出集合变化会使相关旧确认失效。

**C. 只记录确认时的 Git commit SHA**

- 含义：Node 确认绑定到整个仓库 commit。
- 优点：历史定位直观，几乎不需要自定义版本向量。
- 缺点：未提交修改无法可靠确认；仓库任何无关提交都会使基线含糊；无法精确判断具体 Node/输入是否变化，也不适合 Agent 在工作树中逐个确认。

**D. 保存完整传递上游版本向量**

- 含义：confirm 快照记录所有直接和间接上游 Node 版本。
- 优点：每条传递影响都可直接追溯。
- 缺点：记录体积和写入放大随图增长，拓扑小变化会使大量确认失效；实际上提前构建了重型快照系统，超出当前边界。

#### 推荐

推荐 **B**。它以最小的一跳版本向量保存足够事实：自身变更由自身 fingerprint 判断，推导变化由 Derivation fingerprint 判断，直接前提变更由输入有效版本比较判断，传递影响继续通过 DAG 逐层计算。这样既能解释状态，又不引入完整事件溯源或全图快照。

#### 决定

产品负责人选择 **B：记录目标 Node 自身文件集合 fingerprint、producing Derivation fingerprint，以及直接输入 Node 的有效版本向量**。

由此确定：

- Node 的当前有效版本由自身文件集合 fingerprint、完整 producing Derivation fingerprint 和按 Node ID 稳定排序的直接输入有效版本向量确定性计算。
- 源 Derivation 的输入版本向量为空。
- confirm 保存目标 Node 当时的三部分基线，仅更新该 Node 的确认记录。
- 当前三部分事实与上次确认基线不一致时，该 Node 需要检查；原因可以分别归类为自身文件变化、推导变化或输入版本变化。
- 下游状态通过 DAG 和有效版本逐层推导；确认上游 Node 不会修改或清除任何下游确认记录。

### Q3：确认记录是否作为 Git 跟踪的共享项目事实（已决定）

#### 发现

Node 和 Derivation 规范元数据必须进入 Git，扫描索引和锁等可重建缓存不应进入 Git。尚未决定的是 `NodeConfirmation`：如果进入 Git，人类和 Agent 可以共享同一个“已检查到哪个版本”的状态；如果只保存在本地，不同工作区看到的待检查列表会不同。

#### 为什么影响架构

该选择决定 Git 跟踪目录、confirm 的写入行为、状态能否跨会话/设备重建、合并冲突策略，以及未来历史比较能否解释某个版本是否已经检查。它也会决定是否需要额外的“发布确认”流程和两层状态模型。

#### 选项

**A. 每个 Node 的确认记录进入 Git（推荐）**

- 含义：规范 Node、Derivation 和按 Node 分文件的 Confirmation 都是共享项目事实；index、扫描缓存、锁和临时 observation 被忽略。
- 优点：人类与 Agent 共享同一状态；clone/checkout 后可确定性重建；confirm 可与对应文档修改一起提交；Git 自然保存必要确认历史，不需要数据库或事件日志。
- 缺点：每次 confirm 都会产生工作树变更；多人同时确认同一 Node 可能产生合并冲突；fingerprint 元数据会增加 Git diff 噪声。

**B. 确认记录仅保存在本地并被 Git 忽略**

- 含义：Git 只保存拓扑；每个工作区维护自己的确认基线。
- 优点：confirm 不污染提交，不产生跨用户冲突；实现简单。
- 缺点：状态不能在人类、Agent、设备或 CI 之间共享；本地状态丢失后全部需要重新确认；无法满足“Agent 接口与人类图谱共享当前状态”的直接预期。

**C. 本地确认 + 显式 publish 后进入 Git**

- 含义：confirm 先写本地 overlay，另一个命令把选择的确认发布为共享基线。
- 优点：允许个人检查过程与项目认可状态分离，减少提交噪声。
- 缺点：引入两套当前状态和新的发布工作流；需要定义冲突、覆盖和未发布确认的展示；当前没有多人审批需求支撑这份复杂度。

**D. 不保存 NodeConfirmation，仅用 Git commit 推断**

- 含义：把最近提交视为全部 Node 的统一确认点。
- 优点：无额外确认文件。
- 缺点：无法表达 Node 级独立确认，也无法处理工作树中的逐步复查，违反已经确定的 confirm 语义。

#### 推荐

推荐 **A**。Confirmation 是 KFlow 当前状态的必要共享事实，而不是可重建缓存。按 Node 分文件可以把冲突限制在同一 Node；频繁 diff 是 Git-native 状态可审计性的合理代价。缓存和 observation 仍保持本地、可删除、可重建。

#### 决定

产品负责人选择 **A：Node、Derivation 和每个 Node 的 Confirmation 进入 Git；index、扫描缓存、锁和临时 observation 不进入 Git**。

由此确定：

- Confirmation 是共享项目事实，不是个人本地状态。
- confirm 产生可提交的元数据变更，并与对应文档/拓扑修改一起进入 Git 历史。
- 不引入本地确认 overlay、publish 流程、用户身份或审批层。
- clone 或 checkout 后，仅凭该版本规范元数据和当前文件即可重建状态。
- 同一 Node 的并发确认冲突由普通 Git 合并流程显式处理，不做静默 last-write-wins。
