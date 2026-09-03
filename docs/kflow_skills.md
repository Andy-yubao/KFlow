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
6. 已登记实体定义变化使用 `node edit` / `derivation edit` 完整替换，失效关系使用 `remove`，不另建重名实体；
7. 只有确有充分理由时才使用受限的 `confirm NODE --downstream`（见下节）。

## 显式批量确认：`confirm NODE --downstream`（受限能力）

普通 `kflow confirm NODE` 永远是安全默认：一次只确认一个你实际检查过的 Node，不级联。

`confirm NODE --downstream` 是显式、更强的批量 assertion：

- scope = NODE + 从它可达的全部 downstream Node；
- 只把范围内当前仍 `needs_review` 的 Node 按稳定全局拓扑顺序写入当前 Confirmation；
- 已经 current 的 Node 不会被重写，也不会进入 confirmed 结果；
- 每个 Node 都使用现有单 Node confirm 逐次确认；KFlow 不做语义推断，不判断“下游一定正确”，只执行你明确发出的批量 assertion；
- 中途失败时，之前已确认的 Node 保留，失败 Node 及其后不再继续；该操作不是跨整个 scope 的原子事务。

### 允许使用

是否允许 `--downstream`，取决于这次变化是否可能改变知识语义、接口、约束、行为或下游结论，而不是它是不是 edit / rename。前提始终是你已能确认整个 downstream scope 无需逐 Node 重新分析；典型是纯机械、不改变知识语义的修正：

- 纯拼写修正；
- 标点 / 排版 / 格式修正；
- 修复后不改变含义、接口、约束或行为的机械语法修正；
- 机械性路径 rename；
- 机械性 Node rename；
- 机械性 Derivation rename；
- 整个 downstream scope 已经由人工或 Agent 一次性完整审查过。

### 禁止或需要逐 Node

以下情况必须逐 Node 阅读并走普通 `review-order` + `confirm`，禁止 `--downstream`：

- 需求 / 接口 / 架构 / 算法 / 约束 / 行为 / 数据格式 / 依赖关系变化；
- 可能改变知识语义或下游结论的 Node / Derivation 定义变化，例如改变 Derivation 语义的 edit，或改变 Node 所代表知识范围的 files/name edit；
- 任何不确定是否纯机械的实体定义变化，或影响范围不明的修改；
- 任何可能改变下游结论的语义修改。

关键不是“是否 rename / edit”，而是“是否可能改变知识语义、接口、约束、行为或下游结论”：可能改变 → 禁止 `--downstream`；能确认只受纯机械影响 → 可以。机械 rename 可走 `--downstream`，语义性 rename 仍要逐 Node 审查。

“代码语法错误”不自动等于安全：修复可能改变程序行为。

### rename 与 downstream

- Node / Derivation rename 照常触发 review；
- KFlow 不替你判断 rename 是否安全；
- 只有当你确认整个 downstream scope 只受机械 rename 影响时，才可 `confirm ROOT --downstream` 一次性收尾；ROOT 使用 edit 后当前有效的 Node reference。

### 决策规则

- 需要逐个打开 downstream Node 才能判断它是否仍正确 → 不要 `--downstream`；
- 已能在当前证据下确认整个 downstream scope 不受语义影响 → 可以 `--downstream`；
- 拿不准 → 使用普通 `review-order` + 单 Node `confirm`。

### 禁止自动调用

不要因为检测到 typo 或 rename 就自动 downstream confirm，也不要制定“所有 rename / formatting 都 downstream confirm”这种固定规则。是否使用由 Agent 基于具体任务判断。

## 禁止行为

- 未阅读目标文件就确认；
- 自动或默认级联确认；批量确认只允许显式 `confirm NODE --downstream`；
- 把 `affected` 当成必然错误；
- 把默认文本当作稳定机器协议；
- 自动登记未受管文件；
- 要求 KFlow 返回正文、摘要、片段或 Prompt；
- 用固定关系类型、向量相似度或自动推断替代显式 Derivation。
