# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

KFlow（Knowledge Flow）是一个面向 AI 与人的知识拓扑管理 CLI 工具。它不存储知识内容，而是维护知识之间的 DAG 关系，记录知识如何由已有知识推导而来。

完整设计文档见：`docs/superpowers/specs/2026-06-27-kflow-design.md`
实现前必须阅读。

## 技术栈

- Python 3.11+ / CLI 工具
- 分发：pip/pipx/uv，通过 `pyproject.toml` 的 `[project.scripts]` entry point
- 无外部依赖（MVP 阶段标准库优先）
- 命令风格：Git 式平铺，`kflow <verb> [args...]`

## 核心架构

存储模型三层：

```
.kflow/index.json          ← 聚合索引（拓扑 + 全局搜索入口，不进 Git）
.kflow/nodes/<id>.json     ← 节点详情（分文件真相源）
.kflow/derivations/<id>.json ← 推导详情（含完整模板）
knowledge/*.md             ← 用户 Markdown（进 Git，KFlow 不修改内容）
```

核心对象：
- **Node**：知识节点，通常对应 `knowledge/<name>.md`，三色状态（green/yellow/red）
- **Derivation**：多输入单输出的推导关系，记录 role（输入扮演的角色）和 method（输出的生成方式）
- 一个 Node（非源节点）一定有唯一产出它的 Derivation。删 Node = 删 Derivation

双向引用：Node 侧存 `derivations_as_input` 和 `derivations_as_output` 的引用，Derivation 侧存完整 input/output 关系。分文件是真相源，index.json 是缓存。

## 命名规范

KFlow 自身定义的术语（命令名、字段名、JSON key、代码标识符、CLI 输出标签）采用工程化、低歧义的词汇。避免 AI/认知科学词汇进入 API 和数据结构命名。

**使用：** Node、Operation、Relation、Dependency、Query、Index、Validation、Source、Context、Affect、Snapshot、Workspace

**避免：** Cognition、Thinking、Reasoning、Memory、Intelligence、Understanding

此规范仅约束 KFlow 定义的术语。说明性文字（文档、注释、commit message）不受限制——"AI 负责思考"、"认知结构" 等自然语言描述是合理的。

## 开发命令

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行（开发模式）
python -m kflow <args>

# 测试
pytest
pytest tests/ -k <pattern>

# 格式化与检查
ruff check .
ruff format .
```

## 关键设计约束

- 一 Derivation 一输出。多输出拆成多条 `kflow derive`
- index.json 不进 Git。`kflow reindex` 从分文件重建
- `role` 和 `method` 各有短（index 存）和详（分文件存）两层
- 状态传播：`modify` → 下游变黄，`remove` → 下游变红，`confirm` → 变绿（可选 `--cascade`）
- 所有输出支持 `--json`，供 AI/MCP 消费
