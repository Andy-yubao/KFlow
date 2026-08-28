# KFlow Human Interface Demo 项目

本文记录 Human Interface 人工验证项目的位置、维护边界和可复制的 Graph Diff Demo 教程。后续收到“更新 Demo”任务时，应先阅读本文。

## 默认位置与维护边界

Demo 默认位于 KFlow 仓库外：

```text
../KFlow-human-interface-demo
```

Demo 不进入 KFlow 仓库，不由 KFlow CI 管理，也不作为自动化测试夹具。普通未登记文件可以存在于 Demo 中，但不得自动进入项目图。

Demo 不随每次功能开发自动维护。只有项目负责人明确要求时才更新 Demo 和本教程，以避免它成为第二套产品实现。

## Demo 的有意 Git 状态

Graph Diff 比较“当前工作区”与固定的 Git `HEAD`。因此此 Demo 的正确最终状态不是干净工作区：

- `HEAD` 是完整、有效且已提交的 KFlow 基线图；
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

当前未提交变化用于验证全部六类 Graph Diff：

- Added Node：`api-release-notes`、`operations-guide`；
- Removed Node：`api-legacy-notes`、`legacy-reference`；
- Changed Node：稳定 ID 的 `architecture` 改名为 `system-architecture`，文件从 `docs/architecture.md` 改为 `docs/architecture.svg` 与 `docs/system-architecture.md`；
- Added Derivation：`deployment-plan → operations-guide`；
- Removed Derivation：`api-design → legacy-reference`；
- Changed Derivation：API Derivation 的 `short`、`detail`、inputs 和 outputs 都变化；稳定 role 展示字段修改，另有新增及删除 role。

Node 改名还会让引用它的 Derivation role 名称随公共图结构一起变化，因此实际 Changed Derivation 数量为 3。这是预期的公开结构差异，不是重复关系。

## 一次性构造脚本

仓库中的 `scripts/setup_graph_diff_demo.py` 只用于创建外部 Demo，不属于生产运行路径。它复用 `KnowledgeGraph`、storage、confirm、validate 和 Graph Diff 公共实现，不复制领域校验，也不增加编辑或删除类 CLI 命令。

从 KFlow 仓库根目录运行：

```powershell
$demoRoot = Join-Path (Split-Path (Get-Location).Path -Parent) "KFlow-human-interface-demo"
if (Test-Path -LiteralPath $demoRoot) {
    throw "Demo already exists; inspect and rename it before rebuilding: $demoRoot"
}

python scripts/setup_graph_diff_demo.py $demoRoot
```

若 `python` 不是项目使用的 Python 3.11+ 解释器，请用实际解释器路径替换它。脚本拒绝覆盖已存在的目标目录；需要重建时，先确认它确实是 KFlow Demo，再把旧目录改名备份。脚本会：

1. 创建并验证基线图；
2. 确认全部基线 Node；
3. 提交 `chore: create graph diff demo baseline`；
4. 使用同一套领域模型写入当前合法图；
5. 精确移除只属于历史基线的事实；
6. 验证并输出完整 Graph Diff JSON，但不提交当前结构变化。

## 命令行验证

进入 Demo 后使用当前 KFlow 环境运行：

```powershell
Set-Location $demoRoot
kflow validate
kflow overview
git status --short
```

验收标准：

- `kflow validate` 成功；
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
kflow ui
```

在 `Graph Diff vs HEAD` 中人工检查：

- HEAD 短 SHA 和 subject 与 `git log -1` 一致；
- Added、Changed Node 和 Derivation 可定位当前画布；Removed 项不可选择当前画布；
- Changed Node 显示名称的旧值 → 新值，并用 `-` / `+` 显示文件集合差异；
- Changed Derivation 显示 short/detail 的旧值 → 新值；
- inputs 和 outputs 分别显示 role 的 Added、Removed 和按 Node 对齐的 Changed 字段；
- 文案为 `Topological order changed.`；
- Search、Review Order、Inspector 和登记文件 Open 仍正常；
- `notes/personal-note.md` 不出现在图中。

结束服务使用 `Ctrl+C`。不要在验收结束后顺手提交 Demo 当前变化；未提交状态正是这个 Graph Diff Demo 的设计要求。
