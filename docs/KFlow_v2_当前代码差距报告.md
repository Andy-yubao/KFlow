# KFlow v2 当前代码差距报告

> 评估基线：2026-08-22 工作树中的 `kflow/v2/` 与 `tests/v2/`。
> 产品依据：`KFlow_核心原则.md`、正式 `KFlow_v2_使用场景清单.md`、`kflow_skills.md` 与 `KFlow_v2_领域模型与重构方案.md`。
> 本报告只分析差距，不修改业务代码或测试。

## 1. 结论

当前 v2 是与 v1 隔离的纯领域原型，已覆盖不可变值对象、部分图不变量、稳定拓扑遍历和 effective version 的基本传播，但仍固化“每个 Node 恰好一个 producer、源 Node 使用零输入 Derivation”的旧模型。

因此它尚不能执行正式 Agent 黄金流程。首切片应先修正纯领域内核，再补最小规范读写、scan、impact（含 `review_order`）和单 Node confirm；不能直接在现有模型上堆 CLI。

## 2. 已满足或可复用

| 能力 | 当前证据 | 结论 |
|---|---|---|
| v1/v2 隔离 | `kflow/v2/` 独立命名空间，未接入 v1 CLI | 满足继续渐进重构的隔离要求 |
| 不可变领域值 | `models.py` 使用 frozen/slots dataclass，并把集合归一为 tuple | 可复用 |
| 多文件 Node | `KnowledgeNode.files` 非空、去重并使用仓库相对 POSIX 路径 | 部分满足；文件存在性与普通文件校验尚无项目层实现 |
| endpoint 基础约束 | `Derivation` 拒绝重复 input、重复 output 与 input/output 交叉 | 可复用 |
| 全局唯一性 | `graph.py` 检测重复 Node/Derivation ID、Node 名称和文件归属 | 满足领域图内校验 |
| 引用与多 producer 校验 | `graph.py` 检测缺失 Node 引用和多个 producer | “至多一个 producer”的多 producer 部分可复用 |
| DAG 与确定性 | `graph.py` 投影 input→output、检测环，并以稳定 ID 生成拓扑序 | 可复用 |
| 基础图遍历 | `upstream`、`downstream`、`sibling_outputs` 已存在 | 可作为查询内核，返回契约仍需重做 |
| Derivation fingerprint | `versioning.py` 覆盖 ID、语义和拓扑，并对 endpoint 排序 | 可复用；需接入规范 fingerprint 类型与可空 detail |
| 版本传递 | `compute_effective_versions` 能让文件或上游变化传递到派生 Node | 派生 Node 算法基础可复用 |
| 确认不参与版本计算 | `compute_effective_versions` 不读取 Confirmation | 符合“confirm 记录基线，不改变事实” |

## 3. 固化旧模型、必须修改的现有模块

### `kflow/v2/models.py`

当前旧规则：

- `Derivation` 明确允许零个 input，只拒绝零 output；
- 三层 `detail` 都被强制为非空；
- docstring 仍称“zero-or-more-input”。

必须修改：

- inputs 与 outputs 均至少一个；
- 三层 `short` 非空，三层 `detail` 允许规范空字符串；
- 增加 `ProjectManifest` 与 `NodeConfirmation` 的领域表示，或在同层新模块定义后从领域包统一导出；
- 保持 Node 可独立存在，不在 Node 上增加 `source` 布尔字段。

### `kflow/v2/graph.py`

当前旧规则：

- `_collect_producers` 把没有 producer 的 Node 报为 `missing_producer`；
- `producer_of` 总是假设 producer 存在；
- `sibling_outputs` 对源 Node 没有明确行为；
- 图构建未独立拒绝零 input Derivation。

必须修改：

- producer 映射只记录派生 Node，无 producer 与孤立 Node 合法；
- producer 查询使用可选结果或显式的源 Node 行为；
- 图层再次防守 inputs/outputs 非空、至多一个 producer、无环；
- 为按文件定位和 neighborhood/影响路径提供足够索引，但不把可重建索引写入规范模型。

### `kflow/v2/versioning.py`

当前旧规则：

- 每个 Node 都调用 `graph.producer_of`，源 Node 无法计算 effective version；
- 测试通过伪造零输入 producer 才能构造源 Node；
- 只接收预聚合字符串，没有实现文件 fingerprint 的规范结构。

必须修改：

- 分开实现 source 与 derived effective version 公式；
- producer 缺失时只使用 Node ID 与当前 files fingerprint；
- producer 存在时加入 Derivation fingerprint 与直接 input effective versions；
- 保持计算与 Confirmation 解耦；
- 接入带算法标签的文件/集合 fingerprint，确保路径、内容恢复和多文件差异可解释。

### `kflow/v2/__init__.py`

