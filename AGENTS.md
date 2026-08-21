# AGENTS.md

本文件适用于整个 KFlow 仓库。开始工作前请先阅读本文件及当前任务直接引用的设计文档。

## 项目梗概

KFlow（Knowledge Flow）是一个面向人类与 AI Agent 协同开发的知识拓扑和影响范围管理工具。它维护重要项目文件之间的 Knowledge Node、Derivation、变化状态和必要的 Git 历史，帮助 Agent 判断应该关注哪些文件以及为什么，同时帮助人类理解项目结构。

KFlow 不存储或向 Agent 返回文档正文，不是文档编辑器、通用语义检索系统或真伪判断器。

- GitHub：<https://github.com/Andy-yubao/KFlow>
- Git remote：`origin = https://github.com/Andy-yubao/KFlow.git`
- Python：3.11 及以上
- 运行时依赖：当前为标准库，无第三方运行时依赖
- 开发工具：pytest、Ruff

## 当前代码状态

- `kflow/` 中的原有模块是可运行的 v1 CLI，保留为行为基线。
- `kflow/v2/` 是与 v1 隔离的 v2 纯领域内核，当前只包含模型、图不变量和有效版本计算。
- v2 开发目前暂停。除非用户明确要求恢复开发，否则不要继续实现 codec、存储、CLI、迁移器、Web UI 或 MCP。
- 不要为了兼容 v1 而改变已批准的 v2 领域模型，也不要在没有明确授权时删除 v1。

## 权威文档

按以下顺序理解 v2：

1. `KFlow_v2_重构启动指令.md`：产品边界和重构原则。
2. `docs/KFlow_v2_领域模型与重构方案.md`：已批准的 v2 schema、状态算法和实施路线。
3. `docs/KFlow_v2_首轮审查报告.md`：v1/v2 差异、迁移风险和决策记录。
4. `README.md` 和 `docs/superpowers/`：v1 使用方式与历史设计。

`docs/KFlow_v2_重构计划书.md` 是被启动指令取代的早期历史草案，不得以其中的章节级 Node、固定关系类型、event sourcing、正文 ContextBundle 等内容覆盖已批准方案。

## Conda 与 Python 环境

项目约定的 Conda 环境名统一使用小写：`kflow`。

```powershell
conda activate kflow
python --version
```

2026-08-20 在当前机器执行 `conda env list` 的核对结果：没有发现名为 `kflow`、`KFlow` 或其他大小写变体的环境；当前激活的是 `base`，Python 3.13.9。不要把 `base` 误写成项目专用环境，也不要在未获授权时自动创建或重建 Conda 环境。需要创建时建议使用：

```powershell
conda create -n kflow python=3.11
```

## 常用命令

```powershell
python -m kflow --help
pytest -q
ruff check .
ruff format --check .
```

Windows 沙箱中 pytest 的默认 `tmp_path` 可能因临时目录权限失败；这属于运行环境问题。需要改用工作区临时目录时，测试后必须清理该明确目录，不得留下生成物。

## 开发约束

- 修改前先检查工作树，保留用户已有改动。
- 使用小任务、小改动、测试先行和明确验收标准。
- v2 代码继续放在独立命名空间，直到替换策略获批。
- Knowledge Node 只管理一个或多个完整文件；不建立章节、段落或代码片段级 Node。
- 每个 Node 恰好由一个 Derivation 产生；源 Node 使用零输入 Derivation。
- confirm 只作用于一个 Node，绝不级联确认。
- Node、Derivation、Confirmation 是 Git 跟踪的共享事实；缓存、锁和临时 observation 不是。
- KFlow 不得创建、编辑、移动或删除用户正文。
- Agent 输出不得包含文档正文、片段、自动摘要或拼装 Prompt。
- 不引入固定关系类型、向量数据库、event sourcing 或替代方案特殊关系。

## Git 约束

- 提交前运行相关测试与 Ruff。
- 精确暂存本任务文件，不使用 `git add .`、`git add -A` 或 `git add --all`。
- 不提交 `.pytest_cache/`、`.ruff_cache/`、`__pycache__/`、`*.egg-info/` 或机器本地设置。
- 默认分支是 `main`；普通变更使用功能分支，除非用户明确要求直接修改默认分支。
- commit、push、PR 等外部写操作分别遵循用户授权范围。
