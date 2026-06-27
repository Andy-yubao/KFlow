"""Graph operations — BFS traversal, cycle detection, topological sort."""
from collections import deque
from kflow.models import Index


def bfs_upstream(index: Index, target_id: str, max_depth: int | None = None) -> list[str]:
    """BFS upward from target through derivation inputs.

    Returns nodes in topological order: source nodes first, target last.
    """
    visited: dict[str, int] = {}
    edges: list[tuple[str, str]] = []  # (input_id, output_id)
    queue: deque[tuple[str, int]] = deque([(target_id, 0)])

    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited:
            continue
        if max_depth is not None and depth > max_depth:
            continue
        visited[node_id] = depth

        node = index.nodes.get(node_id)
        if node is None:
            continue

        for dv_id in node.derivations_as_output:
            dv = index.derivations.get(dv_id)
            if dv is None:
                continue
            for inp in dv.inputs:
                inp_id = inp["node"]
                edges.append((inp_id, node_id))
                if inp_id not in visited:
                    queue.append((inp_id, depth + 1))

    return toposort_nodes(index, list(visited.keys()))


def bfs_downstream(index: Index, target_id: str, max_depth: int | None = None) -> dict[str, int]:
    """BFS downward from target through derivations.

    Returns dict mapping node_id → depth.
    """
    visited: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(target_id, 0)])

    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited:
            continue
        if max_depth is not None and depth > max_depth:
            continue
        visited[node_id] = depth

        node = index.nodes.get(node_id)
        if node is None:
            continue

        for dv_id in node.derivations_as_input:
            dv = index.derivations.get(dv_id)
            if dv is None:
                continue
            output_id = dv.output["node"]
            if output_id not in visited:
                queue.append((output_id, depth + 1))

    return visited


def has_cycle(index: Index) -> bool:
    """Detect cycles via Kahn's topological sort algorithm."""
    in_degree: dict[str, int] = {nid: 0 for nid in index.nodes}
    adj: dict[str, list[str]] = {nid: [] for nid in index.nodes}

    for dv in index.derivations.values():
        output_id = dv.output["node"]
        for inp in dv.inputs:
            inp_id = inp["node"]
            if inp_id in adj and output_id in adj:
                adj[inp_id].append(output_id)
                in_degree[output_id] = in_degree.get(output_id, 0) + 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    visited_count = 0

    while queue:
        nid = queue.popleft()
        visited_count += 1
        for neighbor in adj.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited_count < len(index.nodes)


def would_create_cycle(index: Index, input_ids: list[str], output_id: str) -> bool:
    """Check if adding edges input_i → output_id would create a cycle."""
    adj: dict[str, list[str]] = {nid: [] for nid in index.nodes}
    for dv in index.derivations.values():
        dv_output = dv.output["node"]
        for inp in dv.inputs:
            inp_id = inp["node"]
            if inp_id in adj and dv_output in adj:
                adj[inp_id].append(dv_output)

    for inp_id in input_ids:
        if inp_id in adj and output_id in adj:
            adj[inp_id].append(output_id)

    visited: set[str] = set()
    stack = [output_id]
    input_set = set(input_ids)

    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        for neighbor in adj.get(nid, []):
            if neighbor in input_set:
                return True
            if neighbor not in visited:
                stack.append(neighbor)

    return False


def toposort_nodes(index: Index, node_ids: list[str]) -> list[str]:
    """Sort node_ids topologically based on derivation edges in index."""
    sub_ids = set(node_ids)
    in_degree: dict[str, int] = {nid: 0 for nid in sub_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in sub_ids}

    for dv in index.derivations.values():
        output_id = dv.output["node"]
        if output_id not in sub_ids:
            continue
        for inp in dv.inputs:
            inp_id = inp["node"]
            if inp_id not in sub_ids:
                continue
            adj[inp_id].append(output_id)
            in_degree[output_id] = in_degree.get(output_id, 0) + 1

    queue: deque[str] = deque(nid for nid in sub_ids if in_degree.get(nid, 0) == 0)
    result: list[str] = []

    while queue:
        nid = queue.popleft()
        result.append(nid)
        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    for nid in sub_ids:
        if nid not in set(result):
            result.append(nid)

    return result
