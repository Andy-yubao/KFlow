import json

import pytest

from kflow.cli import main


def _json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def _text(capsys, *arguments):
    main(list(arguments))
    return capsys.readouterr().out


def test_noun_first_entity_lifecycle_text_and_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("输入 文档", "output", "replacement"):
        (docs / f"{name}.md").write_text(name, encoding="utf-8")
    _json(capsys, "init")

    source = _json(capsys, "node", "add", "输入", "--file", "docs\\输入 文档.md")
    assert source["schema_version"] == 4
    assert source["node"]["files"] == ["docs/输入 文档.md"]
    assert _text(capsys, "node", "add", "output", "--file", "docs/output.md") == (
        "Added Node: output\n"
    )

    added = _json(
        capsys,
        "derivation",
        "add",
        "input-to-output",
        "--short",
        "Create output",
        "--detail",
        "Full meaning",
        "--input",
        "输入",
        "provides input",
        "--output",
        "output",
        "produces output",
    )
    assert added["schema_version"] == 4
    assert added["derivation"]["name"] == "input-to-output"
    derivation_id = added["derivation"]["id"]

    edited = _json(
        capsys,
        "derivation",
        "edit",
        "input-to-output",
        "--name",
        "renamed-flow",
        "--short",
        "Create output again",
        "--input",
        "输入",
        "provides input",
        "--output",
        "output",
        "produces output",
    )
    assert edited["derivation"]["id"] == derivation_id
    assert edited["derivation"]["detail"] == ""
    assert edited["previous_name"] == "input-to-output"

    removed = _json(capsys, "derivation", "remove", "renamed-flow")
    assert removed["derivation"]["id"] == derivation_id
    assert removed["derivation"]["name"] == "renamed-flow"

    output_id = next(
        node["id"]
        for node in _json(capsys, "overview")["nodes"]
        if node["name"] == "output"
    )
    edited_node = _json(
        capsys,
        "node",
        "edit",
        "output",
        "--name",
        "renamed-output",
        "--file",
        "docs/replacement.md",
    )
    assert edited_node["node"]["id"] == output_id
    assert edited_node["node"]["files"] == ["docs/replacement.md"]
    assert _text(capsys, "node", "remove", "renamed-output") == (
        "Removed Node: renamed-output\n"
    )


@pytest.mark.parametrize("old_command", ["add-node", "derive"])
def test_old_entity_commands_are_not_public(old_command, capsys):
    with pytest.raises(SystemExit) as error:
        main([old_command, "--json"])
    assert error.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["issues"][0]["code"] == "invalid_argument"


@pytest.mark.parametrize(
    "arguments",
    [
        ("node", "edit", "old", "--file", "docs/a.md"),
        ("node", "edit", "old", "--name", "new"),
        (
            "derivation",
            "edit",
            "old",
            "--short",
            "short",
            "--input",
            "a",
            "role",
            "--output",
            "b",
            "role",
        ),
    ],
)
def test_complete_edit_arguments_are_required(arguments, capsys):
    with pytest.raises(SystemExit) as error:
        main([*arguments, "--json"])
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["issues"][0]["code"] == (
        "invalid_argument"
    )
