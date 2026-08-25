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

Agent 完成文件修改后先执行只读扫描：

```bash
kflow status --json
```

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

稳定结果包含：

- `node`：目标 ID、名称、全部文件、当前状态和 reasons；
- `upstream`：目标的上游依赖；
- `downstream`：下游 Node、状态、直接或间接影响原因、深度和路径；
- `derivations`：相关推导及显式 input/output 作用；
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

## 4. 只检查必要范围

Agent 根据 context 和 explain 决定读取哪些文件。这个场景只要求关注：

1. `docs/architecture.md`
2. `docs/implementation.md`
3. `docs/tests.md`

未出现在影响路径中的普通项目文件不应仅为了“完整扫描”而读取。`affected` 表示可能需要检查，不表示一定需要修改。

对每个 Node，Agent 可以：

- 需要修改：读取并修改文件，然后重新执行 `status`；
- 无需修改：确认它在当前输入条件下仍成立；
- 暂时无法判断：保留待检查状态。

## 5. 分别确认

Agent 完成实际检查后，按顺序分别确认：

```bash
kflow confirm architecture --json
kflow confirm implementation --json
kflow confirm tests --json
```

confirm 一次只作用于一个 Node，不级联，也不改变 effective version。确认上游后，下游仍保持原来的待检查状态，直到它自身完成检查并被单独确认。

## 6. 验证闭环

最后重新扫描：

```bash
kflow status --json
kflow validate --json
```

本次影响范围内的 Node 应全部为 `confirmed` 且 reasons 为空，validation issues 也应为空。项目中与本次变化无关的历史未确认 Node 不阻塞该闭环。

## 边界

这个流程不会：

- 返回文件正文、片段、自动摘要或拼装 Prompt；
- 自动修改文件或生成修改方案；
- 自动确认下游或 sibling outputs；
- 调用 LLM、MCP、IDE 插件或 watcher；
- 自动发现或猜测 Derivation。
