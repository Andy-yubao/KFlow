# KFlow 实现设计文档

> 版本: 1.0 / 日期: 2026-06-27 / 状态: 实现设计冻结
>
> 本文档是 [2026-06-27-kflow-design.md](./2026-06-27-kflow-design.md) 的实现级补充，
> 记录 brainstorming 中确定的所有工程决策。高层设计以原文为准，本文档细化实现细节。

---

## 1. 项目结构

```
kflow/
├── __init__.py
├── __main__.py              # python -m kflow 入口
├── cli.py                   # argparse 定义（含 derive 自定义 action）
├── models.py                # @dataclass: Node, Derivation, Index, InputSpec, OutputSpec
├── store.py                 # 文件 I/O：读/写分文件、原子写 index.json
├── graph.py                 # BFS 上游/下游、拓扑排序、循环检测
├── status.py                # 状态传播（modify 传播、remove 传播、cascade）
├── errors.py                # KFlowError 异常类 + 错误消息模板
├── output.py                # --json / 人类可读输出的统一格式化
├── commands/
│   ├── __init__.py
│   ├── init.py
│   ├── create.py
│   ├── derive.py
│   ├── modify.py
│   ├── confirm.py
│   ├── remove.py
│   ├── context.py
│   ├── affect.py
│   ├── query.py
│   ├── list_cmd.py          # list 是 Python 保留字
│   ├── validate.py
│   └── reindex.py
└── interactive.py           # derive 交互式模式

tests/
├── conftest.py              # tmp_kflow fixture
├── test_models.py
├── test_store.py
├── test_graph.py
├── test_status.py
├── test_cli_*.py            # 每条命令一个测试文件
├── test_errors.py
└── test_json_output.py
```

---

## 2. 数据模型（dataclasses）

所有模型使用 Python 标准库 `dataclasses`。`asdict()` 直接序列化为 JSON，
反序列化用 `Node(**d)` 展开。

### 2.1 Node

```python
from dataclasses import dataclass, field

@dataclass
class Node:
    id: str                                    # "nd_a1b2c3"
    name: str                                  # "architecture"
    file: str | None                           # "knowledge/architecture.md" 或 None
    status: str                                # "green" | "yellow" | "red"
    derivations_as_input: list[str] = field(default_factory=list)
    derivations_as_output: list[str] = field(default_factory=list)
```

### 2.2 Derivation

```python
@dataclass
class InputSpec:
    node: str            # 节点 ID
    role: str            # 短角色
    role_detail: str     # 详角色

@dataclass
class OutputSpec:
    node: str            # 输出节点 ID
    method: str          # 短方法
    method_detail: str   # 详方法

@dataclass
class Derivation:
    id: str              # "dv_d4e5f6"
    summary: str
    inputs: list[InputSpec]
    output: OutputSpec
```

### 2.3 Index（聚合索引）

```python
@dataclass
class IndexNode:
    """index.json 中的精简 Node 视图"""
    name: str
    file: str | None
    status: str
    derivations_as_input: list[str]
    derivations_as_output: list[str]

@dataclass
class IndexDerivation:
    """index.json 中的精简 Derivation 视图（无 detail 字段）"""
    summary: str
    inputs: list[dict]   # [{"node": "...", "role": "..."}]
    output: dict         # {"node": "...", "method": "..."}

@dataclass
class Index:
    nodes: dict[str, IndexNode]
    derivations: dict[str, IndexDerivation]
```

### 2.4 序列化映射

| 模型 | 文件位置 | 序列化方式 |
|------|---------|-----------|
| `Node` | `.kflow/nodes/<id>.json` | `asdict(node)` |
| `Derivation` | `.kflow/derivations/<id>.json` | `asdict(derivation)` |
| `Index` | `.kflow/index.json` | 手写 `to_dict(index)`（嵌套 `IndexNode`/`IndexDerivation`） |

---

## 3. ID 生成

