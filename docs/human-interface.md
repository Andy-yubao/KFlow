# KFlow Human Interface

> 本文定义 KFlow Human Interface 的当前权威架构。领域事实与机器字段分别以
> [正式架构](architecture.md)和[机器契约](schema.md)为准。

## 1. 目标

Human Interface 帮助人类快速理解项目中的重要 Knowledge Node、完整 Derivation、当前状态、待检查原因和结构关系。它是 KFlow 已有项目图的只读人类视图，不是文档编辑器或另一套领域实现。

## 2. 核心原则

- Human Interface 与 Agent Interface 消费同一领域事实。
- `query_project_graph()` 是完整项目图的唯一公共来源；Human Interface 不直接解析 `.kflow` 元数据。
- 展示层不复制 status、impact 或 topological order 算法，也不把 UI 状态写入 Core。
- Derivation 是第一等实体，始终保留完整的多输入、多输出语义。
- Git 是结构演化和历史差异的数据源，不建立平行历史引擎；当前 MVP 只比较工作区与固定 `HEAD`。
- 当前 Human Interface 只读。

## 3. 当前技术架构

```text
Python Core
→ Git HEAD 临时快照 / 纯结构 Graph Diff
→ 本地只读 HTTP Adapter
→ React + TypeScript + Vite
→ React Flow
→ Dagre
```

- `kflow/core/` 维护领域事实、图不变量、状态和公共查询。
- `kflow/human/` 只负责本地 HTTP 生命周期、公共查询的 JSON 传输和包内静态资源服务。
- `kflow/human/git_snapshot.py` 使用参数数组执行只读 Git 命令，将 `HEAD` archive 解压到自动清理的临时目录，并对快照调用公共 `query_project_graph()`；`graph_diff.py` 不执行 Git，只比较两个公共项目图结果。
- `ui/` 保存可维护的 React 与 TypeScript 源码、项目图到画布图的纯转换以及页面状态。
- React Flow 负责图交互，Dagre 只计算当前会话中的从左向右坐标。

## 4. 运行流程

```text
kflow ui
→ 确认当前工作目录
→ 在 127.0.0.1 的随机空闲端口启动服务
→ 输出本地 URL 并默认打开浏览器
→ 浏览器加载包内静态资源
→ 前端分别请求 GET /api/project、GET /api/review-order 与 GET /api/graph-diff
→ GET /api/project 调用 query_project_graph(root)
→ GET /api/review-order 调用 query_affected_context(root)
→ GET /api/graph-diff 对当前 root 调用 query_project_graph(root)，并从 Git HEAD 临时快照再次调用 query_project_graph(snapshot_root)
→ 前端转换并布局 Knowledge Node 与 Derivation
→ 用户在单页图和 Inspector 中只读查看项目
```

服务以前台进程运行，按 `Ctrl+C` 正常关闭；不创建后台 daemon、PID 文件、轮询器或 watcher。

## 5. API

当前正式端点：

```text
GET /api/health
GET /api/project
GET /api/review-order
GET /api/graph-diff
POST /api/open-file
```

`GET /api/health` 返回本地服务健康信息。`GET /api/project` 直接返回当前 `ProjectGraphResult`，不定义第二套 DTO，不经过 CLI stdout，也不缓存第二份长期状态。`GET /api/review-order` 直接返回 `query_affected_context(root)`，前端不重新计算影响范围或检查顺序。未初始化、文件缺失或其他领域问题仍通过正常 HTTP JSON 响应返回，使用 `result.ok == false` 和 `issues` 表达。

`GET /api/graph-diff` 返回独立的 `schema_version: 1` Graph Diff 协议，不改变或冒充 `ProjectGraphResult.schema_version`。可用结果包含 `base`（固定 `revision: HEAD`、完整和短 commit SHA、subject）、计数 `summary`、Node/Derivation 的 `added`、`removed`、`changed`、变化前后拓扑顺序和 `issues`。`changed` 项包含固定顺序的 `changed_fields` 以及 `before` / `after` 公开结构快照；全部数组按 ID 确定性排序。

Node 按 ID 对齐，只比较 `id`、`name` 和 `files`。Derivation 按 ID 对齐，整体比较 `id`、`short`、`detail`、`inputs`、`outputs`，每个角色保留 `node`、`name`、`short`、`detail`，多输入、多输出不会展开为笛卡尔积。`status`、`reasons`、`changed_files` 描述 review 状态，不计入结构历史 diff。`topology_changed` 表示公共查询的确定性拓扑顺序是否变化。

