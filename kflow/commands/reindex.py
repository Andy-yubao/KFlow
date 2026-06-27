"""kflow reindex — rebuild index.json from individual files."""
from pathlib import Path
from kflow.store import reindex


def reindex_project(root: Path) -> dict:
    counts = reindex(root)
    return {"ok": True, "node_count": counts["node_count"], "derivation_count": counts["derivation_count"]}
