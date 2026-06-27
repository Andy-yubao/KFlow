# KFlow 设计文档

> 版本: 1.0 / 日期: 2026-06-27 / 状态: MVP 设计冻结

---

## 1. 项目定位

KFlow（Knowledge Flow）是一个面向 AI 与人的**知识拓扑管理工具**。

KFlow 不负责存储知识内容，而是维护知识之间的关系，使 AI 能够快速理解一个长期项目中已有的认知结构，无需重新阅读大量历史对话。

KFlow 将知识组织为带有显式拓扑关系的有向无环图（DAG），并记录知识如何由已有知识推导而来。Markdown 文件保持开放，任何编辑器、AI 或开发工具可直接访问，KFlow 仅维护文件之间的结构关系与推导过程。

### 一句话愿景

> **KFlow 不记录"你想了什么"，而记录"你的知识是如何组织起来的"。**

---

## 2. 核心设计理念

1. **Markdown 永远属于用户** — 所有知识以普通 `.md` 保存于 `knowledge/` 目录，KFlow 不修改其内容，只告诉 AI 文件在哪
2. **KFlow 维护知识结构，而非知识内容** — 真正存储的不是"论文写了什么"而是"论文 A + 实验 → 事实库"
3. **AI 不一次读取整个项目** — 每次按需查询局部拓扑，动态加载
4. **复杂业务逻辑交给程序** — 循环检查、影响分析、路径查询由 KFlow 完成，AI 负责思考
5. **Derivation 记录知识的组合方式** — 不记录原因，不记录总结，只记录知识如何组合

### 已淘汰的非目标

- 不是 AI Memory
- 不让 AI 维护所有业务逻辑
- 不把系统建立在 Summary 上
- 不把 Markdown 作为数据库
- 不把整张图一次交给 AI
- Derivation 不记录思考过程

---

## 3. 技术选型

| 决策 | 选择 |
|------|------|
| 形态 | 纯 CLI 工具（Git 风格） |
| 语言 | Python |
| 分发 | pip/pipx/uv（pyproject.toml entry point） |
| 命令前缀 | `kflow` |
| 数据存储 | `.kflow/` 隐藏目录 |
| Markdown 存放 | `knowledge/` 文件夹 |
| 节点文件组织 | `.kflow/nodes/<id>.json`（每节点独立） |
| Derivation 文件组织 | `.kflow/derivations/<id>.json`（每推导独立） |
| 聚合索引 | `.kflow/index.json`（拓扑遍历 + 全局搜索入口） |
| index.json 版本控制 | 不进 Git，可重建 |
| 双向引用策略 | 分文件为真相源，index 为缓存 |
| 一致性模型 | Node 侧存引用，Derivation 侧存完整关系 |

---

## 4. 存储模型

### 4.1 目录结构

```
项目根目录/
├── .kflow/                    # KFlow 元数据（不进 Git）
│   ├── index.json             # 聚合索引
│   ├── nodes/
│   │   └── nd_xxxxxx.json     # 每个节点独立存储
│   └── derivations/
│       └── dv_xxxxxx.json     # 每个 Derivation 独立存储
├── knowledge/                 # 用户 Markdown 文件（进 Git）
│   ├── architecture.md
│   ├── experiment.md
│   └── ...
└── ...
```

### 4.2 index.json（聚合索引）

拓扑遍历和全局搜索的唯一入口。不包含详细描述字段（role_detail、method_detail），只存精简版。每次 mutation 整体重写。不从分文件重建时不存在或被标记为损坏。

```json
{
  "nodes": {
    "nd_a1b2c3": {
      "name": "architecture",
      "file": "knowledge/architecture.md",
      "status": "green",
      "derivations_as_input": ["dv_d4e5f6"],
      "derivations_as_output": []
    }
  },
  "derivations": {
    "dv_d4e5f6": {
      "summary": "构建事实库",
      "inputs": [
        {"node": "nd_a1b2c3", "role": "提供预测框架"},
        {"node": "nd_j1k2l3", "role": "提供参数"}
      ],
      "output": {
        "node": "nd_m3n4o5",
        "method": "依据模型组织实验数据"
      }
    }
  }
}
```

### 4.3 nodes/<id>.json（节点详情）

```json
{
  "id": "nd_a1b2c3",
  "name": "architecture",
  "file": "knowledge/architecture.md",
  "status": "green",
  "derivations_as_input": ["dv_d4e5f6"],
  "derivations_as_output": []
}
```

