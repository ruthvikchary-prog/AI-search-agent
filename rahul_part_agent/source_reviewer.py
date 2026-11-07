"""
source_reviewer.py - CrewAI Source Reviewer Agent & Custom Tools
=============================================================================
Project: Multi-Agent Academic Research Assistant Using CrewAI
Module 3: Source Reviewer & Citation Validation (Student 3: Rahul)
Institution: KG Reddy College of Engineering & Technology
Batch 6 | Professional Elective - IV (Agentic AI)
=============================================================================
Defines:
  1. Custom CrewAI Tools for domain credibility, claim checking, and metrics.
  2. The CrewAI Agent for Source Reviewer.
  3. A robust execution pipeline that bridges Student 2 (Research Analyst)
     and Student 4 (Academic Report Writer).
"""

import os
import sys
import json
import warnings
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Set thread limits before importing numerical and LLM libraries to prevent OpenBLAS issues on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
warnings.filterwarnings("ignore", category=DeprecationWarning)

from dotenv import load_dotenv
load_dotenv()

try:
    from crewai import Agent, LLM
    from crewai.tools import tool
except Exception:
    Agent = LLM = None

    def tool(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

from schemas import (
    RawSource,
    RawResearchInput,
    EvaluatedSource,
    ClaimVerificationResult,
    Module3Metrics,
    VerifiedEvidenceDossier,
    VerificationStatus,
    ClaimSupportStatus,
    CredibilityTier
)
from citation_validator import CitationValidator


# Global validator instance for tools
validator_engine = CitationValidator(quality_threshold=65.0, relevance_threshold=50.0)


# ============================================================================
# 1. Custom CrewAI Tools for Source Reviewer Agent
# ============================================================================

@tool("Verify Source Credibility Tool")
def verify_source_credibility_tool(source_json: str) -> str:
    """
    Evaluates a source's credibility based on domain authority, TLD (.edu/.gov),
    author attribution, and publication date.
    Input must be a JSON string with keys: 'url', 'title', 'snippet', 'author', 'published_date'.
    Returns a JSON string with credibility tier, score (0-100), and authority assessment.
    """
    try:
        data = json.loads(source_json)
        raw = RawSource(
            id=data.get("id", "S_TEMP"),
            title=data.get("title", "Untitled"),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            author=data.get("author"),
            published_date=data.get("published_date")
        )
        tier, score, notes = validator_engine.evaluate_source_credibility(raw)
        return json.dumps({
            "domain": validator_engine.extract_domain(raw.url),
            "credibility_tier": tier.value,
            "credibility_score": score,
            "passed_threshold": score >= validator_engine.quality_threshold,
            "review_notes": notes
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to verify source: {str(e)}"})


@tool("Validate Claim Evidence Tool")
def validate_claim_evidence_tool(claim_and_sources_json: str) -> str:
    """
    Cross-checks a specific factual claim against a list of verified sources to
    detect hallucinations, unsupported assertions, or contradictions.
    Input JSON must contain:
      - 'claim': str (the assertion to verify)
      - 'sources': list of dicts with 'id', 'title', 'snippet', 'url'
    Returns JSON with status (SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED),
    confidence score, and supporting evidence excerpts.
    """
    try:
        payload = json.loads(claim_and_sources_json)
        claim = payload.get("claim", "")
        raw_sources = payload.get("sources", [])

        # Wrap as EvaluatedSources for the engine
        eval_sources = []
        for s in raw_sources:
            eval_sources.append(
                EvaluatedSource(
                    id=s.get("id", "S1"),
                    title=s.get("title", ""),
                    url=s.get("url", ""),
                    domain=validator_engine.extract_domain(s.get("url", "")),
                    credibility_tier=CredibilityTier.TIER_1_ACADEMIC,
                    credibility_score=85.0,
                    relevance_score=80.0,
                    status=VerificationStatus.ACCEPTED,
                    status_reason="Pre-verified candidate",
                    snippet=s.get("snippet", "")
                )
            )

        res = validator_engine.verify_claim_against_sources(claim, eval_sources)
        return json.dumps({
            "claim": res.claim,
            "status": res.status.value,
            "confidence": res.confidence,
            "supporting_source_ids": res.supporting_source_ids,
            "evidence_snippet": res.evidence_snippet,
            "reviewer_notes": res.reviewer_notes
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Claim validation error: {str(e)}"})


@tool("Filter Duplicate and Low Quality Sources Tool")
def filter_sources_tool(sources_payload_json: str) -> str:
    """
    Filters out redundant duplicate URLs, identical papers, and low-trust domains.
    Input JSON must contain:
      - 'topic': str (the user's research topic)
      - 'sources': list of raw source objects
    Returns JSON listing accepted verified sources and rejected sources with reasons.
    """
    try:
        data = json.loads(sources_payload_json)
        topic = data.get("topic", "")
        sources_list = [
            RawSource(**s) for s in data.get("sources", [])
        ]
        evaluated = validator_engine.review_all_sources(topic, sources_list)
        accepted = [s.model_dump() for s in evaluated if s.status == VerificationStatus.ACCEPTED]
        rejected = [s.model_dump() for s in evaluated if s.status == VerificationStatus.REJECTED]

        return json.dumps({
            "total_evaluated": len(evaluated),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "accepted_sources": accepted,
            "rejected_sources": rejected
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Filtering error: {str(e)}"})


@tool("Check Citation Integrity Tool")
def check_citation_integrity_tool(text_and_catalog_json: str) -> str:
    """
    Analyzes draft academic text to ensure all citations (e.g. [1], [S1]) map to genuine
    verified sources in the catalog. Detects hallucinated 'phantom' citations.
    Input JSON must contain:
      - 'draft_text': str
      - 'catalog_sources': list of accepted source dicts
    Returns an integrity score and lists of valid vs phantom citations.
    """
    try:
        data = json.loads(text_and_catalog_json)
        draft = data.get("draft_text", "")
        sources = [EvaluatedSource(**s) for s in data.get("catalog_sources", [])]
        result = validator_engine.validate_in_text_citations(draft, sources)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Citation integrity check error: {str(e)}"})


@tool("Calculate Review Metrics Tool")
def calculate_review_metrics_tool(metrics_payload_json: str) -> str:
    """
    Calculates quantitative metrics corresponding to Slide 13 of the project review:
      - Source quality (%)
      - Relevance accuracy (%)
      - Verified sources count
      - Faithfulness (%) (RAGAs benchmark)
      - Noise filtering (%) (MIRAGE benchmark)
    Input JSON must contain:
      - 'raw_count': int
      - 'evaluated_sources': list of EvaluatedSource objects
      - 'claim_verifications': list of ClaimVerificationResult objects
    Returns calculated metrics JSON.
    """
    try:
        data = json.loads(metrics_payload_json)
        raw_count = data.get("raw_count", 0)
        evaluated = [EvaluatedSource(**s) for s in data.get("evaluated_sources", [])]
        claims = [ClaimVerificationResult(**c) for c in data.get("claim_verifications", [])]
        metrics = validator_engine.compute_metrics(raw_count, evaluated, claims)
        return metrics.model_dump_json(indent=2)
    except Exception as e:
        return json.dumps({"error": f"Metrics calculation error: {str(e)}"})


# ============================================================================
# 2. CrewAI Agent Definition
# ============================================================================

def create_source_reviewer_agent(
    llm_instance: Optional[Any] = None,
    include_tools: bool = True,
) -> Agent:
    """
    Creates and configures the Source Reviewer Agent for Student 3 (Rahul).
    Equipped with 5 specialized validation tools and domain review instructions.
    """
    tools = [
        verify_source_credibility_tool,
        validate_claim_evidence_tool,
        filter_sources_tool,
        check_citation_integrity_tool,
        calculate_review_metrics_tool,
    ] if include_tools else []

    agent_kwargs: Dict[str, Any] = {
        "role": "Senior Academic Source Reviewer & Citation Validation Specialist",
        "goal": (
            "Rigorously evaluate source reliability, remove low-credibility or duplicate web pages, "
            "cross-examine research claims against retrieved evidence, and produce an authenticated, "
            "citation-grounded evidence summary with formal verification metrics."
        ),
        "backstory": (
            "You are an expert peer-review auditor and academic fact-checker with extensive experience "
            "in scholarly publishing and scientific integrity. You ensure that no hallucinated statistics, "
            "unverified claims, or phantom citations pass through to the academic writing phase. "
            "You rigorously filter out unreliable blogs and forums, prioritize peer-reviewed research "
            "(.edu, .gov, arXiv, IEEE, ACM, Springer), and cross-examine assertions against source excerpts."
        ),
        "tools": tools,
        "verbose": True,
        "memory": False,
        "allow_delegation": False
        ,"max_iter": 1
        ,"max_execution_time": 90
    }

    if llm_instance is not None:
        agent_kwargs["llm"] = llm_instance

    return Agent(**agent_kwargs)


# ============================================================================
# 3. High-Level Module 3 Pipeline & Execution Runner
# ============================================================================

class SourceReviewerPipeline:
    """
    High-level controller for Module 3.
    Executes the entire verification sequence deterministically or via CrewAI.
    """

    def __init__(self, quality_threshold: float = 65.0, relevance_threshold: float = 50.0):
        self.validator = CitationValidator(
            quality_threshold=quality_threshold,
            relevance_threshold=relevance_threshold
        )

    def process_research(self, raw_input: RawResearchInput) -> VerifiedEvidenceDossier:
        """
        Executes complete verification flow:
          1. Deduplicate & evaluate source credibility/relevance.
          2. Cross-verify every key finding against accepted sources.
          3. Calculate Slide 13 metrics (Quality %, Relevance %, Count, Faithfulness %).
          4. Assemble structured evidence dossier.
        """
        # Step 1: Review and filter sources
        evaluated_sources = self.validator.review_all_sources(raw_input.topic, raw_input.sources)
        accepted_sources = [s for s in evaluated_sources if s.status == VerificationStatus.ACCEPTED]
        rejected_sources = [s for s in evaluated_sources if s.status == VerificationStatus.REJECTED]

        # Step 2: Cross-examine claims
        claim_results: List[ClaimVerificationResult] = []
        for claim in raw_input.key_findings:
            res = self.validator.verify_claim_against_sources(claim, accepted_sources)
            claim_results.append(res)

        # Step 3: Compute Slide 13 metrics
        metrics = self.validator.compute_metrics(
            raw_sources_count=len(raw_input.sources),
            evaluated_sources=evaluated_sources,
            claim_verifications=claim_results
        )

        # Step 4: Synthesize evidence summary
        summary_lines = [
            f"Evidence review for topic '{raw_input.topic}' completed.",
            f"Received {len(raw_input.sources)} candidate sources; {len(accepted_sources)} verified, {len(rejected_sources)} rejected.",
            f"Overall Source Quality: {metrics.source_quality_pct}% | Relevance Accuracy: {metrics.relevance_accuracy_pct}%",
            f"Claim Faithfulness Rate: {metrics.faithfulness_pct}% | Noise Filtered: {metrics.noise_filtered_pct}%"
        ]

        return VerifiedEvidenceDossier(
            topic=raw_input.topic,
            summary_of_evidence=" ".join(summary_lines),
            verified_sources=accepted_sources,
            rejected_sources=rejected_sources,
            claim_verifications=claim_results,
            metrics=metrics
        )

    def generate_markdown_report(self, dossier: VerifiedEvidenceDossier) -> str:
        """
        Generates a professional academic markdown audit report.
        Displays verification tables, metrics, and claim citations.
        """
        md = []
        md.append(f"# 🛡️ Source Review & Citation Verification Report")
        md.append(f"**Research Topic:** {dossier.topic}\n")

        md.append("## 📊 Module 3 Metrics (Mid-I Presentation Slide 13)")
        md.append("| Metric | Measured Value | Standard Benchmark |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **Source Quality (%)** | `{dossier.metrics.source_quality_pct}%` | ≥ 75.0% (High Authority) |")
        md.append(f"| **Relevance Accuracy (%)** | `{dossier.metrics.relevance_accuracy_pct}%` | ≥ 60.0% (Topic Alignment) |")
        md.append(f"| **Verified Sources Count** | `{dossier.metrics.verified_sources_count}` | ≥ 3 Credible Sources |")
        md.append(f"| **Faithfulness Rate (%)** | `{dossier.metrics.faithfulness_pct}%` | RAGAs Faithfulness Benchmark |")
        md.append(f"| **Noise Filtering Ratio (%)** | `{dossier.metrics.noise_filtered_pct}%` | MIRAGE Robustness Benchmark |\n")

        md.append("## ✅ Verified Sources (Approved for Academic Report)")
        if dossier.verified_sources:
            md.append("| ID | Title | Domain | Credibility Tier | Score | Status |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for s in dossier.verified_sources:
                tier_short = s.credibility_tier.value.split(":")[0]
                md.append(f"| `[{s.id}]` | [{s.title[:45]}...]({s.url}) | `{s.domain}` | {tier_short} | `{s.credibility_score}` | ✅ Approved |")
        else:
            md.append("_No sources met the credibility criteria._")

        if dossier.rejected_sources:
            md.append("\n## 🚫 Rejected / Filtered Sources (Weak or Duplicate)")
            md.append("| ID | Title / URL | Rejection Reason |")
            md.append("| :--- | :--- | :--- |")
            for s in dossier.rejected_sources:
                md.append(f"| `[{s.id}]` | {s.title[:40]}... | {s.status_reason} |")

        md.append("\n## 🔍 Claim-Evidence Cross-Verification")
        for i, c in enumerate(dossier.claim_verifications, 1):
            status_icon = "✅" if c.status == ClaimSupportStatus.SUPPORTED else ("⚠️" if c.status == ClaimSupportStatus.PARTIALLY_SUPPORTED else "❌")
            md.append(f"### Claim {i}: {status_icon} `{c.status.value}` (Confidence: {c.confidence * 100:.0f}%)")
            md.append(f"> **Assertion:** \"{c.claim}\"")
            if c.supporting_source_ids:
                md.append(f"- **Supporting References:** {', '.join(f'`[{sid}]`' for sid in c.supporting_source_ids)}")
            md.append(f"- **Auditor Notes:** {c.reviewer_notes}")
            if c.evidence_snippet and c.evidence_snippet != "None found":
                md.append(f"- **Evidence Context:**\n```text\n{c.evidence_snippet}\n```")
            md.append("")

        return "\n".join(md)


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from mock_team_data import get_mock_research_analyst_output

    console = Console(legacy_windows=False)

    console.print("\n[bold cyan]========================================================================[/bold cyan]")
    console.print("[bold yellow]  🤖 RUNNING CREWAI SOURCE REVIEWER AGENT (STUDENT 3: RAHUL)[/bold yellow]")
    console.print("[bold white]  Multi-Agent Academic Research Assistant Using CrewAI[/bold white]")
    console.print("[bold cyan]========================================================================[/bold cyan]\n")

    # 1. Instantiate the agent
    agent = create_source_reviewer_agent()
    console.print(Panel(
        f"[bold white]Role:[/bold white] {agent.role}\n"
        f"[bold white]Goal:[/bold white] {agent.goal}\n"
        f"[bold white]Active Tools ({len(agent.tools)}):[/bold white]\n" +
        "\n".join(f"  • [green]{t.name}[/green]: [dim]{t.description[:85]}...[/dim]" for t in agent.tools),
        title="🛡️ Agent Profile & Registered Tools",
        border_style="cyan"
    ))

    # 2. Check for LLM keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    has_llm_key = bool(
        (openai_key and not openai_key.startswith("your_")) or
        (groq_key and not groq_key.startswith("your_"))
    )

    raw_input = get_mock_research_analyst_output()
    console.print(f"\n[bold green]📥 Received Research Package from Student 2 (Research Analyst):[/bold green]")
    console.print(f"  • [bold white]Topic:[/bold white] {raw_input.topic}")
    console.print(f"  • [bold white]Candidate Sources:[/bold white] {len(raw_input.sources)}")
    console.print(f"  • [bold white]Assertions to Cross-Examine:[/bold white] {len(raw_input.key_findings)}")

    if has_llm_key:
        console.print("\n[bold green]🔑 LLM API Key detected. Initializing CrewAI Crew orchestration...[/bold green]")
        try:
            from crewai import Crew, Process
            from review_tasks import (
                create_source_evaluation_task,
                create_claim_cross_examination_task,
                create_evidence_synthesis_task
            )
            raw_sources_json = json.dumps([s.model_dump() for s in raw_input.sources], indent=2)
            key_findings_json = json.dumps(raw_input.key_findings, indent=2)

            t1 = create_source_evaluation_task(agent, raw_input.topic, raw_sources_json)
            t2 = create_claim_cross_examination_task(agent, raw_input.topic, key_findings_json, context_task=t1)
            t3 = create_evidence_synthesis_task(agent, raw_input.topic, context_tasks=[t1, t2])

            crew = Crew(
                agents=[agent],
                tasks=[t1, t2, t3],
                process=Process.sequential,
                verbose=True
            )
            console.print("[bold yellow]⚡ Running CrewAI execution (kickoff)...[/bold yellow]")
            crew_result = crew.kickoff()
            console.print(Panel(str(crew_result), title="Crew Output", border_style="green"))
        except Exception as e:
            console.print(f"[bold red]CrewAI execution encountered error: {e}[/bold red]")
            console.print("[dim]Falling back to pipeline execution engine...[/dim]")
            has_llm_key = False

    if not has_llm_key:
        console.print("\n[dim]Executing Source Reviewer Agent verification pipeline...[/dim]\n")
        pipeline = SourceReviewerPipeline(quality_threshold=65.0, relevance_threshold=50.0)
        dossier = pipeline.process_research(raw_input)

        # 1. Sources Evaluation Table
        table_sources = Table(box=box.ROUNDED, title="Source Credibility & Filtering Results")
        table_sources.add_column("ID", style="cyan", width=6)
        table_sources.add_column("Source Title", style="white")
        table_sources.add_column("Domain / Tier", style="blue")
        table_sources.add_column("Score", justify="right", style="magenta")
        table_sources.add_column("Status", justify="center")

        for s in dossier.verified_sources:
            tier_short = s.credibility_tier.value.split(":")[0]
            table_sources.add_row(
                f"[{s.id}]",
                s.title[:45] + "...",
                f"{s.domain} ({tier_short})",
                f"{s.credibility_score:.1f}",
                "[bold green]ACCEPTED[/bold green]"
            )
        for s in dossier.rejected_sources:
            table_sources.add_row(
                f"[{s.id}]",
                s.title[:45] + "...",
                s.domain,
                f"{s.credibility_score:.1f}",
                "[bold red]REJECTED[/bold red]"
            )
        console.print(table_sources)

        # 2. Claim-Evidence Cross-Verification Table
        table_claims = Table(box=box.ROUNDED, title="Claim-Evidence Cross-Examination (Hallucination Defense)")
        table_claims.add_column("Assertion / Finding", style="white", width=42)
        table_claims.add_column("Status", justify="center", width=20)
        table_claims.add_column("Evidence Grounding", style="cyan")
        table_claims.add_column("Conf.", justify="right", style="green", width=8)

        for c in dossier.claim_verifications:
            if c.status == ClaimSupportStatus.SUPPORTED:
                badge = "[bold green]SUPPORTED[/bold green]"
            elif c.status == ClaimSupportStatus.PARTIALLY_SUPPORTED:
                badge = "[bold yellow]PARTIAL[/bold yellow]"
            elif c.status == ClaimSupportStatus.CONTRADICTED:
                badge = "[bold red]CONTRADICTED[/bold red]"
            else:
                badge = "[bold red]UNSUPPORTED (FAKE)[/bold red]"
            sources_tag = f"Sources: {', '.join(c.supporting_source_ids)}" if c.supporting_source_ids else "None"
            table_claims.add_row(
                c.claim,
                badge,
                f"{sources_tag}\n[dim]{c.reviewer_notes[:65]}...[/dim]",
                f"{c.confidence * 100:.0f}%"
            )
        console.print(table_claims)

        # 3. Slide 13 Evaluation Metrics
        table_metrics = Table(box=box.DOUBLE_EDGE, title="Slide 13 Quantitative Evaluation Metrics")
        table_metrics.add_column("Metric Component", style="bold white")
        table_metrics.add_column("Measured Value", style="bold green", justify="center")
        table_metrics.add_column("Target Threshold", style="dim", justify="center")
        table_metrics.add_row("Source Quality (%)", f"{dossier.metrics.source_quality_pct}%", "≥ 75.0%")
        table_metrics.add_row("Relevance Accuracy (%)", f"{dossier.metrics.relevance_accuracy_pct}%", "≥ 60.0%")
        table_metrics.add_row("Verified Sources Count", f"{dossier.metrics.verified_sources_count} sources", "≥ 3 sources")
        table_metrics.add_row("Faithfulness Rate (%)", f"{dossier.metrics.faithfulness_pct}%", "≥ 66.0%")
        table_metrics.add_row("Noise Filtering Ratio (%)", f"{dossier.metrics.noise_filtered_pct}%", "> 0.0%")
        console.print(table_metrics)

        # Save Markdown dossier
        report_filename = "verified_evidence_dossier.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(pipeline.generate_markdown_report(dossier))
        console.print(f"\n[bold green]✨ Verified Evidence Dossier written to [underline]{report_filename}[/underline] for Student 4 (Report Writer)![/bold green]\n")
