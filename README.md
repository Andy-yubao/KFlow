# KFlow — Knowledge Flow CLI

面向 AI 与人的知识拓扑管理工具。不存储知识内容，而是维护知识之间的 DAG 关系，记录知识如何由已有知识推导而来。

## 安装

```bash
pip install -e .
```

或通过 pipx/uv 安装：

```bash
pipx install .
# 或
uv tool install .
```

## 快速开始

```bash
# 1. 初始化项目
kflow init

# 2. 创建知识节点
kflow create architecture

# 3. 从已有知识推导出新知识
kflow derive \
  --input architecture --role "提供系统框架" --role-detail "定义模块边界和数据流" \
  --input requirements  --role "提供需求约束" --role-detail "功能与非功能需求列表" \
  --output design --method "综合架构与需求形成设计方案" --method-detail "以架构为骨架..." \
  --summary "从架构和需求推导设计方案"

# 4. 查询知识拓扑
kflow list                 # 平铺列出所有节点
kflow context design       # 查看 design 的上游知识链
kflow affect architecture  # 查看 architecture 影响的下游知识
kflow query api            # 搜索包含 "api" 的知识

# 5. 维护知识图谱
kflow modify architecture  # 标记 architecture 已修改，下游自动变黄
kflow confirm design       # 确认 design 仍成立，恢复绿色
kflow remove requirements --force  # 删除节点，下游自动变红
```

## 核心概念

### Node（知识节点）

每个 Node 对应一个 `knowledge/<name>.md` 文件。KFlow 不修改 Markdown 内容，只维护节点之间的结构关系。

节点有三种状态：

| 状态 | 颜色 | 含义 |
|------|------|------|
| `green` | 🟢 | 知识完整，来源可靠 |
| `yellow` | 🟡 | 上游被修改，可能不一致 |
| `red` | 🔴 | 上游来源缺失，需要确认 |

### Derivation（推导关系）

记录已有知识如何**组合**形成新知识。每次推导是"多输入 → 单输出"：

```
architecture ─┐
              ├─→ [推导: 设计方案] → design
requirements ─┘
```

每个输入有角色（role）：描述该知识在推导中扮演的角色。
输出有方法（method）：描述输出如何从输入组合生成。

### DAG（有向无环图）

整个项目是 Node + Derivation 组成的 DAG。源节点（无上游推导）代表从零开始的知识，其余节点都有且仅有一条产出它的 Derivation。

### index.json

`.kflow/index.json` 是聚合索引，每次写操作自动重写，供拓扑遍历和全局搜索使用。损坏时可通过 `kflow reindex` 从分文件重建。**不进 Git。**

## 命令参考

所有命令支持 `--json` 标志输出结构化 JSON，供 AI/MCP 消费。

### `kflow init [path]`

初始化 KFlow 项目，创建 `.kflow/` 和 `knowledge/` 目录。

```bash
kflow init
kflow init /path/to/project
```

### `kflow create <name> [--no-file]`

创建源知识节点（无上游推导的节点）。自动创建 `knowledge/<name>.md`。

```bash
kflow create architecture
kflow create pure-concept --no-file   # 不创建 .md 文件
```

### `kflow derive`

从已有节点推导出新节点。支持命令行参数和交互式两种方式。

**命令行模式：**

```bash
kflow derive \
  --input <name> --role <短角色> --role-detail <详细描述> \
  --output <name> --method <短方法> --method-detail <详细描述> \
  --summary <一句话摘要>
```

`--input` 可重复多次。`--role` / `--role-detail` 与最近的 `--input` 配对。

**交互式模式（无参数时自动触发）：**

```bash
kflow derive
# Output node name: factbase
# Method (short): 依据模型组织实验数据
# Method detail: ...
# Input #1 name: architecture
# Input #1 role: 提供预测框架
# Input #1 role detail: ...
# Add another input? [y/N]:
# Summary: 构建事实库
```

### `kflow modify <name>`

标记节点内容已修改。目标节点自身变绿（表示修改后的内容已确认），所有下游节点传播为黄色（警告可能不一致）。

```bash
kflow modify architecture
# architecture [green]
#   Affected: design, api_spec, deployment_plan
```

### `kflow confirm <name> [--cascade]`

确认节点知识仍然成立，恢复绿色。

```bash
kflow confirm design             # 仅确认 design
kflow confirm architecture --cascade  # 确认 architecture 及整条下游链
```

> 红节点执行 `confirm` 表示"我手动验证过，即使来源缺失，此知识也成立"，节点直接变绿。

### `kflow remove <name> [--force] [--keep-file]`

删除节点。若有下游依赖则拒绝（除非 `--force`）。

```bash
kflow remove orphan              # 删除无下游的节点
kflow remove architecture --force    # 强制删除，下游全部染红
kflow remove draft --keep-file   # 删除节点但保留 .md 文件
```

### `kflow context <name> [--depth N]`

向上游追溯知识上下文，按拓扑序展示从源节点到目标节点的完整推导链。