| 字段 | 说明 |
|------|------|
| `id` | 内部唯一标识，格式 `nd_<6位随机>` |
| `name` | 人类可读名称，对应 `knowledge/<name>.md` |
| `file` | Markdown 文件路径，纯概念节点为 `null` |
| `status` | `green` / `yellow` / `red` |
| `derivations_as_input` | 此节点作为输入的 Derivation ID 列表 |
| `derivations_as_output` | 产出此节点的 Derivation ID（源节点为空数组） |

### 4.4 derivations/<id>.json（推导详情）

包含完整的结构化模板（包括详细描述）。index.json 中的 Derivation 是其精简子集。

```json
{
  "id": "dv_d4e5f6",
  "summary": "构建事实库",
  "inputs": [
    {
      "node": "nd_a1b2c3",
      "role": "提供预测框架",
      "role_detail": "模型定义了参数空间和优化目标，是事实生成的数学骨架。"
    },
    {
      "node": "nd_j1k2l3",
      "role": "提供参数",
      "role_detail": "实验数据通过参数拟合将模型实例化，填充具体的数值。"
    }
  ],
  "output": {
    "node": "nd_m3n4o5",
    "method": "依据模型组织实验数据",
    "method_detail": "以模型定义的框架为行、以实验拟合的参数为值，按事实类型分组组织。"
  }
}
```

| 字段 | 位置 | 说明 |
|------|------|------|
| `summary` | 顶层 + index | 一句话，拓扑图展示用 |
| `inputs[].role` | 顶层 + index | 该知识在推导中的角色（短） |
| `inputs[].role_detail` | 仅分文件 | 角色详细描述 |
| `output.method` | 顶层 + index | 输出生成方式（短） |
| `output.method_detail` | 仅分文件 | 生成方式详细描述 |

**关键约束：一个 Derivation 只有一个输出节点。多输出场景拆成多条 `kflow derive`。**

### 4.5 分层存储原则

| 存储位置 | 存什么 | 用途 |
|----------|--------|------|
| `index.json` | summary + role + method（短） | 拓扑遍历、全局检索、快速展示 |
| `nodes/<id>.json` | 节点完整信息 | 详情查询 |
| `derivations/<id>.json` | Derivation 完整信息（含 role_detail + method_detail） | 深层展开、context 组装 |

---

## 5. 核心对象

### 5.1 Node（知识节点）

一个知识节点通常对应一个 Markdown 文件。可通过 `--no-file` 创建纯概念节点。

每个非源节点都有一条产出它的 Derivation。删节点 = 删产出它的 Derivation。

#### 三色状态模型

| 状态 | 含义 | 触发 |
|------|------|------|
| 🟢 `green` | 知识完整，来源可靠 | `create` / `confirm` |
| 🟡 `yellow` | 上游被修改，可能矛盾 | `modify` 上游时自动传播 |
| 🔴 `red` | 来源缺失 | `remove` 上游时自动传播 |

状态流转：

```
create ──→ green
modify 上游 ──→ yellow (下游)
remove 上游 ──→ red (下游)
confirm ──→ green (自身)
confirm --cascade ──→ green (自身 + 整条下游链)
```

### 5.2 Derivation（推导关系）

记录已有知识如何**组合**形成新知识。不是"为什么这样做"，而是"输入以什么角色参与、输出以什么方式生成"。

### 5.3 Graph

整个项目是 Node + Derivation 组成的 **有向无环图（DAG）**。一个项目可以有任意多个源节点（无上游 Derivation）。

---

## 6. 命令集

所有命令平铺，Git 风格：`kflow <verb> [args...]`。

每个涉及输出的命令支持 `--json` 标志，输出结构化 JSON 供 AI 消费。

### 6.1 命令速览

| 命令 | 做什么 | 类别 |
|------|--------|------|
| `init` | 初始化项目 | 生命周期 |
| `create` | 创建源节点 | 写 |
| `derive` | 建立推导，生成新节点 | 写 |
| `modify` | 标记节点已修改，下游染黄 | 写 |
| `confirm` | 确认验证，恢复绿色 | 写 |
| `remove` | 删除节点，下游染红 | 写 |
| `context` | 向上游组装知识上下文 | 读 |
| `affect` | 向下游追踪影响范围 | 读 |
| `query` | 全局搜索 | 读 |
| `list` | 平铺列出所有节点 | 读 |
| `validate` | 完整性检查，只报告不修复 | 维护 |
| `reindex` | 从分文件重建 index.json | 维护 |

