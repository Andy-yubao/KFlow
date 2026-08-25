import pytest

from kflow.core.models import (
    ConfirmationFile,
    ConfirmationInput,
    ConfirmationProducer,
    Derivation,
    DerivationInput,
    DerivationOutput,
    Fingerprint,
    KnowledgeNode,
    NodeConfirmation,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


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
        id="dv_ab",
        short="形成 B",
        detail="",
        inputs=[DerivationInput("nd_a", "使用 A", "")],
        outputs=[DerivationOutput("nd_b", "形成 B", "")],
    )

    assert node.files == ("docs/a.md",)
    assert derivation.inputs == (DerivationInput("nd_a", "使用 A", ""),)
    assert derivation.outputs == (DerivationOutput("nd_b", "形成 B", ""),)


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


def test_derivation_supports_multiple_inputs_and_outputs():
    derivation = Derivation(
        id="dv_design",
        short="形成设计",
        detail="",
        inputs=(
            DerivationInput("nd_a", "使用 A", ""),
            DerivationInput("nd_b", "使用 B", ""),
        ),
        outputs=(
            DerivationOutput("nd_c", "形成 C", ""),
            DerivationOutput("nd_d", "形成 D", ""),
        ),
    )

    assert tuple(item.node for item in derivation.inputs) == ("nd_a", "nd_b")
    assert tuple(item.node for item in derivation.outputs) == ("nd_c", "nd_d")


@pytest.mark.parametrize("empty_side", ["inputs", "outputs"])
def test_derivation_rejects_empty_endpoints(empty_side):
    kwargs = {
        "id": "dv_ab",
        "short": "形成 B",
        "detail": "",
        "inputs": (DerivationInput("nd_a", "使用 A", ""),),
        "outputs": (DerivationOutput("nd_b", "形成 B", ""),),
    }
    kwargs[empty_side] = ()

    with pytest.raises(ValueError):
        Derivation(**kwargs)


def test_derivation_rejects_duplicate_or_overlapping_endpoints():
    with pytest.raises(ValueError):
        Derivation(
            id="dv_duplicate",
            short="重复输入",
            detail="",
            inputs=(
                DerivationInput("nd_a", "输入 A", ""),
                DerivationInput("nd_a", "输入 A", ""),
            ),
            outputs=(DerivationOutput("nd_b", "输出 B", ""),),
        )

    with pytest.raises(ValueError):
        Derivation(
            id="dv_overlap",
            short="自环",
            detail="",
            inputs=(DerivationInput("nd_a", "输入 A", ""),),
            outputs=(DerivationOutput("nd_a", "输出 A", ""),),
        )


def test_all_derivation_detail_fields_accept_canonical_empty_string():
    derivation = Derivation(
        id="dv_ab",
        short="形成 B",
        detail="",
        inputs=(DerivationInput("nd_a", "使用 A", ""),),
        outputs=(DerivationOutput("nd_b", "形成 B", ""),),
    )

    assert derivation.detail == ""
    assert derivation.inputs[0].detail == ""
    assert derivation.outputs[0].detail == ""


@pytest.mark.parametrize("level", ["derivation", "input", "output"])
def test_all_derivation_short_fields_require_non_empty_text(level):
    input_short = " " if level == "input" else "使用 A"
    output_short = " " if level == "output" else "形成 B"

    with pytest.raises(ValueError):
        Derivation(
            id="dv_ab",
            short=" " if level == "derivation" else "形成 B",
            detail="",
            inputs=(DerivationInput("nd_a", input_short, ""),),
            outputs=(DerivationOutput("nd_b", output_short, ""),),
        )


def test_fingerprint_requires_labelled_lowercase_sha256():
    assert Fingerprint("sha256", SHA_A).value == SHA_A

    with pytest.raises(ValueError):
        Fingerprint("sha1", SHA_A)
    with pytest.raises(ValueError):
        Fingerprint("sha256", SHA_A.upper())


def test_source_confirmation_records_exactly_one_node_without_producer_inputs():
    confirmation = NodeConfirmation(
        node="nd_a",
        files=(ConfirmationFile("docs/a.md", Fingerprint("sha256", SHA_A)),),
        files_fingerprint=Fingerprint("sha256", SHA_B),
        producing_derivation=None,
        inputs=(),
        effective_version=SHA_A,
    )

    assert confirmation.node == "nd_a"
    assert confirmation.producing_derivation is None
    assert confirmation.inputs == ()


def test_derived_confirmation_requires_producer_and_direct_inputs_together():
    file_fact = ConfirmationFile("docs/b.md", Fingerprint("sha256", SHA_A))
    producer = ConfirmationProducer("dv_ab", Fingerprint("sha256", SHA_B))

    confirmation = NodeConfirmation(
        node="nd_b",
        files=(file_fact,),
        files_fingerprint=Fingerprint("sha256", SHA_A),
        producing_derivation=producer,
        inputs=(ConfirmationInput("nd_a", SHA_A),),
        effective_version=SHA_B,
    )
    assert confirmation.producing_derivation == producer

    with pytest.raises(ValueError):
        NodeConfirmation(
            node="nd_b",
            files=(file_fact,),
            files_fingerprint=Fingerprint("sha256", SHA_A),
            producing_derivation=producer,
            inputs=(),
            effective_version=SHA_B,
        )
