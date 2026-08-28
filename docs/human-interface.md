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
- Git 是未来结构演化和历史差异的数据源，不建立平行历史引擎。
- 当前 Human Interface 只读。

## 3. 当前技术架构

```text
Python Core
→ 本地只读 HTTP Adapter
→ React + TypeScript + Vite
→ React Flow
→ Dagre
```

- `kflow/core/` 维护领域事实、图不变量、状态和公共查询。
- `kflow/human/` 只负责本地 HTTP 生命周期、公共查询的 JSON 传输和包内静态资源服务。
- `ui/` 保存可维护的 React 与 TypeScript 源码、项目图到画布图的纯转换以及页面状态。
- React Flow 负责图交互，Dagre 只计算当前会话中的从左向右坐标。

## 4. 运行流程

```text
kflow ui
→ 确认当前工作目录
→ 在 127.0.0.1 的随机空闲端口启动服务
→ 输出本地 URL 并默认打开浏览器
→ 浏览器加载包内静态资源
→ 前端请求 GET /api/project 与 GET /api/review-order
→ 服务端在每次请求时调用 query_project_graph(root)
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
POST /api/open-file
```

`GET /api/health` 返回本地服务健康信息。`GET /api/project` 直接返回当前 `ProjectGraphResult`，不定义第二套 DTO，不经过 CLI stdout，也不缓存第二份长期状态。`GET /api/review-order` 直接返回 `query_affected_context(root)`，前端不重新计算影响范围或检查顺序。未初始化、文件缺失或其他领域问题仍通过正常 HTTP JSON 响应返回，使用 `result.ok == false` 和 `issues` 表达。

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

当前版本提供单页面项目摘要、完整知识图、缩放、平移、fit view、搜索、状态筛选、Only needs review、直接邻接高亮、Review Order、Knowledge Node 与 Derivation 选择、详情 Inspector、已登记文件 Open、错误/空项目状态以及手动 Reload。

Knowledge Node 保持 `240 × 120` 主卡片；Derivation 使用 `32 × 32` 边上连接点，Dagre 同步使用相同尺寸。悬停显示 `short` 的轻量 tooltip，单击后 Inspector 显示 ID、完整语义和全部输入输出角色。搜索只降低非命中上下文的透明度；状态与 needs-review 筛选控制可见 Node，Derivation 在至少一个相关 Node 可见时保留。选择元素时只高亮直接邻接，不计算传递闭包。

当前不实现 Git 历史或 diff、编辑、confirm、正文预览、自动摘要、自动轮询、watcher、WebSocket、远程访问和桌面封装。

## 10. 后续演进

```text
阶段 1：只读项目图
阶段 2：搜索、筛选、直接邻接高亮和 review order（已完成）
阶段 3：Git-backed graph history / diff
阶段 4：经过单独设计后再评估编辑能力
阶段 5：有实际分发需求后再评估 Tauri
```

这些阶段只记录方向，不为尚未确认的需求预建接口、插件或空抽象。

## 11. 防止过度工程

每一层新增抽象都必须消除当前真实重复，或直接支持已经确认的近期功能。不要为了假设中的未来需求增加架构。

当前取舍是：产品能力优先，公共契约认真设计，工程化保持够用，高级扩展按真实需求延后。
