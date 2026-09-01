# KFlow Human Interface Demo 项目

本文记录 Human Interface 人工验证项目的位置、维护边界和可复制的 Graph Diff Demo 教程。后续收到“更新 Demo”任务时，应先阅读本文。

## 与 README Quickstart 的分工

README Quickstart 面向第一次接触 KFlow 的用户。`scripts/create_readme_quickstart.py` 只生成六个普通文件，用户或 Agent 再亲手执行 `init`、`add-node`、`derive` 和逐 Node `confirm`，主要学习 Node、Derivation、Confirmation 与影响传播。

本文的完整 Demo 面向 Human Interface 开发和高级人工验收。它会自动构造多个 Git 结构提交、Graph Diff 基线和有意保留的未提交变化，以覆盖 Added / Removed / Changed Node 与 Derivation。它不替代基础 Quickstart，也不需要随普通 README 修改自动重构。

## 默认位置与维护边界

Demo 默认位于 KFlow 仓库外：

```text
../KFlow-human-interface-demo
```

Demo 不进入 KFlow 仓库，不由 KFlow CI 管理，也不作为自动化测试夹具。普通未登记文件可以存在于 Demo 中，但不得自动进入项目图。

Demo 不随每次功能开发自动维护。只有项目负责人明确要求时才更新 Demo 和本教程，以避免它成为第二套产品实现。

## Demo 的有意 Git 状态

Graph Diff 默认比较“当前工作区”与 Git `HEAD`，也可选择更早的结构提交。因此此 Demo 的正确最终状态不是干净工作区：

- Git 历史至少包含两个完整、有效的 KFlow 结构提交；
- `HEAD` 是较新的已提交基线图；
- 当前工作区故意保留未提交的 `.kflow` 结构变化和新增文件；
- 启动 UI 前不要提交这些变化，否则 `Graph Diff vs HEAD` 会变为空结果；
- `notes/personal-note.md` 已提交但未登记，因而不会进入项目图。

`topology_changed` 只比较前后两个稳定拓扑顺序。界面相应显示 `Topological order changed.` 或 `Topological order unchanged.`，这不等同于“所有边结构是否发生变化”。

## 图结构与差异覆盖

基线保留六个主要 Node：

```text
requirements + constraints → architecture
architecture + requirements → api-design + api-legacy-notes
architecture → deployment-plan + testing-plan
api-design → legacy-reference
```

当前工作区仍覆盖：

- N-to-1：`requirements + constraints → system-architecture`；
- N-to-M：`system-architecture + constraints → api-design + api-release-notes`；
- 1-to-N：`system-architecture → deployment-plan + testing-plan`；
- 1-to-1：`deployment-plan → operations-guide`；
- 未登记文件：`notes/personal-note.md`。

当前未提交变化相对 `HEAD` 用于验证全部六类 Graph Diff：

- Added Node：`api-release-notes`、`operations-guide`；
- Removed Node：`api-legacy-notes`、`legacy-reference`；
- Changed Node：稳定 ID 的 `architecture` 改名为 `system-architecture`，文件从 `docs/architecture.md` 改为 `docs/architecture.svg` 与 `docs/system-architecture.md`；
- Added Derivation：`deployment-plan → operations-guide`；
- Removed Derivation：`api-design → legacy-reference`；
- Changed Derivation：API Derivation 的 `short`、`detail`、inputs 和 outputs 都变化；稳定 role 展示字段修改，另有新增及删除 role。

Node 改名还会让引用它的 Derivation role 名称随公共图结构一起变化，因此实际 Changed Derivation 数量为 3。这是预期的公开结构差异，不是重复关系。

## 一次性构造脚本

仓库中的 `scripts/setup_graph_diff_demo.py` 只用于创建外部 Demo，不属于生产运行路径。它复用 `KnowledgeGraph`、storage、confirm、validate、Git History 和 Graph Diff 公共实现，不复制领域校验，也不增加编辑或删除类 CLI 命令。

从 KFlow 仓库根目录运行：

