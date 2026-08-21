import pytest

from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)


def test_node_accepts_multiple_files():
    node = KnowledgeNode(
        id="nd_architecture",
        name="architecture",
        files=("docs/architecture.md", "docs/architecture.svg"),
    )

    assert node.files == ("docs/architecture.md", "docs/architecture.svg")


def test_domain_collections_are_normalized_to_immutable_tuples():
    node = KnowledgeNode(id="nd_a", name="a", files=["docs/a.md"])
    derivation = Derivation(
        id="dv_a",
        short="登记 A",
        detail="登记源知识 A。",
        inputs=[],
        outputs=[DerivationOutput("nd_a", "形成 A", "登记 A。")],
    )

    assert node.files == ("docs/a.md",)
    assert derivation.inputs == ()
    assert derivation.outputs == (DerivationOutput("nd_a", "形成 A", "登记 A。"),)


@pytest.mark.parametrize(
    "files",
    [
        (),
        ("/absolute.md",),
        ("C:/absolute.md",),
        ("docs\\windows.md",),
        ("docs/../outside.md",),
        ("docs/a.md", "docs/a.md"),
    ],
)
def test_node_rejects_invalid_file_sets(files):
    with pytest.raises(ValueError):
        KnowledgeNode(id="nd_a", name="a", files=files)


def test_zero_input_multi_output_derivation_is_valid():
    derivation = Derivation(
        id="dv_sources",
        short="登记初始约束",
        detail="将项目已有的需求和约束登记为共同的源知识。",
        inputs=(),
        outputs=(
            DerivationOutput("nd_requirements", "形成需求", "登记项目功能需求。"),
            DerivationOutput("nd_constraints", "形成约束", "登记项目实现约束。"),
        ),
    )

    assert derivation.inputs == ()
    assert len(derivation.outputs) == 2


def test_derivation_rejects_zero_outputs():
    with pytest.raises(ValueError):
        Derivation(
            id="dv_empty",
            short="无输出",
            detail="非法推导。",
            inputs=(),
            outputs=(),
        )


def test_derivation_rejects_duplicate_or_overlapping_endpoints():
    with pytest.raises(ValueError):
        Derivation(
            id="dv_duplicate",
            short="重复输入",
            detail="同一输入出现两次。",
            inputs=(
                DerivationInput("nd_a", "输入 A", "第一次。"),
                DerivationInput("nd_a", "输入 A", "第二次。"),
            ),
            outputs=(DerivationOutput("nd_b", "输出 B", "形成 B。"),),
        )

    with pytest.raises(ValueError):
        Derivation(
            id="dv_overlap",
            short="自环",
            detail="同一 Node 同时作为输入和输出。",
            inputs=(DerivationInput("nd_a", "输入 A", "提供 A。"),),
            outputs=(DerivationOutput("nd_a", "输出 A", "形成 A。"),),
        )


@pytest.mark.parametrize("field", ["short", "detail"])
def test_derivation_requires_non_empty_semantics(field):
    kwargs = {
        "id": "dv_a",
        "short": "形成 A",
        "detail": "登记源知识 A。",
        "inputs": (),
        "outputs": (DerivationOutput("nd_a", "输出 A", "形成 A。"),),
    }
    kwargs[field] = "   "

    with pytest.raises(ValueError):
        Derivation(**kwargs)