```python
import secrets

def generate_id(prefix: str) -> str:
    """生成 6 位小写十六进制 ID。
    
    Args:
        prefix: "nd" 或 "dv"
    Returns:
        例如 "nd_a1b2c3" 或 "dv_d4e5f6"
    """
    return f"{prefix}_{secrets.token_hex(3)}"

def generate_unique_id(prefix: str, existing: set[str]) -> str:
    """生成不与已有 ID 冲突的新 ID。碰撞时重试。"""
    while True:
        new_id = generate_id(prefix)
        if new_id not in existing:
            return new_id
```

16^6 = 16,777,216 空间。`secrets.token_hex()` 用于密码学级随机性，非 `random` 模块。

---

## 4. 存储层

### 4.1 原子写 index.json

```
写操作流程：
  1. 修改分文件 (nodes/<id>.json 或 derivations/<id>.json)
  2. 更新内存中的 Index 结构
  3. json.dump(index) → .kflow/.index.tmp
  4. os.replace(.index.tmp, .kflow/index.json)  ← 原子重命名

崩溃恢复：
  - 若 .kflow/.index.tmp 残留（上次写入中断），忽略该文件
  - index.json 始终是上一个完整状态
  - 最坏情况：分文件已更新但 index 未更新 → 不一致
    → validate 检测到，reindex 修复
```

### 4.2 "每次 mutation 整体重写" 的明确含义

每次写命令（`create` `derive` `modify` `confirm` `remove`）执行后，
**整个 `index.json` 从头序列化写入**，不做原地局部修改。

为何：`index.json` 是冗余缓存（真相源在分文件），整体重写消除局部 patch 的不一致风险。
性能：几百节点的 JSON 序列化在毫秒级，不是瓶颈。

### 4.3 读取流程

```
读命令启动：
  1. 检查 .kflow/ 存在，否则 ProjectNotInitError
  2. 若 .kflow/.index.tmp 存在：忽略（上次写入残留）
  3. 读取 .kflow/index.json
  4. 若文件缺失或 JSON 解析失败：自动触发 reindex，然后继续
  5. 按需从分文件加载详情（role_detail, method_detail）
```

### 4.4 节点命名规则

- 允许任何文件系统合法字符（禁止 `<>:"/\|?*`）
- 长度 ≤ 255
- 不做大小写规范化（`Architecture` 和 `architecture` 是不同的知识）
- 重复检查：`create` 和 `derive --output` 时在 index 中查重

---

## 5. CLI 设计

### 5.1 整体结构

```python
# cli.py
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kflow")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # 每个命令由 commands/ 下对应模块注册
    register_init(sub)
    register_create(sub)
    register_derive(sub)
    # ...
    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        dispatch(args)
    except KFlowError as e:
        handle_error(e, json_output=getattr(args, 'json', False))
```

### 5.2 `derive` 参数解析（自定义 action）

```python
class DeriveInputAction(argparse.Action):
    """收集 --input <name> --role <短> --role-detail <详> 三元组。
    
    用法示例：
      kflow derive --input arch --role "框架" --role-detail "..." \
                   --input exp  --role "参数" --role-detail "..." \
                   --output factbase --method "组织" --method-detail "..." \
                   --summary "构建事实库"
    """
    def __call__(self, parser, namespace, values, option_string=None):
        inputs = getattr(namespace, 'inputs', None) or []
        # 当 --input 出现时，结束上一个三元组，开始新的
        if not hasattr(namespace, '_derive_current_input'):
            namespace._derive_current_input = {}
        else:
            # 上一个三元组完成，存入列表
            prev = namespace._derive_current_input
            if prev:
                inputs.append(prev)
                namespace._derive_current_input = {}
        namespace._derive_current_input['node'] = values
        namespace.inputs = inputs

class DeriveRoleAction(argparse.Action):
    """--role 填入当前三元组"""
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, '_derive_current_input'):
            raise argparse.ArgumentError(self, "--role must follow --input")
        namespace._derive_current_input['role'] = values

class DeriveRoleDetailAction(argparse.Action):
    """--role-detail 填入当前三元组"""
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, '_derive_current_input'):
            raise argparse.ArgumentError(self, "--role-detail must follow --input")
        namespace._derive_current_input['role_detail'] = values
```

### 5.3 交互式模式（derive 无参数时触发）

