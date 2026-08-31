# AGENTS.md

本文件适用于整个 KFlow 仓库。开始工作前请阅读本文件及当前任务直接引用的设计文档。

## 项目梗概

KFlow（Knowledge Flow）是面向人类与 AI Agent 协同开发的知识拓扑和影响范围管理工具。它维护重要项目文件之间的 Knowledge Node、Derivation、变化状态和必要的 Git 历史，帮助 Agent 判断应该关注哪些文件以及为什么，同时帮助人类理解项目结构。

KFlow 不存储或返回文档正文，不是文档编辑器、通用语义检索系统或真伪判断器。

- GitHub：<https://github.com/Andy-yubao/KFlow>
- Git remote：`origin = https://github.com/Andy-yubao/KFlow.git`
- Python：3.11 及以上
- 运行时依赖：标准库，无第三方运行时依赖
- 开发工具：pytest、Ruff
- 主要开发分支：`main`

## 当前代码状态

- `kflow/core/` 是唯一正式领域与应用实现，包含领域模型、图不变量、有效版本、Git-native 持久化、即时状态、单 Node confirm、只读项目图/context/impact/review-order 查询与稳定机器契约；`query_project_graph` 是 Human Interface 和 Agent Interface 共用的完整项目图公共入口。
- `kflow/cli.py` 是唯一正式 CLI 入口，提供 `init`、`add-node`、`derive`、`overview [--status]`、`context`、`impact`、`review-order`、`confirm`、`validate` 和 `ui`。
- `kflow/human/` 与 `ui/` 实现当前本地只读 Human Interface，权威架构见 `docs/human-interface.md`；正式启动入口是 `kflow ui`。
- Human Interface 必须消费 `query_project_graph`，不得直接读取 `.kflow` JSON 后复制图、状态、Derivation 序列化或拓扑排序逻辑，也不得把加载、选择或画布坐标等 UI 状态塞入 Core。
- `kflow/human/static/` 是由 `ui/` 的 Vite build 生成并随 Python 包分发的资源，不手动编辑；`ui/node_modules/` 不进入 Git。
- 当前 Human Interface 只读。除非用户明确授权，不要扩展编辑、Git 历史/diff、watcher、远程服务、MCP 或桌面封装。
- Human Interface Demo 的说明与试用教程见 `docs/demo-project.md`，默认位于仓库外的 `../KFlow-human-interface-demo`。Demo 不自动维护；只有用户明确要求时才更新 Demo 和教程。
- `docs/history/` 只保存历史决策材料，不定义当前产品行为。

## 权威文档

按以下顺序理解 KFlow：

1. `docs/core-principles.md`：产品使命、边界和设计决策过滤器。
2. `docs/architecture.md`：正式领域模型、图不变量、状态算法和架构边界。
3. `docs/kflow_skills.md`：Agent 与人类正确使用 KFlow 的流程与边界。
4. `docs/agent-workflow.md`：正式 CLI 的端到端维护闭环。
5. `docs/schema.md`：稳定机器契约。
6. `docs/human-interface.md`：Human Interface 技术架构、边界与演进阶段。
7. `README.md`：首次使用入口与命令概览。

历史文档不得覆盖上述正式决策。

## Conda 与 Python 环境

项目约定的 Conda 环境名统一使用小写：`kflow`。

```powershell
conda activate kflow
python --version
```

2026-08-20 在当前机器核对时没有发现名为 `kflow` 或大小写变体的环境；当前激活的是 `base`，Python 3.13.9。不要把 `base` 写成项目专用环境，也不要在未获授权时创建或重建 Conda 环境。需要创建时建议使用：

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

Windows 沙箱中 pytest 的默认 `tmp_path` 可能因临时目录权限失败；可改用工作区内明确的临时目录，测试后必须清理，不得留下生成物。

## 开发约束

- 修改前检查工作树并保留用户已有改动。
- 使用小任务、小改动、测试先行和明确验收标准。
- 正式领域代码放在 `kflow/core/`；不要创建带产品版本号的平行运行路径。
- Knowledge Node 只管理一个或多个完整文件；不建立章节、段落或代码片段级 Node。
- Node 可以独立存在；没有 producing Derivation 的 Node 自动视为源 Node。
- Derivation 至少有一个输入和一个输出；每个 Node 至多由一个 Derivation 产生。
- confirm 只作用于一个 Node，绝不级联确认。
- Node、Derivation、Confirmation 是 Git 跟踪的共享事实；缓存、锁和临时 observation 不是。
- KFlow 不得创建、编辑、移动或删除用户正文。
- Agent 输出不得包含文档正文、片段、自动摘要或拼装 Prompt。
- 不引入固定关系类型、向量数据库、event sourcing 或替代方案特殊关系。

## Git 约束

- 提交前运行相关测试与 Ruff。
- 精确暂存本任务文件，不使用 `git add .`、`git add -A` 或 `git add --all`。
- 不提交 `.pytest_cache/`、`.ruff_cache/`、`__pycache__/`、`*.egg-info/` 或机器本地设置。
- 普通变更使用功能分支，除非用户明确要求直接修改主分支。
- commit、push、PR 等外部写操作分别遵循用户授权范围。
