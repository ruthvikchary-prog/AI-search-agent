"""Unit tests for ReportFormatter and ReportLab PDF generation (Student 4)."""

import tempfile
from pathlib import Path
from models.schemas import (
    AcademicReport,
    ReportSection,
    ReferenceEntry,
    CitationStyle
)
from services.report_formatter import ReportFormatter


def create_dummy_report():
    return AcademicReport(
        id="rep-pdf-test-1",
        title="Automated Synthesis and Verification of Neural Networks",
        topic="Neural Verification",
        abstract="This paper explores mathematical formal verification applied to deep neural networks.",
        keywords=["Formal Verification", "SMT Solvers", "Neural Robustness"],
        sections=[
            ReportSection(
                heading="1. Introduction",
                level=1,
                content="Robustness verification assesses whether small perturbations cause misclassification [SRC-1].",
                citations=["SRC-1"]
            ),
            ReportSection(
                heading="2. Bound Propagation Methodologies",
                level=1,
                content="Interval bound propagation provides guaranteed certified bounds against adversarial attacks [SRC-2].",
                citations=["SRC-2"]
            )
        ],
        conclusion="Verification frameworks provide provable bounds necessary for safety-critical deployment.",
        references=[
            ReferenceEntry(source_id="SRC-1", citation_number=1, formatted_text="[1] G. Katz et al., 'Reluplex: An SMT Solver for Neural Networks,' CAV 2017."),
            ReferenceEntry(source_id="SRC-2", citation_number=2, formatted_text="[2] S. Gowal et al., 'Scalable Certified Bounds,' NeurIPS 2018.")
        ],
        citation_style=CitationStyle.IEEE,
        target_page_count=3,
        created_at="2026-10-15T00:00:00Z"
    )


def test_pdf_generation_file_creation():
    """Verify that ReportLab creates a valid, non-empty PDF file."""
    report = create_dummy_report()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pdf_file = ReportFormatter.generate_pdf(report, output_dir=tmp_path)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 1000  # Non-trivial PDF size

        # Check PDF header
        with open(pdf_file, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"


def test_markdown_and_html_exports():
    """Verify conversion to clean Markdown and academic HTML preview."""
    report = create_dummy_report()

    md = ReportFormatter.to_markdown(report)
    assert "# Automated Synthesis" in md
    assert "## Abstract" in md
    assert "[1] G. Katz" in md

    html = ReportFormatter.to_academic_html(report)
    assert "Automated Synthesis and Verification" in html
    assert "citation-badge" in html
    assert "references-card" in html
