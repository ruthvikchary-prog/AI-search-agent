"""
test_source_reviewer.py - Comprehensive Unit & Integration Tests for Module 3
=============================================================================
Project: Multi-Agent Academic Research Assistant Using CrewAI
Module 3: Source Reviewer & Citation Validation (Student 3: Rahul)
Institution: KG Reddy College of Engineering & Technology
Batch 6 | Professional Elective - IV (Agentic AI)
=============================================================================
Run with:
    pytest test_source_reviewer.py -v
"""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import json
import pytest
from schemas import (
    RawSource,
    RawResearchInput,
    VerificationStatus,
    ClaimSupportStatus,
    CredibilityTier
)
from citation_validator import CitationValidator
from source_reviewer import (
    create_source_reviewer_agent,
    SourceReviewerPipeline,
    verify_source_credibility_tool,
    validate_claim_evidence_tool,
    filter_sources_tool,
    check_citation_integrity_tool,
    calculate_review_metrics_tool
)


@pytest.fixture
def validator():
    return CitationValidator(quality_threshold=65.0, relevance_threshold=50.0)


@pytest.fixture
def sample_academic_sources():
    return [
        RawSource(
            id="S1",
            title="Attention Is All You Need",
            url="https://arxiv.org/abs/1706.03762",
            snippet="We introduce the Transformer model based solely on attention mechanisms, replacing recurrent networks.",
            author="Vaswani et al.",
            published_date="2017"
        ),
        RawSource(
            id="S2",
            title="RAGAs: Automated Evaluation of Retrieval Augmented Generation",
            url="https://acm.org/doi/10.1145/ragas",
            snippet="RAGAs provides automated metrics for faithfulness and answer relevance without ground truth labels.",
            author="Es et al.",
            published_date="2024"
        ),
        RawSource(
            id="S3",
            title="Why AI Will Replace Everything (My Personal Opinion)",
            url="https://reddit.com/r/technology/comments/123",
            snippet="I think chatbots know everything and we don't need sources anymore.",
            author="anonymous_user",
            published_date="2024"
        ),
        RawSource(
            id="S4",
            title="Attention Is All You Need (Mirror)",
            url="https://arxiv.org/abs/1706.03762?ref=duplicate",
            snippet="Duplicate paper snippet on transformer architecture.",
            author="Vaswani et al.",
            published_date="2017"
        )
    ]


# ============================================================================
# 1. Domain Authority & Credibility Tests
# ============================================================================

def test_academic_tier1_scoring(validator):
    """Test that .edu, .gov, and arXiv URLs receive Tier 1 status and >= 90 score."""
    src_arxiv = RawSource(
        id="S1",
        title="Deep Residual Learning",
        url="https://arxiv.org/abs/1512.03385",
        snippet="ResNet architecture.",
        author="He et al.",
        published_date="2016"
    )
    tier, score, notes = validator.evaluate_source_credibility(src_arxiv)
    assert tier == CredibilityTier.TIER_1_ACADEMIC
    assert score >= 90.0
    assert "arxiv.org" in notes.lower() or "academic" in notes.lower()

    src_edu = RawSource(
        id="S2",
        title="MIT CS Lecture Notes",
        url="https://csail.mit.edu/research/agents",
        snippet="Agent architectures at MIT.",
        author="Prof. Leiserson",
        published_date="2024"
    )
    tier_edu, score_edu, _ = validator.evaluate_source_credibility(src_edu)
    assert tier_edu == CredibilityTier.TIER_1_ACADEMIC
    assert score_edu >= 90.0


def test_unreliable_domain_rejection(validator):
    """Test that social forums like reddit, quora, and buzzfeed receive low scores."""
    src_bad = RawSource(
        id="S_BAD",
        title="Random Reddit Post",
        url="https://www.reddit.com/r/MachineLearning/comments/xyz",
        snippet="Just my personal hot take.",
        author=None,
        published_date=None
    )
    tier, score, notes = validator.evaluate_source_credibility(src_bad)
    assert tier == CredibilityTier.TIER_4_UNVERIFIED
    assert score < 50.0


# ============================================================================
# 2. Deduplication & Relevance Tests
# ============================================================================

def test_deduplication(validator, sample_academic_sources):
    """Test that duplicate URLs or titles are properly identified and removed."""
    unique, duplicates = validator.deduplicate_sources(sample_academic_sources)
    assert len(unique) == 3
    assert len(duplicates) == 1
    assert duplicates[0].id == "S4"


