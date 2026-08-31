# KFlow 机器契约

本文定义当前公开 JSON result。所有数组都具有确定性顺序，所有错误都使用 `issues`；结果不包含登记文件正文。

## 1. 版本边界

KFlow 有三个独立协议边界：

| 协议 | 当前版本 | 使用者 |
|---|---:|---|
| Git metadata | 2 | `.kflow/project.json`、Node、Derivation、Confirmation |
| Project Graph | 2 | `query_project_graph`、`overview --json`、Human Interface |
| Task Query / CLI operation | 3 | `context`、`impact`、`review-order`、mutation、validate、参数错误 |

Graph Diff 仍是独立 v2 协议，Git History 是独立 v1 协议。消费者必须按具体 result kind 解释 `schema_version`。

query schema 从 v2 升至 v3，因为旧共享封套中的 `relations`、`impact`、`review_order` 同时承载多种语义；v3 将其拆成三个不同结果 shape，并把 `context` 改为严格一跳关系。

## 2. 公共字段

### QueryIssue

```json
{
  "code": "unknown_node",
  "message": "unknown node: legacy-api",
  "references": ["legacy-api"]
}
```

### NodeIdentity

```json
{
  "id": "nd_opaque",
  "name": "architecture",
  "files": ["docs/architecture.md"]
}
```

### StatusNode

```json
{
  "id": "nd_opaque",
  "name": "architecture",
  "files": ["docs/architecture.md"],
  "changed_files": [],
  "status": "affected",
  "reasons": ["input_changed"]
}
```

`status` 为 `valid`、`confirmed`、`affected` 或在阻断性 validation issue 下为 `null`。是否需要检查由 `reasons` 是否非空决定。

### DerivationResult

```json
{
  "id": "dv_opaque",
  "short": "Define system architecture",
  "detail": "",
  "inputs": [
    {
      "node": "nd_requirements",
      "name": "requirements",
      "short": "project requirements",
      "detail": ""
    }
  ],
  "outputs": [
    {
      "node": "nd_architecture",
      "name": "architecture",
      "short": "system architecture",
      "detail": ""
    }
  ]
}
```

Derivation 保留完整 inputs/outputs，不投影为笛卡尔积边。`inputs` 与 `outputs` 各自按规范 Node ID 排序。

## 3. ProjectGraphResult v2

```json
{
  "ok": true,
  "schema_version": 2,
  "project": {
    "status": "attention_required",
    "node_count": 6,
    "derivation_count": 3,
    "needs_review_count": 5,
    "issue_count": 0
  },
  "nodes": [],
  "derivations": [],
  "topological_order": [],
  "issues": []
}
```

`nodes` 按 `topological_order`；`derivations` 按 Derivation ID 排序；每个 Derivation 的 `inputs` 与 `outputs` 各自按规范 Node ID 排序。这些是冻结的 Project Graph v2 数组顺序，与默认文本为了阅读而采用的拓扑投影相互独立。

## 4. ContextResult v3

```json
{
  "ok": true,
  "schema_version": 3,
  "node": {},
  "nodes": [],
  "producing_derivation": null,
  "consumer_derivations": [],
  "issues": []
}
```

- `node`：目标 StatusNode；
- `nodes`：目标及所有直接 Derivation 角色 Node，按全局拓扑序；
- `producing_derivation`：目标 producer，源 Node 为 `null`；
- `consumer_derivations`：目标直接作为 input 的完整 Derivation。

不包含传递 upstream/downstream、影响路径或项目 review order。

## 5. ImpactResult v3

```json
{
  "ok": true,
  "schema_version": 3,
  "node": {},
  "direct_derivations": [],
  "direct_outputs": [],
  "further_downstream": [],
  "issues": []
}
```

- `direct_derivations`：目标直接作为 input 的全部完整 Derivation；
- `direct_outputs`：上述 Derivation 的 output Node 并集；
- `further_downstream`：所有可达 Node 去掉目标和 direct outputs 后的集合。

Node 数组按稳定全局拓扑序，`further_downstream` 不包含状态或路径。

## 6. ReviewOrderResult v3

```json
{
  "ok": true,
  "schema_version": 3,
  "scope": null,
  "nodes": [],
  "review_order": [],
  "issues": []
}
```

`scope` 在全项目查询时为 `null`；指定 Node 时为该 NodeIdentity。`nodes` 只包含范围内 reasons 非空的 StatusNode，按稳定拓扑序。`review_order` 是同一顺序的 Node ID 数组，供 Human Interface 等已有消费者直接关联完整项目图。

## 7. Mutation 与 validate

`init`、`add-node`、`derive`、`confirm` 和 `validate` 使用 v3 operation envelope。创建结果返回新 identity；`confirm` 返回目标、确认前后状态，以及复用全项目 review order 得到的 `next` StatusNode 或 `null`。

validate 成功：

```json
{"ok": true, "schema_version": 3, "issues": []}
```

## 8. 错误

参数解析错误使用最小合法封套：

```json
{
  "ok": false,
  "schema_version": 3,
  "issues": [
    {
      "code": "invalid_argument",
      "message": "the following arguments are required: node",
      "references": []
    }
  ]
}
```

领域查询错误保留对应 ContextResult、ImpactResult、ReviewOrderResult 或 ProjectGraphResult 的完整 shape，相关数据数组为空。JSON stdout 不混入 usage 或普通文本。

## 9. 兼容性规则

- 相同协议版本保持顶层字段、字段类型和字段语义；
- 新增破坏性字段要求、删除字段或改变字段语义时提升对应协议版本；
- 默认文本允许改善措辞和布局，但必须使用同一 Core Query；
- ID、路径、reason 和 issue code 区分大小写；
- 不根据未知字段推断正文或关系。
