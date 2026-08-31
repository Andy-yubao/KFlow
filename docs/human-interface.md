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
- Git 是结构演化和历史差异的数据源，不建立平行历史引擎；当前 MVP 比较工作区与 `HEAD` 或一个由历史 API 返回的祖先 commit。
- 当前 Human Interface 只读。

## 3. 当前技术架构

```text
Python Core
→ Git 结构提交列表 / commit 临时快照 / 纯结构 Graph Diff
→ 本地只读 HTTP Adapter
→ React + TypeScript + Vite
→ React Flow
→ Dagre
```

- `kflow/core/` 维护领域事实、图不变量、状态和公共查询。
- `kflow/human/` 只负责本地 HTTP 生命周期、公共查询的 JSON 传输和包内静态资源服务。
- `kflow/human/git_snapshot.py` 使用参数数组和 literal pathspec 执行只读 Git 命令，列出当前项目 `.kflow/project.json`、`.kflow/nodes/` 和 `.kflow/derivations/` 的近期结构提交，将 `HEAD` 或经校验的祖先 commit archive 解压到自动清理的临时目录，并对快照调用公共 `query_project_graph()`；`graph_diff.py` 不执行 Git，只比较两个公共项目图结果。
- `ui/` 保存可维护的 React 与 TypeScript 源码、项目图到画布图的纯转换以及页面状态。
- React Flow 负责图交互，Dagre 只计算当前会话中的从左向右坐标。

## 4. 运行流程

```text
kflow ui
→ 确认当前工作目录
→ 在 127.0.0.1 的随机空闲端口启动服务
→ 输出本地 URL 并默认打开浏览器
→ 浏览器加载包内静态资源
→ 前端分别请求 GET /api/project、GET /api/review-order、GET /api/git-history 与 GET /api/graph-diff
→ Project Graph 与 Review Order 完成后立即更新核心界面，不等待 Git History
→ Git History 独立校正历史基线，再请求对应 Graph Diff
→ GET /api/project 调用 query_project_graph(root)
→ GET /api/review-order 调用 query_review_order(root)
→ GET /api/git-history 只列当前 HEAD 可达且修改项目 .kflow/project.json、.kflow/nodes/ 或 .kflow/derivations/ 的近期结构提交
→ GET /api/graph-diff 对当前 root 调用 query_project_graph(root)，并从 HEAD 或指定 commit 临时快照再次调用 query_project_graph(snapshot_root)
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
GET /api/git-history
GET /api/graph-diff
POST /api/open-file
```

`GET /api/health` 返回本地服务健康信息。`GET /api/project` 直接返回当前 `ProjectGraphResult`，不定义第二套 DTO，不经过 CLI stdout，也不缓存第二份长期状态。`GET /api/review-order` 直接返回 `query_review_order(root)`，前端不重新计算检查范围或顺序。Project Graph 使用 schema v2，Review Order 使用 task query schema v3。未初始化、文件缺失或其他领域问题仍通过正常 HTTP JSON 响应返回，使用 `result.ok == false` 和 `issues` 表达。

`GET /api/git-history` 返回独立的 `schema_version: 1` Git History 协议。`head` 包含当前 tip 的完整和短 commit SHA、subject 与 committed time；`commits` 只包含当前 `HEAD` 可达、修改过 `<project-relative-path>/.kflow/project.json`、`<project-relative-path>/.kflow/nodes/` 或 `<project-relative-path>/.kflow/derivations/` 的近期结构提交，按新到旧排列，默认最多 30 条、内部上限 100。仓库相对路径使用 literal Git pathspec，因此目录中的空格、中文和 pathspec 元字符不会扩大匹配范围。confirmation-only commit 和普通正文提交不进入列表。若 `HEAD` 本身是结构提交，它只作为独立默认项出现，不在 `commits` 重复。端点不扫描所有历史图来预判有效性。

`GET /api/graph-diff` 返回独立的 `schema_version: 2` Graph Diff 协议，不改变或冒充 `ProjectGraphResult.schema_version`。无 query 时固定比较 working tree vs `HEAD`；`?base=<full-commit-sha>` 比较 working tree vs selected commit。可用结果包含 `base.reference`、解析后的完整和短 commit SHA、subject、committed time、计数 `summary`、Node/Derivation 的 `added`、`removed`、`changed`、变化前后拓扑顺序和 `issues`。`changed` 项包含固定顺序的 `changed_fields` 以及 `before` / `after` 公开结构快照；全部数组按 ID 确定性排序。

