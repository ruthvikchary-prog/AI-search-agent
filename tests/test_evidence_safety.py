from agents.evaluation import EvaluationAgent
from models.schemas import AcademicReport, ReferenceEntry, ReportSection, ResearchSource
from research_analyst import multi_source_search


def _report(content: str, source_id: str = "SRC-1") -> AcademicReport:
    return AcademicReport(
        id="safety-test",
        title="Evidence Safety Test",
        topic="Evidence safety",
        abstract="A report used to verify evidence safety gates.",
        sections=[ReportSection(heading="1. Findings", content=content)],
        conclusion="The evidence is limited.",
        references=[ReferenceEntry(
            source_id=source_id,
            citation_number=1,
            formatted_text="[1] Verified source."
        )],
        created_at="2025-01-01T00:00:00Z",
    )


def test_search_failure_does_not_create_synthetic_sources(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setattr("research_analyst._ddg_search", lambda query, n: [])
    monkeypatch.setattr("research_analyst._arxiv_search", lambda query, n: [])
    assert multi_source_search("topic with no results") == []


def test_duplicate_paragraphs_block_publication():
    source = ResearchSource(
        source_id="SRC-1",
        title="Verified source",
        url="https://example.edu/paper",
        excerpts=["Evidence supports the reported observation."],
    )
    repeated = "Evidence supports the reported observation and is documented [SRC-1]."
    result = EvaluationAgent(passing_score=0).evaluate(_report(f"{repeated}\n\n{repeated}"), [source])
    assert result.passed is False
    assert any("Duplicate paragraph" in error for error in result.critical_errors)


def test_unsupported_numeric_claim_blocks_publication():
    source = ResearchSource(
        source_id="SRC-1",
        title="Verified source",
        url="https://example.edu/paper",
        excerpts=["Evidence supports the reported observation."],
    )
    result = EvaluationAgent(passing_score=0).evaluate(
        _report("The method achieved 99% accuracy [SRC-1]."),
        [source],
    )
    assert result.passed is False
    assert any("Unsupported numeric claim" in error for error in result.critical_errors)
