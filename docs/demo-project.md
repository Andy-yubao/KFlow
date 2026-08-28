# KFlow Human Interface Demo 项目

本文记录 Human Interface 人工验证项目的位置、维护原则和可复制的 PowerShell 教程。后续收到“更新 Demo”任务时，应先阅读本文。

## 默认位置与边界

Demo 默认位于：

```text
../KFlow-human-interface-demo
```

也就是：

```text
<KFlow 仓库父目录>/KFlow-human-interface-demo
```

Demo 不放入 KFlow 仓库，不由 KFlow CI 管理，也不作为自动化测试夹具。它只用于人工验证 Human Interface、Node / Derivation 显示、状态变化、文件打开和典型多端关系。普通未登记文件可以存在于 Demo 中，但不得自动进入项目图。

## 维护原则

> Demo 不需要随每一次功能开发同步更新。只有项目负责人明确要求时才更新 Demo 和试用教程，以避免无意义维护和 token 消耗。

## 默认图结构

教程创建六个 Knowledge Node：

```text
requirements ─┐
              ├─→ architecture ─→ api-design
constraints  ─┘          │
                          └─→ deployment-plan
                              testing-plan
```

它覆盖：

- N-to-1：`requirements + constraints → architecture`；
- 1-to-1：`architecture → api-design`；
- 1-to-N：`architecture → deployment-plan + testing-plan`；
- 未登记文件：`notes/personal-note.md`。

N-to-M 由前端自动化测试覆盖。若要在 Demo 中人工验证 N-to-M，应新建没有 producer 的输出 Node，或用 N-to-M 替换 1-to-N；不能让 `deployment-plan`、`testing-plan` 同时由两个 Derivation 产生。

## 完整 PowerShell 教程

以下命令从 KFlow 仓库根目录执行。它们不会删除已有 Demo；若默认目录已存在，请先人工确认、备份或改用新目录。

### 1. 创建独立项目和文件

```powershell
$kflowRepo = (Get-Location).Path
$demoRoot = Join-Path (Split-Path $kflowRepo -Parent) "KFlow-human-interface-demo"
if (Test-Path -LiteralPath $demoRoot) {
    throw "Demo already exists: $demoRoot"
}

New-Item -ItemType Directory -Path $demoRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $demoRoot "docs") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $demoRoot "notes") | Out-Null
Set-Location $demoRoot

@'
# Requirements

The service must expose project structure locally without editing project files.
'@ | Set-Content -LiteralPath "docs/requirements.md" -Encoding utf8

@'
# Constraints

The service must bind to loopback and keep the Python runtime dependency-free.
'@ | Set-Content -LiteralPath "docs/constraints.md" -Encoding utf8

@'
# Architecture

The application separates domain queries, a local HTTP adapter, and a browser UI.
'@ | Set-Content -LiteralPath "docs/architecture.md" -Encoding utf8

@'
# API Design

The local adapter exposes narrowly scoped JSON endpoints for the Human Interface.
'@ | Set-Content -LiteralPath "docs/api-design.md" -Encoding utf8

@'
# Deployment Plan

The Python package distributes the production frontend assets.
'@ | Set-Content -LiteralPath "docs/deployment-plan.md" -Encoding utf8

@'
# Testing Plan

Automated and manual checks validate the graph, HTTP boundary, and packaged UI.
'@ | Set-Content -LiteralPath "docs/testing-plan.md" -Encoding utf8

@'
# Personal Note

This file intentionally remains outside the KFlow knowledge graph.
'@ | Set-Content -LiteralPath "notes/personal-note.md" -Encoding utf8
```

### 2. 初始化 Git 与 KFlow

```powershell
git init
git config user.name "KFlow Demo"
git config user.email "kflow-demo@example.local"
git add docs/requirements.md
git add docs/constraints.md
git add docs/architecture.md
git add docs/api-design.md
git add docs/deployment-plan.md
git add docs/testing-plan.md
git add notes/personal-note.md
git commit -m "docs: create human interface demo files"

kflow init
kflow add-node requirements --file docs/requirements.md
kflow add-node constraints --file docs/constraints.md
kflow add-node architecture --file docs/architecture.md
kflow add-node api-design --file docs/api-design.md
kflow add-node deployment-plan --file docs/deployment-plan.md
kflow add-node testing-plan --file docs/testing-plan.md
```

不要为 `notes/personal-note.md` 执行 `kflow add-node`。

### 3. 建立 N-to-1、1-to-1 与 1-to-N

```powershell
kflow derive `
  --short "Requirements and constraints shape architecture" `
  --detail "Product goals and operating constraints jointly determine the structure." `
  --input requirements "Provides product goals" `
  --input constraints "Provides operating limits" `
  --output architecture "Defines the system structure"

kflow derive `
  --short "Architecture defines API design" `
  --detail "System boundaries determine the local interface." `
  --input architecture "Provides component boundaries" `
  --output api-design "Defines the local API"

kflow derive `
  --short "Architecture drives delivery plans" `
  --detail "The same architecture informs deployment and testing." `
  --input architecture "Provides runtime and component boundaries" `
  --output deployment-plan "Defines packaging and launch" `
  --output testing-plan "Defines verification coverage"

kflow overview
kflow validate
```

### 4. 建立基线并制造受影响状态

```powershell
kflow scan
kflow confirm requirements
kflow confirm constraints
kflow confirm architecture
kflow confirm api-design
kflow confirm deployment-plan
kflow confirm testing-plan
kflow validate

git add .kflow/project.json
git add .kflow/nodes
git add .kflow/derivations
git add .kflow/confirmations
git commit -m "chore: register demo knowledge graph"

@'

## New Requirement

The project view must expose a stable review order.
'@ | Add-Content -LiteralPath "docs/requirements.md" -Encoding utf8

kflow scan
kflow status
kflow context --affected
kflow review-order
```

### 5. 验证未登记文件与启动界面

```powershell
$overview = kflow overview --json | ConvertFrom-Json
$overview.nodes.files | Should -Not -Contain "notes/personal-note.md"
```

如果当前 PowerShell 没有 Pester 的 `Should`，使用：

```powershell
$registeredFiles = @($overview.nodes | ForEach-Object { $_.files })
if ($registeredFiles -contains "notes/personal-note.md") {
    throw "Unregistered file unexpectedly entered the graph"
}
```

启动正式打包界面：

```powershell
kflow ui
```

人工检查：

- 六个 Knowledge Node 与三个 Derivation 正确显示；
- Derivation 是边上的小连接点，悬停显示 `short`，单击显示完整 Inspector；
- N-to-1、1-to-1、1-to-N 都只有一个 Derivation 中间节点；
- Search、状态筛选、Only needs review 和直接上下游高亮有效；
- Review Order 点击后定位并选中对应 Node；
- Node 的 Open 只能打开已登记且仍位于项目内的普通文件；
- `notes/personal-note.md` 不出现在图中。

结束服务使用 `Ctrl+C`。
