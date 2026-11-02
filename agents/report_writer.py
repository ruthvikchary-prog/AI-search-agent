"""
agents/report_writer.py - Module 3: Academic Report Writer Agent
=============================================================================
Owners: Ruthvik (23QM1A6698) & Kunal (23QM1A6677)
Course: Professional Elective - IV (Agentic AI) | Batch 6
Institution: KG Reddy College of Engineering & Technology

Role:
  - Ingests verified evidence from Module 2 (Rahul).
  - Synthesizes publication-grade academic papers strictly grounded in verified sources.
  - Generates Title, Abstract, Keywords, 8 Comprehensive Sections (with subsections),
    Conclusion, and Formatted Bibliographic References.
  - Enforces in-text citation grounding ([1], [2]) without phantom references.

Standalone Usage:
    python agents/report_writer.py

Input:
    outputs/m2_review.json (or passed in-memory from M2)

Output:
    outputs/m3_report.json
=============================================================================
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Union, Dict, Any, List, Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from models.schemas import (
    AcademicReport,
    ResearchSource,
    CitationStyle,
    ReportLength
)
from agents.academic_writer import AcademicWriterAgent

from config import Config

OUTPUTS_DIR = Config.OUTPUTS_DIR
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
M2_INPUT_FILE = OUTPUTS_DIR / "m2_review.json"
M3_OUTPUT_FILE = OUTPUTS_DIR / "m3_report.json"


def _run_crewai_writer_local(
    topic: str,
    sources: List[ResearchSource],
    feedback: Optional[str],
) -> tuple[Optional[AcademicReport], Dict[str, Any]]:
    """Generate a report through a CrewAI Agent/Task and parse its JSON contract."""
    timings: Dict[str, float] = {}
    started = time.monotonic()
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("NVIDIA_NIM_API_KEY"):
        return None, {"mode": "deterministic_fallback", "reason": "No configured LLM credential."}
    try:
        timings["initialization_seconds"] = round(time.monotonic() - started, 3)
        from crewai import Agent, Crew, Process, Task
        from research_analyst import get_llm
        from services.groq import (
            disable_unsupported_cache_breakpoints,
            get_active_model,
            preflight,
        )

        preflight_started = time.monotonic()
        check = preflight()
        timings["preflight_seconds"] = round(time.monotonic() - preflight_started, 3)
        if not check.real_request_ok:
            return None, {"mode": "deterministic_fallback", "reason": f"Groq preflight failed: {check.reason}"}
        os.environ["GROQ_ACTIVE_MODEL"] = check.active_model or check.configured_model
        disable_unsupported_cache_breakpoints()
        writer = AcademicWriterAgent()
        evidence = json.dumps(
            [
                {
                    "id": source.source_id,
                    "title": source.title[:180],
                    "authors": source.authors[:5],
                    "year": source.year,
                    "venue": source.venue,
                    "doi": source.doi,
                    "url": source.url[:240],
                    "evidence": " ".join(source.excerpts)[:650],
                }
                for source in sources
            ],
            ensure_ascii=False,
        )
        llm = get_llm()
        llm.timeout = 60
        agent_started = time.monotonic()
        agent = Agent(
            role="Academic Report Writer",
            goal="Write a distinct, evidence-grounded academic report without unsupported claims or repeated paragraphs.",
            backstory=(
                "You are a scholarly technical writer. You use only the supplied evidence excerpts, "
                "retain uncertainty, and never invent metadata, statistics, results, or citations."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=False,
            max_iter=1,
            max_execution_time=90,
            max_retry_limit=0,
        )
        timings["agent_creation_seconds"] = round(time.monotonic() - agent_started, 3)
        task_started = time.monotonic()
        task = Task(
            description=(
                f"Topic: {topic}\n\nVerified evidence dossier:\n{evidence}\n\n"
                "Return ONLY valid JSON with title, abstract, keywords, sections, conclusion, and references. "
                "Use only sections justified by the evidence, normally including Introduction, Literature Review, "
                "Research Problem and Objectives, Research Methodology, Technical Background, Comparative Analysis, "
                "Results and Discussion, Applications, Challenges and Limitations, Future Scope, and one Conclusion. "
                "Do not duplicate the conclusion as a body section. Write complete paragraphs with enough explanation "
                "to be academically useful; do not pad the report to reach a page count. "
                "Each section must have a different objective and cite only supplied source IDs. "
                "Every factual sentence needs a citation. Do not add numbers, results, authors, DOI, "
                "or publication details unless present in the supplied evidence. References must contain "
                "only cited supplied IDs and exact supplied metadata. "
                f"Additional instructions: {feedback or 'none'}"
            ),
            expected_output="Strict JSON matching the AcademicReport fields.",
            agent=agent,
        )
        result = Crew(
            agents=[agent], tasks=[task], process=Process.sequential, verbose=False
        ).kickoff()
        timings["crewai_task_seconds"] = round(time.monotonic() - task_started, 3)
        # CrewAI encapsulates the provider call; its duration is included in
        # this task timing and cannot be separated without changing CrewAI.
        raw = result.raw or ""
        parse_started = time.monotonic()
        report = writer._parse_json_to_report(
            raw,
            report_id=f"report-{int(time.time())}",
            topic=topic,
            citation_style=CitationStyle.IEEE,
            target_page_count=8,
            sources=sources,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        timings["report_parse_seconds"] = round(time.monotonic() - parse_started, 3)
        timings["total_seconds"] = round(time.monotonic() - started, 3)
        return report, {
            "mode": "crewai",
            "agent": agent.role,
            "model": get_active_model(),
            "timings": timings,
        }
    except Exception as exc:
        timings["total_seconds"] = round(time.monotonic() - started, 3)
        return None, {
            "mode": "deterministic_fallback",
            "reason": f"{type(exc).__name__}: {exc}",
            "timings": timings,
        }


def _run_crewai_writer(
    topic: str,
    sources: List[ResearchSource],
    feedback: Optional[str],
) -> tuple[Optional[AcademicReport], Dict[str, Any]]:
    """Run exactly one M3 CrewAI task in an externally terminable worker."""
    started = time.monotonic()
    payload = {
        "topic": topic,
        "sources": [source.model_dump() for source in sources],
        "feedback": feedback,
    }
    worker = subprocess.Popen(
        [sys.executable, "-m", "agents.m3_worker"],
        cwd=str(ROOT_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = worker.communicate(
            json.dumps(payload, ensure_ascii=False),
            timeout=75,
        )
    except subprocess.TimeoutExpired:
        timeout_started = time.monotonic()
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
        return None, {
            "mode": "deterministic_fallback",
            "reason": "M3 worker exceeded 75-second hard deadline and was terminated.",
            "worker_terminated": True,
            "worker_exit_code": worker.returncode,
            "timings": {
                "parent_worker_seconds": round(time.monotonic() - started, 3),
                "timeout_cleanup_seconds": round(time.monotonic() - timeout_started, 3),
            },
        }

    if worker.returncode != 0:
        return None, {
            "mode": "deterministic_fallback",
            "reason": f"M3 worker exited with code {worker.returncode}: {stderr[-500:]}",
            "worker_terminated": False,
            "worker_exit_code": worker.returncode,
            "timings": {"parent_worker_seconds": round(time.monotonic() - started, 3)},
        }
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
        report_data = result.get("report")
        status = result.get("status", {})
        report = AcademicReport(**report_data) if report_data else None
        status["parent_worker_seconds"] = round(time.monotonic() - started, 3)
        return report, status
    except (ValueError, TypeError, IndexError) as exc:
        return None, {
            "mode": "deterministic_fallback",
            "reason": f"Invalid M3 worker response: {type(exc).__name__}: {exc}",
            "worker_terminated": False,
            "worker_exit_code": worker.returncode,
            "timings": {"parent_worker_seconds": round(time.monotonic() - started, 3)},
        }


def run(input_data: Union[Dict[str, Any], str] = None, feedback: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for Module 3 - Academic Report Writer Agent.
    
    Args:
        input_data: Optional dict matching M2 output schema. If None, loads from outputs/m2_review.json.
        feedback: Optional textual critique/instructions for report refinement.
    Returns:
        dict: Complete academic paper with title, abstract, sections, conclusion, references.
    """
    start_time = time.time()

    # Load input from file if not provided
    if input_data is None:
        if not M2_INPUT_FILE.exists():
            print(f"[M3 WARNING] Previous agent output not found at '{M2_INPUT_FILE}'. Running M2 first...")
            from agents import source_reviewer
            input_data = source_reviewer.run()
        else:
            with open(M2_INPUT_FILE, "r", encoding="utf-8") as f:
                input_data = json.load(f)

    topic = input_data.get("topic", "Agentic AI") if isinstance(input_data, dict) else "Agentic AI"
    verified_sources_data = input_data.get("verified_sources", []) if isinstance(input_data, dict) else []
    feedback_text = feedback or (input_data.get("feedback") if isinstance(input_data, dict) else None)

    print(f"\n[M3 START] Academic Report Writer (Ruthvik & Kunal) starting for topic: '{topic}'")
    if feedback_text:
        print(f"  -> Applying User Improvement Feedback: '{feedback_text}'")
    print(f"  -> Grounding report in {len(verified_sources_data)} verified evidence sources from Rahul's M2...")

    # Transform verified sources to ResearchSource objects
    grounded_sources: List[ResearchSource] = []
    for s in verified_sources_data:
        grounded_sources.append(
            ResearchSource(
                source_id=s.get("id", "SRC-1"),
                title=s.get("title", "Research Source"),
                url=s.get("url", ""),
                authors=s.get("authors", []) or ([s.get("author")] if s.get("author") else []),
                year=int(s.get("published_date")) if s.get("published_date") and str(s.get("published_date")).isdigit() else None,
                venue=s.get("venue") or s.get("domain", ""),
                doi=s.get("doi"),
                excerpts=[x for x in [s.get("abstract"), s.get("snippet", "")] if x],
                credibility_score=round(float(s.get("credibility_score", 80)) / 100.0, 2),
                is_verified=True
            )
        )

    writer = AcademicWriterAgent()
    report, crewai_status = _run_crewai_writer(topic, grounded_sources, feedback_text)
    if report is not None:
        expected_topic = " ".join(topic.lower().split())
        actual_topic = " ".join(report.topic.lower().split())
        if actual_topic != expected_topic:
            crewai_status = {
                "mode": "deterministic_fallback",
                "reason": (
                    f"CrewAI returned topic '{report.topic}' instead of requested "
                    f"topic '{topic}'."
                ),
                "rejected_report_topic": report.topic,
            }
            report = None
    if report is None:
        fallback_started = time.monotonic()
        report = writer._generate_deterministic_report(
            report_id=f"report-{int(time.time())}",
            topic=topic,
            sources=grounded_sources,
            citation_style=CitationStyle.IEEE,
            target_page_count=8,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        crewai_status.setdefault("timings", {})["fallback_seconds"] = round(
            time.monotonic() - fallback_started, 3
        )

    elapsed_time = round(time.time() - start_time, 2)
    crewai_status.setdefault("timings", {})["final_report_seconds"] = elapsed_time
    total_words = sum(len(s.content.split()) for s in report.sections) + len(report.abstract.split()) + len(report.conclusion.split())

    # Compile structured hand-off payload
    result = {
        "owner": "Ruthvik (23QM1A6698) & Kunal (23QM1A6677)",
        "module": "Module 3 - Academic Report Writer Agent",
        "topic": topic,
        "citation_style": report.citation_style.value,
        "target_page_count": report.target_page_count,
        "title": report.title,
        "abstract": report.abstract,
        "keywords": report.keywords,
        "sections": [s.model_dump() for s in report.sections],
        "conclusion": report.conclusion,
        "references": [r.model_dump() for r in report.references],
        "sources_used": report.sources_used,
        "execution_mode": crewai_status["mode"],
        "crewai_status": crewai_status,
        "word_count": total_words,
        "time_taken_seconds": elapsed_time,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Save to outputs/m3_report.json
    with open(M3_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[M3 DONE - {elapsed_time}s] Synthesized {len(report.sections)} sections ({total_words} words).")
    print(f"  -> Citation Style: {report.citation_style.value}")
    print(f"  -> References Formatted: {len(report.references)}")
    print(f"  -> Output saved to: {M3_OUTPUT_FILE}\n")

    return result


if __name__ == "__main__":
    run()
