# KFlow Agent 工作流

> 本文定义 Agent 使用公开 CLI 完成一次知识维护闭环的推荐流程。命令职责见 [CLI 信息架构](cli-information-architecture.md)，机器字段见 [机器契约](schema.md)。

## 1. 进入项目

先确认项目根目录是否有 `.kflow/project.json`。没有启用 KFlow 时，不自动初始化或猜测关系。

首次进入陌生项目时，用完整图建立结构全貌：

```bash
kflow overview --json
```

需要在完整拓扑上了解当前状态时：

```bash
kflow overview --status --json
```

如果任务已明确指定 Node 或登记文件，可直接使用对应的局部查询，不必机械地调用全部命令。

## 2. 确定当前检查范围

文件修改后直接查询当前事实，不需要额外同步步骤：

```bash
kflow review-order --json
```

结果只包含当前 reasons 非空的 Node，按稳定全局拓扑序排列。处理某个 Node 及其下游子图时：

```bash
kflow review-order architecture --json
```

指定根如果已经 current，不会被强制加入列表；仍需检查的下游会保留。

## 3. 在处理前补足信息

需要理解目标 Node 的直接生产和消费关系时：

```bash
kflow context architecture --json
```

读取目标登记文件，以及 `producing_derivation`、`consumer_derivations` 中直接角色 Node 的文件。`context` 是一跳局部关系，不包含项目级 review order 或传递影响。

需要知道目标的结构性下游范围时：

```bash
kflow impact architecture --json
```

先检查 `direct_derivations` 的完整 inputs/outputs，再按需读取 `further_downstream`。该查询不判断文件必然需要修改，也不返回正文或完整影响路径。

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
kflow confirm architecture --json
```

Confirmation 一次只更新一个 Node，不级联。JSON 中 `next` 复用正式全项目 review order；默认文本也会显示下一项，或说明当前范围已清空。

每次确认后，可继续处理 `next`，也可以重新查询：

```bash
kflow review-order --json
```

## 6. 结束验收

```bash
kflow review-order --json
kflow validate --json
```

完成条件：

- `review_order` 为空；
- `validate.ok` 为 `true`；
- 任务需要的真实文件测试或检查已经完成。

## 7. 建图操作

新知识只有在值得长期保存来源与影响时才登记：

```bash
kflow add-node api-design --file docs/api.md --json
```

关系明确后，以一次完整活动登记 Derivation：

```bash
kflow derive --short "架构形成接口和测试" --input architecture "提供组件边界" --output api-design "形成接口契约" --output test-plan "形成验证计划" --json
```

不得把多输入、多输出推导拆成意义不完整的二元边，也不得根据正文或文件名自动猜测关系。

## 8. Agent 边界

- 不把 `affected` 解释为文件一定错误；
- 不在未阅读目标文件时确认；
- 不级联确认多个 Node；
- 不解析默认文本作为稳定机器协议；
- 不期待 KFlow 返回正文、摘要、片段或 Prompt；
- 不把未登记文件自动加入图。
