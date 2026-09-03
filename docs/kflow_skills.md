# KFlow Agent Skill

> 状态：当前 Agent 使用基线（2026-08-31）

## 目的

KFlow 是重要项目文件之间知识拓扑与影响范围的外部记忆。它提供 Node、完整 Derivation、登记路径、状态、review order 和 validation issues；Agent 负责读取、理解、修改与验证真实文件。

## 何时调用

项目存在 `.kflow/project.json` 且任务涉及受管知识时使用 KFlow。未启用时，不自动初始化或猜测关系。

Agent 直接阅读默认文本，根据缺失信息选择一个查询：

- 陌生项目或跨多个知识区域：`kflow overview`；
- 需要完整图的当前状态：`kflow overview --status`；
- 开始处理当前变化：`kflow review-order [NODE]`；
- 处理具体 Node 前：`kflow context NODE`；
- 需要结构性下游范围：`kflow impact NODE`；
- 实际检查完成：`kflow confirm NODE`；
- 结束前：`kflow review-order` 与 `kflow validate`。

不需要机械地依次调用所有查询命令。

## 结果解释

`overview` 从 `KFlow project:` 开始；`--status` 在项目有效时补充 `Need review:`。每个 Derivation 都完整展示全部 inputs 和 outputs。

`context` 只是一跳局部关系。读取 `Files:`、`Produced by:` 与 `Used by:`；producer 与 consumer Derivation 都保留全部角色。

`impact` 从 `Impact from:` 开始。`Direct derivations` 展示目标直接参与的完整活动，`Further downstream, in topological order` 已排除目标和直接输出并去重。

`review-order` 的 `Review order` 编号清单只包含仍需检查的 Node。无 NODE 时范围是全项目；有 NODE 时范围是目标及可达下游。指定目标如果当前有效，不会因此被强制加入。

规范 reasons：`unconfirmed`、`files_changed`、`derivation_changed`、`input_changed`。它们表示需要检查的条件，不表示内容一定错误。

## 操作规则

1. 只读取当前任务需要的登记文件；
2. 对派生 Node 同时检查 producer 与直接输入条件；
3. 完成真实判断和必要验证后，单独确认该 Node；
4. 新 Node 只登记值得长期保存来源与影响的完整文件；
5. 新 Derivation 必须保存一次完整 N-to-M 语义；
6. 已登记实体定义变化使用 `node edit` / `derivation edit` 完整替换，失效关系使用 `remove`，不另建重名实体。

## 禁止行为

- 未阅读目标文件就确认；
- 级联确认下游或 sibling output；
- 把 `affected` 当成必然错误；
- 把默认文本当作稳定机器协议；
- 自动登记未受管文件；
- 要求 KFlow 返回正文、摘要、片段或 Prompt；
- 用固定关系类型、向量相似度或自动推断替代显式 Derivation。
