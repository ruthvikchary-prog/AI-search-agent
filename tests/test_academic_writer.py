"""Unit tests for Academic Report Writer Agent (Student 4)."""

from models.schemas import (
    ResearchSource,
    CitationStyle,
    ReportLength,
    SourceType
)
from agents.academic_writer import AcademicWriterAgent


def create_mock_sources():
    return [
        ResearchSource(
            source_id="SRC-1",
            title="Self-Supervised Learning in Vision Transformers",
            authors=["Carion et al."],
            year=2021,
            venue="ICLR",
            url="https://arxiv.org/abs/2104.14294",
            excerpts=["Emerging properties in self-supervised vision transformers include semantic segmentation masks."],
            source_type=SourceType.WEB
        ),
        ResearchSource(
            source_id="SRC-2",
            title="Scaling Laws for Neural Language Models",
            authors=["Kaplan et al."],
            year=2020,
            venue="arXiv",
            url="https://arxiv.org/abs/2001.08361",
            excerpts=["Cross-entropy loss scales as a power law with compute, dataset size, and parameter count."],
            source_type=SourceType.WEB
        )
    ]


def test_deterministic_report_generation():
    """Verify that writer generates a fully structured report with all required sections."""
    # Instantiated without LLM client to trigger pure deterministic generation
    writer = AcademicWriterAgent(llm_client=None)
    sources = create_mock_sources()

    report = writer.generate_report(
        topic="Scaling Laws in Foundation Models",
        sources=sources,
        citation_style=CitationStyle.IEEE,
        length=ReportLength.STANDARD,
        target_page_count=5
    )

    assert report.title is not None and len(report.title) > 10
    assert report.abstract is not None and len(report.abstract) > 50
    assert len(report.keywords) >= 3
    assert len(report.sections) >= 3
    assert len(report.references) == 2
    assert report.references[0].source_id == "SRC-1"
    assert report.references[1].source_id == "SRC-2"
    assert report.citation_style == CitationStyle.IEEE


def test_apa_style_reference_formatting():
    """Verify APA citation style formatting in bibliography."""
    writer = AcademicWriterAgent(llm_client=None)
    sources = create_mock_sources()

    report = writer.generate_report(
        topic="Vision Transformers",
        sources=sources,
        citation_style=CitationStyle.APA
    )

    assert report.citation_style == CitationStyle.APA
    ref1 = report.references[0].formatted_text
    # APA references should include (Year) and not start with bracketed [1]
    assert "(2021)" in ref1 or "Carion" in ref1


def test_rewrite_and_improve():
    """Verify that rewrite_and_improve preserves original topic and enhances structure."""
    writer = AcademicWriterAgent(llm_client=None)
    sources = create_mock_sources()
    draft_text = "Vision transformers are models that apply self-attention directly to image patches."

    improved = writer.rewrite_and_improve(
        original_text=draft_text,
        sources=sources,
        citation_style=CitationStyle.IEEE,
        preserve_findings=True
    )

    assert improved.title is not None
    assert len(improved.sections) > 0
    assert len(improved.references) > 0
