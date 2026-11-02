"""Unit tests for deterministic citation and reference validator (Student 4)."""

from models.schemas import (
    AcademicReport,
    ReportSection,
    ReferenceEntry,
    ResearchSource,
    CitationStyle,
    SourceType
)
from services.citation_validator import CitationValidator


def create_sample_sources():
    return [
        ResearchSource(
            source_id="SRC-1",
            title="Transformer Architectures in Modern AI",
            authors=["A. Vaswani", "N. Shazeer"],
            year=2017,
            venue="NeurIPS",
            url="https://arxiv.org/abs/1706.03762",
            excerpts=["The Transformer is based entirely on self-attention mechanisms without recurrence."],
            source_type=SourceType.WEB
        ),
        ResearchSource(
            source_id="SRC-2",
            title="Deep Residual Learning for Image Recognition",
            authors=["K. He", "X. Zhang"],
            year=2016,
            venue="CVPR",
            url="https://arxiv.org/abs/1512.03385",
            excerpts=["Residual connections allow gradients to flow directly through skip paths."],
            source_type=SourceType.WEB
        )
    ]


def test_valid_citation_verification():
    """Verify that a compliant report with valid citations and references passes."""
    sources = create_sample_sources()
    validator = CitationValidator()

    report = AcademicReport(
        id="rep-valid-1",
        title="Survey of Deep Learning Architectures",
        topic="Deep Learning Architectures",
        abstract="This paper synthesizes modern deep learning breakthroughs including transformers and residual networks.",
        keywords=["Transformers", "ResNet", "Deep Learning"],
        sections=[
            ReportSection(
                heading="1. Attention Mechanisms",
                level=1,
                content="Self-attention mechanisms revolutionized sequential modeling [SRC-1].",
                citations=["SRC-1"]
            ),
            ReportSection(
                heading="2. Residual Frameworks",
                level=1,
                content="Deep residual networks introduce identity shortcut connections [SRC-2].",
                citations=["SRC-2"]
            )
        ],
        conclusion="Both architectures demonstrate foundational utility in contemporary neural engineering.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] A. Vaswani, 'Transformer Architectures,' 2017."),
            ReferenceEntry(source_id="SRC-2", citation_number=2, formatted_text="[2] K. He, 'Deep Residual Learning,' 2016.")
        ],
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )

    result = validator.validate(report, sources)
    assert result.is_valid is True
    assert "SRC-1" in result.resolved_citations
    assert "SRC-2" in result.resolved_citations
    assert len(result.unresolved_citations) == 0
    assert len(result.fabricated_references) == 0


def test_unresolved_in_text_citation():
    """Verify that citing an unknown source ID (e.g. [SRC-99]) fails validation."""
    sources = create_sample_sources()
    validator = CitationValidator()

    report = AcademicReport(
        id="rep-invalid-unresolved",
        title="Flawed Survey",
        topic="AI Testing",
        abstract="Testing unmapped citation references.",
        sections=[
            ReportSection(
                heading="1. Unverified Assertions",
                level=1,
                content="According to recent claims [SRC-99], quantum speedup is infinite.",
                citations=["SRC-99"]
            )
        ],
        conclusion="Summary.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] Vaswani, 2017.")
        ],
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )

    result = validator.validate(report, sources)
    assert result.is_valid is False
    assert "SRC-99" in result.unresolved_citations


def test_fabricated_reference_detection():
    """Verify that inventing a reference not present in research sources is caught."""
    sources = create_sample_sources()
    validator = CitationValidator()

    report = AcademicReport(
        id="rep-invalid-fab",
        title="Survey With Fabricated Reference",
        topic="AI Testing",
        abstract="Testing fabricated references.",
        sections=[
            ReportSection(
                heading="1. Introduction",
                level=1,
                content="Standard transformer overview [SRC-1].",
                citations=["SRC-1"]
            )
        ],
        conclusion="Summary.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] Real reference."),
            # Fabricated source ID that was never ingested or verified
            ReferenceEntry(source_id="SRC-FAKE-42", citation_number=2, formatted_text="[2] F. Author, 'Invented Study,' 2025.")
        ],
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )

    result = validator.validate(report, sources)
    assert result.is_valid is False
    assert "SRC-FAKE-42" in result.fabricated_references
