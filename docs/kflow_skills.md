# KFlow Agent Skill

> 状态：当前 Agent 使用基线（2026-08-25）
> 本文描述应调用的能力、顺序与边界，不固定命令名、参数或返回字段拼写。

## 目的

KFlow 是项目知识拓扑与影响范围的外部记忆。它只返回受管文件路径、Node、Derivation、显式语义、状态、影响范围和校验问题；不返回正文、片段、自动摘要或拼装 Prompt。

Agent 负责读取、理解和修改文件，也负责判断受影响 Node 是否真的需要修改。

## 适合纳入 KFlow 的内容

进入项目并准备处理重要文件时，先判断项目是否启用 KFlow。未启用时，不自动初始化或建图。

已启用时，按 Node ID、唯一 name 或已登记文件路径定位目标 Node；文件路径只是 Node reference，后续操作仍以 Node 为单位。未受管文件会得到 `unknown_node` 查询结果，但不代表项目图无效，也不应因此自动登记。

新文件只有在值得长期记住“从哪里来、变化后影响哪里”时才适合登记，例如：

- 重要设计决策与长期需求；
- 架构关系和跨文件约束；
- 复杂推导的输入、输出与依据；
- 会被人类或 Agent 反复使用的设计或验证结论；
- 变化后需要检查其他重要文件的知识单元。

## 不适合纳入 KFlow 的内容

以下内容通常不登记：

- 大量普通源码；
- 临时草稿、日志或一次性输出；
- 缓存、构建产物和可重建文件；
- 简单配置或不影响其他内容的小修改；
- 只有主题相似、没有明确推导关系的材料。

无法判断时，保持为普通文件或向人类建议，不静默扩图。

## 黄金流程

```text
判断项目是否启用
→ 按文件定位 Node
→ 按需查询 upstream / neighborhood
→ Agent 修改文件
→ scan
→ 查询影响范围与 review_order
→ 逐 Node 检查
→ 单独 confirm
→ 查看剩余影响
```

### 1. 判断启用并定位 Node

先查询项目是否已初始化且 schema 可用，再按一个或多个目标文件路径查询所属 Node。

定位结果应提供 Node 的稳定身份、名称和全部文件路径。Agent 不需要预先知道 Node ID。

### 2. 修改前按需查询

当目标 Node 的依据或约束不明确时，查询 upstream 或直接 neighborhood，获得相关 Node、文件路径、Derivation、input/output 作用和稳定拓扑顺序。

Agent 根据当前上下文决定哪些文件需要读取。明显的拼写或格式修复可以跳过这一步。

### 3. 修改真实文件

使用编辑器或 Agent 自身工具修改文件，KFlow 不参与正文编辑。

若修改派生 Node，按需核对其 producing Derivation、直接 inputs 和 sibling outputs。推导逻辑没有变化时，不机械修改 Derivation。

### 4. scan

完成一轮文件或图谱修改后执行只读 scan。scan 校验元数据和文件，计算当前 fingerprint、effective version、review reasons 与 validation issues；它不修改共享事实，也不自动 confirm。

常见 review reasons：

- `unconfirmed`
- `files_changed`
- `derivation_changed`
- `input_changed`

缺失文件、坏引用、非法图或损坏 schema 属于 validation issue，不属于普通 review reason。

### 5. 查询影响与检查顺序

对本次变化查询 impact。结果应包含变化根、直接和传递受影响 Node、全部文件路径、影响深度、来源根、经过的 Derivation、可解释路径、reasons、issues，以及稳定的 `review_order`。

`review_order` 始终来自 impact 结果，也不会自动执行。CLI 的 `review-order` 只是同一 impact 结果的专用展示，不是另一套排序算法或领域操作。把 affected 理解为“可能需要检查”，不要理解为“一定错误、必须修改”。

### 6. 逐 Node 检查

按 `review_order` 处理每个 Node：

- 需要修改：读取并修改文件，然后重新 scan，按新结果继续。
- 不需要修改：确认当前文件在本次变化条件下仍成立，然后单独 confirm。
- 暂时无法判断：保留 `needs_review`，不要为清空列表而确认。

### 7. 单独 confirm

只在目标 Node 已实际检查后 confirm。其含义是：该 Node 已在当前文件、当前生产推导和当前直接输入条件下完成检查。

一次只确认一个 Node；不得级联确认 sibling outputs、下游或整个子图。confirm 不是审批、真伪证明或永久绿色状态。存在阻断性 validation issue 时不得强行确认。

### 8. 查看剩余影响

每次修改或 confirm 后，继续查询与本次变化根相关的待检查 Node、剩余 `review_order` 和 validation issues。

当本次影响范围内不再有未处理的 `needs_review`，且没有阻断该流程的问题时，维护闭环完成。项目中可以保留与本次任务无关的历史未确认 Node。

## Human 使用方式

人类与 Agent 使用同一套事实。人类可以通过：

- `kflow status` 查看项目整体状态、待关注 Node 与原因；
- `kflow context <node>` 理解一个重要知识单元的上下游关系；
- `kflow explain <node>` 理解一次修改可能传播到哪里；
- `kflow review-order` 获得稳定的建议检查顺序；
- Git 历史查看 Node、Derivation 与 Confirmation 的演化。

KFlow 给出结构和影响提示，人类仍负责阅读真实文件、判断是否需要修改，并只在实际检查后确认对应 Node。

## 建图与维护边界

- Node 绑定一个或多个已存在的完整文件；不管理目录、章节、段落或代码片段。
- 没有 producing Derivation 的 Node 合法，并自动视为源 Node。
- Derivation 至少有一个 input 和一个 output，支持多输入、多输出；每个 Node 至多一个 producer，图必须无环。
- producer 变化通过修改相关 Derivation 组合完成；不要寻找独立 `rewire` 能力。
- KFlow 元数据操作不得创建、编辑、移动或删除用户正文。
- 不根据文件名、主题相似性或正文自动猜测并写入 Derivation。
- 不要求 KFlow 提供正文上下文包，也不让它自动改写下游。

## 最短检查表

修改前：

- [ ] 项目是否启用，schema 是否可用？
- [ ] 目标文件属于哪个 Node？
- [ ] 是否需要 upstream / neighborhood？

修改后：

- [ ] 是否完成 scan？
- [ ] 是否查询 impact，并按 `review_order` 检查？
- [ ] 每个已检查 Node 是否单独 confirm？
- [ ] 本次影响范围是否仍有未处理项或阻断问题？