### 6.2 `kflow init`

```bash
kflow init [path]
```

1. 在目标目录创建 `.kflow/`（含 `nodes/` 和 `derivations/` 子目录）
2. 创建空 `index.json`：`{"nodes": {}, "derivations": {}}`
3. 创建空 `knowledge/` 目录
4. 若已初始化则报错退出

### 6.3 `kflow create`

```bash
kflow create <name> [--no-file]
```

1. 生成节点 ID（`nd_<6位随机>`）
2. 检查 name 唯一性，重复则报错
3. 文件关联：检查 `knowledge/<name>.md` 是否存在；存在则直接关联，不存在则创建空文件
4. 若 `--no-file`：不创建不关联 .md 文件，`file` 字段为 `null`
5. 写入 `nodes/<id>.json`：`{id, name, file, status: "green", derivations_as_input: [], derivations_as_output: []}`
6. 更新 `index.json`
7. 输出：`Created node 'architecture' (nd_a1b2c3)`

### 6.4 `kflow derive`

```bash
kflow derive \
  --input <name> --role <短> --role-detail <详> \
  [--input <name> --role <短> --role-detail <详> ...] \
  --output <name> --method <短> --method-detail <详> \
  --summary <一句话>
```

`--input` 可重复多次，至少一个。`--role` / `--role-detail` 与最近的 `--input` 配对。`--output` 只有一个。

行为：
1. 校验所有 `--input` 指向的节点存在
2. 校验 `--output` 指定的 name 不与已有节点冲突
3. 生成 Derivation ID（`dv_<6位随机>`）
4. 生成 Output 节点 ID，`status: "green"`
5. 创建 `knowledge/<output>.md`
6. 写入 `derivations/<id>.json`（含 role_detail, method_detail）
7. 写入 `nodes/<output_id>.json`
8. 更新所有 Input 节点的 `derivations_as_input`，加上此 Derivation ID
9. 更新 `index.json`

### 6.5 `kflow modify`

```bash
kflow modify <name>
```

1. 查找节点，不存在则报错
2. 将该节点的 `status` 设为 `"green"`（自身确认）
3. 沿下游遍历：所有直接和间接下游节点 `status` 设为 `"yellow"`
4. 更新所有受影响节点的 `.json` 文件和 `index.json`
5. 输出受影响节点列表

### 6.6 `kflow confirm`

```bash
kflow confirm <name> [--cascade]
```

1. 查找节点
2. 将 `status` 设为 `"green"`
3. 若 `--cascade`：递归确认所有直接和间接下游节点，整条下游链全部变绿
4. 更新节点 `.json` 和 `index.json`
5. 不传播，不影响下游

**红节点 confirm 行为：** 用户执行 `confirm` = 声明"我手动验证过，即使来源缺失此知识也成立"。节点直接变绿，不做额外检查。

### 6.7 `kflow remove`

```bash
kflow remove <name> [--force] [--keep-file]
```

1. 查找节点，不存在则报错
2. 查该节点的 `derivations_as_input`：若非空且无 `--force`，拒绝并列出所有下游节点
3. 若 `--force`：
   - 从该节点的 `derivations_as_output` 获取产出它的 Derivation，删除之
   - 遍历 `derivations_as_input` 中的所有 Derivation，将其输出节点置 `"red"`
   - 删除该节点的 `nodes/<id>.json`
   - 若未 `--keep-file`，删除 `knowledge/<name>.md`
   - 更新 `index.json`
4. 输出所有被置红的节点列表

### 6.8 `kflow context`

```bash
kflow context <name> [--depth N] [--json]
```

1. 从 `index.json` 加载拓扑
2. 从目标节点出发，BFS 向上游遍历（受 `--depth` 限制，默认无限）
3. 按拓扑序排列所有上游节点（源节点优先，目标节点最后）
4. 去重：每个节点只出现一次
5. 对每个节点输出：`name` + `status` + 来源 Derivation 的 `summary` + `.md` 文件路径

