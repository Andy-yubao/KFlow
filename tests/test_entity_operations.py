import json

import pytest

import kflow.core.storage as storage
from kflow.core.operations import (
    add_derivation,
    add_node,
    edit_derivation,
    edit_node,
    remove_derivation,
    remove_node,
)
from kflow.core.scan import confirm, scan
from kflow.core.storage import initialize_project, load_confirmations, load_graph


def _write(root, path: str, content: str | None = None) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or path, encoding="utf-8")


def _project(root):
    for name in ("a", "b", "c", "d", "extra"):
        _write(root, f"docs/{name}.md")
    initialize_project(root)
    nodes = {
        name: add_node(root, name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d")
    }
    first = add_derivation(
        root,
        "a-to-b",
        "A produces B",
        "first detail",
        (("a", "uses A", ""),),
        (("b", "produces B", ""),),
    )
    second = add_derivation(
        root,
        "b-to-c",
        "B produces C",
        "second detail",
        (("b", "uses B", ""),),
        (("c", "produces C", ""),),
    )
    for name in ("a", "b", "c", "d"):
        confirm(root, name)
    return nodes, first, second


def test_node_rename_preserves_id_confirmation_and_propagates_review(tmp_path):
    nodes, _, _ = _project(tmp_path)
    confirmation_path = tmp_path / f".kflow/confirmations/{nodes['b'].id}.json"
    before_confirmation = confirmation_path.read_bytes()

    edited = edit_node(tmp_path, "b", name="renamed-b", files=("docs/b.md",))

    graph = load_graph(tmp_path)
    statuses = scan(tmp_path).statuses
    assert edited.id == nodes["b"].id
    assert graph.nodes[edited.id].name == "renamed-b"
    assert all(node.name != "b" for node in graph.nodes.values())
    assert statuses[edited.id].reasons == ("files_changed",)
    assert statuses[nodes["c"].id].reasons == ("input_changed",)
    assert confirmation_path.read_bytes() == before_confirmation


def test_node_edit_replaces_files_and_rejects_invalid_candidates_atomically(tmp_path):
    nodes, _, _ = _project(tmp_path)
    node_path = tmp_path / f".kflow/nodes/{nodes['d'].id}.json"
    original = node_path.read_bytes()

    edited = edit_node(tmp_path, "d", name="d", files=("docs/d.md", "docs/extra.md"))
    assert edited.files == ("docs/d.md", "docs/extra.md")
    assert edited.id == nodes["d"].id

    valid = node_path.read_bytes()
    with pytest.raises(ValueError, match="multiple node owners"):
        edit_node(tmp_path, "d", name="d", files=("docs/a.md",))
    assert node_path.read_bytes() == valid

    with pytest.raises(ValueError, match="does not exist"):
        edit_node(tmp_path, "d", name="d", files=("docs/missing.md",))
    assert node_path.read_bytes() == valid

    with pytest.raises(ValueError, match="multiple owners"):
        edit_node(tmp_path, "d", name="a", files=("docs/d.md",))
    assert node_path.read_bytes() == valid
    assert original != valid


def test_derivation_name_edit_preserves_id_and_propagates_review(tmp_path):
    nodes, first, _ = _project(tmp_path)
    confirmation_paths = {
        name: tmp_path / f".kflow/confirmations/{nodes[name].id}.json"
        for name in ("b", "c")
    }
    baselines = {name: path.read_bytes() for name, path in confirmation_paths.items()}

    edited = edit_derivation(
        tmp_path,
        "a-to-b",
        name="a-to-renamed-b",
        short="A produces B",
        detail="first detail",
        inputs=(("a", "uses A", ""),),
        outputs=(("b", "produces B", ""),),
    )

    statuses = scan(tmp_path).statuses
    assert edited.id == first.id
    assert edited.name == "a-to-renamed-b"
    assert statuses[nodes["b"].id].reasons == ("derivation_changed",)
    assert statuses[nodes["c"].id].reasons == ("input_changed",)
    assert {
        name: path.read_bytes() for name, path in confirmation_paths.items()
    } == baselines


def test_derivation_edit_is_complete_and_invalid_candidates_do_not_write(tmp_path):
    nodes, first, _ = _project(tmp_path)
    path = tmp_path / f".kflow/derivations/{first.id}.json"

    edited = edit_derivation(
        tmp_path,
        "a-to-b",
        name="a-and-d-to-b",
        short="Updated",
        detail="",
        inputs=(("a", "uses A", ""), ("d", "uses D", "")),
        outputs=(("b", "produces B", ""),),
    )
    assert edited.detail == ""
    assert {item.node for item in edited.inputs} == {nodes["a"].id, nodes["d"].id}
    valid = path.read_bytes()

    with pytest.raises(ValueError, match="multiple owners"):
        edit_derivation(
            tmp_path,
            "a-and-d-to-b",
            name="b-to-c",
            short="duplicate",
            detail="",
            inputs=(("a", "uses A", ""),),
            outputs=(("b", "produces B", ""),),
        )
    assert path.read_bytes() == valid

    with pytest.raises(ValueError, match="cycle"):
        edit_derivation(
            tmp_path,
            "a-and-d-to-b",
            name="cycle",
            short="cycle",
            detail="",
            inputs=(("c", "uses C", ""),),
            outputs=(("b", "produces B", ""),),
        )
    assert path.read_bytes() == valid

    with pytest.raises(ValueError, match="multiple producing"):
        edit_derivation(
            tmp_path,
            "a-and-d-to-b",
            name="second-producer",
            short="producer",
            detail="",
            inputs=(("a", "uses A", ""),),
            outputs=(("c", "produces C", ""),),
        )
    assert path.read_bytes() == valid


def test_node_remove_is_strict_non_cascading_and_deletes_only_its_baseline(tmp_path):
    nodes, first, second = _project(tmp_path)

    with pytest.raises(ValueError) as error:
        remove_node(tmp_path, "b")
    message = str(error.value)
    assert "a-to-b" in message and "b-to-c" in message
    assert load_graph(tmp_path).derivations.keys() == {first.id, second.id}

    body = (tmp_path / "docs/d.md").read_bytes()
    removed = remove_node(tmp_path, "d")
    assert removed.id == nodes["d"].id
    assert nodes["d"].id not in load_graph(tmp_path).nodes
    assert nodes["d"].id not in load_confirmations(tmp_path)
    assert (tmp_path / "docs/d.md").read_bytes() == body
    assert set(load_graph(tmp_path).derivations) == {first.id, second.id}


def test_removing_last_node_is_valid(tmp_path):
    _write(tmp_path, "only.md")
    initialize_project(tmp_path)
    node = add_node(tmp_path, "only", ("only.md",))
    confirm(tmp_path, "only")

    remove_node(tmp_path, "only")

    assert load_graph(tmp_path).nodes == {}
    assert node.id not in load_confirmations(tmp_path)
    assert (tmp_path / "only.md").is_file()


def test_node_remove_restores_confirmation_if_node_staging_fails(tmp_path, monkeypatch):
    _write(tmp_path, "only.md")
    initialize_project(tmp_path)
    node = add_node(tmp_path, "only", ("only.md",))
    confirm(tmp_path, "only")
    real_replace = storage.os.replace

    def fail_node_stage(source, destination):
        if source.name == f"{node.id}.json" and source.parent.name == "nodes":
            raise OSError("simulated node staging failure")
        return real_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", fail_node_stage)
    with pytest.raises(storage.StorageError, match="cannot remove KFlow metadata"):
        remove_node(tmp_path, "only")

    assert load_graph(tmp_path).nodes[node.id] == node
    assert node.id in load_confirmations(tmp_path)


def test_derivation_remove_keeps_nodes_and_confirmations_and_changes_status(tmp_path):
    nodes, first, second = _project(tmp_path)
    baselines = {
        name: (tmp_path / f".kflow/confirmations/{nodes[name].id}.json").read_bytes()
        for name in ("b", "c")
    }

    removed = remove_derivation(tmp_path, "a-to-b")

    graph = load_graph(tmp_path)
    statuses = scan(tmp_path).statuses
    assert removed.id == first.id
    assert set(graph.nodes) == {node.id for node in nodes.values()}
    assert set(graph.derivations) == {second.id}
    assert graph.producer_of(nodes["b"].id) is None
    assert statuses[nodes["b"].id].reasons == ("derivation_changed",)
    assert statuses[nodes["c"].id].reasons == ("input_changed",)
    assert {
        name: (tmp_path / f".kflow/confirmations/{nodes[name].id}.json").read_bytes()
        for name in ("b", "c")
    } == baselines

    with pytest.raises(ValueError, match="unknown Derivation name"):
        remove_derivation(tmp_path, "missing")


def test_schema_v2_and_v3_derivation_without_name_are_rejected(tmp_path):
    initialize_project(tmp_path)
    manifest = tmp_path / ".kflow/project.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["schema_version"] = 2
    manifest.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema version: 2"):
        load_graph(tmp_path)

    value["schema_version"] = 3
    manifest.write_text(json.dumps(value), encoding="utf-8")
    _write(tmp_path, "docs/a.md")
    node = add_node(tmp_path, "a", ("docs/a.md",))
    derivation_path = tmp_path / ".kflow/derivations/dv_invalid.json"
    derivation_path.write_text(
        json.dumps(
            {
                "kind": "derivation",
                "schema_version": 3,
                "id": "dv_invalid",
                "short": "No fallback",
                "detail": "",
                "inputs": [{"node": node.id, "short": "input", "detail": ""}],
                "outputs": [{"node": node.id, "short": "output", "detail": ""}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required field: name"):
        load_graph(tmp_path)


def test_node_add_and_edit_return_and_persist_canonical_file_order(tmp_path):
    for path in ("docs/z.md", "docs/a.md", "docs/m.md"):
        _write(tmp_path, path)
    initialize_project(tmp_path)

    added = add_node(tmp_path, "node", ("docs/z.md", "docs/a.md"))
    assert added.files == ("docs/a.md", "docs/z.md")
    assert load_graph(tmp_path).nodes[added.id].files == ("docs/a.md", "docs/z.md")

    edited = edit_node(tmp_path, "node", name="node", files=("docs/z.md", "docs/m.md"))
    assert edited.files == ("docs/m.md", "docs/z.md")
    assert load_graph(tmp_path).nodes[edited.id].files == ("docs/m.md", "docs/z.md")

    with pytest.raises(ValueError, match="duplicate paths"):
        add_node(tmp_path, "other", ("docs/a.md", "docs/a.md"))
