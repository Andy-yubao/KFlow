# KFlow v2 首个垂直切片实施计划

> 状态：进行中。领域内核、最小规范持久化、scan/status、单 Node confirm、context、impact explanation 与 `review_order` 已实现；按文件定位、直接 neighborhood 和剩余影响闭环仍待后续阶段。
> 本计划仍只约束正式使用场景 Section A 的 Agent 黄金流程；后续不得借此扩展迁移、UI、MCP 或 watcher。

## 1. 目标与停止点

唯一目标是用真实文件和规范 v2 元数据跑通：

```text
判断项目是否启用
→ 按文件定位 Node
→ 查询 upstream / neighborhood
→ Agent 修改文件
→ scan
→ impact + review_order
→ confirm 单个 Node
→ 查看剩余影响
```

明确停止点：一个预建图 fixture 项目完成上述闭环，契约测试证明状态、影响顺序、单 Node confirm、原子写入和零正文输出后，首切片即结束。不得顺手扩展完整建图、删除、迁移、UI、MCP 或 watcher。

## 2. 模块边界

现有模块必须修改：

- `kflow/v2/models.py`：正式 Node、Derivation、ProjectManifest、Confirmation 值对象；
- `kflow/v2/graph.py`：无 producer 源 Node、非空 Derivation、图索引和稳定遍历；
- `kflow/v2/versioning.py`：文件/Derivation fingerprint 与 source/derived effective version；
- `kflow/v2/__init__.py`：只导出稳定领域契约。

建议新增的最小模块：

- `kflow/v2/codec.py`：schema v2 的确定性 JSON 解码/编码；
- `kflow/v2/repository.py`：规范元数据加载、按文件索引、Confirmation 原子替换；
- `kflow/v2/status.py`：当前事实与 Confirmation 的 reasons 比较；
- `kflow/v2/scan.py`：只读扫描、文件 fingerprint、issues 与状态快照；
- `kflow/v2/query.py`：文件定位、upstream、neighborhood、impact 和 `review_order`；
- `kflow/v2/application.py`：组合黄金流程所需用例，不承载领域规则；
- `kflow/v2/output.py`：带 schema version 的机器结果与错误封装；
- 一个薄 Agent/CLI 适配入口：只暴露本切片能力，不固定本文中的命令拼写。

测试按同名职责放入 `tests/v2/`；端到端 fixture 只包含手写的最小规范元数据和真实文件，不依赖完整建图入口。

## 3. 依赖顺序

```text
阶段 1 领域内核
  ↓
阶段 2 codec + 只读 repository + 基础查询
  ↓
阶段 3 scan + status + impact/review_order
  ↓
阶段 4 confirm 原子写入 + 剩余影响
  ↓
阶段 5 薄适配层 + 端到端验收
  ↓
停止
```

后续阶段不得通过复制旧规则绕过前置阶段。每阶段相关单元测试通过并审查契约后再进入下一阶段。

## 4. 分阶段计划

### 阶段 1：修正纯领域内核

目标：让代码表达正式领域模型，而不是零输入 Derivation 旧模型。

实现范围：

- Node 无 producer 与孤立状态合法；
- Derivation 至少一个 input 和一个 output；
- 每个 Node 至多一个 producer，Node 图无环；
- 三层 short 必填、detail 可为空；
- source/derived effective version 分支；
- Confirmation 记录文件、producer 和直接输入版本基线；
- producer 增删/替换产生可比较的旧基线，不删除 Confirmation。

测试与验收：

- 重写所有显式创建零输入 Derivation 的测试；
- 无 producer Node 可构图、排序、查询和计算版本；
- 多 producer、零 input/output、交叉 endpoint 和环均拒绝；
- 源文件变化只改变自身及下游版本；派生语义变化改变 outputs 及下游版本；
- confirm 数据不参与 effective version 计算。

阶段出口：`tests/v2/test_models.py`、`test_graph.py`、`test_versioning.py` 全部表达新模型，不保留兼容旧模型的双分支。

### 阶段 2：加载项目、按文件定位与修改前查询

目标：在不实现完整建图 CLI 的前提下读取一个预建 v2 项目，并支持黄金流程前三步。

实现范围：

- 识别 `.kflow/project.json` 与 schema 版本；
- 确定性解码 Node、Derivation、Confirmation；
- 加载后执行结构和图校验；
- 建立可重建的文件→Node、producer、consumer 索引；
- 按文件路径定位 Node；
- 查询 upstream 与直接 neighborhood，包括 Derivation、角色语义、全部文件和 sibling outputs。

测试与验收：