当前只导出原型模型、图和版本函数。完成首切片后需导出正式领域契约；不应在此耦合 v1 CLI。

## 4. 必须重写或新增的测试

### 必须重写

| 测试文件 | 固化旧规则的测试 | 新断言 |
|---|---|---|
| `tests/v2/test_models.py` | `test_zero_input_multi_output_derivation_is_valid` | 零 input 被拒绝；非空 input/output 可多对多 |
| `tests/v2/test_models.py` | `test_derivation_requires_non_empty_semantics` 把 detail 与 short 等同 | 三层 short 拒绝空白，三层 detail 接受规范空值 |
| `tests/v2/test_graph.py` | `source()` 用零输入 Derivation 造源 | 直接以无 producer Node 构造源 |
| `tests/v2/test_graph.py` | `test_graph_requires_exactly_one_producer_per_node` | 无 producer 合法；多个 producer 仍拒绝 |
| `tests/v2/test_graph.py` | `test_graph_supports_zero_input_and_multi_output_derivations` | 无 producer 源 + 非空多输入多输出 Derivation |
| `tests/v2/test_versioning.py` | `build_chain()` 为 A 创建零输入 producer | A 直接作为源；验证 source/derived 两套公式 |

### 必须新增

- Node 与 Derivation codec 的确定性 round-trip、未知 schema 与损坏 JSON；
- ProjectManifest 启用判断与 schema 不可用结果；
- 按文件路径定位 Node，含未登记、多文件 Node 与重复归属；
- 源 Node、孤立 Node、派生 Node 及 producer 增删/替换后的 effective version；
- 多文件逐路径 fingerprint 与内容精确恢复；
- scan 同时产生 `unconfirmed`、`files_changed`、`derivation_changed`、`input_changed`，并与 validation issues 分离；
- `A,B → C,D`、多根汇合、最小 depth、全部来源根、可解释路径与稳定 `review_order`；
- upstream、neighborhood、sibling outputs 和稳定排序；
- confirm 只写一个 Node，保留其他 output/downstream Confirmation；有阻断 issue 时拒绝；
- 删除 producer 后保留旧 Confirmation，output 为 `derivation_changed`、下游为 `input_changed`；
- cache 删除后重建结果相同；
- 机器输出 schema version、成功/错误分离和零正文泄漏契约；
- 原子替换失败与事务恢复不留下半写状态。

现有 `tests/` 下的 v1 测试是行为基线，本轮和首切片都不因 v2 模型变化而改写。

## 5. 尚未实现的正式能力

### 黄金流程直接缺口

- 判断项目是否启用及 schema 是否可用；
- 按文件路径定位 Node；
- 可供 Agent 使用的 upstream/neighborhood 结果契约；
- Node/Derivation/Confirmation 的 JSON codec 与规范存储加载；
- 真实文件 fingerprint 与只读 scan；
- Confirmation 模型、状态比较和单 Node confirm；
- impact 的 changed/affected、depth、roots、路径、reasons/issues；
- impact 内的稳定 `review_order`；
- 与本次变化根相关的剩余影响查询；
- 稳定机器输出、错误分类和零正文泄漏测试。

### 建图与可靠性缺口

- ProjectManifest、规范目录、原子写入、事务恢复、锁；
- 文件存在性、普通文件、schema 和 Confirmation 完整性校验；
- cache/index 重建；
- Node/Derivation 生命周期服务。

这些缺口不意味着全部进入首切片；只实现黄金流程依赖的最小部分。

## 6. 首个垂直切片范围

首切片必须包含：

1. 修正上述三个纯领域模块及其测试；
2. 读取一个已存在、合法的最小 v2 项目；
3. 判断启用、按文件定位、upstream/neighborhood；
4. scan 并计算四类 reasons 与独立 issues；
5. impact 返回稳定 `review_order`；
6. 原子 confirm 单个 Node；
7. 再次查询本次变化根的剩余影响；
8. 用端到端 fixture 验证完整黄金流程和零正文输出。

为控制范围，可以用测试 fixture 预先提供图元数据；无需在首切片实现完整建图 CLI。

## 7. 应推迟

以下能力不用于证明首切片成立：

- 完整 Node/Derivation 建图 CLI；
- 完整删除策略和面向用户的所有生命周期入口；
- v1 迁移器；
- 人类总览与图谱；
- Git 拓扑历史比较；
- MCP、Web UI 与深度 Agent 集成；
- watcher、hook 或常驻服务；
- 自动候选文件发现、自动关系猜测；
- 多写者合并、分布式锁和实时协作；
- event sourcing、快照数据库、时间旅行和正文上下文包。

## 8. 本轮修改确认

本轮报告与设计收敛只修改 Markdown 文档，不修改 `kflow/v2/` 业务代码、`tests/v2/` 或任何 v1 代码和测试。
