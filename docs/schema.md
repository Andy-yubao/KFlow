# KFlow 机器契约

本文定义当前公开 JSON result。所有数组都具有确定性顺序，所有错误都使用 `issues`；结果不包含登记文件正文。

## 1. 版本边界

KFlow 的不同机器协议独立版本化：

| 协议 | 当前版本 | 使用者 |
|---|---:|---|
| Git metadata | 3 | `.kflow/project.json`、Node、Derivation、Confirmation |
| Project Graph | 3 | `query_project_graph`、`overview --json`、Human Interface |
| Context / Impact | 4 | `context`、`impact` |
| Review Order / Confirm / Validate | 3 | shape 未改变的任务结果 |
| Downstream Confirm | 1 | `confirm NODE --downstream` |
| Entity Mutation | 4 | `node add/edit/remove`、`derivation add/edit/remove` |
| Argument Error | 3 | argparse 最小错误封套 |

Graph Diff 是独立 v3 协议，Git History 是独立 v1 协议。消费者必须按具体 result kind 解释 `schema_version`。

query schema 从 v2 升至 v3，因为旧共享封套中的 `relations`、`impact`、`review_order` 同时承载多种语义；v3 将其拆成三个不同结果 shape，并把 `context` 改为严格一跳关系。

Metadata v3 是 clean break：manifest、Node、Derivation 与 Confirmation 必须全部声明 `schema_version: 3`。Derivation 必须包含 `name`；Confirmation 必须包含 `node_fingerprint`。v2 输入或缺失 required `name` 的 Derivation 会被明确拒绝，不存在 `short -> name` fallback。

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
  "name": "architecture-design",
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

## 3. ProjectGraphResult v3

```json
{
  "ok": true,
  "schema_version": 3,
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

`nodes` 按 `topological_order`；`derivations` 按 Derivation ID 排序；每个 Derivation 的 `inputs` 与 `outputs` 各自按规范 Node ID 排序。这些是冻结的 Project Graph v3 数组顺序，与默认文本为了阅读而采用的拓扑投影相互独立。v3 的 breaking change 是每个 Derivation 都包含 required、unique `name`。

## 4. ContextResult v4

```json
{
  "ok": true,
  "schema_version": 4,
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

## 5. ImpactResult v4

```json
{
  "ok": true,
  "schema_version": 4,
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

## 7. DownstreamConfirmResult v1

`confirm NODE --downstream` 使用独立 result kind，不改动普通单 Node confirm 的 v3 shape。普通 `confirm NODE` 返回目标、确认前后状态和复用全项目 review order 得到的 `next`，保持完全不变。

### 成功 shape

```json
{
  "ok": true,
  "schema_version": 1,
  "scope": {
    "id": "nd_requirements",
    "name": "requirements",
    "files": ["docs/requirements.md"]
  },
  "confirmed": [
    {
      "id": "nd_requirements",
      "name": "requirements",
      "files": ["docs/requirements.md"]
    }
  ],
  "skipped_current": [],
  "remaining": [],
  "issues": []
}
```

- `scope`：解析后的目标 NodeIdentity；
- `confirmed`：本次实际写入当前 baseline 的 NodeIdentity，按稳定拓扑序；已 current 的 Node 不进入；
- `skipped_current`：范围内已 current、因此未重写的 NodeIdentity，按稳定拓扑序；
- `remaining`：收尾时范围内仍 needs_review 的 StatusNode（正常清空后为空）；
- `issues`：查询 issue。

### 部分失败 shape

运行期失败（例如某次写入 I/O 异常）保留此前已确认的 Node，并明确报告停止点。该操作不是跨整个 scope 的原子事务：

```json
{
  "ok": false,
  "schema_version": 1,
  "scope": {
    "id": "nd_requirements",
    "name": "requirements",
    "files": ["docs/requirements.md"]
  },
  "confirmed": [
    {
      "id": "nd_requirements",
      "name": "requirements",
      "files": ["docs/requirements.md"]
    }
  ],
  "skipped_current": [],
  "remaining": [],
  "failed_node": {
    "id": "nd_api_design",
    "name": "api-design",
    "files": ["docs/api.md"]
  },
  "issues": [
    {
      "code": "io_error",
      "message": "cannot confirm node api-design: simulated write failure",
      "references": ["nd_api_design"]
    }
  ]
}
```

- `failed_node`：停止处的 NodeIdentity；整批无法开始时为 `null`；
- `confirmed`：仍携带本次已成功写入的 NodeIdentity。

初始 scan 已存在 validation issue 时，在写入任何 Confirmation 前拒绝：`ok` 为 `false`、`confirmed` 为空、`failed_node` 为 `null`、`issues` 携带这些 scan issue。KFlow 不做语义推断；是否整个 downstream scope 可确认由调用者断言。

### 领域错误路由与 pre-write 失败

合法的 downstream invocation（parser 已确认 `command=confirm` 且 `--downstream`）遇到领域 / 项目错误时一律使用 Downstream Confirm v1，绝不落到通用 task-query v3 envelope。领域错误至少包括：unknown Node、invalid project metadata、invalid graph、missing / unreadable managed file、initial scan issue、runtime confirmation failure、final / post-write verification issue。真正的 argparse / command-shape 错误（例如缺少 NODE）仍使用最小 Argument Error v3。

selector / pre-write 错误无法解析目标时，`scope` 与 `failed_node` 均为 `null`。例如 unknown Node：

```json
{
  "ok": false,
  "schema_version": 1,
  "scope": null,
  "confirmed": [],
  "skipped_current": [],
  "remaining": [],
  "failed_node": null,
  "issues": [
    {
      "code": "unknown_node",
      "message": "unknown node: missing",
      "references": ["missing"]
    }
  ]
}
```

### 最终校验 / post-write 失败

写入完成后，若最终验证 scan / review-order 出现 blocking issue（missing file、I/O error、validation issue），结果同样是 partial failure，绝不包装成成功：`ok` 为 `false`、`schema_version` 为 1、`confirmed` 保留本次已成功写入的 Node、`failed_node` 为 `null`、`issues` 携带该 final issue。只要存在 blocking downstream issue，就不产生 `ok: true`，默认文本也不会输出 `Review scope is clear.`。

## 8. Mutation 与 validate

`node add/edit/remove` 与 `derivation add/edit/remove` 使用 v4 mutation envelope，返回 stable ID 和完整规范实体。edit 结果同时返回 `previous_name`。Derivation 的完整实体包含 `name`、`short`、`detail`、`inputs` 与 `outputs`。

`init`、`confirm` 和 `validate` 的 shape 未改变，保持 v3。`confirm` 返回目标、确认前后状态，以及复用全项目 review order 得到的 `next` StatusNode 或 `null`。

validate 成功：

```json
{"ok": true, "schema_version": 3, "issues": []}
```

## 9. 错误

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

## 10. 兼容性规则

- 相同协议版本保持顶层字段、字段类型和字段语义；
- 新增破坏性字段要求、删除字段或改变字段语义时提升对应协议版本；
- 默认文本允许改善措辞和布局，但必须使用同一 Core Query；
- ID、路径、reason 和 issue code 区分大小写；
- 不根据未知字段推断正文或关系。