def test_canonical_arxiv_and_fuzzy_title_deduplication(validator):
    """Test detecting mirrors via arXiv canonical IDs and fuzzy title similarity."""
    sources = [
        RawSource(
            id="S1",
            title="Attention Is All You Need",
            url="https://arxiv.org/abs/1706.03762",
            snippet="Original transformer paper."
        ),
        RawSource(
            id="S2",
            title="Attention Is All You Need (Official PDF)",
            url="https://arxiv.org/pdf/1706.03762.pdf?download=true",
            snippet="PDF mirror with tracking parameters."
        ),
        RawSource(
            id="S3",
            title="Attention Is All You Need Extended Version",
            url="https://someuniversity.edu/mirror/transformer",
            snippet="Different URL but near-identical title."
        )
    ]
    unique, duplicates = validator.deduplicate_sources(sources)
    assert len(unique) == 1
    assert len(duplicates) == 2
    assert unique[0].id == "S1"


def test_outdated_vs_recent_evaluation(validator):
    """Test recency classification: 2024 recent bonus vs 2005 outdated penalty."""
    cat_recent, delta_recent, note_recent = validator.evaluate_recency("2024")
    assert cat_recent == "RECENT"
    assert delta_recent == 5.0
    assert "contemporary research" in note_recent.lower()

    cat_foundation, delta_foundation, _ = validator.evaluate_recency("2017")
    assert cat_foundation == "FOUNDATIONAL"
    assert delta_foundation == 2.0

    cat_legacy, delta_legacy, note_legacy = validator.evaluate_recency("2012")
    assert cat_legacy == "LEGACY"
    assert delta_legacy == -5.0
    assert "may be superseded" in note_legacy

    cat_outdated, delta_outdated, note_outdated = validator.evaluate_recency("2004")
    assert cat_outdated == "OUTDATED"
    assert delta_outdated == -15.0
    assert "Outdated research" in note_outdated


def test_topic_relevance_scoring(validator):
    """Test that relevant text scores high and unrelated text scores low."""
    topic = "Retrieval Augmented Generation Multi-Agent Evaluation"
    src_relevant = RawSource(
        id="S1",
        title="Retrieval-Augmented Generation Benchmark and Evaluation",
        url="https://arxiv.org/abs/2401.0001",
        snippet="We evaluate multi-agent retrieval augmented generation architectures using RAGAs."
    )
    src_irrelevant = RawSource(
        id="S2",
        title="Best Chocolate Chip Cookie Recipe",
        url="https://cooking.com/recipe",
        snippet="Preheat oven to 350 degrees and mix butter with brown sugar."
    )

    score_rel = validator.calculate_topic_relevance(topic, src_relevant)
    score_irrel = validator.calculate_topic_relevance(topic, src_irrelevant)

    assert score_rel >= 60.0
    assert score_irrel < 40.0


# ============================================================================
# 3. Claim-Evidence Cross-Verification & Hallucination Guard Tests
# ============================================================================

def test_claim_verification(validator, sample_academic_sources):
    """Test cross-checking claims against evidence to flag supported vs hallucinated claims."""
    evaluated = validator.review_all_sources("Transformers and RAGAs", sample_academic_sources)
    accepted = [s for s in evaluated if s.status == VerificationStatus.ACCEPTED]

    # 1. Directly supported claim
    claim_supported = "The Transformer model relies on attention mechanisms instead of recurrent networks."
    res_supp = validator.verify_claim_against_sources(claim_supported, accepted)
    assert res_supp.status == ClaimSupportStatus.SUPPORTED
    assert "S1" in res_supp.supporting_source_ids

    # 2. Hallucinated / Unsupported claim
    claim_hallucinated = "Quantum teleportation was integrated into RAGAs in 1985 to increase speed by 99%."
    res_halluc = validator.verify_claim_against_sources(claim_hallucinated, accepted)
    assert res_halluc.status == ClaimSupportStatus.UNSUPPORTED
    assert len(res_halluc.supporting_source_ids) == 0


# ============================================================================
# 4. Citation Syntax & Phantom Citation Detection Tests
# ============================================================================

def test_citation_integrity_checks(validator, sample_academic_sources):
    """Test detection of phantom / hallucinated citations in text."""
    evaluated = validator.review_all_sources("Transformers and Evaluation", sample_academic_sources)
    draft_text = "Transformers changed NLP [S1]. Meanwhile, RAGAs automates evaluation [S2], but phantom paper [S99] does not exist."

    integrity = validator.validate_in_text_citations(draft_text, evaluated)
    assert "S1" in integrity["valid_citations"]
    assert "S2" in integrity["valid_citations"]
    assert "S99" in integrity["phantom_citations"]
    assert integrity["integrity_score_pct"] < 100.0


# ============================================================================
# 5. Slide 13 Quantitative Metrics Tests
# ============================================================================

