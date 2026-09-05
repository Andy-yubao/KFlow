from pathlib import Path


def test_direct_agent_workflows_use_human_task_outputs() -> None:
    workflow = Path("docs/agent-workflow.md").read_text(encoding="utf-8")
    skills = Path("docs/kflow_skills.md").read_text(encoding="utf-8")

    for document in (workflow, skills):
        assert "--json" not in document
        assert "KFlow project:" in document
        assert "Review order" in document
        assert "Produced by:" in document


def test_agent_integration_is_labeled_as_programmatic_adapter() -> None:
    integration = Path("docs/agent-integration.md").read_text(encoding="utf-8")

    assert "程序化适配层" in integration
    assert "不是 Agent 的直接终端工作流" in integration
    assert "--json" in integration


def test_current_docs_use_only_the_noun_first_entity_commands() -> None:
    documents = [
        Path("README.md"),
        Path("AGENTS.md"),
        Path("CLAUDE.md"),
        *Path("docs").glob("*.md"),
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in documents)

    assert "kflow node add" in contents
    assert "kflow derivation add" in contents
    assert "kflow add-node" not in contents
    assert "kflow review-plan" not in contents
    assert "docs/history" not in contents
