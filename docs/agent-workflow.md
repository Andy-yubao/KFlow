# KFlow Agent Workflow

本文展示 Agent 如何使用 KFlow 的正式 CLI 完成一次重要文件变化的检查闭环。KFlow 只提供文件路径、知识拓扑、状态和影响原因；文件内容仍由 Agent 按需读取和修改。

## 场景

项目已经登记以下知识链路：

```text
architecture
    ↓
implementation
    ↓
tests
```

它们分别绑定：

- `docs/architecture.md`
- `docs/implementation.md`
- `docs/tests.md`

三个 Node 都已经在当前版本下分别确认。用户随后修改 `docs/architecture.md`。

## 1. 检测变化

Agent 完成文件修改后先执行扫描：

```bash
kflow scan --json
```

`scan` 比较当前受管文件与上次可重建观察值（首次执行时使用 Confirmation
基线），输出 `added`、`modified`、`deleted` 变化摘要，并把最新 fingerprint
写入被 Git 忽略的 `.kflow/cache/scan.json`。它不修改 Node、Derivation、
Confirmation 或用户文件；共享状态仍由当前事实与 Confirmation 即时计算。

预期结果：

- `architecture` 为 `files_changed`；
- `implementation` 为 `input_changed`；
- `tests` 为 `input_changed`。

KFlow 只读取原始字节计算 fingerprint，不解析、返回或总结正文，也不会判断这些文件是否必须修改。

## 2. 获取目标 Context

Agent 查询变化目标的结构化上下文：

```bash
kflow context architecture --json
```

`context` 与 `explain` 共享同一个稳定 JSON 顶层契约：

- `schema_version`：当前机器契约版本；
- `node`、`status`、`reasons`：目标身份与当前状态；
- `relations`：上游、下游身份及相关 Derivation；
- `impact`：变化根、受影响 Node、深度和可解释路径；
- `review_order`：目标之外仍需检查的下游顺序；
- `issues`：与 review reasons 分离的校验问题。

人类可读输出使用 `Target Node`、`Current Status`、`Why Relevant`、`Upstream Dependencies`、`Downstream Impact` 和 `Recommended Review Order` 区块。Agent 应优先使用 `--json`，不解析人类文本。

## 3. 解释影响

需要展开变化根到下游的影响路径时执行：

```bash
kflow explain architecture --json
```

结果把 `implementation` 标为直接影响，把 `tests` 标为间接影响，并提供经过的 Node 与 Derivation。显式 explain 始终从指定 Node 遍历，不依赖它当前是否有 review reason。

`explain` 的 `review_order` 包含仍需检查的变化根；`context` 已单独展示目标，因此它的 `review_order` 复用同一排序后排除目标本身。

## 4. 获取项目级待检查范围

不想预先指定变化根时，Agent 可以直接查询：

```bash
kflow context --affected --json
```

结果列出当前变化范围内的 `needs_review` Node、每个 Node 的 reasons，以及稳定的
`review_order`。自动检测到的 `files_changed` 或 `derivation_changed` Node 位于
`impact.changed_nodes`；相关下游位于 `impact.affected_nodes`。即使变化根先被
确认，KFlow 仍能从下游保存的直接输入版本基线恢复该范围，尚未确认的
`input_changed` 下游会继续保留。与这次变化无关的孤立 `unconfirmed` Node 不会
被混入 `--affected` 结果。

空结果保持同一 JSON schema：`node` 为 `null`、`status` 为 `confirmed`，
`impact` 和 `review_order` 使用空数组，不要求调用方解析文本或特殊分支。

## 5. 只检查必要范围

Agent 根据 context 和 explain 决定读取哪些文件。这个场景只要求关注：

1. `docs/architecture.md`
2. `docs/implementation.md`
3. `docs/tests.md`

未出现在影响路径中的普通项目文件不应仅为了“完整扫描”而读取。`affected` 表示可能需要检查，不表示一定需要修改。

对每个 Node，Agent 可以：

- 需要修改：读取并修改文件，然后重新执行 `status`；
- 无需修改：确认它在当前输入条件下仍成立；
- 暂时无法判断：保留待检查状态。

## 6. 分别确认

Agent 完成实际检查后，按顺序分别确认：

```bash
kflow confirm architecture --json
kflow confirm implementation --json
kflow confirm tests --json
```

confirm 一次只作用于一个 Node，不级联，也不改变 effective version。确认上游后，下游仍保持原来的待检查状态，直到它自身完成检查并被单独确认。

## 7. 验证闭环

最后重新扫描：

```bash
kflow scan --json
kflow context --affected --json
kflow validate --json
```

本次影响范围内的 Node 应全部为 `confirmed` 且 reasons 为空，validation issues 也应为空。项目中与本次变化无关的历史未确认 Node 不阻塞该闭环。

## 完整命令序列

```text
Agent 修改 docs/architecture.md
→ kflow scan --json
→ kflow explain architecture --json
→ kflow context architecture --json
→ kflow context --affected --json
→ Agent 按 review_order 检查相关文件
→ kflow confirm architecture --json
→ kflow confirm implementation --json
→ kflow confirm tests --json
→ kflow context --affected --json
```

## 边界

这个流程不会：

- 返回文件正文、片段、自动摘要或拼装 Prompt；
- 自动修改文件或生成修改方案；
- 自动确认下游或 sibling outputs；
- 调用 LLM、MCP、IDE 插件或 watcher；
- 自动发现或猜测 Derivation。
