"""Final Report Generator & Publication Agent.

Combines outputs from:
  - M1: Research Analyst (Karthik - 23QM1A66B7) -> outputs/m1_research.json
  - M2: Source Reviewer (Rahul - 23QM1A66A2)     -> outputs/m2_review.json
  - M3: Report Writer (Ruthvik - 23QM1A6698 & Kunal - 23QM1A6677) -> outputs/m3_report.json
  - Evaluation Quality Gate (8-Dimension Verification) -> outputs/evaluation.json

Produces:
  - outputs/final_report.json (Complete unified pipeline package)
  - outputs/final_report.pdf  (Authentic IEEE Access 2-column publication PDF)
"""

import sys
import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import pypdf

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from models.schemas import AcademicReport
from services.report_formatter import ReportFormatter


def run(input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute Final Synthesis Agent.
    
    Ingests all prior module outputs, renders the authoritative IEEE publication PDF,
    and writes the comprehensive master package to outputs/final_report.json.
    """
    start_time = time.perf_counter()
    outputs_dir = ROOT_DIR / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" [FINAL AGENT] Multi-Agent Synthesis & Publication Engine")
    print("=" * 70)

    # 1. Ingest M1 Research Data
    m1_data: Dict[str, Any] = {}
    if input_data and "m1" in input_data:
        m1_data = input_data["m1"]
    else:
        m1_file = outputs_dir / "m1_research.json"
        if m1_file.exists():
            print(f"[*] Ingesting M1 Research from {m1_file.name}...")
            with open(m1_file, "r", encoding="utf-8") as f:
                m1_data = json.load(f)
        else:
            print("[!] Warning: outputs/m1_research.json not found.")

    # 2. Ingest M2 Review Data
    m2_data: Dict[str, Any] = {}
    if input_data and "m2" in input_data:
        m2_data = input_data["m2"]
    else:
        m2_file = outputs_dir / "m2_review.json"
        if m2_file.exists():
            print(f"[*] Ingesting M2 Source Review from {m2_file.name}...")
            with open(m2_file, "r", encoding="utf-8") as f:
                m2_data = json.load(f)
        else:
            print("[!] Warning: outputs/m2_review.json not found.")

    # 3. Ingest M3 Report Data
    m3_data: Dict[str, Any] = {}
    if input_data and "m3" in input_data:
        m3_data = input_data["m3"]
    else:
        m3_file = outputs_dir / "m3_report.json"
        if m3_file.exists():
            print(f"[*] Ingesting M3 Academic Report from {m3_file.name}...")
            with open(m3_file, "r", encoding="utf-8") as f:
                m3_data = json.load(f)
        else:
            raise FileNotFoundError(f"Missing {m3_file}! Run M3 Report Writer first.")

    # 4. Ingest Evaluation Data
    eval_data: Dict[str, Any] = {}
    if input_data and "evaluation" in input_data:
        eval_data = input_data["evaluation"]
    else:
        eval_file = outputs_dir / "evaluation.json"
        if eval_file.exists():
            print(f"[*] Ingesting Evaluation Scorecard from {eval_file.name}...")
            with open(eval_file, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
        else:
            print("[!] Warning: outputs/evaluation.json not found.")

    if not eval_data.get("passed", False):
        raise RuntimeError("Publication blocked because the academic quality gate did not pass.")

    expected_topic = str(m1_data.get("topic") or m2_data.get("topic") or "").strip()
    report_topic = str(m3_data.get("topic") or "").strip()
    if expected_topic and report_topic.casefold() != expected_topic.casefold():
        raise RuntimeError(
            f"Publication blocked because report topic '{report_topic}' does not match "
            f"requested topic '{expected_topic}'."
        )

    # 5. Build AcademicReport object for PDF generation
    rep_payload = dict(m3_data)
    if "id" not in rep_payload:
        rep_payload["id"] = "REP-" + uuid.uuid4().hex[:8]
    if "created_at" not in rep_payload:
        rep_payload["created_at"] = datetime.now(timezone.utc).isoformat()
    if "conclusion" not in rep_payload:
        rep_payload["conclusion"] = ""

    academic_report = AcademicReport(**rep_payload)

    # 6. Render IEEE Access Two-Column Publication PDF
    pdf_path = outputs_dir / "final_report.pdf"
    print(f"\n[*] Compiling authentic IEEE Access two-column PDF to {pdf_path.name}...")
    ReportFormatter._generate_ieee_access_pdf(academic_report, pdf_path)

    # Verify PDF and extract statistics
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to generate valid PDF at {pdf_path}")

    reader = pypdf.PdfReader(str(pdf_path))
    actual_page_count = len(reader.pages)
    file_size_kb = round(pdf_path.stat().st_size / 1024, 2)
    final_time = round(time.perf_counter() - start_time, 4)

    # 7. Compute Total Pipeline Latency
    m1_latency = m1_data.get("time_taken_seconds", 0.0)
    m2_latency = m2_data.get("time_taken_seconds", 0.0)
    m3_latency = m3_data.get("time_taken_seconds", 0.0)
    eval_latency = eval_data.get("time_taken_seconds", 0.0)
    total_pipeline_time = round(m1_latency + m2_latency + m3_latency + eval_latency + final_time, 2)

    # 8. Assemble Master outputs/final_report.json
    final_package = {
        "title": "Multi-Agent Academic Research Assistant - Final Publication Report",
        "topic": academic_report.topic,
        "paper_title": academic_report.title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": "COMPLETED_AND_VERIFIED",
        "team_contributions": {
            "M1_Research_Analyst": {
                "owner": "Karthik (23QM1A66B7)",
                "responsibility": "Multi-Source Scientific Literature Discovery & Topic Decomposition",
                "sources_gathered": len(m1_data.get("sources", [])),
                "execution_seconds": m1_latency
            },
            "M2_Source_Reviewer": {
                "owner": "Rahul (23QM1A66A2)",
                "responsibility": "Credibility Tiering, Authority Scoring & Claim-Source Entailment",
                "verified_sources": m2_data.get("verified_sources_count", len(m2_data.get("verified_sources", []))),
                "rejected_sources": m2_data.get("rejected_sources_count", 0),
                "execution_seconds": m2_latency
            },
            "M3_Report_Writer": {
                "owner": "Ruthvik (23QM1A6698) & Kunal (23QM1A6677)",
                "responsibility": "In-Depth Academic Report Synthesis, IEEE Citations & Formatting",
                "sections_count": len(academic_report.sections),
                "word_count": m3_data.get("word_count", sum(len(s.content.split()) for s in academic_report.sections)),
                "execution_seconds": m3_latency
            },
            "Evaluation_Gate": {
                "responsibility": "8-Dimension Deterministic Academic Quality Audit & Scorecard",
                "overall_score": eval_data.get("overall_score", 0.0),
                "grade": eval_data.get("grade", "N/A"),
                "passed": eval_data.get("passed", False),
                "execution_seconds": eval_latency
            },
            "Final_Agent": {
                "responsibility": "Pipeline Integration & IEEE Access Two-Column Layout Rendering",
                "execution_seconds": final_time
            }
        },
        "publication_metrics": {
            "pdf_file": str(pdf_path),
            "pdf_pages": actual_page_count,
            "pdf_size_kb": file_size_kb,
            "citation_style": academic_report.citation_style.value,
            "total_references_cited": len(academic_report.references),
            "overall_evaluation_score": eval_data.get("overall_score", 0.0),
            "overall_evaluation_grade": eval_data.get("grade", "N/A"),
            "total_pipeline_time_seconds": total_pipeline_time
        },
        "m1_research": m1_data,
        "m2_review": m2_data,
        "m3_report": m3_data,
        "evaluation": eval_data
    }

    out_file = outputs_dir / "final_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_package, f, indent=2)

    # 9. Formatted Terminal Summary
    print(f"\n[+] Status: SUCCESS [ALL AGENTS COMPLETE]")
    print(f"[+] Total Pipeline Execution Time: {total_pipeline_time}s")
    print(f"[+] PDF Output: {pdf_path} ({actual_page_count} pages, {file_size_kb} KB)")
    print(f"[+] JSON Master: {out_file}\n")

    print(f"{'Module / Agent':<35} {'Owner / Role':<32} {'Time (s)':<10}")
    print("-" * 77)
    print(f"{'M1: Research Analyst':<35} {'Karthik (23QM1A66B7)':<32} {m1_latency:<10.2f}")
    print(f"{'M2: Source Reviewer':<35} {'Rahul (23QM1A66A2)':<32} {m2_latency:<10.2f}")
    print(f"{'M3: Academic Report Writer':<35} {'Ruthvik & Kunal':<32} {m3_latency:<10.2f}")
    print(f"{'Evaluation Quality Gate':<35} {'8-Dimension Scorecard':<32} {eval_latency:<10.2f}")
    print(f"{'Final Synthesis & PDF':<35} {'IEEE Access Publisher':<32} {final_time:<10.2f}")
    print("-" * 77)
    print(f"{'TOTAL PIPELINE LATENCY':<67} {total_pipeline_time:<10.2f}s\n")

    return final_package


if __name__ == "__main__":
    run()
