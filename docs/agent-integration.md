# KFlow Agent Integration

本文说明 Agent 或未来适配层如何组合 KFlow 的稳定只读查询与原子 confirm 操作。详细的
人工演练见 [agent-workflow.md](agent-workflow.md)，机器字段见
[schema.md](schema.md)。当前阶段不实现 MCP Server、IDE 插件、Web UI 或常驻 watcher。

## 1. 集成目标

KFlow 是项目知识拓扑和影响范围的外部记忆。它帮助 Agent 缩小应检查的范围并解释原因，
但不向 Agent 传递正文，也不替 Agent 理解或修改项目。

集成应消费正式 CLI 的 JSON 输出，或调用 `kflow.core.query` 的四个公共入口：

- `query_project_graph(root)`：完整项目图、全部 Derivation、当前 Node 状态与稳定拓扑顺序；
- `query_context(root, node_reference)`：目标 Node 的状态、上下游和相关 Derivation；
- `query_impact(root, node_reference=None)`：显式或自动检测的下游影响；
- `query_affected_context(root)`：当前变化范围内仍待检查的项目级上下文。

字段与封套见 [KFlow 机器契约](schema.md)。适配层不应直接调用 Query 模块的下划线内部函数，
也不应复制 impact 或 `review_order` 算法。

## 2. Agent 工作流程

```text
修改真实文件
    ↓
kflow scan
    ↓
获取 affected context 与 review_order
    ↓
Agent 读取必要文件并逐 Node 判断
    ↓
按需修改真实文件并重新 scan
    ↓
逐 Node confirm
    ↓
再次获取 affected context，直到本次范围闭合
```

### 2.1 修改前

进入项目时先判断 `.kflow/project.json` 是否存在且 schema 可用。首次进入陌生项目或任务涉及多个知识区域时，调用 `kflow overview --json` 建立全貌；目标已明确时不必重复 overview。不要自动初始化、遍历
正文建图或登记全部文件。

若目标文件属于受管 Node，并且依据或约束不清楚，先查询目标 context。Agent 根据返回的
文件路径、Derivation 和显式角色决定要读取哪些文件；简单格式修复可以跳过这一步。

### 2.2 修改与扫描

Agent 使用编辑器或自身工具修改真实文件。完成一轮修改后执行 `kflow scan --json`：

- scan 读取受管文件字节只为计算 fingerprint；
- scan 不返回正文，不写 Confirmation，不自动确认；
- `issues` 与普通 review reasons 分开处理。

如果 `ok` 为 `false`，Agent 应先处理阻断本次流程的 issue，不应强行 confirm。

### 2.3 获取受影响上下文

调用 `kflow context --affected --json` 获取当前变化根、可能受影响的 Node 和
`review_order`。如需解释单个变化根，调用 `kflow explain <node> --json`。

Agent 按 `review_order` 逐个处理：

1. 只从返回的 `files` 得到候选路径；
2. 自行判断哪些文件尚未在当前上下文中并读取必要文件；
3. 结合 `reasons`、`impact_reason` 和 `paths` 理解为何需要检查；
4. 判断 Node 需要修改、不需要修改，或暂时无法判断。

`affected` 表示“可能需要检查”，不表示 KFlow 已证明文件错误。

### 2.4 修改与确认

需要修改时，Agent 修改真实文件并重新 scan，以新结果继续。不需要修改且已实际检查时，
执行 `kflow confirm <node> --json`。

confirm 一次只作用于一个 Node。不得级联确认 sibling outputs、下游或整个子图；暂时无法
判断的 Node 保持待检查。

每次修改或 confirm 后重新查询 affected context。当本次变化范围的 `review_order` 为空且
没有阻断 issue 时，本次闭环完成。项目中可以保留与本任务无关的历史未确认 Node。

## 3. 职责边界

### KFlow 负责

- 保存 Knowledge Node、Derivation 和 Confirmation 共享事实；
- 扫描文件 fingerprint 并计算版本与状态；
- 分析直接和传递影响；
- 返回文件路径、显式关系、原因、路径、问题和稳定检查顺序。

### Agent 负责

- 选择是否以及何时读取文件；
- 理解正文、需求、约束和实现；
- 判断受影响 Node 是否真的需要修改；
- 使用合适工具修改项目；
- 只在实际检查后逐 Node confirm。

### KFlow 不负责

- 返回正文、片段、自动摘要或拼装 Prompt；
- 创建、编辑、移动或删除用户正文；
- 自动判断内容真伪或决定实现方案；
- 根据正文或相似性自动推断关系；
- 替代 Git、编辑器或 Agent。

## 4. 集成护栏

- 以 `schema_version` 选择解析器；不依赖人类可读 CLI 文本。
- 始终检查 `ok` 和 `issues`，错误结果仍使用稳定 Query 封套。
- 将 Node ID 作为稳定身份；名称和文件路径用于展示与定位。
- 保留返回顺序，不在适配层另造 review order。
- Human Interface 与 Agent Interface 都从 `query_project_graph` 获取完整图，不直接读取 `.kflow` JSON 后复制领域逻辑。
- 不把 Query 输出当作文档上下文包；Agent 需要正文时自行读取返回路径。
- 不因未登记文件或空项目自动扩图；未登记本身不是错误。