```bash
kflow context factbase
# ## Context for: factbase
#
# ### architecture 🟢  knowledge/architecture.md
# 来源: (source node)
#
# ### experiment 🟢  knowledge/experiment.md
# 来源: (source node)
#
# ### factbase 🟢  knowledge/factbase.md
# 来源: 构建事实库 — 由 architecture(预测框架)、experiment(参数) 组合生成

kflow context factbase --depth 1  # 仅一层上游
```

### `kflow affect <name> [--depth N]`

向下游追踪影响范围，树形展示被目标节点影响的全部下游知识。

```bash
kflow affect architecture
# architecture 🟢
#   → design 🟢
#   → api_spec 🟡
#     → implementation 🟡
#     → tests 🟡
```

### `kflow query <word>`

在节点名、推导摘要、输入角色、输出方法中全文搜索。

```bash
kflow query api
# ## Nodes (2)
#   api_spec     knowledge/api_spec.md     [green] 🟢
#   api_client   knowledge/api_client.md   [yellow] 🟡
# ## Derivations (1)
#   生成 API 规范 (dv_a1b2c3)
#     architecture, requirements → api_spec
```

### `kflow list`

平铺列出所有节点。

```bash
kflow list
# architecture  [green]  🟢  knowledge/architecture.md
# api_spec      [yellow] 🟡  knowledge/api_spec.md
# experiment    [green]  🟢  knowledge/experiment.md
```

### `kflow validate`

运行 6 项完整性检查，只报告不修复：

| # | 检查项 | 严重度 |
|---|--------|--------|
| 1 | 孤立节点（无输入也无输出） | warning |
| 2 | 悬挂引用（节点与 Derivation 间引用断裂） | error |
| 3 | 循环引用（DAG 中出现环） | error |
| 4 | index.json 与分文件不一致 | error |
| 5 | file 指向的 .md 不存在 | error |
| 6 | knowledge/ 下存在未注册的 .md | warning |

```bash
kflow validate
# ✓ All checks passed.
```

### `kflow reindex`

从 `nodes/` 和 `derivations/` 下的分文件重建 `index.json`。

```bash
kflow reindex
# Reindexed: 5 nodes, 3 derivations
```

## 典型工作流

### 场景：AI 辅助的渐进式知识构建

```bash
# Session 1: AI 理解需求，创建初始知识节点
kflow init
kflow create requirements      # 创建需求文档
kflow create constraints        # 创建约束条件

# Session 2: AI 推导设计方案
kflow derive \
  --input requirements --role "功能需求" --role-detail "..." \
  --input constraints   --role "设计约束" --role-detail "..." \
  --output system-design --method "权衡需求与约束" --method-detail "..." \
  --summary "从需求与约束推导系统设计"

# Session 3: AI 修改需求，触发影响分析
kflow modify requirements
kflow affect requirements       # 查看哪些知识受影响（变黄）
kflow context api-spec --json    # AI 获取需要复查的上下文

# Session 4: AI 逐项确认受影响的知识
kflow confirm system-design
kflow confirm api-spec --cascade
kflow validate
```

### 场景：手动维护知识图谱

```bash
# 创建知识
kflow create research-paper

# 记录推导过程
kflow derive \
  --input research-paper --role "理论基础" --role-detail "..." \
  --input experiment    --role "实验验证" --role-detail "..." \
  --output conclusion --method "综合理论与实验" --method-detail "..." \
  --summary "论文结论推导"

# 论文修改后
kflow modify research-paper     # 下游变黄

# 检查影响
kflow affect research-paper

# 确认结论仍成立
kflow confirm conclusion
```

## JSON 输出（供 AI/MCP 消费）

所有命令支持 `--json` 标志。错误走 stderr + 非零退出码，成功走 stdout。

```bash
kflow context factbase --json
```

```json
{
  "target": "nd_m3n4o5",
  "nodes": [
    {
      "id": "nd_a1b2c3",
      "name": "architecture",
      "status": "green",
      "file": "knowledge/architecture.md",
      "source": null
    },
    {
      "id": "nd_m3n4o5",
      "name": "factbase",
      "status": "green",
      "file": "knowledge/factbase.md",
      "source": {
        "derivation_id": "dv_d4e5f6",
        "summary": "构建事实库",
        "inputs": [
          {"node": "nd_a1b2c3", "role": "提供预测框架"},
          {"node": "nd_x1y2z3", "role": "提供参数"}
        ]
      }
    }
  ]
}
```

## 目录结构

```
项目根目录/
├── .kflow/                    # 元数据（不进 Git）
│   ├── index.json             # 聚合索引
│   ├── nodes/
│   │   └── nd_xxxxxx.json     # 每个节点独立存储
│   └── derivations/
│       └── dv_xxxxxx.json     # 每个 Derivation 独立存储
├── knowledge/                 # Markdown 文件（进 Git）
│   ├── architecture.md
│   ├── experiment.md
│   └── ...
└── ...
```

## 技术栈

- Python 3.11+
- 零外部依赖（标准库优先）
- 命令风格：Git 式平铺

## 许可证

MIT
