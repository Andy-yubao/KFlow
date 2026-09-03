# KFlow Agent 工作流

> 本文定义 Agent 直接阅读公开 CLI 默认文本、完成一次知识维护闭环的推荐流程。程序化适配器的 JSON 字段见 [机器契约](schema.md)。

## 1. 进入项目

先确认项目根目录是否有 `.kflow/project.json`。没有启用 KFlow 时，不自动初始化或猜测关系。

首次进入陌生项目时，用完整图建立结构全貌：

```bash
kflow overview
```

需要在完整拓扑上了解当前状态时：

```bash
kflow overview --status
```

从 `KFlow project:` 标题确认 Node 与 Derivation 数量；使用 `--status` 时，再读取 `Need review:` 或项目无效提示。

如果任务已明确指定 Node 或登记文件，可直接使用对应的局部查询，不必机械地调用全部命令。

## 2. 确定当前检查范围

文件修改后直接查询当前事实，不需要额外同步步骤：

```bash
kflow review-order
```

阅读 `Review order` 标题下的编号清单；它只列当前需要检查的 Node，并按稳定全局拓扑序排列。处理某个 Node 及其下游子图时：

```bash
kflow review-order architecture
```

指定根如果已经 current，不会被强制加入列表；仍需检查的下游会保留。

## 3. 在处理前补足信息

需要理解目标 Node 的直接生产和消费关系时：

```bash
kflow context architecture
```

先看目标名称和 `Files:`，再阅读 `Produced by:` 与 `Used by:` 下的完整 Derivation。`context` 是一跳局部关系，不包含项目级 review order 或传递影响。

需要知道目标的结构性下游范围时：

```bash
kflow impact architecture
```

先检查 `Direct derivations` 下的完整 inputs/outputs，再按需处理 `Further downstream, in topological order`。该查询不判断文件必然需要修改，也不返回正文或完整影响路径。

## 4. 阅读、判断和修改

Agent 使用编辑器或自身文件工具读取真实文件。KFlow 只提供登记路径与显式关系。

对 review order 中的每个 Node：

1. 阅读其登记文件；
2. 对派生 Node 检查当前 producer 和直接输入条件；
3. 判断是否需要修改；
4. 完成必要修改与验证；
5. 只确认当前已实际检查的 Node。

## 5. 单 Node 确认

```bash
kflow confirm architecture
```

Confirmation 一次只更新一个 Node，不级联。成功后读取 `Confirmed:` 与 `Next:`；若没有下一项，命令会说明当前范围已清空。

每次确认后，可继续处理 `next`，也可以重新查询：

```bash
kflow review-order
```

普通逐 Node confirm 是唯一默认流程。批量收尾是受限能力，见第 6 节。

## 6. 受限：显式批量确认

`confirm NODE --downstream` 只在 Agent 已能判断整个 downstream scope（目标及其全部可达下游）无需逐 Node 重新分析时才使用。典型场景是纯机械修正：拼写、标点、排版、格式化、明显机械性路径 / 命名修正，或整个 scope 已被一次性完整审查：

```bash
kflow confirm requirements --downstream
```

执行时 KFlow 只把范围内当前仍 needs_review 的 Node 按稳定全局拓扑序写入 Confirmation；已 current 的 Node 不重写。它不做语义推断，不判断“下游一定正确”；中途失败保留已写入部分并明确报告失败 Node，不是原子事务。

必须逐 Node 阅读才能判断是否正确 → 不要 `--downstream`。涉及需求 / 接口 / 架构 / 算法 / 行为 / 约束 / 依赖 / Derivation 定义 / Node 定义等语义变化 → 禁止 `--downstream`。拿不准 → 普通 `review-order` + 单 Node `confirm`。

rename（`node edit` / `derivation edit`）照常触发 review；只有当你确认整个 downstream scope 只受机械 rename 影响时才可 `confirm ROOT --downstream` 收尾，ROOT 使用 edit 后当前有效的 Node reference。完整允许 / 禁止清单见 [KFlow Agent Skill](kflow_skills.md)。

## 7. 结束验收

```bash
kflow review-order
kflow validate
```

完成条件：

- 输出 `Review scope is clear.`；
- 输出 `KFlow metadata is valid.`；
- 任务需要的真实文件测试或检查已经完成。

## 8. 建图操作

新知识只有在值得长期保存来源与影响时才登记：

```bash
kflow node add api-design --file docs/api.md
```

关系明确后，以一次完整活动登记 Derivation：

```bash
kflow derivation add architecture-to-plans --short "架构形成接口和测试" --input architecture "提供组件边界" --output api-design "形成接口契约" --output test-plan "形成验证计划"
```

不得把多输入、多输出推导拆成意义不完整的二元边，也不得根据正文或文件名自动猜测关系。

## 9. 实体维护

已登记实体的定义或关系变化使用 edit/remove 维护，不要另建重名实体。定位一律使用精确旧 name，不接受 ID、文件路径或模糊匹配：

```text
建立新实体         → node add / derivation add
已有实体定义变化   → node edit / derivation edit
关系失效           → derivation remove
Node 不再属于 KFlow → node remove
内容修改后的 review → review-order + confirm
```

- Node edit：按精确旧 name 定位，完整替换该 Node 定义，必须重新声明完整 files；stable ID 不变；rename / files 变化会进入正常 review；不自动 confirm。
- Derivation edit：按精确旧 name 定位，name / short / detail / inputs / outputs 全部完整重新声明；stable ID 不变；任何定义或拓扑变化都走正常 review；不修改任何 Node 正文。
- Derivation remove：只删除该 Derivation，不删除任何 Node；其 output Node 会根据剩余图自然变成 Source / Isolated / 其他角色；Confirmation 保留，状态由现有 review 机制重新计算。
- Node remove：只有完全不被任何 Derivation input/output 引用时才允许删除；若仍有引用，先 edit/remove 相关 Derivation；不 cascade、不删除正文文件；成功后只删除该 Node 的 metadata 和它自己的 Confirmation。

KFlow 维护的是知识实体定义与推导关系，不是正文。不要混用：定义变化走 edit/remove；正文内容变化而不涉及定义时无需改动图。Agent 仍通过编辑器读取和修改真实文件，修改后用 `review-order` + `confirm` 收尾。

## 10. Agent 边界

- 不把 `affected` 解释为文件一定错误；
- 不在未阅读目标文件时确认；
- 不使用自动或默认级联确认；批量收尾只允许显式 `--downstream` 且满足第 6 节条件；
- 不解析默认文本作为稳定机器协议；
- 不期待 KFlow 返回正文、摘要、片段或 Prompt；
- 不把未登记文件自动加入图。