```powershell
$demoRoot = Join-Path (Split-Path (Get-Location).Path -Parent) "KFlow-human-interface-demo"
if (Test-Path -LiteralPath $demoRoot) {
    throw "Demo already exists; inspect and rename it before rebuilding: $demoRoot"
}

python scripts/setup_graph_diff_demo.py $demoRoot
```

若 `python` 不是项目使用的 Python 3.11+ 解释器，请用实际解释器路径替换它。脚本拒绝覆盖已存在的目标目录；需要重建时，先确认它确实是 KFlow Demo，再把旧目录改名备份。脚本会：

1. 创建并验证较早的 `initial graph history` 图；
2. 确认全部 Node 并提交第一个结构版本；
3. 写入、确认并提交 `graph diff demo HEAD baseline`；
4. 使用同一套领域模型写入当前合法图；
5. 精确移除只属于 HEAD 基线的事实；
6. 对 HEAD Diff summary、具体 Node / Derivation ID、未登记文件和非干净工作区做精确断言；
7. 验证 History 至少能提供较早结构提交，且选择它会得到另一个有效、不同的 Diff；
8. 输出 HEAD、history、HEAD diff、较早 commit diff 和 `git status --short`，但不提交当前结构变化。

`tests/test_graph_diff_demo.py` 会在临时目录真实调用 `create_demo()`，验证 Git 仓库、两个结构提交、当前图校验、精确差异、history 顺序、未登记文件、非干净状态和拒绝覆盖已有目录。真实外部 Demo 仍不作为 CI fixture。

## 命令行验证

进入 Demo 后使用当前 KFlow 环境运行：

```powershell
Set-Location $demoRoot
kflow validate
kflow overview
git status --short
git log --oneline -- .kflow
```

验收标准：

- `kflow validate` 成功；
- `.kflow` 历史至少有两个提交，且按新到旧排列；
- overview 中存在当前 8 个 Node 和 4 个 Derivation；
- `git status --short` 显示与 Added / Removed / Changed 结构对应的未提交元数据及新增文件；
- overview 的登记文件列表不包含 `notes/personal-note.md`；
- Graph Diff 六类计数依次为 Node `2 / 2 / 1`、Derivation `1 / 1 / 3`；
- Topological order 状态为 changed。

可以用以下 PowerShell 检查未登记文件：

```powershell
$overview = kflow overview --json | ConvertFrom-Json
$registeredFiles = @($overview.nodes | ForEach-Object { $_.files })
if ($registeredFiles -contains "notes/personal-note.md") {
    throw "Unregistered file unexpectedly entered the graph"
}
```

## Human Interface 验证

启动正式打包界面：

```powershell
kflow ui start
```

在 Graph Diff 面板中人工检查：

- selector 至少包含 `HEAD` 和一个更早结构提交，每项显示 short SHA、subject 与 committed time；
- HEAD 短 SHA 和 subject 与 `git log -1` 一致；
- 切换更早 commit 后标题和 Diff 正确变化，但主画布、Inspector、Review Order、Search 与文件 Open 不重新加载或消失；
- 快速切换 commit 后结果保持在最后选择；切回 HEAD 正常；
- Added、Changed Node 和 Derivation 可定位当前画布；Removed 项不可选择当前画布；
- Changed Node 显示名称的旧值 → 新值，并用 `-` / `+` 显示文件集合差异；
- Changed Derivation 显示 short/detail 的旧值 → 新值；
- inputs 和 outputs 分别显示 role 的 Added、Removed 和按 Node 对齐的 Changed 字段；
- 文案为 `Topological order changed.`；
- Search、Review Order、Inspector 和登记文件 Open 仍正常；
- `notes/personal-note.md` 不出现在图中。

在 1366 × 768 与 1920 × 1080 下确认主画布不再保留明显多余纵向空间，右侧面板可滚动且 React Flow Controls 可用。现有搜索、选择、清除选择和手动缩放引起的 fit view、缩放和平移重置行为是已接受现状；本阶段不验证 viewport persistence。

结束服务使用 `Ctrl+C`。不要在验收结束后顺手提交 Demo 当前变化；未提交状态正是这个 Graph Diff Demo 的设计要求。
