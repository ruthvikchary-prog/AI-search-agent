"""Unit tests for the Academic Report Evaluation Module (Student 4)."""

from models.schemas import (
    AcademicReport,
    ReportSection,
    ReferenceEntry,
    ResearchSource,
    CitationStyle,
    SourceType
)
from agents.evaluation import EvaluationAgent
from services.citation_validator import CitationValidator


def create_sample_sources():
    return [
        ResearchSource(
            source_id="SRC-1",
            title="Advancements in Quantum Teleportation and Error Correction",
            authors=["J. Preskill"],
            year=2021,
            venue="Physical Review",
            url="https://doi.org/10.1103/PhysRevA.100",
            excerpts=["Quantum error correction protects logical qubits through topological entanglement."],
            source_type=SourceType.WEB
        )
    ]


def test_high_quality_report_evaluation_passes():
    """Verify that a well-structured, evidence-grounded report passes quality gates."""
    sources = create_sample_sources()
    evaluator = EvaluationAgent(passing_score=75.0)

    report = AcademicReport(
        id="rep-good",
        title="Analysis of Quantum Error Correction and Fault Tolerance",
        topic="Quantum Error Correction and Fault Tolerance",
        abstract=(
            "Quantum error correction represents an indispensable milestone in scaling quantum computational architectures. "
            "This investigation examines topological entanglement schemes, fault-tolerant thresholds, and logical qubit fidelity. "
            "Through systematic synthesis of empirical and theoretical literature, we delineate current implementation challenges "
            "and suggest calibrated engineering priorities for next-generation noisy intermediate-scale quantum devices."
        ),
        keywords=["Quantum Computing", "Error Correction", "Fault Tolerance", "Qubits"],
        sections=[
            ReportSection(
                heading="1. Introduction to Quantum Fault Tolerance",
                level=1,
                content="Building scalable quantum computers necessitates suppressing decoherence and environmental noise [SRC-1].",
                citations=["SRC-1"]
            ),
            ReportSection(
                heading="2. Literature Review and Findings",
                level=1,
                content="Quantum error correction protects logical qubits through topological entanglement schemes [SRC-1].",
                citations=["SRC-1"]
            )
        ],
        conclusion="In conclusion, error correction protocols are fundamental for achieving quantum computational supremacy.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] J. Preskill, 'Advancements in Quantum Teleportation,' 2021.")
        ],
        citation_style=CitationStyle.IEEE,
        target_page_count=3,
        created_at="2026-10-15T00:00:00Z"
    )

    eval_result = evaluator.evaluate(report, sources)
    assert eval_result.passed is True
    assert eval_result.overall_score >= 75.0
    assert len(eval_result.dimensions) == 8
    assert len(eval_result.critical_errors) == 0


def test_hard_quality_gate_on_fabricated_references():
    """Ensure that fabricated references trigger critical errors and block report approval."""
    sources = create_sample_sources()
    evaluator = EvaluationAgent(passing_score=70.0)

    # Report has high text quality, but includes a fabricated reference
    report = AcademicReport(
        id="rep-fab-gate",
        title="Quantum Computing Analysis",
        topic="Quantum Computing",
        abstract="Valid abstract of sufficient length describing the problem and findings in detail.",
        keywords=["Quantum", "Testing", "Fault Tolerance"],
        sections=[
            ReportSection(
                heading="1. Introduction",
                level=1,
                content="Quantum text [SRC-1].",
                citations=["SRC-1"]
            ),
            ReportSection(
                heading="2. Findings",
                level=1,
                content="More text discussing findings.",
                citations=[]
            )
        ],
        conclusion="Valid conclusion summarizing the paper.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] Real reference."),
            ReferenceEntry(source_id="SRC-PHANTOM-99", citation_number=2, formatted_text="[2] Fabricated phantom reference.")
        ],
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )

    eval_result = evaluator.evaluate(report, sources)
    # MUST FAIL despite possible high points in other areas
    assert eval_result.passed is False
    assert any("fabricated" in err.lower() for err in eval_result.critical_errors)


def test_informal_tone_penalty():
    """Verify that colloquialisms trigger tone warnings and score deductions."""
    sources = create_sample_sources()
    evaluator = EvaluationAgent()

    report = AcademicReport(
        id="rep-colloquial",
        title="Informal Quantum Review",
        topic="Quantum Computing",
        abstract="This paper is basically looking at a lot of cool quantum stuff and gonna see what happens.",
        keywords=["Quantum", "Testing"],
        sections=[
            ReportSection(
                heading="1. Introduction",
                level=1,
                content="Quantum computing is kind of awesome and a huge deal [SRC-1].",
                citations=["SRC-1"]
            )
        ],
        conclusion="Anyways, quantum is crazy.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] Real source.")
        ],
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )

    eval_result = evaluator.evaluate(report, sources)
    tone_dim = next(d for d in eval_result.dimensions if d.name == "Academic Tone & Clarity")
    assert tone_dim.score < 80.0
    assert any("colloquial" in w.lower() for w in eval_result.warnings)
