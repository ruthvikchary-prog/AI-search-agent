"""Pydantic schemas and models for the Multi-Agent Academic Research Assistant.

Provides data boundaries, validation, and serialization across agents and services.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CitationStyle(str, Enum):
    IEEE = "IEEE"
    APA = "APA"
    MLA = "MLA"
    CHICAGO = "Chicago"
    HARVARD = "Harvard"


class ReportLength(str, Enum):
    BRIEF = "brief"             # ~3-4 pages / ~1500 words
    STANDARD = "standard"       # ~5-7 pages / ~2500 words
    COMPREHENSIVE = "comprehensive"  # ~8-12 pages / ~4000+ words


class SourceType(str, Enum):
    PDF = "pdf"
    WEB = "web"
    TEAMMATE = "teammate"
    MANUAL = "manual"


class ResearchSource(BaseModel):
    """Represents a verified, structured research source with evidence excerpts."""
    source_id: str = Field(description="Unique source identifier, e.g. SRC-1")
    title: str = Field(description="Title of paper, article, or document")
    authors: List[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(default=None, description="Year of publication")
    venue: Optional[str] = Field(default=None, description="Journal, conference, or publisher")
    url: Optional[str] = Field(default=None, description="Direct URL if available")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier if available")
    excerpts: List[str] = Field(default_factory=list, description="Extracted evidence quotes/excerpts")
    credibility_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Heuristic credibility score")
    is_verified: bool = Field(default=True, description="Whether the source underwent verification")
    source_type: SourceType = Field(default=SourceType.WEB, description="Origin of the source")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("source_id cannot be empty")
        return v


class ReportSection(BaseModel):
    """Represents a structured subsection or main section of an academic report."""
    heading: str = Field(description="Section title, e.g. '1. Introduction' or 'Literature Review'")
    level: int = Field(default=1, ge=1, le=4, description="Heading level: 1 (Main), 2 (Sub), etc.")
    content: str = Field(description="Body text containing citations e.g. [SRC-1] or [1]")
    citations: List[str] = Field(default_factory=list, description="Source IDs cited within this section")
    subsections: List["ReportSection"] = Field(default_factory=list, description="Nested child subsections")


class ReferenceEntry(BaseModel):
    """Represents a single bibliographic reference in the References section."""
    source_id: str = Field(description="Associated source ID, e.g. SRC-1")
    citation_number: Optional[int] = Field(default=None, description="Numeric index e.g. [1] for IEEE")
    formatted_text: str = Field(description="Bibliographically formatted reference string")
    url: Optional[str] = Field(default=None)
    doi: Optional[str] = Field(default=None)


class AcademicReport(BaseModel):
    """The complete structured academic report document."""
    id: str = Field(description="Unique report UUID or slug")
    title: str = Field(description="Academic paper title")
    topic: str = Field(description="Underlying research query or topic")
    abstract: str = Field(description="Executive academic abstract (150-300 words)")
    keywords: List[str] = Field(default_factory=list, description="Key indexing terms (3-7 keywords)")
    sections: List[ReportSection] = Field(default_factory=list, description="Main paper body sections")
    conclusion: str = Field(description="Concluding remarks, limitations, and future outlook")
    references: List[ReferenceEntry] = Field(default_factory=list, description="Bibliographic reference entries")
    citation_style: CitationStyle = Field(default=CitationStyle.IEEE)
    target_page_count: int = Field(default=5, ge=1, le=30)
    sources_used: List[str] = Field(default_factory=list, description="List of source IDs utilized")
    created_at: str = Field(description="ISO timestamp")


class CitationValidationResult(BaseModel):
    """Deterministic validation results for citations and references."""
    is_valid: bool = Field(description="True if citation rules and grounding pass")
    resolved_citations: List[str] = Field(default_factory=list, description="Citations correctly mapped to sources")
    unresolved_citations: List[str] = Field(default_factory=list, description="In-text citations with no known source")
    unused_sources: List[str] = Field(default_factory=list, description="Sources in bibliography never cited")
    fabricated_references: List[str] = Field(default_factory=list, description="References with no matching research source")
    formatting_errors: List[str] = Field(default_factory=list, description="Style discrepancies or syntax issues")
    unsupported_claims: List[str] = Field(default_factory=list, description="Claims lacking grounded evidence excerpts")
    details: List[str] = Field(default_factory=list, description="Diagnostic human-readable log")


class EvaluationDimension(BaseModel):
    """Individual grading dimension in the academic report evaluation scorecard."""
    name: str = Field(description="Dimension name (e.g. 'Evidence Support', 'Citation Consistency')")
    score: float = Field(ge=0.0, le=100.0, description="Numerical score from 0 to 100")
    weight: float = Field(ge=0.0, le=1.0, description="Relative weight in final calculation")
    passed: bool = Field(description="True if score >= dimension threshold")
    feedback: str = Field(description="Actionable explanation of the score")


class EvaluationReport(BaseModel):
    """Comprehensive multi-dimensional evaluation report."""
    overall_score: float = Field(ge=0.0, le=100.0, description="Weighted composite score")
    passed: bool = Field(description="Whether the report meets the academic quality threshold")
    dimensions: List[EvaluationDimension] = Field(default_factory=list)
    critical_errors: List[str] = Field(default_factory=list, description="Fatal errors blocking report approval")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings for improvement")
    suggested_corrections: List[str] = Field(default_factory=list, description="Specific feedback for the writer")
    correction_attempt: int = Field(default=0, ge=0, description="Current correction iteration (max 3)")


class WorkflowStage(str, Enum):
    IDLE = "idle"
    INPUT_VALIDATION = "input_validation"
    PDF_EXTRACTION = "pdf_extraction"
    RESEARCH_COLLECTION = "research_collection"
    SOURCE_VERIFICATION = "source_verification"
    ACADEMIC_WRITING = "academic_writing"
    CITATION_VALIDATION = "citation_validation"
    QUALITY_EVALUATION = "quality_evaluation"
    CORRECTION_LOOP = "correction_loop"
    FORMATTING_EXPORT = "formatting_export"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowJob(BaseModel):
    """Tracks background multi-agent execution status."""
    job_id: str
    stage: WorkflowStage = WorkflowStage.IDLE
    stage_label: str = "Initialized"
    status: str = "pending"  # pending, running, completed, failed
    progress: int = 0         # 0 - 100%
    message: str = "Job created"
    error: Optional[str] = None
    report_id: Optional[str] = None
    evaluation: Optional[EvaluationReport] = None
    pdf_filename: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class NewReportRequest(BaseModel):
    """User input for generating a brand new academic report."""
    topic: str = Field(min_length=3, max_length=500, description="Research topic or question")
    length: ReportLength = Field(default=ReportLength.STANDARD)
    target_page_count: int = Field(default=5, ge=1, le=25)
    citation_style: CitationStyle = Field(default=CitationStyle.IEEE)
    source_preference: str = Field(default="both", description="'uploaded_only', 'online_only', 'both', 'teammate'")
    additional_text: Optional[str] = Field(default="", max_length=50000)


class ImproveReportRequest(BaseModel):
    """User input for enhancing and revising an existing report."""
    report_text: str = Field(min_length=50, description="Raw text or markdown of existing report")
    citation_style: CitationStyle = Field(default=CitationStyle.IEEE)
    preserve_findings: bool = Field(default=True, description="Strictly preserve original findings and topic")
    additional_sources: Optional[str] = Field(default="", description="Optional additional source text or JSON")


class TeammateResearchSubmission(BaseModel):
    """Payload format for connected teammate agents providing external research."""
    agent_name: str = Field(min_length=2, description="Name or identifier of teammate agent")
    topic: str = Field(min_length=3)
    sources: List[ResearchSource] = Field(min_length=1, description="List of structured research sources")
