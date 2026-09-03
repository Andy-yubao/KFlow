# KFlow CLI 信息架构

> 本文定义 KFlow 当前公开命令的职责、默认文本和查询机器契约。领域规则见 [正式架构](architecture.md)，字段定义见 [机器契约](schema.md)。

## 1. 两类输出

默认文本服务于人类，以及直接阅读终端结果的 Agent。它使用 Node 名称，围绕当前任务组织信息，只展示完成判断所需的结构、状态和文件，不展示随机内部 ID，也不输出空的 issue 区块。

`--json` 服务于 MCP、IDE、自动化脚本、前端适配层和其他机器消费者。机器结果保留稳定 ID、完整角色字段、规范状态、确定性排序和统一 issue 结构。默认文本是同一 Core Query 的任务投影，不是 JSON 的逐字段翻译。

## 2. 公开命令集

```text
kflow init [PATH]
kflow node add NAME --file PATH [...]
kflow node edit OLD_NAME --name NEW_NAME --file PATH [...]
kflow node remove NAME
kflow derivation add NAME --short TEXT --input NODE ROLE --output NODE ROLE [...]
kflow derivation edit OLD_NAME --name NEW_NAME --short TEXT --input NODE ROLE --output NODE ROLE [...]
kflow derivation remove NAME

kflow overview [--status]
kflow context NODE
kflow impact NODE
kflow review-order [NODE]

kflow confirm NODE
kflow validate

kflow ui start
kflow ui stop
kflow ui status
```

四个查询命令各回答一个问题：

| 命令 | 核心问题 |
|---|---|
| `overview [--status]` | 项目的重要知识怎样相互推导形成？ |
| `context NODE` | 理解或处理该 Node 需要哪些直接相关信息？ |
| `impact NODE` | 该 Node 直接进入哪些 Derivation，更远下游有哪些 Node？ |
| `review-order [NODE]` | 当前真正需要检查哪些 Node，应按什么顺序处理文件？ |

Node reference 可以是精确 Node ID、唯一名称或已登记文件路径；默认文本始终使用名称。

## 3. 默认文本的稳定排序

Node 使用 Core graph 的稳定拓扑顺序：所有上游先于下游；同时可用的 Node 以稳定 Node ID 打破平局。

`overview` 的默认文本把 Project Graph v3 投影为阅读顺序。Derivation 按以下键排序：

1. 最早 output Node 的拓扑位置；
2. 其余 output Node 的拓扑位置序列；
3. Derivation ID 作为最终内部 tie-breaker。

Derivation 内的 inputs 和 outputs 均按 Node 拓扑位置排序。默认文本不展示用于稳定排序的 ID。这个展示投影不改变 Project Graph v3 的冻结机器顺序：`derivations` 按 Derivation ID，角色按 Node ID。

## 4. 标准 Derivation 文本格式

Derivation 始终作为不可拆分的多输入、多输出活动展示。一个区块先列出全部 inputs，再显示 Derivation short，最后列出全部 outputs：

```text
requirements — project requirements [selected]
constraints  — design constraints
  └─ Define system architecture
     → architecture — system architecture
```

多输出使用分支连接符：

```text
architecture — component boundaries
  └─ Design interfaces and verification
     ├─→ api-design — API contract
     └─→ test-plan — verification plan
```

对齐空格只改善可读性，不属于机器契约。`overview` 的角色尾部显示登记文件；`context` 和 `impact` 显示 input/output role short。`[selected]` 只用于 `impact` 标记查询目标。

## 5. `overview [--status]`

`overview` 返回完整项目图，并按稳定 Derivation 顺序把 Node 与推导放在同一逻辑区块中。没有参与任何 Derivation 的 Node 最后进入 `Standalone nodes` 区块。

```text
KFlow project: 6 nodes, 3 derivations

requirements — docs/requirements.md
constraints  — docs/constraints.md
  └─ Define system architecture
     → architecture — docs/architecture.md

architecture — docs/architecture.md
  └─ Design interfaces and verification
     ├─→ api-design — docs/api.md
     └─→ test-plan — docs/tests.md
```

默认不显示状态、review order 或内部 ID。空项目输出：

```text
KFlow project: 0 nodes, 0 derivations

No knowledge nodes registered.
```

`overview --status` 使用相同结构，并在顶部给出待检查数量。只有 reasons 非空的 Node 才带状态标记；无标记表示当前有效。规范 reason 在文本中把下划线替换为空格。

```text
KFlow project: 6 nodes, 3 derivations
Need review: 5 nodes

requirements [files changed] — docs/requirements.md
constraints — docs/constraints.md
  └─ Define system architecture
     → architecture [input changed] — docs/architecture.md
```

validation issue 只在实际存在时追加显示。

项目存在 validation issue 时，`overview --status` 不报告可能误导的零待检查数，而是显示：

```text
Project status: invalid
Review status unavailable until validation issues are resolved.
```

## 6. `context NODE`

`context` 返回目标的一跳局部邻域：目标 Node、producing Derivation、目标直接作为 input 的全部 consumer Derivation，以及这些 Derivation 中出现的全部角色 Node。它不遍历传递 upstream 或 downstream。