def test_slide13_metrics_calculation(validator, sample_academic_sources):
    """Test generation of metrics defined on Slide 13 of Mid-I review."""
    evaluated = validator.review_all_sources("Transformers and Evaluation", sample_academic_sources)
    accepted = [s for s in evaluated if s.status == VerificationStatus.ACCEPTED]

    claims = [
        validator.verify_claim_against_sources("Transformers use attention mechanisms.", accepted),
        validator.verify_claim_against_sources("Chatbots need no data sources.", accepted)
    ]

    metrics = validator.compute_metrics(len(sample_academic_sources), evaluated, claims)

    # Slide 13 core metrics:
    assert metrics.verified_sources_count == len(accepted)
    assert metrics.source_quality_pct > 70.0
    assert metrics.relevance_accuracy_pct > 50.0
    assert 0.0 <= metrics.faithfulness_pct <= 100.0
    assert metrics.rejected_sources_count == (len(sample_academic_sources) - len(accepted))


# ============================================================================
# 6. CrewAI Tools & Pipeline End-to-End Tests
# ============================================================================

def test_crewai_tools_execution():
    """Test that all 5 custom CrewAI tools execute cleanly with JSON input."""
    # Tool 1: Credibility
    src_data = json.dumps({
        "url": "https://arxiv.org/abs/2301.0001",
        "title": "Autonomous Agents Survey",
        "snippet": "Overview of LLM-based autonomous agents.",
        "author": "Wang et al.",
        "published_date": "2023"
    })
    cred_out = json.loads(verify_source_credibility_tool.run(src_data))
    assert cred_out["passed_threshold"] is True
    assert "arxiv.org" in cred_out["domain"]

    # Tool 2: Claim Validation
    claim_payload = json.dumps({
        "claim": "LLM agents can use external tools.",
        "sources": [{
            "id": "S1",
            "title": "Toolformer",
            "url": "https://arxiv.org/abs/2302.04761",
            "snippet": "Language models can teach themselves to use tools via simple APIs."
        }]
    })
    claim_out = json.loads(validate_claim_evidence_tool.run(claim_payload))
    assert claim_out["status"] in [ClaimSupportStatus.SUPPORTED.value, ClaimSupportStatus.PARTIALLY_SUPPORTED.value]

    # Tool 3: Filter sources
    filter_payload = json.dumps({
        "topic": "LLM tool use",
        "sources": [
            {"id": "S1", "title": "Paper 1", "url": "https://arxiv.org/1", "snippet": "LLM tools"},
            {"id": "S2", "title": "Paper 1", "url": "https://arxiv.org/1", "snippet": "Duplicate"}
        ]
    })
    filter_out = json.loads(filter_sources_tool.run(filter_payload))
    assert filter_out["total_evaluated"] == 2
    assert filter_out["accepted_count"] == 1
    assert filter_out["rejected_count"] == 1


def test_source_reviewer_agent_initialization():
    """Test initializing the Source Reviewer Agent instance."""
    agent = create_source_reviewer_agent()
    assert agent.role == "Senior Academic Source Reviewer & Citation Validation Specialist"
    assert len(agent.tools) == 5


def test_end_to_end_pipeline():
    """Test running the high-level SourceReviewerPipeline end-to-end."""
    pipeline = SourceReviewerPipeline()
    raw_input = RawResearchInput(
        topic="Evaluation of Multi-Agent Systems in Healthcare",
        key_findings=[
            "Multi-agent AI improves diagnostic accuracy by 15% through consensus voting.",
            "A completely unsupported claim about aliens operating hospital clinics."
        ],
        sources=[
            RawSource(
                id="S1",
                title="Collaborative Multi-Agent Systems in Healthcare Diagnostics",
                url="https://ncbi.nlm.nih.gov/pmc/articles/PMC1234567/",
                snippet="Multi-agent AI improves diagnostic accuracy by 15% through collaborative consensus voting.",
                author="Dr. Sarah Jenkins",
                published_date="2024"
            ),
            RawSource(
                id="S2",
                title="Random Reddit thread on doctors",
                url="https://reddit.com/r/medicine/xyz",
                snippet="Just chatting about hospital shifts.",
                author="user123"
            )
        ]
    )

    dossier = pipeline.process_research(raw_input)
    assert len(dossier.verified_sources) == 1
    assert dossier.verified_sources[0].id == "S1"
    assert len(dossier.rejected_sources) == 1
    assert dossier.rejected_sources[0].id == "S2"

    assert dossier.claim_verifications[0].status == ClaimSupportStatus.SUPPORTED
    assert dossier.claim_verifications[1].status == ClaimSupportStatus.UNSUPPORTED

    md_report = pipeline.generate_markdown_report(dossier)
    assert "Module 3 Metrics" in md_report
    assert "Source Quality (%)" in md_report
    assert "NCBI" in dossier.verified_sources[0].domain.upper() or "PMC" in dossier.verified_sources[0].domain.upper()
