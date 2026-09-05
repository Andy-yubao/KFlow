"""Core behavior of explicit downstream confirmation (``confirm_downstream``)."""

from __future__ import annotations

import json
import shutil
from importlib import import_module

import pytest

from kflow.core.graph import GraphValidationError, KnowledgeGraph, ValidationIssue
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_review_order
from kflow.core.scan import (
    DownstreamConfirmationError,
    DownstreamConfirmationResult,
    confirm,
    confirm_downstream,
    scan,
)
from kflow.core.storage import (
    StorageError,
    initialize_project,
    load_confirmations,
    save_derivation,
    save_graph,
)

scan_module = import_module("kflow.core.scan")


def build_project(
    root,
    nodes: tuple[str, ...],
    derivations: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...],
    *,
    confirm_all: bool = False,
) -> KnowledgeGraph:
    """Write files and canonical facts for an explicit test topology."""
    for name in nodes:
        path = root / "docs" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    initialize_project(root)
    node_objects = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",)) for name in nodes
    )
    derivation_objects = tuple(
        Derivation(
            f"dv_{index:02d}",
            derivation_name,
            f"Derive {derivation_name}",
            "",
            tuple(
                DerivationInput(f"nd_{item}", f"input {item}", "") for item in inputs
            ),
            tuple(
                DerivationOutput(f"nd_{item}", f"output {item}", "") for item in outputs
            ),
        )
        for index, (derivation_name, inputs, outputs) in enumerate(derivations)
    )
    graph = KnowledgeGraph.build(node_objects, derivation_objects)
    save_graph(root, graph)
    if confirm_all:
        for node_id in graph.topological_order():
            confirm(root, node_id)
    return graph


def change_file(root, name: str, content: str) -> None:
    (root / "docs" / f"{name}.md").write_text(content, encoding="utf-8")


def confirmation_bytes(root) -> dict[str, bytes]:
    return {
        path.stem: path.read_bytes()
        for path in (root / ".kflow" / "confirmations").glob("*.json")
    }


def assert_current(root, *node_names: str) -> None:
    statuses = scan(root).statuses
    for name in node_names:
        assert statuses[f"nd_{name}"].reasons == ()
        assert statuses[f"nd_{name}"].needs_review is False