人类可读输出示例：
```
## Context for: factbase

### architecture [green]  knowledge/architecture.md
来源: (source node)

### experiment [green]  knowledge/experiment.md
来源: (source node)

### factbase [green]  knowledge/factbase.md
来源: 构建事实库 — 由 architecture(提供预测框架)、experiment(提供参数) 组合生成
```

`--json` 输出结构化数组，含每个节点的完整元数据及 Derivation 关系。

### 6.9 `kflow affect`

```bash
kflow affect <name> [--depth N] [--json]
```

1. BFS 向下游遍历
2. 树形展示每条影响路径
3. 标注每个节点的当前 `status`

输出示例：
```
architecture [green]
  → [构建事实库] → factbase [green]
                    → [制定发布计划] → release_plan [yellow]
                    → [生成变更日志] → changelog [green]
```

### 6.10 `kflow query`

```bash
kflow query <word> [--json]
```

1. 加载 `index.json`
2. 在 `node.name`、`derivation.summary`、`input.role`、`output.method` 中全文匹配
3. 返回匹配的节点和 Derivation

输出示例：
```
## Nodes (2)
  architecture  knowledge/architecture.md  [green]
## Derivations (1)
  构建事实库 (dv_d4e5f6)
    architecture → factbase
```

### 6.11 `kflow list`

```bash
kflow list [--json]
```

1. 加载 `index.json`
2. 平铺输出所有节点：`name` + `status` + `file`

输出示例：
```
architecture  [green]  knowledge/architecture.md
experiment    [green]  knowledge/experiment.md
factbase      [green]  knowledge/factbase.md
release_plan  [yellow] knowledge/release_plan.md
```

### 6.12 `kflow validate`

```bash
kflow validate
```

检查项（只报告不修复）：

| # | 检查项 | 类型 |
|---|--------|------|
| 1 | 孤立节点（无 input 也无 output 的节点） | 完整性 |
| 2 | 悬挂引用（Node 引用的 Derivation 不存在，或反之） | 完整性 |
| 3 | 循环引用（DAG 中出现环） | 完整性 |
| 4 | index.json 与分文件不一致 | 完整性 |
| 5 | `file` 指向的 .md 不存在 | 文件系统 |
| 6 | `knowledge/` 下存在未注册的 .md | 文件系统 |

### 6.13 `kflow reindex`

```bash
kflow reindex
```

1. 扫描 `nodes/` 和 `derivations/` 下所有 `.json`
2. 重建 `index.json`
3. 输出：`Reindexed: N nodes, M derivations`

### 6.14 统一错误处理

| 情况 | 行为 |
|------|------|
| 节点重名 | 报错，提示先 `remove` |
| 引用的节点不存在 | 报错，列出缺失的节点名 |
| 已初始化再 `init` | 报错，提示项目已存在 `.kflow/` |
| 未初始化就操作 | 报错，提示先 `kflow init` |
| 删除被依赖节点 | 报错，列出下游节点，提示 `--force` |
| index.json 缺失或损坏 | 自动触发 `reindex` 或提示用户执行 |

---

## 7. Skill 集成大纲

MVP 后，KFlow Skill（给 vibecoding 工具的）核心行为：

| AI 需要... | 执行 |
|------------|------|
| 写知识 | `kflow create` 或 `kflow derive` |
| 理解上下文 | `kflow context <相关节点> --json` |
| 修改了某个 .md | `kflow modify <name>` |
| 确认知识仍成立 | `kflow confirm <name>` |
| 查找知识 | `kflow query <keyword> --json` |
| 删除知识 | `kflow remove <name> --force` |

Skill 本身不存状态，所有状态在 `.kflow/` 中。AI 通过执行命令来操作知识拓扑。

---

## 8. MVP 范围边界

### 8.1 MVP 包含

- 12 条命令全部实现
- `--json` 输出支持
- 三色状态模型
- index.json 聚合索引 + 懒重建
- 双向引用 + 分文件真相源
- 统一错误处理

### 8.2 非 MVP（明确不做）

- `inspect` — `context`（上游）和 `affect`（下游）覆盖了主要查询需求
- 自动检测文件修改 — 用显式 `kflow modify` 代替
- `validate --fix` — MVP 只报告
- `kflow remove derivation` — 删节点即删产出它的 Derivation
- 多输出 Derivation — 一 Derivation 一输出，多输出拆多条
- 配置文件 `.kflow/config` — 暂无需要配置的变量
- MCP Server — CLI 优先，后续基于 `--json` 封装
