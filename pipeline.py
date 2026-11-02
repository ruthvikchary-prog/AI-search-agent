"""
pipeline.py - Master Multi-Agent Academic Research Assistant Pipeline
=============================================================================
Course: Professional Elective - IV (Agentic AI) | Batch 6
Institution: KG Reddy College of Engineering & Technology

Sequential Line-Wise Arrangement:
  [1st] Karthik's Module : Research Analyst Agent (Search & Discovery)
  [2nd] Rahul's Module   : Source Reviewer & Citation Validator (Auditing & NLI)
  [3rd] Mine's Module    : Academic Writer, 8-Dimension Evaluation & PDF Formatter
=============================================================================
Usage:
    python pipeline.py "Federated Learning in Healthcare"
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

# Setup paths so all modules resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent
RAHUL_DIR = ROOT_DIR / "rahul_part_agent"
if str(RAHUL_DIR) not in sys.path:
    sys.path.insert(0, str(RAHUL_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# [1st] Karthik's Module: Research Analyst Agent
# ---------------------------------------------------------------------------
from research_analyst import (
    ResearchOutput,
    run_research_analyst,
    compute_metrics as compute_analyst_metrics
)

# ---------------------------------------------------------------------------
# [2nd] Rahul's Module: Source Reviewer & Citation Validator
# ---------------------------------------------------------------------------
from rahul_part_agent.schemas import (
    RawSource,
    RawResearchInput,
    VerifiedEvidenceDossier,
    VerificationStatus,
    ClaimSupportStatus
)
from rahul_part_agent.source_reviewer import SourceReviewerPipeline

# ---------------------------------------------------------------------------
# [3rd] Mine's Module: Academic Writer, Evaluator & Report Formatter
# ---------------------------------------------------------------------------
from config import Config
from models.schemas import (
    AcademicReport,
    ResearchSource,
    CitationStyle,
    ReportLength
)
from agents.academic_writer import AcademicWriterAgent
from agents.evaluation import EvaluationAgent
from services.citation_validator import CitationValidator as InTextCitationValidator
from services.report_formatter import ReportFormatter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MasterPipeline")


# ===========================================================================
# Line-Wise Orchestrated Pipeline
# ===========================================================================

def run_pipeline(
    topic: str,
    citation_style: CitationStyle = CitationStyle.IEEE,
    output_dir: Optional[Path] = None
) -> dict:
    """
    Executes the 3-module pipeline in strict sequential order:
    1st (Karthik) -> 2nd (Rahul) -> 3rd (Mine).
    """
    output_dir = output_dir or (ROOT_DIR / "generated_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in topic.lower()).strip("_")[:40]

    print("\n" + "=" * 78)
    print(" 🚀 STARTING 3-MODULE MULTI-AGENT ACADEMIC RESEARCH PIPELINE")
    print("=" * 78)
    print(f"Topic: {topic}\n")

    # -----------------------------------------------------------------------
    # STEP 1: Karthik's Module (Research Analyst Agent)
    # -----------------------------------------------------------------------
    print("-" * 78)
    print(" [1ST MODULE - KARTHIK] Research Analyst Agent (Search & Discovery)")
    print("-" * 78)
    print(f" -> Querying academic web sources for '{topic}'...")
    research_output: ResearchOutput = run_research_analyst(topic)
    analyst_metrics = compute_analyst_metrics(research_output)

    print(f" -> Sources Discovered: {len(research_output.sources)}")
    print(f" -> Subtopics Extracted: {len(research_output.subtopics)}")
    print(f" -> Key Findings Generated: {len(research_output.findings)}")
    print(f" -> Unique Domains: {analyst_metrics.get('unique_domains')}")
    print(f" -> Search Relevance: {analyst_metrics.get('search_relevance_percent')}%")

    # -----------------------------------------------------------------------
    # STEP 2: Rahul's Module (Source Reviewer & Citation Validator)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 78)
    print(" [2ND MODULE - RAHUL] Source Reviewer & Citation Validator (Evidence Auditing)")
    print("-" * 78)
    print(" -> Ingesting findings from Karthik's Research Analyst...")

    # Transform 1st output -> 2nd input contract
    raw_sources = [
        RawSource(
            id=f"SRC-{idx + 1}",
            title=src.title,
            url=src.url,
            snippet=src.snippet,
            author=None,
            published_date=src.published
        )
        for idx, src in enumerate(research_output.sources)
    ]
    key_findings = [f"{f.subtopic}: {f.summary}" for f in research_output.findings]

    raw_input = RawResearchInput(
        topic=topic,
        sources=raw_sources,
        key_findings=key_findings
    )

    print(f" -> Auditing {len(raw_sources)} candidate sources against academic domain tiers...")
    reviewer_pipeline = SourceReviewerPipeline(quality_threshold=60.0, relevance_threshold=45.0)
    dossier: VerifiedEvidenceDossier = reviewer_pipeline.process_research(raw_input)

    print(f" -> Verified (Accepted) Sources: {len(dossier.verified_sources)}")
    print(f" -> Filtered (Rejected) Sources: {len(dossier.rejected_sources)}")
    print(f" -> Source Quality Rating: {dossier.metrics.source_quality_pct}%")
    print(f" -> Evidence Faithfulness Rate: {dossier.metrics.faithfulness_pct}%")
    print(f" -> Noise Filtered Ratio: {dossier.metrics.noise_filtered_pct}%")

    # -----------------------------------------------------------------------
    # STEP 3: Mine's Module (Academic Writer, 8-Dimension Evaluation & PDF)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 78)
    print(" [3RD MODULE - MINE] Academic Writer, 8-Dimension Evaluation & PDF Compilation")
    print("-" * 78)
    print(" -> Converting Rahul's verified evidence dossier into grounded research sources...")

    # Convert Rahul's verified sources into Student 4 ResearchSource objects
    grounded_sources: List[ResearchSource] = []
    for s in dossier.verified_sources:
        grounded_sources.append(
            ResearchSource(
                source_id=s.id,
                title=s.title,
                url=s.url,
                authors=[s.author] if s.author else [],
                year=int(s.published_date) if s.published_date and s.published_date.isdigit() else None,
                venue=s.domain,
                excerpts=[s.snippet],
                credibility_score=round(s.credibility_score / 100.0, 2),
                is_verified=True
            )
        )

    # Fallback safety if all sources were rejected
    if not grounded_sources:
        print(" [Warning] No sources passed tier 1/2. Retaining top sources as unverified references.")
        for s in dossier.rejected_sources[:3]:
            grounded_sources.append(
                ResearchSource(
                    source_id=s.id,
                    title=s.title,
                    url=s.url,
                    authors=[],
                    venue=s.domain,
                    excerpts=[s.snippet],
                    credibility_score=0.45,
                    is_verified=False
                )
            )

    writer = AcademicWriterAgent()
    evaluator = EvaluationAgent()
    in_text_validator = InTextCitationValidator()

    print(f" -> Synthesizing structured academic report in {citation_style.value} style...")
    report: AcademicReport = writer.generate_report(
        topic=topic,
        sources=grounded_sources,
        citation_style=citation_style,
        length=ReportLength.STANDARD,
        target_page_count=5
    )

    print(" -> Validating in-text citations & references integrity...")
    cit_val = in_text_validator.validate(report, grounded_sources)
    print(f"    Resolved citations: {len(cit_val.resolved_citations)}")
    print(f"    Unresolved citations: {len(cit_val.unresolved_citations)}")
    print(f"    Fabricated references: {len(cit_val.fabricated_references)}")

    print(" -> Executing 8-Dimension Quality Evaluation Gate...")
    evaluation = evaluator.evaluate(report, grounded_sources, cit_val)
    grade = "A (Exemplary)" if evaluation.overall_score >= 90 else "B (Proficient)" if evaluation.overall_score >= 80 else "C (Satisfactory)"
    print(f"    Overall Quality Score: {evaluation.overall_score:.1f}/100.0 (Passed: {evaluation.passed})")
    print(f"    Grade: {grade}")

    print(" -> Compiling publication-ready PDF using ReportLab layout engine...")
    pdf_path = ReportFormatter.generate_pdf(report, output_dir=output_dir)

    md_content = ReportFormatter.to_markdown(report)
    md_path = output_dir / f"Report_{slug}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print("\n" + "=" * 78)
    print(" ✅ COMPLETE PIPELINE EXECUTION SUCCESSFUL!")
    print("=" * 78)
    print(f"  • [1st - Karthik] Extracted {len(research_output.sources)} raw search sources.")
    print(f"  • [2nd - Rahul]   Audited & verified {len(dossier.verified_sources)} grounded evidence sources.")
    print(f"  • [3rd - Mine]    Synthesized full academic paper & compiled publication PDF:")
    print(f"                    PDF -> {pdf_path}")
    print(f"                    Markdown -> {md_path}")
    print("=" * 78 + "\n")

    return {
        "status": "success",
        "topic": topic,
        "pdf_path": str(pdf_path),
        "md_path": str(md_path),
        "overall_score": evaluation.overall_score,
        "grade": grade,
        "analyst_metrics": analyst_metrics,
        "dossier_metrics": dossier.metrics.model_dump(),
        "evaluation": evaluation.model_dump()
    }


if __name__ == "__main__":
    test_topic = " ".join(sys.argv[1:]).strip() or "Federated Learning in Healthcare"
    run_pipeline(test_topic)