```
$ kflow derive
Output node name: factbase
Method (short): 依据模型组织实验数据
Method detail: 以模型定义的框架为行...
Input #1 name: architecture
Input #1 role (short): 提供预测框架
Input #1 role detail: 模型定义了参数空间和优化目标...
Add another input? [y/N]: y
Input #2 name: experiment
Input #2 role (short): 提供参数
Input #2 role detail: 实验数据通过参数拟合将模型实例化...
Add another input? [y/N]: n
Summary: 构建事实库

Created derivation dv_d4e5f6 → factbase (nd_m3n4o5)
```

---

## 6. 错误处理

### 6.1 异常层次

```python
class KFlowError(Exception):
    """所有 KFlow 错误的基类"""
    exit_code: int = 1
    message: str

class NodeExistsError(KFlowError):
    """节点 name 重复"""
    exit_code = 1

class NodeNotFoundError(KFlowError):
    """节点不存在"""

class DerivationBlockedError(KFlowError):
    """删除被依赖节点时拒绝，列出下游"""

class ProjectAlreadyInitError(KFlowError):
    """.kflow/ 已存在时再次 init"""

class ProjectNotInitError(KFlowError):
    """.kflow/ 不存在时执行非 init 命令"""

class CyclicError(KFlowError):
    """derive 时检测到将形成环"""

class ValidationError(KFlowError):
    """输入参数不合法（如 name 含非法字符）"""
```

### 6.2 错误输出

```python
def handle_error(e: KFlowError, json_output: bool = False):
    if json_output:
        print(json.dumps({
            "ok": False,
            "error": str(e),
            "type": type(e).__name__
        }))
    else:
        print(f"Error: {e}", file=sys.stderr)
    sys.exit(e.exit_code)
```

### 6.3 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 预期错误（重名、缺失、环、被依赖等业务逻辑错误） |
| 2 | 意外错误（文件系统错误、JSON 解析失败等） |

---

## 7. JSON 输出

所有命令通过 `--json` 标志输出结构化 JSON，供 AI/MCP 消费。
无信封格式，裸数据。错误走 stderr + 非零退出码。

### 7.1 各命令 JSON schema

**写命令（create / derive / modify / confirm / remove）：**
```json
{
  "ok": true,
  "node": { "id": "nd_a1b2c3", "name": "architecture", "status": "green", "file": "knowledge/architecture.md" },
  "affected": ["nd_b4c5d6", "nd_e7f8g9"]
}
```
`affected` 列出所有被状态传播影响的节点 ID（modify: 染黄的节点; remove: 染红的节点; confirm --cascade: 变绿的节点）。

**list：**
```json
[
  { "id": "nd_a1b2c3", "name": "architecture", "status": "green", "file": "knowledge/architecture.md" },
  { "id": "nd_d4e5f6", "name": "experiment", "status": "green", "file": "knowledge/experiment.md" }
]
```

**context：**
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
          {"node": "nd_j1k2l3", "role": "提供参数"}
        ]
      }
    }
  ]
}
```
拓扑序排列：源节点在前，目标在最后。

**affect：**
```json
{
  "target": "nd_a1b2c3",
  "nodes": [
    { "id": "nd_a1b2c3", "name": "architecture", "status": "green", "depth": 0 },
    { "id": "nd_m3n4o5", "name": "factbase", "status": "green", "depth": 1 },
    { "id": "nd_x1y2z3", "name": "release_plan", "status": "yellow", "depth": 2 }
  ]
}
```

**query：**
```json
{
  "q": "factbase",
  "nodes": [
    { "id": "nd_m3n4o5", "name": "factbase", "status": "green", "file": "knowledge/factbase.md" }
  ],
  "derivations": [
    {
      "id": "dv_d4e5f6",
      "summary": "构建事实库",
      "inputs": ["nd_a1b2c3", "nd_j1k2l3"],
      "output": "nd_m3n4o5"
    }
  ]
}
```

**validate：**
```json
{
  "ok": true,
  "issues": [
    { "check": "dangling_reference", "severity": "error", "message": "Node nd_abc123 references missing derivation dv_xyz789" },
    { "check": "orphan_node", "severity": "warning", "message": "Node nd_def456 has no input or output derivations" }
  ]
}
```

**reindex：**
```json
{
  "ok": true,
  "node_count": 5,
  "derivation_count": 3
}
```

---

## 8. 图操作

### 8.1 BFS 上游（context）

```
输入: target_node_id, max_depth (None = 无限)
输出: 拓扑序排列的节点列表（源节点在前）