历史 base 只接受非空十六进制完整 object ID，并再次确认它解析为 commit 且可从当前 `HEAD` 到达；不接受 branch、tag、`HEAD~n`、pathspec 或其他 Git 参数。明显非法的 query 返回 HTTP 400 和稳定的 unavailable 空集合；commit 不存在、不可达、archive 失败或快照图无效则以 HTTP 200 只降级该次比较。

Node 按 ID 对齐，只比较 `id`、`name` 和 `files`。Derivation 按 ID 对齐，整体比较 `id`、`short`、`detail`、`inputs`、`outputs`，每个角色保留 `node`、`name`、`short`、`detail`，多输入、多输出不会展开为笛卡尔积。Confirmation 属于 review 基线；它与 `status`、`reasons`、`changed_files` 一样不属于 Graph Diff 结构。`topology_changed` 表示公共查询的确定性拓扑顺序是否变化。

Git 不可用、非 Git 项目、无 `HEAD`、history/archive 失败或快照不是有效 KFlow 项目时，对应端点仍返回 HTTP 200、`ok: true`、`available: false` 和结构化 issue。Graph Diff unavailable 结果还严格保持 `base`、`summary` 为 `null`，六类差异数组及 before/after topological order 全部为空。Project Graph 与 Review Order 属于核心数据，完成后立即显示；Git History 与 Graph Diff 属于辅助数据，其缓慢、失败或解析错误只影响对应面板。连续 Reload 会取消旧请求并忽略仍然返回的旧结果，不让旧错误、loading 状态或历史基线覆盖最新状态。

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

当前版本提供单页面项目摘要、完整知识图、缩放、平移、fit view、搜索、状态筛选、Only needs review、直接邻接高亮、Review Order、Graph Diff vs HEAD / selected structural commit、Knowledge Node 与 Derivation 选择、详情 Inspector、已登记文件 Open、错误/空项目状态以及手动 Reload。正式桌面布局已收紧纵向高度：主画布占用可用高度，右侧面板在需要时滚动；窄屏继续使用响应式排列。

Knowledge Node 保持 `240 × 120` 主卡片；Derivation 使用 `32 × 32` 边上连接点，Dagre 同步使用相同尺寸。悬停显示 `short` 的轻量 tooltip，单击后 Inspector 显示 ID、完整语义和全部输入输出角色。搜索有命中时只降低非命中上下文的透明度；没有任何 Node 或 Derivation 命中时保持图的正常不透明度，并在搜索框附近显示明确提示。状态与 needs-review 筛选仍独立控制可见 Node，Derivation 在至少一个相关 Node 可见时保留。选择元素时只高亮直接邻接，不计算传递闭包。

Graph Diff 面板默认显示 `HEAD`，并提供紧凑的结构提交选择器；每项显示短 SHA、subject 和 committed time。切换基准只请求 Graph Diff，不重新请求项目图或 Review Order；快速切换同时使用请求取消和单调 request id，较早响应不能覆盖最新选择。Reload 在原 SHA 仍位于历史列表时保留选择，否则回退 `HEAD`。Changed 项显示公开结构的 before → after；当前仍存在的新增或修改实体复用 `ProjectContext` 的选择与画布定位；已删除实体只显示历史公开结构，不尝试选择当前不存在的画布元素。这里的 `topology_changed` 只表示稳定拓扑顺序是否变化，不表示任意边结构是否变化。

当前搜索、筛选、选择、清除选择和手动缩放触发的 fit view、缩放和平移重置行为是已接受现状。本阶段不加入 viewport persistence，也不改写 React Flow 定位逻辑。

当前不实现 commit A vs commit B、分支/tag 选择、完整历史时间线、历史图替换主画布、Git patch 或正文 diff、checkout、编辑、confirm、正文预览、自动摘要、自动轮询、watcher、WebSocket、远程访问和桌面封装。

## 10. 后续演进

```text
阶段 1：只读项目图（已完成）
阶段 2：搜索、筛选、直接邻接高亮和 review order（已完成）
阶段 3：Git-backed graph history / diff
  - Current working tree vs HEAD graph diff MVP（已完成）
  - Recent structural commit selector + working tree vs selected commit（已完成）
  - Commit A vs Commit B（未开始）
  - Historical graph as main canvas（未开始）
阶段 4：编辑能力另行评估
阶段 5：桌面封装另行评估
```

这些阶段只记录方向，不为尚未确认的需求预建接口、插件或空抽象。

## 11. 防止过度工程

每一层新增抽象都必须消除当前真实重复，或直接支持已经确认的近期功能。不要为了假设中的未来需求增加架构。

当前取舍是：产品能力优先，公共契约认真设计，工程化保持够用，高级扩展按真实需求延后。
