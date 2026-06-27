"""kflow init — initialize a KFlow project."""
import json
from pathlib import Path
from kflow.errors import ProjectAlreadyInitError


def init_project(path: Path) -> None:
    """Initialize .kflow/ directory structure at the given path."""
    kflow_dir = path / ".kflow"
    if kflow_dir.exists():
        raise ProjectAlreadyInitError(str(path.resolve()))

    kflow_dir.mkdir()
    (kflow_dir / "nodes").mkdir()
    (kflow_dir / "derivations").mkdir()

    index = {"nodes": {}, "derivations": {}}
    with open(kflow_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    knowledge_dir = path / "knowledge"
    if not knowledge_dir.exists():
        knowledge_dir.mkdir()