算法:
  queue = deque([(target_node_id, 0)])
  visited = {}  # node_id → depth
  edges = []    # (input_node, output_node, derivation_id)

  while queue:
    node_id, depth = queue.popleft()
    if node_id in visited: continue
    if max_depth and depth > max_depth: continue
    visited[node_id] = depth

    # 找产出此节点的 Derivation
    node = index.nodes[node_id]
    for dv_id in node.derivations_as_output:
        dv = index.derivations[dv_id]
        for inp in dv.inputs:
            edges.append((inp["node"], node_id, dv_id))
            queue.append((inp["node"], depth + 1))

  # 拓扑排序 visited 中的节点（按 edges 依赖关系）
  return toposort(list(visited.keys()), edges)
```

### 8.2 BFS 下游（affect + 状态传播）

```
输入: target_node_id, max_depth (None = 无限)
输出: 按距离排序的节点列表

算法:
  queue = deque([(target_node_id, 0)])
  visited = {}  # node_id → depth

  while queue:
    node_id, depth = queue.popleft()
    if node_id in visited: continue
    if max_depth and depth > max_depth: continue
    visited[node_id] = depth

    node = index.nodes[node_id]
    for dv_id in node.derivations_as_input:
        dv = index.derivations[dv_id]
        output_id = dv.output["node"]
        queue.append((output_id, depth + 1))

  return visited
```

### 8.3 循环检测

**derive 前置检测：**

```
输入: inputs (列表), output_id (新输出节点)
输出: bool (是否会形成环)

构建临时边集 = 现有 Derivation 边集 + 新边 {input_i → output_id}
从 output_id DFS，检查能否到达任何 input_i
若可达 → 会形成环 → 拒绝
```

**validate 中 Kahn 拓扑排序检测：**

```
输入: 所有节点 + Derivation
输出: 是否存在环 + 拓扑序

入度 = {node_id: 0}
for dv in derivations:
    for inp in dv.inputs:
        edges[inp.node].append(dv.output.node)
        入度[dv.output.node] += 1

queue = [n for n, d in 入度.items() if d == 0]
while queue:
    n = queue.pop()
    排序结果.append(n)
    for m in edges[n]:
        入度[m] -= 1
        if 入度[m] == 0: queue.append(m)

if len(排序结果) < len(nodes): 存在环
```

---

## 9. 状态传播

### 9.1 状态机

```
create ──→ green
derive 的输出 ──→ green
modify 目标 ──→ green；下游 ──→ yellow（全传播）
remove --force ──→ 目标删除；下游 ──→ red（全传播）
confirm ──→ green（仅自身）
confirm --cascade ──→ green（自身 + 整条下游链，不检查其他上游颜色）
```

### 9.2 红传播的实现

```python
def propagate_red(index: Index, start_node_id: str) -> set[str]:
    """从 start_node_id 出发，沿下游 BFS，所有节点染红。
    返回被染红的节点 ID 集合（不含原始被删除的节点）。
    """
    affected = set()
    queue = deque([start_node_id])
    
    while queue:
        node_id = queue.popleft()
        node = index.nodes[node_id]
        node.status = "red"
        affected.add(node_id)
        
        for dv_id in node.derivations_as_input:
            dv = index.derivations[dv_id]
            output_id = dv.output["node"]
            if output_id not in affected:
                queue.append(output_id)
    
    return affected

