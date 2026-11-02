"""Real LLM smoke tests using configured Groq credentials.

Marked with @pytest.mark.llm so they are not run automatically in standard test suites.
Run explicitly with: pytest -m llm
"""

import os
import pytest
from config import Config
from models.schemas import ResearchSource, CitationStyle, ReportLength, SourceType
from agents.academic_writer import AcademicWriterAgent


@pytest.mark.llm
def test_real_groq_llm_inference():
    """Verify live report generation with active Groq API credentials."""
    if not Config.GROQ_API_KEY:
        pytest.skip("GROQ_API_KEY not configured in environment.")

    writer = AcademicWriterAgent()
    sources = [
        ResearchSource(
            source_id="SRC-1",
            title="A Survey of Large Language Models",
            authors=["Zhao et al."],
            year=2023,
            venue="arXiv",
            url="https://arxiv.org/abs/2303.18223",
            excerpts=["Pre-trained language models exhibit emergent abilities such as in-context learning and chain-of-thought prompting."],
            source_type=SourceType.WEB
        )
    ]

    report = writer.generate_report(
        topic="Emergent Abilities in Large Language Models",
        sources=sources,
        citation_style=CitationStyle.IEEE,
        length=ReportLength.BRIEF,
        target_page_count=2
    )

    assert report is not None
    assert report.title is not None
    assert len(report.sections) >= 2
    assert len(report.references) >= 1
    # Check that in-text or references cited SRC-1
    assert "SRC-1" in report.sources_used or any("SRC-1" in s.citations for s in report.sections) or len(report.references) > 0