Git 不可用、非 Git 项目、无 `HEAD`、archive 失败或 HEAD 快照不是有效 KFlow 项目时，端点仍返回 HTTP 200、`ok: true`、`available: false`、空差异集合和结构化 issue。Graph Diff 请求或解析失败只影响该面板，不替换项目图错误状态。

`POST /api/open-file` 只接受一个已出现在当前 `ProjectGraphResult.nodes[*].files` 中的规范项目相对路径，并再次确认它真实存在、是普通文件且解析后仍位于项目根目录内。绝对路径、`..`、URL、目录、不存在文件、项目外符号链接、未登记文件和任意命令均被拒绝。服务只调用操作系统默认打开能力，不接受用户指定程序，也不使用 shell。

## 6. 图语义

画布保留如下二部结构：

```text
KnowledgeNode → DerivationNode → KnowledgeNode
```

每个 input role 形成一条 Knowledge Node 到 Derivation 的边，每个 output role 形成一条 Derivation 到 Knowledge Node 的边。一个多输入、多输出 Derivation 只形成一个可选择的中间节点，不展开为 input 与 output 的笛卡尔积。角色的 `short` 与 `detail` 保留在边数据和 Inspector 中。

## 7. 前端源码与构建产物

```text
ui/                    # 可维护的前端源代码
kflow/human/static/    # Vite 生成并由 Python 包分发的静态产物
```

- `ui/node_modules/` 不进入 Git；`ui/package-lock.json` 进入 Git。
- `kflow/human/static/` 是生成产物，不手动编辑；修改 `ui/` 后重新运行 production build。
- wheel 与 sdist 必须包含 `index.html` 和 `assets/`。
- 最终用户运行 `kflow ui` 不需要安装 Node.js。

## 8. 本地服务边界

- 固定绑定 `127.0.0.1`，默认使用操作系统分配的随机端口，不提供远程监听选项。
- Human Interface 不修改 KFlow 元数据和项目文件。它允许有限的本地只读辅助动作，例如打开已经登记的文件。
- 除受限的 `POST /api/open-file` 外不提供 POST；未知 POST 和其他修改方法返回 405。服务没有账户、登录、认证或宽泛 CORS。
- 静态文件只能来自 Python 包内的 `kflow/human/static/`，请求路径不能越出该目录。
- 该服务只用于本机项目查看，不是生产互联网服务器。

## 9. 当前能力

当前版本提供单页面项目摘要、完整知识图、缩放、平移、fit view、搜索、状态筛选、Only needs review、直接邻接高亮、Review Order、Graph Diff vs HEAD、Knowledge Node 与 Derivation 选择、详情 Inspector、已登记文件 Open、错误/空项目状态以及手动 Reload。

Knowledge Node 保持 `240 × 120` 主卡片；Derivation 使用 `32 × 32` 边上连接点，Dagre 同步使用相同尺寸。悬停显示 `short` 的轻量 tooltip，单击后 Inspector 显示 ID、完整语义和全部输入输出角色。搜索有命中时只降低非命中上下文的透明度；没有任何 Node 或 Derivation 命中时保持图的正常不透明度，并在搜索框附近显示明确提示。状态与 needs-review 筛选仍独立控制可见 Node，Derivation 在至少一个相关 Node 可见时保留。选择元素时只高亮直接邻接，不计算传递闭包。

Graph Diff 面板显示 `HEAD` 短 SHA、subject、六类增删改计数和 topological order changed/unchanged。Changed 项显示公开结构的 before → after；当前仍存在的新增或修改实体复用 `ProjectContext` 的选择与画布定位；已删除实体只显示 HEAD 中的历史公开结构，不尝试选择当前不存在的画布元素。这里的 `topology_changed` 只表示稳定拓扑顺序是否变化，不表示任意边结构是否变化。

当前不实现任意 commit selector、分支选择、历史时间线、Git patch 或正文 diff、checkout、编辑、confirm、正文预览、自动摘要、自动轮询、watcher、WebSocket、远程访问和桌面封装。

## 10. 后续演进

```text
阶段 1：只读项目图（已完成）
阶段 2：搜索、筛选、直接邻接高亮和 review order（已完成）
阶段 3：Git-backed graph history / diff
  - Current working tree vs HEAD graph diff MVP（已完成）
  - Commit selection and historical browsing（未开始）
阶段 4：经过单独设计后再评估编辑能力
阶段 5：有实际分发需求后再评估桌面封装
```

这些阶段只记录方向，不为尚未确认的需求预建接口、插件或空抽象。

## 11. 防止过度工程

每一层新增抽象都必须消除当前真实重复，或直接支持已经确认的近期功能。不要为了假设中的未来需求增加架构。

当前取舍是：产品能力优先，公共契约认真设计，工程化保持够用，高级扩展按真实需求延后。
