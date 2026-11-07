"""
schemas.py - Data Contracts & Pydantic Models
=============================================================================
Project: Multi-Agent Academic Research Assistant Using CrewAI
Module 3: Source Reviewer & Citation Validation (Student 3)
Institution: KG Reddy College of Engineering & Technology
Batch 6 | Professional Elective - IV (Agentic AI)
=============================================================================
This module defines the strict data schemas used across the multi-agent pipeline.
It standardizes inputs from Student 2 (Research Analyst) and formats outputs
for Student 4 (Academic Report Writer).
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class CredibilityTier(str, Enum):
    """Authority and credibility classification tiers for web sources."""
    TIER_1_ACADEMIC = "Tier 1: Peer-Reviewed / Academic / Government (Highest)"
    TIER_2_AUTHORITATIVE = "Tier 2: Recognized Tech / Industry Standard (High)"
    TIER_3_GENERAL = "Tier 3: General Media / Informational (Moderate)"
    TIER_4_UNVERIFIED = "Tier 4: Blogs / Forums / Low Authority (Rejected/Flagged)"


class VerificationStatus(str, Enum):
    """Verification outcome for an evaluated source."""
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNSUPPORTED = "UNSUPPORTED"
    ACCEPTED = "VERIFIED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class ClaimSupportStatus(str, Enum):
    """Natural Language Inference status matching a claim to its evidence."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# ============================================================================
# Inputs from Student 2 (Research Analyst)
# ============================================================================

class RawSource(BaseModel):
    """Source item collected by Student 2 (Research Analyst)."""
    id: str = Field(description="Unique source identifier (e.g. S1, S2)")
    title: str = Field(description="Title of the research paper, article or webpage")
    url: str = Field(description="Direct URL link to the source")
    snippet: str = Field(description="Content excerpt or abstract extracted by the search agent")
    author: Optional[str] = Field(default=None, description="Author or publishing institution")
    published_date: Optional[str] = Field(default=None, description="Publication year or date")
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    metadata_status: str = "unavailable"


class RawResearchInput(BaseModel):
    """Complete research payload handed off by Student 2 to Student 3."""
    topic: str = Field(description="The research topic / query entered by the user")
    key_findings: List[str] = Field(default_factory=list, description="Extracted facts, trends, and claims")
    sources: List[RawSource] = Field(default_factory=list, description="List of raw sources discovered")


# ============================================================================
# Evaluated Data Structures (Student 3 internal & outputs)
# ============================================================================

class EvaluatedSource(BaseModel):
    """Enriched source object after credibility, metadata, and relevance analysis."""
    id: str
    title: str
    url: str
    domain: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    credibility_tier: CredibilityTier
    credibility_score: float = Field(ge=0.0, le=100.0, description="Credibility rating (0-100)")
    relevance_score: float = Field(ge=0.0, le=100.0, description="Semantic/keyword relevance to topic (0-100)")
    status: VerificationStatus
    status_reason: str = Field(description="Justification for acceptance or rejection")
    snippet: str
    doi: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    abstract: Optional[str] = None
    metadata_status: str = "unavailable"
    verification_evidence: List[str] = Field(default_factory=list)


class ClaimVerificationResult(BaseModel):
    """Cross-examination result of a specific research claim against evidence."""
    claim: str
    status: ClaimSupportStatus
    supporting_source_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, description="Verification confidence score (0.0 to 1.0)")
    evidence_snippet: str = Field(description="Specific excerpt from source proving or disproving claim")
    reviewer_notes: str = Field(description="Analytical explanation or hallucination alert")


class Module3Metrics(BaseModel):
    """
    Quantitative metrics required for evaluation.
    Directly addresses Mid-I Review Slide 13 (Module Metrics) and Literature Survey benchmarks.
    """
    total_sources_received: int
    verified_sources_count: int = Field(description="Slide 13: Verified sources count")
    rejected_sources_count: int
    source_quality_pct: float = Field(ge=0.0, le=100.0, description="Slide 13: Source quality (%)")
    relevance_accuracy_pct: float = Field(ge=0.0, le=100.0, description="Slide 13: Relevance accuracy (%)")
    faithfulness_pct: float = Field(ge=0.0, le=100.0, description="RAGAs/CCF benchmark: Claims supported (%)")
    noise_filtered_pct: float = Field(ge=0.0, le=100.0, description="MIRAGE benchmark: Noise reduction (%)")


class VerifiedEvidenceDossier(BaseModel):
    """
    The final verified package delivered to Student 4 (Academic Report Writer).
    Guarantees no unverified claims or broken citations reach the final paper.
    """
    topic: str
    summary_of_evidence: str
    verified_sources: List[EvaluatedSource]
    rejected_sources: List[EvaluatedSource]
    claim_verifications: List[ClaimVerificationResult]
    metrics: Module3Metrics
