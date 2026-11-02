"""
agents/source_reviewer.py - Module 2: Source Reviewer & Citation Validator
=============================================================================
Owner: Rahul (23QM1A66A2)
Course: Professional Elective - IV (Agentic AI) | Batch 6
Institution: KG Reddy College of Engineering & Technology

Role:
  - 4-Tier domain credibility auditing (Tier 1: Peer-reviewed, Tier 2: Preprints, etc.).
  - Duplicate source purging & noise filtering.
  - Claim cross-examination (NLI support / contradiction / unverified checking).
  - Calculates formal verification metrics (Source Quality %, Relevance Accuracy %, Faithfulness %).

Standalone Usage:
    python agents/source_reviewer.py

Input:
    outputs/m1_research.json (or passed in-memory from M1)

Output:
    outputs/m2_review.json
=============================================================================
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Union, Dict, Any, List

# Ensure project root and rahul_part_agent are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
RAHUL_DIR = ROOT_DIR / "rahul_part_agent"

if str(RAHUL_DIR) not in sys.path:
    sys.path.insert(0, str(RAHUL_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from rahul_part_agent.schemas import (
    RawSource,
    RawResearchInput,
    VerifiedEvidenceDossier,
    VerificationStatus
)
from rahul_part_agent.source_reviewer import SourceReviewerPipeline


def _run_crewai_review(topic: str, raw_input: RawResearchInput) -> Dict[str, Any]:
    """Run the CrewAI reviewer as an advisory pass before deterministic gates."""
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("NVIDIA_NIM_API_KEY"):
        return {"mode": "deterministic_fallback", "reason": "No configured LLM credential."}
    try:
        from crewai import Crew, Process
        from research_analyst import get_llm
        from services.groq import (
            disable_unsupported_cache_breakpoints,
            get_active_model,
            preflight,
        )
        from rahul_part_agent.review_tasks import (
            create_source_evaluation_task,
        )
        from rahul_part_agent.source_reviewer import create_source_reviewer_agent

        check = preflight()
        if not check.real_request_ok:
            return {"mode": "deterministic_fallback", "reason": f"Groq preflight failed: {check.reason}"}
        os.environ["GROQ_ACTIVE_MODEL"] = check.active_model or check.configured_model
        disable_unsupported_cache_breakpoints()
        # Deterministic validation below owns source acceptance and claim
        # safety. The CrewAI pass is intentionally one bounded reviewer call
        # with no tools, avoiding repeated malformed JSON tool retries.
        agent = create_source_reviewer_agent(
            llm_instance=get_llm(),
            include_tools=False,
        )
        compact_sources = [
            {
                "id": source.id,
                "title": source.title[:180],
                "url": source.url[:240],
                "snippet": source.snippet[:500],
                "author": source.author,
                "published_date": source.published_date,
                "doi": source.doi,
            }
            for source in raw_input.sources[:5]
        ]
        raw_json = json.dumps(
            {
                "topic": raw_input.topic,
                "sources": compact_sources,
            },
            ensure_ascii=False,
        )
        evaluation = create_source_evaluation_task(agent, topic, raw_json)
        Crew(
            agents=[agent],
            tasks=[evaluation],
            process=Process.sequential,
            verbose=False,
            cache=False,
        ).kickoff()
        return {"mode": "crewai", "agent": agent.role, "model": get_active_model()}
    except Exception as exc:
        return {"mode": "deterministic_fallback", "reason": f"{type(exc).__name__}: {exc}"}

OUTPUTS_DIR = ROOT_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
M1_INPUT_FILE = OUTPUTS_DIR / "m1_research.json"
M2_OUTPUT_FILE = OUTPUTS_DIR / "m2_review.json"


def run(input_data: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
    """
    Main entry point for Module 2 - Source Reviewer Agent.
    
    Args:
        input_data: Optional dict matching M1 output schema. If None, loads from outputs/m1_research.json.
    Returns:
        dict: Verified evidence dossier with verified/rejected sources, claim checks, and metrics.
    """
    start_time = time.time()

    # Load input from file if not passed directly in-memory
    if input_data is None:
        if not M1_INPUT_FILE.exists():
            print(f"[M2 WARNING] Previous agent output not found at '{M1_INPUT_FILE}'. Running M1 first...")
            from agents import research_analyst
            input_data = research_analyst.run()
        else:
            with open(M1_INPUT_FILE, "r", encoding="utf-8") as f:
                input_data = json.load(f)

    # Extract topic, sources, and findings from input
    topic = input_data.get("topic", "Agentic AI")
    raw_sources_data = input_data.get("sources", [])
    findings_data = input_data.get("findings", [])

    print(f"\n[M2 START] Source Reviewer Agent (Rahul) starting for topic: '{topic}'")
    print(f"  -> Ingesting {len(raw_sources_data)} candidate sources from Karthik's M1 Research Analyst...")

    # Convert to Rahul's schemas
    raw_sources: List[RawSource] = []
    for idx, s in enumerate(raw_sources_data):
        raw_sources.append(
            RawSource(
                id=f"SRC-{idx + 1}",
                title=s.get("title", f"Source {idx + 1}"),
                url=s.get("url", ""),
                snippet=s.get("snippet", ""),
                author=", ".join(s.get("authors", [])) or s.get("author"),
                published_date=s.get("published") or s.get("published_date"),
                authors=s.get("authors", []),
                venue=s.get("venue"),
                doi=s.get("doi"),
                abstract=s.get("abstract"),
                metadata_status=s.get("metadata_status", "unavailable"),
            )
        )

    key_findings: List[str] = []
    for f in findings_data:
        sub = f.get("subtopic", "Finding")
        summ = f.get("summary", "")
        key_findings.append(f"{sub}: {summ}")

    raw_input = RawResearchInput(
        topic=topic,
        sources=raw_sources,
        key_findings=key_findings
    )

    print(f"  -> Auditing credibility against 4 domain authority tiers and cross-examining claims...")
    crewai_status = _run_crewai_review(topic, raw_input)
    pipeline = SourceReviewerPipeline(quality_threshold=65.0, relevance_threshold=50.0)
    dossier: VerifiedEvidenceDossier = pipeline.process_research(raw_input)

    verified_sources_list = [s.model_dump() for s in dossier.verified_sources]
    rejected_sources_list = [s.model_dump() for s in dossier.rejected_sources]

    elapsed_time = round(time.time() - start_time, 2)

    # Compile structured hand-off payload
    metrics_dump = dossier.metrics.model_dump()
    result = {
        "owner": "Rahul (23QM1A66A2)",
        "module": "Module 2 - Source Reviewer Agent",
        "topic": topic,
        "total_candidate_sources": len(raw_sources),
        "verified_sources_count": len(verified_sources_list),
        "rejected_sources_count": len(rejected_sources_list),
        "verified_sources": verified_sources_list,
        "rejected_sources": rejected_sources_list,
        "claim_verifications": [c.model_dump() for c in dossier.claim_verifications],
        "summary_of_evidence": dossier.summary_of_evidence,
        "metrics": metrics_dump,
        "execution_mode": (
            "crewai+deterministic_post_validation"
            if crewai_status["mode"] == "crewai"
            else "deterministic_fallback"
        ),
        "crewai_status": crewai_status,
        "time_taken_seconds": elapsed_time,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Save to outputs/m2_review.json
    with open(M2_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[M2 DONE - {elapsed_time}s] Verified {len(verified_sources_list)} sources (Rejected {len(rejected_sources_list)} noise/weak sources).")
    print(f"  -> Source Quality: {metrics_dump.get('source_quality_pct', 0)}%")
    print(f"  -> Relevance Accuracy: {metrics_dump.get('relevance_accuracy_pct', 0)}%")
    print(f"  -> Faithfulness Rate: {metrics_dump.get('faithfulness_pct', 0)}%")
    print(f"  -> Output saved to: {M2_OUTPUT_FILE}\n")

    return result


if __name__ == "__main__":
    run()
