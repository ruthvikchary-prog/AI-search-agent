"""Unit tests for Pydantic data models and schemas."""

import pytest
from pydantic import ValidationError
from models.schemas import (
    ResearchSource,
    SourceType,
    ReportSection,
    AcademicReport,
    CitationStyle,
    ReportLength,
    NewReportRequest,
    ImproveReportRequest
)


def test_research_source_validation():
    """Verify ResearchSource validation constraints."""
    source = ResearchSource(
        source_id="SRC-1",
        title="Attention Is All You Need",
        authors=["Vaswani et al."],
        year=2017,
        excerpts=["The Transformer is the first transduction model relying entirely on self-attention."]
    )
    assert source.source_id == "SRC-1"
    assert source.year == 2017
    assert source.source_type == SourceType.WEB

    # Empty source_id should fail
    with pytest.raises(ValidationError):
        ResearchSource(
            source_id="   ",
            title="Invalid",
            excerpts=[]
        )


def test_new_report_request_validation():
    """Verify input validation for new report requests."""
    valid_req = NewReportRequest(
        topic="Neural Network Architectures for Medical Imaging",
        length=ReportLength.STANDARD,
        target_page_count=5,
        citation_style=CitationStyle.IEEE
    )
    assert valid_req.topic.startswith("Neural")

    # Short topic (< 3 chars) should fail
    with pytest.raises(ValidationError):
        NewReportRequest(
            topic="AB",
            length=ReportLength.STANDARD
        )

    # Out of range target_page_count (> 25) should fail
    with pytest.raises(ValidationError):
        NewReportRequest(
            topic="Valid Topic Name",
            target_page_count=99
        )


def test_academic_report_schema():
    """Verify AcademicReport structure with nested sections and references."""
    report = AcademicReport(
        id="rep-123",
        title="Advances in Quantum Computing",
        topic="Quantum Computing",
        abstract="A comprehensive survey of superconducting qubits and topological protection mechanisms.",
        keywords=["Quantum", "Superconducting", "Qubits"],
        sections=[
            ReportSection(
                heading="1. Introduction",
                level=1,
                content="Quantum computing promises exponential acceleration [SRC-1].",
                citations=["SRC-1"]
            )
        ],
        conclusion="Ongoing work in error mitigation continues to mature.",
        citation_style=CitationStyle.IEEE,
        created_at="2026-10-15T00:00:00Z"
    )
    assert len(report.sections) == 1
    assert report.sections[0].citations == ["SRC-1"]
    assert report.citation_style == CitationStyle.IEEE