def test_plain_confirm_still_writes_exactly_one_confirmation(tmp_path) -> None:
    """Ordinary confirm never cascades to siblings or downstream (regression)."""
    graph = build_project(
        tmp_path,
        ("a", "b", "c"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    before = confirmation_bytes(tmp_path)

    before_status, after_status = confirm(tmp_path, "a")

    assert after_status.reasons == ()
    assert set(load_confirmations(tmp_path)) == set(graph.nodes)
    assert confirmation_bytes(tmp_path)["nd_a"] != before["nd_a"]
    assert confirmation_bytes(tmp_path)["nd_b"] == before["nd_b"]
    assert confirmation_bytes(tmp_path)["nd_c"] == before["nd_c"]
    assert scan(tmp_path).statuses["nd_b"].reasons == ("input_changed",)
    assert before_status.needs_review is True


def test_downstream_clears_every_needs_review_node_in_topological_order(
    tmp_path,
) -> None:
    graph = build_project(
        tmp_path,
        ("a", "b", "c", "d", "e", "z"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c-d", ("b",), ("c", "d")),
            ("d-to-e", ("d",), ("e",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    scope_ids = {node_id for node_id in graph.topological_order() if node_id != "nd_z"}

    result = confirm_downstream(tmp_path, "a")

    assert isinstance(result, DownstreamConfirmationResult)
    expected = tuple(
        node_id for node_id in graph.topological_order() if node_id in scope_ids
    )
    assert result.root == "nd_a"
    assert result.confirmed == expected
    assert result.remaining == ()
    assert result.skipped_current == ()
    assert_current(tmp_path, "a", "b", "c", "d", "e", "z")
    assert query_review_order(tmp_path, "a")["review_order"] == []


def test_downstream_with_current_root_skips_root_and_confirms_affected(
    tmp_path,
) -> None:
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "b", "b changed")
    written: list[str] = []

    real_save = scan_module.save_confirmation

    def spy(root, confirmation) -> None:
        written.append(confirmation.node)
        return real_save(root, confirmation)

    scan_module.save_confirmation = spy
    try:
        result = confirm_downstream(tmp_path, "a")
    finally:
        scan_module.save_confirmation = real_save

    assert result.confirmed == ("nd_b", "nd_c")
    assert result.skipped_current == ("nd_a",)
    assert "nd_a" not in written
    assert_current(tmp_path, "a", "b", "c")
    assert query_review_order(tmp_path, "a")["review_order"] == []


def test_downstream_mixed_scope_confirms_only_affected_without_rewriting_current(
    tmp_path,
) -> None:
    build_project(
        tmp_path,
        ("a", "b", "c", "d"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
            ("c-to-d", ("c",), ("d",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "c", "c changed")
    before = confirmation_bytes(tmp_path)
    written: list[str] = []

    real_save = scan_module.save_confirmation

    def spy(root, confirmation) -> None:
        written.append(confirmation.node)
        return real_save(root, confirmation)

    scan_module.save_confirmation = spy
    try:
        result = confirm_downstream(tmp_path, "a")
    finally:
        scan_module.save_confirmation = real_save

    assert result.confirmed == ("nd_c", "nd_d")
    assert result.skipped_current == ("nd_a", "nd_b")
    assert written == ["nd_c", "nd_d"]
    assert confirmation_bytes(tmp_path)["nd_a"] == before["nd_a"]
    assert confirmation_bytes(tmp_path)["nd_b"] == before["nd_b"]
    assert confirmation_bytes(tmp_path)["nd_c"] != before["nd_c"]
    assert_current(tmp_path, "a", "b", "c", "d")


def test_downstream_with_no_review_debt_writes_nothing_and_succeeds(tmp_path) -> None:
    graph = build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    before = confirmation_bytes(tmp_path)
    written: list[str] = []

    real_save = scan_module.save_confirmation

    def spy(root, confirmation) -> None:
        written.append(confirmation.node)
        return real_save(root, confirmation)

    scan_module.save_confirmation = spy
    try:
        result = confirm_downstream(tmp_path, "a")
    finally:
        scan_module.save_confirmation = real_save

    assert result.confirmed == ()
    assert result.remaining == ()
    assert set(result.skipped_current) == set(graph.nodes)
    assert written == []
    assert confirmation_bytes(tmp_path) == before


def test_downstream_never_touches_an_unrelated_review_branch(tmp_path) -> None:
    build_project(
        tmp_path,
        ("a", "b", "x", "y"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("x-to-y", ("x",), ("y",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    change_file(tmp_path, "x", "x changed")
    before = confirmation_bytes(tmp_path)

    result = confirm_downstream(tmp_path, "a")

    assert result.confirmed == ("nd_a", "nd_b")
    assert scan(tmp_path).statuses["nd_x"].needs_review is True
    assert scan(tmp_path).statuses["nd_y"].needs_review is True
    assert confirmation_bytes(tmp_path)["nd_x"] == before["nd_x"]
    assert confirmation_bytes(tmp_path)["nd_y"] == before["nd_y"]
    assert result.remaining == ()
    assert query_review_order(tmp_path, "a")["review_order"] == []


def test_downstream_confirmed_order_matches_stable_topological_order(tmp_path) -> None:
    """N-to-1 and 1-to-N scope honours the stable global topology and boundary."""
    graph = build_project(
        tmp_path,
        ("a", "b", "c", "d", "e"),
        (
            ("combine", ("a", "b"), ("c",)),
            ("split", ("c",), ("d", "e")),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    change_file(tmp_path, "b", "b changed")
    scope_ids = set(graph.downstream("nd_a"))

    result = confirm_downstream(tmp_path, "a")

    expected = tuple(
        node_id for node_id in graph.topological_order() if node_id in scope_ids
    )
    assert result.confirmed == expected
    assert set(result.confirmed) == scope_ids
    assert "nd_b" not in scope_ids
    assert scan(tmp_path).statuses["nd_b"].needs_review is True
    assert_current(tmp_path, "a", "c", "d", "e")


def test_downstream_is_equivalent_to_sequential_single_confirm(tmp_path) -> None:
    """A --downstream run equals confirming each scope Node one at a time."""
    source = tmp_path / "source"
    build_project(
        source,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    change_file(source, "a", "a changed")
    first = tmp_path / "first"
    second = tmp_path / "second"
    shutil.copytree(source, first)
    shutil.copytree(source, second)

    result = confirm_downstream(first, "a")
    for node_id in query_review_order(second, "a")["review_order"]:
        confirm(second, node_id)

    assert result.confirmed == ("nd_a", "nd_b", "nd_c")
    assert confirmation_bytes(first) == confirmation_bytes(second)

    first_scan = scan(first)
    second_scan = scan(second)
    assert set(first_scan.statuses) == set(second_scan.statuses)
    for node_id in first_scan.statuses:
        assert (
            first_scan.statuses[node_id].reasons
            == second_scan.statuses[node_id].reasons
        )
        assert (
            first_scan.effective_versions[node_id]
            == second_scan.effective_versions[node_id]
        )
    assert query_review_order(first) == query_review_order(second)


def test_downstream_refuses_before_writing_on_missing_file(tmp_path) -> None:
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    before = confirmation_bytes(tmp_path)
    (tmp_path / "docs" / "b.md").unlink()

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root == "nd_a"
    assert error.value.failed_node is None
    assert error.value.confirmed == ()
    assert any(issue.code == "missing_file" for issue in error.value.issues)
    assert confirmation_bytes(tmp_path) == before


def test_downstream_refuses_before_writing_on_invalid_graph(tmp_path) -> None:
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    before = confirmation_bytes(tmp_path)
    cycle = Derivation(
        "dv_cycle",
        "cycle-back",
        "Cycle back",
        "",
        (DerivationInput("nd_c", "input c", ""),),
        (DerivationOutput("nd_a", "output a", ""),),
    )
    save_derivation(tmp_path, cycle)

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root is None
    assert error.value.confirmed == ()
    assert any(issue.code == "cycle" for issue in error.value.issues)
    assert confirmation_bytes(tmp_path) == before


def test_downstream_runtime_failure_is_partial_and_explicit(
    tmp_path, monkeypatch
) -> None:
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    before = confirmation_bytes(tmp_path)

    real_save = scan_module.save_confirmation

    def fail_on_b(root, confirmation) -> None:
        if confirmation.node == "nd_b":
            raise OSError("simulated write failure")
        return real_save(root, confirmation)

    monkeypatch.setattr(scan_module, "save_confirmation", fail_on_b)

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root == "nd_a"
    assert error.value.failed_node == "nd_b"
    assert error.value.confirmed == ("nd_a",)
    assert error.value.issues[0].code == "io_error"
    assert "b" in error.value.issues[0].message
    # Prior write is retained; the failed node and its downstream are untouched.
    assert confirmation_bytes(tmp_path)["nd_a"] != before["nd_a"]
    assert confirmation_bytes(tmp_path)["nd_b"] == before["nd_b"]
    assert confirmation_bytes(tmp_path)["nd_c"] == before["nd_c"]
    assert scan(tmp_path).statuses["nd_b"].needs_review is True


def test_downstream_unknown_reference_is_a_downstream_domain_error(
    tmp_path,
) -> None:
    build_project(
        tmp_path,
        ("a", "b"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "missing")

    assert error.value.root is None
    assert error.value.failed_node is None
    assert error.value.confirmed == ()
    assert error.value.issues[0].code == "unknown_node"
    assert error.value.issues[0].message == "unknown node: missing"


def test_downstream_invalid_metadata_is_a_downstream_domain_error(tmp_path) -> None:
    build_project(
        tmp_path,
        ("a", "b"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )
    (tmp_path / ".kflow" / "project.json").write_text(
        '{"kind": "broken", "schema_version": 3}', encoding="utf-8"
    )

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root is None
    assert error.value.failed_node is None
    assert error.value.confirmed == ()
    assert error.value.issues[0].code == "invalid_project"


def test_downstream_malformed_node_missing_name_is_invalid_project(tmp_path) -> None:
    """A decode-stage bare KeyError stays on v1 as invalid_project."""
    build_project(
        tmp_path,
        ("a", "b"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )
    node = tmp_path / ".kflow" / "nodes" / "nd_a.json"
    value = json.loads(node.read_text(encoding="utf-8"))
    del value["name"]
    node.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root is None
    assert error.value.failed_node is None
    assert error.value.confirmed == ()
    assert error.value.issues[0].code == "invalid_project"
    assert error.value.issues[0].message == "name"


def test_downstream_malformed_node_field_type_is_invalid_project(tmp_path) -> None:
    """A decode-stage ValueError stays on v1 as invalid_project."""
    build_project(
        tmp_path,
        ("a", "b"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )
    node = tmp_path / ".kflow" / "nodes" / "nd_a.json"
    value = json.loads(node.read_text(encoding="utf-8"))
    value["name"] = 5
    node.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root is None
    assert error.value.failed_node is None
    assert error.value.confirmed == ()
    assert error.value.issues[0].code == "invalid_project"
    assert "node name must be non-empty text" in error.value.issues[0].message


def test_downstream_mid_run_scan_storage_error_is_partial_and_explicit(
    tmp_path, monkeypatch
) -> None:
    """A mid-run scan() throwing still reports a v1 partial failure."""
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    before = confirmation_bytes(tmp_path)

    real_scan = scan_module.scan
    calls = 0

    def corrupt_before_b(root):
        # Scans so far: initial, a-current, a-before, a-after. The next one is
        # the current scan that prepares candidate b.
        nonlocal calls
        calls += 1
        if calls == 5:
            raise StorageError("simulated metadata failure")
        return real_scan(root)

    monkeypatch.setattr(scan_module, "scan", corrupt_before_b)

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root == "nd_a"
    assert error.value.confirmed == ("nd_a",)
    assert error.value.failed_node == "nd_b"
    assert error.value.issues[0].code == "invalid_project"
    # a's write is retained; b and c are never written after the mid-run failure.
    assert confirmation_bytes(tmp_path)["nd_a"] != before["nd_a"]
    assert confirmation_bytes(tmp_path)["nd_b"] == before["nd_b"]
    assert confirmation_bytes(tmp_path)["nd_c"] == before["nd_c"]


def test_downstream_final_scan_error_is_partial_without_a_failed_node(
    tmp_path, monkeypatch
) -> None:
    """A final scan() throwing keeps every write and reports no single failure."""
    build_project(
        tmp_path,
        ("a", "b", "c"),
        (
            ("a-to-b", ("a",), ("b",)),
            ("b-to-c", ("b",), ("c",)),
        ),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")
    before = confirmation_bytes(tmp_path)

    real_scan = scan_module.scan
    calls = 0

    def corrupt_final_verification(root):
        # a, b and c each trigger a current scan plus confirm's before/after scan
        # (9 calls), after the initial scan (1). The 11th is the post-write
        # verification scan.
        nonlocal calls
        calls += 1
        if calls == 11:
            raise GraphValidationError(
                (ValidationIssue("cycle", "simulated graph error"),)
            )
        return real_scan(root)

    monkeypatch.setattr(scan_module, "scan", corrupt_final_verification)

    with pytest.raises(DownstreamConfirmationError) as error:
        confirm_downstream(tmp_path, "a")

    assert error.value.root == "nd_a"
    assert error.value.failed_node is None
    assert error.value.confirmed == ("nd_a", "nd_b", "nd_c")
    assert error.value.issues[0].code == "cycle"
    assert confirmation_bytes(tmp_path)["nd_a"] != before["nd_a"]
    assert confirmation_bytes(tmp_path)["nd_b"] != before["nd_b"]
    assert confirmation_bytes(tmp_path)["nd_c"] != before["nd_c"]


def test_downstream_accepts_exact_node_id_path_and_name_references(tmp_path) -> None:
    build_project(
        tmp_path,
        ("a", "b"),
        (("a-to-b", ("a",), ("b",)),),
        confirm_all=True,
    )
    change_file(tmp_path, "a", "a changed")

    by_name = confirm_downstream(tmp_path, "a")
    change_file(tmp_path, "a", "a changed again")
    by_id = confirm_downstream(tmp_path, "nd_a")
    change_file(tmp_path, "a", "a changed yet again")
    by_path = confirm_downstream(tmp_path, "docs/a.md")

    assert by_name.root == "nd_a"
    assert by_id.root == "nd_a"
    assert by_path.root == "nd_a"
    assert by_name.confirmed == ("nd_a", "nd_b")
    assert by_id.confirmed == ("nd_a", "nd_b")
    assert by_path.confirmed == ("nd_a", "nd_b")
