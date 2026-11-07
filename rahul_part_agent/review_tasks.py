"""
review_tasks.py - CrewAI Tasks for Source Review & Citation Validation
=============================================================================
Project: Multi-Agent Academic Research Assistant Using CrewAI
Module 3: Source Reviewer & Citation Validation (Student 3: Rahul)
Institution: KG Reddy College of Engineering & Technology
Batch 6 | Professional Elective - IV (Agentic AI)
=============================================================================
Defines specialized CrewAI Task definitions:
  1. Source Evaluation & Deduplication Task
  2. Claim-Evidence Cross-Examination & Hallucination Detection Task
  3. Evidence Synthesis & Quantitative Metrics Task
"""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from typing import Optional, Dict, Any, List
try:
    from crewai import Task, Agent
except Exception:
    Task = Agent = None


def create_source_evaluation_task(
    agent: Agent,
    topic: str,
    raw_sources_json: str
) -> Task:
    """
    Task 1: Evaluates raw sources collected by Student 2 (Research Analyst).
    Checks domain authority, author credibility, publication dates, and removes duplicates.
    """
    description = f"""
    You are evaluating candidate web sources retrieved for the research topic: "{topic}".
    Raw Sources Payload:
    {raw_sources_json}

    INSTRUCTIONS:
    1. Use the 'Filter Duplicate and Low Quality Sources Tool' and 'Verify Source Credibility Tool'.
    2. Assess domain authority (.edu, .gov, arXiv, IEEE, ACM, Nature get Tier 1; top tech labs get Tier 2; blogs/forums get rejected).
    3. Remove any duplicate URLs, mirror articles, or unverified personal blog posts.
    4. Reject sources that fall below the minimum credibility threshold (65.0 pts) or relevance threshold (50.0%).
    5. Formulate a list of approved, verified sources and a list of rejected sources with clear justifications.
    """

    expected_output = """
    A structured report containing:
    - Total sources evaluated, accepted count, and rejected count.
    - List of Approved Sources with ID, domain, credibility tier, and quality score.
    - List of Rejected Sources with specific disqualification reasons (e.g. low authority, duplicate, off-topic).
    """

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent
    )


def create_claim_cross_examination_task(
    agent: Agent,
    topic: str,
    key_findings_json: str,
    context_task: Optional[Task] = None
) -> Task:
    """
    Task 2: Cross-examines individual assertions, facts, and statistics against
    verified source evidence to eliminate AI hallucinations and ungrounded statements.
    """
    description = f"""
    Cross-examine the following key findings and claims extracted for topic: "{topic}".
    Claims to inspect:
    {key_findings_json}

    INSTRUCTIONS:
    1. Cross-reference each claim against the excerpts of approved sources from the previous evaluation.
    2. Use the 'Validate Claim Evidence Tool' to test every assertion.
    3. Determine the support status for each claim:
       - SUPPORTED: directly confirmed by verified source excerpt.
       - PARTIALLY_SUPPORTED: general concept found, but specific metric or detail unconfirmed.
       - UNSUPPORTED: no evidence in sources (Hallucination Alert).
       - CONTRADICTED: evidence directly refutes the claim.
    4. For any unsupported claim, flag it with an explicit Hallucination Warning so the Academic Writer omits it.
    """

    expected_output = """
    A detailed cross-examination table for each claim:
    - Claim text
    - Verification Status (SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED)
    - Supporting Source IDs (e.g. [S1], [S2])
    - Specific evidence quote or excerpt
    - Confidence score (0.0 to 1.0) and reviewer notes.
    """

    task_kwargs: Dict[str, Any] = {
        "description": description,
        "expected_output": expected_output,
        "agent": agent
    }
    if context_task is not None:
        task_kwargs["context"] = [context_task]

    return Task(**task_kwargs)


def create_evidence_synthesis_task(
    agent: Agent,
    topic: str,
    context_tasks: Optional[List[Task]] = None
) -> Task:
    """
    Task 3: Synthesizes the finalized 'Verified Evidence Dossier' and computes
    quantitative metrics matching Mid-I Review Slide 13.
    """
    description = f"""
    Synthesize the final verified evidence dossier for topic: "{topic}".

    INSTRUCTIONS:
    1. Use the 'Calculate Review Metrics Tool' to compute formal evaluation metrics:
       - Source Quality (%) [Slide 13]
       - Relevance Accuracy (%) [Slide 13]
       - Verified Sources Count [Slide 13]
       - Faithfulness Rate (%) [RAGAs benchmark]
       - Noise Filtering Ratio (%) [MIRAGE benchmark]
    2. Compile a clean, authenticated Markdown Dossier containing:
       - Verified Sources Catalog (ready for IEEE/APA citation mapping).
       - Verified Claims with exact source attribution tags (e.g. [S1], [S2]).
       - Quality & Reliability Audit Summary.
    3. Ensure this dossier provides clean, hallucination-free input for Student 4 (Academic Report Writer).
    """

    expected_output = """
    A comprehensive Markdown Verified Evidence Dossier including:
    - Executive Evidence Summary
    - Slide 13 Metrics Table (Source Quality %, Relevance Accuracy %, Verified Count)
    - Verified Sources Table with URLs, domains, and credibility tiers
    - Grounded Claims Section with citation mapping keys
    - Audit Trail of filtered/rejected sources.
    """

    task_kwargs: Dict[str, Any] = {
        "description": description,
        "expected_output": expected_output,
        "agent": agent
    }
    if context_tasks:
        task_kwargs["context"] = context_tasks

    return Task(**task_kwargs)
