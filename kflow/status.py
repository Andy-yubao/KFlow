"""Status propagation logic — yellow, red, and green cascade."""
from collections import deque
from kflow.models import Index


def propagate_yellow(index: Index, start_node_id: str) -> set[str]:
    """Mark all downstream nodes yellow. start_node_id itself is NOT changed."""
    affected: set[str] = set()
    queue: deque[str] = deque()

    node = index.nodes.get(start_node_id)
    if node is None:
        return affected

    for dv_id in node.derivations_as_input:
        dv = index.derivations.get(dv_id)
        if dv is None:
            continue
        output_id = dv.output["node"]
        if output_id not in affected:
            queue.append(output_id)

    while queue:
        node_id = queue.popleft()
        if node_id in affected:
            continue
        current = index.nodes.get(node_id)
        if current is None:
            continue
        current.status = "yellow"
        affected.add(node_id)

        for dv_id in current.derivations_as_input:
            dv = index.derivations.get(dv_id)
            if dv is None:
                continue
            output_id = dv.output["node"]
            if output_id not in affected:
                queue.append(output_id)

    return affected


def propagate_red(index: Index, start_node_id: str) -> set[str]:
    """Mark start_node_id and all downstream nodes red."""
    affected: set[str] = set()
    queue: deque[str] = deque([start_node_id])

    while queue:
        node_id = queue.popleft()
        if node_id in affected:
            continue
        current = index.nodes.get(node_id)
        if current is None:
            continue
        current.status = "red"
        affected.add(node_id)

        for dv_id in current.derivations_as_input:
            dv = index.derivations.get(dv_id)
            if dv is None:
                continue
            output_id = dv.output["node"]
            if output_id not in affected:
                queue.append(output_id)

    return affected


def propagate_green_cascade(index: Index, start_node_id: str) -> set[str]:
    """Mark start_node_id and all downstream nodes green. Does NOT check other upstreams."""
    affected: set[str] = set()
    queue: deque[str] = deque([start_node_id])

    while queue:
        node_id = queue.popleft()
        if node_id in affected:
            continue
        current = index.nodes.get(node_id)
        if current is None:
            continue
        current.status = "green"
        affected.add(node_id)

        for dv_id in current.derivations_as_input:
            dv = index.derivations.get(dv_id)
            if dv is None:
                continue
            output_id = dv.output["node"]
            if output_id not in affected:
                queue.append(output_id)

    return affected