- 未启用、受支持 schema、未知 schema、损坏 JSON 结果明确；
- 已登记路径返回唯一 Node 和全部文件，未登记路径不是错误；
- upstream 上游先于目标、顺序稳定；neighborhood 只含直接关系；
- 删除内存索引后从规范文件重建，结果完全一致；
- 所有返回均不含正文、片段、摘要或 Prompt。

阶段出口：Agent 能从文件路径开始定位并获得修改前所需拓扑，不需要知道 Node ID。

### 阶段 3：scan、状态、impact 与 `review_order`

目标：Agent 修改真实文件后，KFlow 能只读计算当前变化和处理范围。

实现范围：

- 按原始字节计算文件 fingerprint，并聚合多文件 Node；
- scan 产出 `unconfirmed`、`files_changed`、`derivation_changed`、`input_changed`；
- validation issues 与 review reasons 分离；
- impact 合并多个变化根，返回直接/传递 depth、全部 roots、经过的 Derivation 和可解释路径；
- impact 同时返回相关 `needs_review` 子图的稳定 `review_order`。

测试与验收：

- 多文件 Node 指出具体变化路径；内容恢复后 fingerprint 与状态恢复；
- `A,B → C,D` 中 A 变化时 C、D 都是 depth 1；
- 汇合目标只出现一次，保留最小 depth 和全部 roots；
- 上游先于下游，同层按稳定 ID；重复 scan 结果字节级稳定；
- 缺失文件、坏引用、环和坏 schema 只作为 issues，不伪装成普通 reasons；
- `review_order` 只由 impact 结果契约计算，不增加独立领域对象；专用 CLI 视图必须直接复用同一结果。

阶段出口：修改文件后可得到完整、稳定且可解释的待检查范围。

### 阶段 4：单 Node confirm 与剩余影响

目标：完成黄金流程的状态闭环，并验证 confirm 不级联。

实现范围：

- 在同一有效扫描事实下创建目标 Node 的当前 Confirmation；
- 使用同目录临时文件、flush/fsync 和原子替换写入一个 Confirmation；
- 有阻断性 issue、文件不可读或扫描事实已过期时拒绝；
- 返回确认前 reasons、确认后状态和与当前变化根相关的剩余影响；
- producer 删除后保留旧 Confirmation，并按基线差异继续计算状态。

测试与验收：

- `A,B → C,D` 中 confirm C 不改变 D；
- `A → B → C` 中 A 变化后 confirm B，C 仍为 `input_changed`；
- confirm 源 Node 不改变 effective version；
- 写入失败不破坏旧 Confirmation、不留下规范目录内半写文件；
- 重复 confirm 同一事实得到等价基线；
- 只在本次影响范围全部处理后返回闭环完成，项目无关未确认 Node 不阻塞。

阶段出口：逐 Node 检查、确认和剩余范围查询可以循环到本次影响闭合。

### 阶段 5：薄适配层与端到端验收

目标：证明 Agent 能通过稳定机器契约完成一次真实闭环。

实现范围：

- 为阶段 2–4 的应用用例提供最薄入口；
- 所有成功结果带 schema version，错误使用明确类型；
- 不加入正文读取、自动摘要、自动建图或高层复合命令。

端到端 fixture：

```text
A、B → C、D
C → E
```

验收步骤：

1. 判断 fixture 已启用；
2. 按 `A` 的文件路径定位 Node；
3. 查询目标 upstream/neighborhood；
4. 测试代码模拟 Agent 修改 A 的真实文件；
5. scan 得到 A 的自身变化以及 C、D、E 的传递影响；
6. impact 返回稳定 `review_order`；
7. 分别检查并 confirm A、C、D、E，证明任一 confirm 不级联；
8. 查询剩余影响为空；
9. 对所有机器输出执行正文哨兵检查，证明没有正文泄漏。

质量门：相关 pytest 全部通过，`ruff check .` 与 `ruff format --check .` 通过；现有 v1 测试保持通过。

阶段出口与项目停止点相同。通过后只提交切片成果和已知限制，不进入下一产品范围。

## 5. 明确不在切片内

- 初始化、创建、修改、删除的完整建图 CLI；
- 完整删除策略与 producer 迁移界面；
- v1 迁移器；
- 人类项目总览、图谱与 Git 历史比较；
- MCP、Web UI、deep Agent integration；
- watcher、hook、后台服务；
- 自动候选文件发现、自动关系猜测；
- 多写者合并、分布式锁、实时协作；
- event sourcing、快照数据库、时间旅行；
- 正文、片段、摘要、Prompt 或上下文包。

若实现过程中发现必须引入上述任一能力才能继续，应停止并重新审查切片设计，而不是扩大范围。