def remove_node_with_propagation(index: Index, node_id: str) -> set[str]:
    """删除节点及其相关 Derivation，传播红色。
    
    操作顺序：
    1. 收集上游 Derivation（derivations_as_output）
    2. 对每个下游 Derivation（derivations_as_input）：
       - 获取 output 节点
       - 对该 output 节点执行 propagate_red()
    3. 删除节点和所有相关 Derivation
    """
    node = index.nodes[node_id]
    affected = set()
    
    # 删除产出此节点的 Derivation（如果不是源节点）
    for dv_id in node.derivations_as_output:
        del index.derivations[dv_id]
    
    # 对每个下游 Derivation，output 节点染红并传播
    for dv_id in node.derivations_as_input.copy():
        dv = index.derivations[dv_id]
        output_id = dv.output["node"]
        red_nodes = propagate_red(index, output_id)
        affected.update(red_nodes)
        del index.derivations[dv_id]
    
    del index.nodes[node_id]
    return affected
```

### 9.3 黄传播的实现

```python
def propagate_yellow(index: Index, start_node_id: str) -> set[str]:
    """从 start_node_id 出发，沿下游 BFS，所有节点染黄。
    start_node_id 自身不变（已在 modify 中设为 green）。
    """
    affected = set()
    queue = deque()
    
    # 从 start_node_id 的直接下游开始
    node = index.nodes[start_node_id]
    for dv_id in node.derivations_as_input:
        dv = index.derivations[dv_id]
        output_id = dv.output["node"]
        queue.append(output_id)
    
    while queue:
        node_id = queue.popleft()
        if node_id in affected:
            continue
        node = index.nodes[node_id]
        node.status = "yellow"
        affected.add(node_id)
        
        for dv_id in node.derivations_as_input:
            dv = index.derivations[dv_id]
            output_id = dv.output["node"]
            if output_id not in affected:
                queue.append(output_id)
    
    return affected
```

### 9.4 cascade 绿色的实现

```python
def propagate_green_cascade(index: Index, start_node_id: str) -> set[str]:
    """沿下游 BFS，所有节点染绿。不检查其他上游颜色。"""
    index.nodes[start_node_id].status = "green"
    affected = {start_node_id}
    queue = deque([start_node_id])
    
    while queue:
        node_id = queue.popleft()
        node = index.nodes[node_id]
        
        for dv_id in node.derivations_as_input:
            dv = index.derivations[dv_id]
            output_id = dv.output["node"]
            if output_id not in affected:
                index.nodes[output_id].status = "green"
                affected.add(output_id)
                queue.append(output_id)
    
    return affected
```

---

## 10. 测试策略

### 10.1 覆盖目标

| 层级 | 覆盖内容 | 占总测试比例 |
|------|---------|------------|
| 单元测试 | models, graph, store, status（纯逻辑） | ~50% |
| 集成测试 | 每条命令的正常路径 + 错误分支 | ~40% |
| JSON 输出 | --json 格式验证 | ~10% |

### 10.2 关键测试场景

**状态传播：**
```
- modify → yellow 单链传播
- modify → yellow 分支传播（一个节点有多个下游）
- remove → red 单链传播
- remove → red 分支传播
- confirm --cascade 分支图
- 红节点 confirm 后下游不自动恢复
- red 的三级传播（A→B→C→D，remove A → 全部红）
```

**图操作：**
```
- BFS 上游，达到 max_depth
- BFS 下游，达到 max_depth
- 源节点的 context（返回自身）
- 叶节点的 affect（空下游）
- 循环检测：菱形图（不应误报）
- 循环检测：真正有环（应检出）
```

**边界：**
```
- 空项目（0 节点）的 list/query/validate/reindex
- 节点名含中文/空格/特殊字符
- index.json 损坏时自动 reindex
- --no-file 节点的行为
```

---

## 11. 技术栈与依赖

| 项 | 选择 |
|----|------|
| Python 版本 | 3.11+ |
| 外部依赖（生产） | **零** |
| 外部依赖（开发） | pytest |
| 打包 | pyproject.toml + `[project.scripts]` entry point `kflow` |
| 代码格式化 | ruff |
| CI | `pip install -e ".[dev]" && pytest` |

---

## 12. 与设计文档的关系

| 设计文档（原） | 本文档（补充） |
|--------------|-------------|
| 高层架构、存储模型、命令行为 | 实现级细节、代码结构、算法伪代码 |
| MVP 范围定义 | 具体工程决策 |
| 概念术语 | 变量名、类名、JSON schema |

若两文档冲突，以本文档为准（brainstorming 后的最新决策）。
