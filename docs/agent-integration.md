# KFlow Agent 程序化集成

本文描述供 MCP、IDE、脚本和其他机器消费者使用的程序化适配层，不是 Agent 的直接终端工作流。直接操作终端的 Agent 应阅读默认文本并遵循 [Agent 工作流](agent-workflow.md)。

程序化适配层有两类稳定入口：Python Core Query 与 CLI `--json`。两者都只返回结构事实、登记路径、状态和 issues，不返回文件正文。

## 公共 Query

- `query_project_graph(root)`：完整项目图、状态、完整 Derivation 和稳定拓扑序；
- `query_context(root, reference)`：目标的一跳 producing/consumer Derivation；
- `query_impact(root, reference)`：目标直接进入的 Derivation、direct outputs 和更远下游；
- `query_review_order(root, reference=None)`：全项目或指定下游子图中当前仍需检查的 Node。

Human Interface 和 Agent Interface 共用 `query_project_graph` 与 `query_review_order`。适配层不得复制图遍历、状态判断或排序算法。

## 典型调用选择

```text
陌生项目结构       → overview
完整图叠加状态     → overview --status
当前待检查范围     → review-order [NODE]
目标直接关系       → context NODE
目标结构性下游     → impact NODE
完成一个检查       → confirm NODE
结构与文件校验     → validate
```

这些命令按信息缺口选择，不是每次任务都必须顺序调用的固定流水线。

## Node reference

Node 操作接受精确 Node ID、唯一名称或已登记文件路径。查询路径可规范化开头单个 `./` 和 Windows `\` 分隔符。绝对路径、drive path、包含 `..` 的路径和未登记文件返回 `unknown_node`，不会自动建图。

## JSON 与错误

机器消费者使用：

```bash
kflow overview --json
kflow context architecture --json
kflow impact requirements --json
kflow review-order architecture --json
```

stdout 只包含一个 JSON object。查询领域错误保留该命令的完整结果 shape，并使用 `ok: false` 和非空 `issues`。参数解析错误使用最小 envelope：`ok`、`schema_version`、`issues`。

完整项目图使用 v2；按任务拆分的查询和 CLI operation envelope 使用 v3；持久化 metadata 使用 v2。具体 shape 见 [机器契约](schema.md)。

## 安全边界

- 只按登记路径读取真实文件；
- 不把 KFlow 状态当成内容真伪结论；
- 不把 Derivation 投影成普通二元边后丢失角色语义；
- 不在适配层维护第二套 review order；
- 不自动修改正文、建立 embedding、拼装 Prompt 或级联确认。