```text
architecture [input changed]

Files:
- docs/architecture.md

Produced by:

requirements [files changed] — project requirements
constraints — design constraints
  └─ Define system architecture
     → architecture [input changed] — system architecture

Used by:

architecture [input changed] — system architecture
  └─ Design interfaces and verification
     ├─→ api-design [input changed] — API contract
     └─→ test-plan [input changed] — verification plan
```

没有 producer 时显示 `Produced by: source node`；没有 consumer 时显示 `Used by: no direct derivations`。机器结果中的 `nodes` 提供目标和全部直接角色 Node 的当前状态，Derivation 仍通过 Node ID 引用它们。

## 7. `impact NODE`

`impact` 要求一个 Node 参数。`direct_derivations` 是目标直接作为 input 的所有完整 Derivation；`direct_outputs` 是这些 Derivation 的输出并集；`further_downstream` 是从目标可达、但不含目标和 direct outputs 的 Node 集合。

```text
Impact from: requirements

Direct derivations

requirements — project requirements [selected]
constraints  — design constraints
  └─ Define system architecture
     → architecture — system architecture

Further downstream, in topological order

1. api-design
2. test-plan
3. implementation
```

`further_downstream` 去重并使用全局稳定拓扑序。它只列名称，不展开后续 Derivation、路径、文件或状态。没有更远下游时显示 `Further downstream: none`；没有 direct Derivation 时显示 `No downstream derivations from NAME.`。

缺少 NODE 是参数错误。JSON 模式返回统一合法错误封套。

## 8. `review-order [NODE]`

不指定 Node 时，搜索范围是整个项目。结果只包含 reasons 非空的 Node，并直接使用全局拓扑顺序：

```text
Review order

1. requirements — files changed
   docs/requirements.md

2. architecture — input changed
   docs/architecture.md
```

没有待检查 Node 时输出 `Review scope is clear.`。

指定 Node 时，搜索范围是该 Node 及其全部可达下游。目标本身只有在 reasons 非空时才进入结果：

```text
Review order from: architecture

1. architecture — files changed
   docs/architecture.md

2. api-design — input changed
   docs/api.md
```

子图没有待检查 Node 时输出 `No nodes need review from architecture.`。Core Query 负责范围遍历、过滤、去重和排序；CLI presentation 不自行重建图算法。

## 9. 状态、ID 与确认

默认文本只对需要检查的 Node 显示 reasons。reason 顺序由领域状态算法规范化；显示时使用 `unconfirmed`、`files changed`、`derivation changed`、`input changed`。多个 reason 使用逗号连接。

内部 Node/Derivation ID 只进入 `--json`。实体维护命令的 JSON 返回 stable ID 与完整规范实体；默认文本使用正式 name，例如 `Added Node: architecture` 与 `Edited Derivation: architecture-design -> system-design`。

Node 与 Derivation 的 edit/remove 只接受精确旧 name，不接受 ID、文件路径、output Node、short 或模糊匹配。edit 必须完整重新声明新定义；`--detail` 省略时规范化为空字符串，不表示沿用旧值。Node remove 只允许完全没有 Derivation 引用的 Node，且只删除其 metadata 和 Confirmation；Derivation remove 不删除任何 Node 或 Confirmation。

`confirm NODE` 一次只确认一个 Node。确认后复用全项目 `review-order` 选择下一项：

```text
Confirmed: architecture
Next: api-design — input changed
```

若当前范围完成：

```text
Confirmed: implementation
Current review scope is clear.
```

## 10. 校验、空结果与错误

成功校验：

```text
KFlow metadata is valid.
```

失败校验：

```text
KFlow metadata is invalid.

- missing_file: docs/architecture.md
```

错误的 JSON 最少包含 `ok: false`、当前查询协议版本和非空 `issues`；stdout 不混入普通文本。默认文本错误写入 stderr。issue 使用 `code`、`message`、`references`。默认文本可把 `missing_file`、`unreadable_file` 简写为登记路径；cycle、multiple producer、duplicate name、unknown node 等图或查询错误保留完整 message。

## 11. 关系形态示例

标准格式直接覆盖所有 Derivation 基数，不拆成二元边：

```text
# 1-to-1
api-design
  └─ Implement the service
     → implementation

# 1-to-N
architecture
  └─ Design interfaces and verification
     ├─→ api-design
     └─→ test-plan

# N-to-1
requirements
constraints
  └─ Define system architecture
     → architecture

# N-to-M
requirements
constraints
  └─ Plan delivery
     ├─→ implementation-plan
     └─→ verification-plan
```

## 12. 机器版本边界

Git 跟踪的 Node、Derivation、Confirmation 和 project manifest 使用存储 schema v3。完整项目图 `ProjectGraphResult` 使用 v3，因为 Derivation 增加 required `name`。

`context` 与 `impact` 因完整 Derivation shape 改变使用 v4；shape 未改变的 `review-order`、`confirm` 和 `validate` 保持 v3；实体 mutation 使用 v4。`overview` 和 Human Interface Graph Diff 各自使用 v3。消费者必须按具体 result kind 读取 `schema_version`，不能把版本号当成全仓库单一格式版本。
