import pytest
from kflow.errors import (
    KFlowError,
    NodeExistsError,
    NodeNotFoundError,
    DerivationBlockedError,
    ProjectAlreadyInitError,
    ProjectNotInitError,
    CyclicError,
    ValidationError,
    handle_error,
)


def test_kflow_error_default_exit_code():
    e = KFlowError("something went wrong")
    assert e.exit_code == 1
    assert str(e) == "something went wrong"


def test_node_exists_error():
    e = NodeExistsError("architecture")
    assert "architecture" in str(e)
    assert e.exit_code == 1


def test_node_not_found_error():
    e = NodeNotFoundError("unknown")
    assert "unknown" in str(e)


def test_derivation_blocked_error_lists_downstream():
    e = DerivationBlockedError("nd_a", ["nd_b", "nd_c"])
    assert "nd_a" in str(e)
    assert "nd_b" in str(e)
    assert "nd_c" in str(e)


def test_project_already_init_error():
    e = ProjectAlreadyInitError("/some/path")
    assert "/some/path" in str(e)


def test_project_not_init_error():
    e = ProjectNotInitError()
    assert "init" in str(e).lower()


def test_cyclic_error():
    e = CyclicError("nd_a → nd_b → nd_a")
    assert "cycle" in str(e).lower()


def test_validation_error():
    e = ValidationError("name contains invalid character: <>")
    assert "<>" in str(e)


def test_handle_error_json_output(capsys):
    e = NodeNotFoundError("test_node")
    with pytest.raises(SystemExit) as exc:
        handle_error(e, json_output=True)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert '"ok": false' in captured.out or '"ok":false' in captured.out
    assert 'NodeNotFoundError' in captured.out


def test_handle_error_text_output(capsys):
    e = NodeNotFoundError("test_node")
    with pytest.raises(SystemExit) as exc:
        handle_error(e, json_output=False)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "test_node" in captured.err
