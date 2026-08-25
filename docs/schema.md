# KFlow 机器契约

本文冻结 KFlow 面向 CLI、Agent 和后续适配层的只读查询协议。当前公共查询入口是
`kflow.core.query` 中的 `query_context`、`query_impact` 和
`query_affected_context`；正式 CLI 的 `context`、`explain` 与
`review-order` 复用这些入口。

KFlow 查询只描述受管文件的路径、显式知识拓扑、状态和影响关系。协议不包含文件正文、
片段、自动摘要或拼装 Prompt。

## 1. 公共查询封套

`kflow context <node> --json` 以及其他公共 Query API 返回相同的顶层结构：

```json
{
  "ok": true,
  "schema_version": 2,
  "node": null,
  "status": "confirmed",
  "reasons": [],
  "relations": {
    "upstream": [],
    "downstream": [],
    "derivations": []
  },
  "impact": {
    "changed_nodes": [],
    "affected_nodes": []
  },
  "review_order": [],
  "issues": []
}
```

顶层字段固定如下：

| 字段 | 类型 | 含义 |
|---|---|---|
| `ok` | boolean | 本次查询是否在没有 validation issue 的情况下完成。 |
| `schema_version` | integer | 机器协议大版本；当前固定为 `2`。 |
| `node` | object 或 `null` | 单 Node 查询的目标；项目级查询为 `null`。 |
| `status` | string 或 `null` | 目标状态，或项目级的 `affected` / `confirmed`；查询错误为 `error`。 |
| `reasons` | string array | 目标或当前受影响范围的规范 review reasons。 |
| `relations` | object | `upstream`、`downstream` 和相关 `derivations`。 |
| `impact` | object | 当前变化根与显式下游影响。 |
| `review_order` | string array | 建议检查的 Node ID，按稳定拓扑顺序排列。 |
| `issues` | object array | 与普通 review reason 分离的查询或校验问题。 |

### 1.1 Node 与关系对象

`node` 包含 `id`、`name`、全部 `files` 和 `changed_files`。关系中的 Node 身份包含
`id`、`name` 和全部 `files`。文件路径均为规范的项目相对路径。

`relations.derivations[]` 包含：

- `id`、`short`、`detail`：显式 Derivation 事实；
- `inputs[]` 与 `outputs[]`：各自的 `node`、`name`、`short`、`detail`。

这些文本是用户登记的关系语义，不是 KFlow 从文件正文提取的内容。

### 1.2 状态与原因

Node 状态为：

- `valid`：尚无 Confirmation；
- `affected`：当前事实与 Confirmation 基线不同；
- `confirmed`：当前事实与基线一致。

规范 review reasons 为 `unconfirmed`、`files_changed`、
`derivation_changed` 和 `input_changed`。同一 Node 可以同时有多个原因。

### 1.3 Issue 与错误结果

每个 issue 固定包含 `code`、`message` 和 `references`。未知 Node 使用
`unknown_node`；未初始化或无法读取的项目使用 `invalid_project`。图校验错误保留各自的
具体 code。

错误不改用另一套封套：`ok` 为 `false`、`status` 为 `error`，集合字段保持存在并使用空
数组，`node` 为 `null`。已初始化的空项目不是错误；项目级 impact/context 返回
`confirmed` 和空集合。

## 2. Impact Schema

`impact` 描述显式 Derivation 图中的影响关系，不描述文件内容，也不表示受影响文件一定
错误或必须修改。

### 2.1 `changed_nodes`

每项包含 `id`、`name`、`files`、`changed_files`、`status` 和 `reasons`。

- 未指定 Node 的 `query_impact` 从当前 `files_changed` 或
  `derivation_changed` Node 自动选择变化根；
- 显式指定 Node 时，该 Node 始终作为遍历根，即使其当前已确认；
- `unconfirmed` 本身不会自动成为内容变化根。

### 2.2 `affected_nodes`

每项在 Node 状态字段之外还包含：

| 字段 | 含义 |
|---|---|
| `depth` | 距变化根的最短 Derivation 层数，直接输出为 `1`。 |
| `roots` | 可影响该 Node 的变化根 ID。 |
| `impact_reason` | 直接影响为 `input_changed`，传递影响为 `upstream_changed`。 |
| `paths` | 可解释路径；每项包含 `root`、经过的 `nodes` 与 `derivations`。 |

`reasons` 是该 Node 相对 Confirmation 的当前 review reasons；
`impact_reason` 是它为何出现在本次影响遍历中的关系原因，两者不可互换。

### 2.3 `review_order`

`review_order` 位于公共封套顶层，是本次相关且仍需检查的 Node 子图的稳定拓扑序：

- 上游先于下游；
- 同层按稳定 Node ID 排序；
- 只提供建议顺序，不执行读取、修改或确认；
- `query_context` 的结果不重复包含作为目标的 Node；显式 `query_impact` 可以包含变化根。

`kflow review-order` 只是同一 impact 结果的专用展示，不维护另一套排序状态。

## 3. Version Schema

Version 是从当前事实确定性计算的 SHA-256 值，不是时间戳、Git commit 或持久化状态
颜色。文件 fingerprint 和 Derivation fingerprint 均带 `algorithm: sha256` 标签；
effective version 当前保存在 Confirmation 基线中，不作为公共 Query 结果的正文上下文。

### 3.1 Source Node version

没有 producing Derivation 的 Node 是 source Node。其 effective version 由以下事实计算：

```text
source_version = SHA256(node.id, current_files_fingerprint)
```

`current_files_fingerprint` 覆盖该 Node 的完整规范路径集合及各文件原始字节 fingerprint，
因此内容变化、文件集合变化或路径变化都会改变版本。

### 3.2 Derived Node version

派生 Node 的 effective version 由以下事实计算：

```text
derived_version = SHA256(
  node.id,
  current_files_fingerprint,
  producing_derivation_fingerprint,
  sorted[(input_node_id, input_effective_version)]
)
```

输入向量按 Node ID 稳定排序。Confirmation 记录确认时的 `effective_version`，并为派生
Node 记录 producing Derivation 的 ID/fingerprint 与直接输入版本向量；confirm 只观察并
保存当前基线，不改变版本。

### 3.3 Derivation 变化传播

Derivation 的 ID、显式语义、inputs、outputs 或各角色描述变化都会改变其 fingerprint，
从而改变全部 outputs 的 effective version。输出 Node 相对旧基线产生
`derivation_changed`，后续下游因直接输入版本改变产生 `input_changed`。传播只报告可能
需要检查的范围，不读取或判断正文。

## 4. 兼容性规则

- 当前 `schema_version: 2` 内保持上述顶层字段、类型、错误封套和确定性排序；
- 新增破坏现有调用方的必填字段、删除字段或改变字段语义，需要提升
  `schema_version`；
- 展示层可以省略视觉上无关的信息，但 `--json` 和公共 Query API 必须遵守本协议；
- 相同项目事实产生字节语义等价、顺序稳定的查询结果。
