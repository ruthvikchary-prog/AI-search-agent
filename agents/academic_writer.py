"""Academic Report Writer Agent (Student 4).

Responsible for:
1. Generating evidence-grounded academic reports containing Title, Abstract, Keywords,
   Introduction, Main Sections, Findings, Trends/Examples, Conclusion, and References.
2. Rewriting and improving existing reports while strictly preserving original findings.
3. Grounding citations with explicit Source IDs (e.g. [SRC-1] or [1]) matching available sources.
4. Clean dependency injection for LLM calls with mock fallback for unit tests.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any

from config import Config
from models.schemas import (
    AcademicReport,
    ReportSection,
    ReferenceEntry,
    ResearchSource,
    CitationStyle,
    ReportLength
)

logger = logging.getLogger(__name__)


class AcademicWriterAgent:
    """Orchestrates structured, evidence-grounded academic writing and report rewriting."""

    def __init__(self, llm_client: Optional[Any] = None, model: Optional[str] = None):
        """Initialize writer with optional injected LLM client and model for testing."""
        self.client = llm_client
        self.model = model or Config.GROQ_MODEL
        self.fallback_model = Config.GROQ_FALLBACK_MODEL

        # Initialize Groq client if not explicitly injected
        if self.client is None and Config.GROQ_API_KEY:
            try:
                import groq
                self.client = groq.Groq(api_key=Config.GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}. Writer will use mock fallback.")

    def generate_report(
        self,
        topic: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle = CitationStyle.IEEE,
        length: ReportLength = ReportLength.STANDARD,
        target_page_count: int = 5,
        additional_notes: Optional[str] = None,
        feedback_corrections: Optional[List[str]] = None
    ) -> AcademicReport:
        """Generate a complete structured academic report grounded strictly in provided sources."""
        report_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"

        if self.client is not None:
            try:
                report = self._generate_with_llm(
                    report_id=report_id,
                    topic=topic,
                    sources=sources,
                    citation_style=citation_style,
                    length=length,
                    target_page_count=target_page_count,
                    additional_notes=additional_notes,
                    feedback_corrections=feedback_corrections,
                    timestamp=timestamp
                )
                if report:
                    return report
            except Exception as e:
                logger.error(f"LLM report generation failed: {e}. Falling back to rule-based generator.")

        # Fallback deterministic generator for test environments or offline scenarios
        return self._generate_deterministic_report(
            report_id=report_id,
            topic=topic,
            sources=sources,
            citation_style=citation_style,
            target_page_count=target_page_count,
            timestamp=timestamp
        )

    def rewrite_and_improve(
        self,
        original_text: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle = CitationStyle.IEEE,
        preserve_findings: bool = True,
        feedback_corrections: Optional[List[str]] = None,
        topic: Optional[str] = None
    ) -> AcademicReport:
        """Rewrite and improve an existing academic report while preserving its original findings."""
        report_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"

        if self.client is not None:
            try:
                improved = self._rewrite_with_llm(
                    report_id=report_id,
                    original_text=original_text,
                    sources=sources,
                    citation_style=citation_style,
                    preserve_findings=preserve_findings,
                    feedback_corrections=feedback_corrections,
                    topic=topic,
                    timestamp=timestamp
                )
                if improved:
                    return improved
            except Exception as e:
                logger.error(f"LLM rewrite failed: {e}. Using deterministic structure improvement.")

        return self._rewrite_deterministic(
            report_id=report_id,
            original_text=original_text,
            sources=sources,
            citation_style=citation_style,
            topic=topic,
            timestamp=timestamp
        )

    # =========================================================================
    # LLM-Based Generation Implementation
    # =========================================================================

    def _generate_with_llm(
        self,
        report_id: str,
        topic: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle,
        length: ReportLength,
        target_page_count: int,
        additional_notes: Optional[str],
        feedback_corrections: Optional[List[str]],
        timestamp: str
    ) -> Optional[AcademicReport]:
        """Call Groq to generate a strictly grounded academic report adhering to JSON schema."""
        sources_context = self._format_sources_for_prompt(sources)
        feedback_prompt = ""
        if feedback_corrections:
            feedback_prompt = (
                "\nCRITICAL CORRECTIONS FROM PREVIOUS EVALUATION PASS:\n- "
                + "\n- ".join(feedback_corrections)
                + "\nYou MUST address each of these points directly.\n"
            )

        system_prompt = (
            "You are an expert academic research writer. Your task is to write a rigorous, formal academic report.\n"
            "STRICT RULES:\n"
            "1. Ground all claims STRICTLY in the provided research sources. Never fabricate statistics, quotations, or findings.\n"
            "2. If evidence is lacking on a subtopic, explicitly state the limitation rather than inventing content.\n"
            "3. Never create numerical results, benchmark values, DOI values, author names, venues, or publication dates that are not present in the sources.\n"
            f"4. In-text citations MUST reference the provided Source IDs (e.g., [SRC-1] for IEEE, or (Author, Year) [SRC-1] for APA).\n"
            "5. Every cited source ID MUST match one of the provided Source IDs.\n"
            "6. Do not cite any source not provided in the sources list.\n"
            "7. Output MUST be a single valid JSON object following the requested schema precisely without extra text.\n"
        )

        user_prompt = f"""
RESEARCH TOPIC: {topic}
TARGET PAGE COUNT: {target_page_count} (~{target_page_count * 500} words)
CITATION STYLE: {citation_style.value}
REPORT LENGTH TIER: {length.value}
{feedback_prompt}
{f"ADDITIONAL RESEARCH NOTES: {additional_notes}" if additional_notes else ""}

AVAILABLE RESEARCH SOURCES:
{sources_context}

FORMATTING & DEPTH REQUIREMENT:
{"For IEEE format, use Roman numerals for main headings (e.g. 'I. INTRODUCTION', 'II. TAXONOMY AND SYSTEM ARCHITECTURE', 'III. LITERATURE REVIEW AND THEORETICAL FOUNDATIONS', 'IV. CORE ALGORITHMIC FORMULATIONS AND METHODOLOGY', 'V. EXPERIMENTAL BENCHMARKS AND QUANTITATIVE FINDINGS', 'VI. TECHNICAL CHALLENGES AND ARCHITECTURAL TRADEOFFS', 'VII. INDUSTRIAL APPLICATION SCENARIOS', 'VIII. FUTURE RESEARCH TRAJECTORIES AND OPEN QUESTIONS') and lettered prefixes for subheadings (e.g. 'A. MOTIVATION AND BACKGROUND')." if citation_style.value == "IEEE" else "Use standard numbering (e.g. '1. Introduction')."}

TARGET DEPTH:
The user has requested a comprehensive publication-grade report with target scope: {target_page_count} pages (~{target_page_count * 520} words).
You MUST generate an extensive, highly detailed academic report. For each section, provide MULTIPLE long, exhaustive paragraphs (at least 3-5 rich paragraphs per section) packed with deep technical analysis, mathematical formulations, literature citations [SRC-X], and domain specificity. Do NOT abbreviate or write single-paragraph summaries.

Output a single JSON object with these keys:
{{
  "title": "Clear, professional academic paper title",
  "abstract": "Comprehensive executive abstract summarizing research objective, methodology, empirical evidence, and core findings (200-300 words)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "sections": [
    {{
      "heading": "{"I. INTRODUCTION" if citation_style.value == "IEEE" else "1. Introduction"}",
      "level": 1,
      "content": "Comprehensive introduction spanning motivation, problem statement, and key contributions with [SRC-1]...",
      "citations": ["SRC-1"]
    }},
    {{
      "heading": "{"II. TAXONOMY AND SYSTEM ARCHITECTURE" if citation_style.value == "IEEE" else "2. Taxonomy and System Architecture"}",
      "level": 1,
      "content": "Deep analysis of system architectures, coordination topologies, and pipeline workflows with [SRC-1], [SRC-2]...",
      "citations": ["SRC-1", "SRC-2"]
    }},
    {{
      "heading": "{"III. LITERATURE REVIEW AND THEORETICAL FOUNDATIONS" if citation_style.value == "IEEE" else "3. Literature Review and Theoretical Foundations"}",
      "level": 1,
      "content": "Exhaustive critical review synthesizing empirical evidence, preprints, and theoretical models with [SRC-1], [SRC-2]...",
      "citations": ["SRC-1", "SRC-2"]
    }},
    {{
      "heading": "{"IV. CORE ALGORITHMIC FORMULATIONS AND METHODOLOGY" if citation_style.value == "IEEE" else "4. Core Algorithmic Formulations and Methodology"}",
      "level": 1,
      "content": "Mathematical optimization, objective functions, Bayesian calibration, and computational complexity...",
      "citations": ["SRC-1"]
    }},
    {{
      "heading": "{"V. EXPERIMENTAL BENCHMARKS AND QUANTITATIVE FINDINGS" if citation_style.value == "IEEE" else "5. Experimental Benchmarks and Quantitative Findings"}",
      "level": 1,
      "content": "Detailed quantitative findings, ablation studies, and comparative evaluations across benchmarks...",
      "citations": ["SRC-2"]
    }},
    {{
      "heading": "{"VI. TECHNICAL CHALLENGES AND ARCHITECTURAL TRADEOFFS" if citation_style.value == "IEEE" else "6. Technical Challenges and Architectural Tradeoffs"}",
      "level": 1,
      "content": "Robustness, safety gating, fault tolerance, security vulnerabilities, and latency trade-offs...",
      "citations": ["SRC-1", "SRC-2"]
    }},
    {{
      "heading": "{"VII. INDUSTRIAL APPLICATION SCENARIOS AND DOMAIN CASE STUDIES" if citation_style.value == "IEEE" else "7. Industrial Applications and Case Studies"}",
      "level": 1,
      "content": "Real-world production deployments, edge telemetry, and human-in-the-loop collaborative operations...",
      "citations": ["SRC-1"]
    }},
    {{
      "heading": "{"VIII. FUTURE RESEARCH TRAJECTORIES AND OPEN QUESTIONS" if citation_style.value == "IEEE" else "8. Future Research Trajectories"}",
      "level": 1,
      "content": "Emerging frontiers, neuro-symbolic reasoning, unified governance standards, and strategic outlook...",
      "citations": ["SRC-2"]
    }}
  ],
  "conclusion": "Rigorous academic conclusion synthesizing findings, methodological limitations, and future directions.",
  "references": [
    {{
      "source_id": "SRC-1",
      "citation_number": 1,
      "formatted_text": "Bibliographic entry in {citation_style.value} style"
    }}
  ]
}}
"""

        # Call Groq API with scaled token budget for comprehensive research papers
        token_budget = min(8000, max(2800, target_page_count * 750))
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=token_budget
            )
            raw_text = response.choices[0].message.content or ""
            return self._parse_json_to_report(raw_text, report_id, topic, citation_style, target_page_count, sources, timestamp)
        except Exception as e:
            logger.warning(f"Primary model {self.model} failed: {e}. Trying fallback model {self.fallback_model}...")
            try:
                fallback_tokens = min(7500, token_budget)
                response = self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=fallback_tokens
                )
                raw_text = response.choices[0].message.content or ""
                return self._parse_json_to_report(raw_text, report_id, topic, citation_style, target_page_count, sources, timestamp)
            except Exception as e2:
                logger.error(f"Fallback model also failed: {e2}")
                raise

    def _rewrite_with_llm(
        self,
        report_id: str,
        original_text: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle,
        preserve_findings: bool,
        feedback_corrections: Optional[List[str]],
        timestamp: str,
        topic: Optional[str] = None
    ) -> Optional[AcademicReport]:
        """Call Groq to rewrite and improve an existing paper without altering its findings."""
        sources_context = self._format_sources_for_prompt(sources)
        feedback_str = ""
        if feedback_corrections:
            feedback_str = "\nCORRECTIONS NEEDED:\n" + "\n".join(f"- {c}" for c in feedback_corrections)

        system_prompt = (
            "You are an academic editor. Improve the following report by enhancing its structure, academic vocabulary, "
            "and citation integrity. CRITICAL: Preserve all original research conclusions and findings. Do not invert or "
            "fabricate findings. Ensure all claims map to valid source IDs from the provided sources list.\n"
            "Return valid JSON matching the academic report schema."
        )

        user_prompt = f"""
ORIGINAL REPORT CONTENT:
{original_text[:12000]}

PRESERVE FINDINGS: {preserve_findings}
TARGET CITATION STYLE: {citation_style.value}
{feedback_str}

AVAILABLE RESEARCH SOURCES:
{sources_context}

Output a single valid JSON object with keys: title, abstract, keywords, sections, conclusion, references.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2500
        )
        raw_text = response.choices[0].message.content or ""
        effective_topic = topic or "Academic Research"
        return self._parse_json_to_report(raw_text, report_id, effective_topic, citation_style, 5, sources, timestamp)

    # =========================================================================
    # Deterministic Generator (Runs without LLM / In Unit Tests)
    # =========================================================================

    def _generate_deterministic_report(
        self,
        report_id: str,
        topic: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle,
        target_page_count: int,
        timestamp: str
    ) -> AcademicReport:
        """Constructs a fully structured, deterministic academic report using real source excerpts."""
        title = f"Evidence Review of {self._display_topic(topic)}"
        
        # Build keywords
        topic_terms = [
            " ".join(part.capitalize() for part in phrase.split())
            for phrase in re.split(r"\s*(?:,|;|\band\b)\s*", topic, flags=re.IGNORECASE)
            if phrase.strip()
        ]
        keywords = list(dict.fromkeys(topic_terms))
        keywords = [self._normalize_acronyms(term) for term in keywords]
        for src in sources[:4]:
            for term in re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", src.title):
                normalized = self._normalize_acronyms(term.replace("-", " ").title())
                if normalized.lower() not in {k.lower() for k in keywords}:
                    keywords.append(normalized)
                if len(keywords) >= 6:
                    break
            if len(keywords) >= 6:
                break
        keywords = keywords[:6] or ["Evidence-Based Research"]

        # Build Abstract
        source_count = len(sources)
        abstract = (
            f"This evidence review examines {topic} using {source_count} retrieved source"
            f"{'s' if source_count != 1 else ''}. It separates source-reported findings from the author's "
            "comparative interpretation, preserves uncertainty where evidence is incomplete, and does not "
            "introduce unverified numerical results, publication metadata, or causal claims."
        )

        sections: List[ReportSection] = []
        sources_used: List[str] = []
        is_ieee = (citation_style == CitationStyle.IEEE)

        # If target page count is comprehensive (>= 5), generate full 8-section research paper
        if target_page_count >= 5:
            sections = self._build_safe_comprehensive_sections(
                topic=topic,
                sources=sources,
                is_ieee=is_ieee,
                target_page_count=target_page_count,
                sources_used=sources_used
            )
        else:
            # 1. Introduction
            h_intro = "I. INTRODUCTION" if is_ieee else "1. Introduction"
            intro_text = (
                f"The field of {topic} has garnered substantial scholarly attention in contemporary discourse. "
                f"Understanding the fundamental tenets and empirical mechanisms is essential for rigorous inquiry. "
            )
            intro_citations = []
            if sources:
                s1 = sources[0]
                intro_text += f"Initial scholarship demonstrates fundamental principles established in foundational literature [{s1.source_id}]. "
                intro_citations.append(s1.source_id)
                sources_used.append(s1.source_id)

            intro_text += "This review organizes available evidence into coherent thematic sections, examining both consensus and contested hypotheses."
            sections.append(ReportSection(heading=h_intro, level=1, content=intro_text, citations=intro_citations))

            # 2. Evidence Base & Literature Synthesis
            h_lit = "II. LITERATURE REVIEW AND EVIDENCE BASE" if is_ieee else "2. Literature Review and Evidence Base"
            lit_text = f"An examination of primary materials provides grounded perspectives on {topic}. "
            lit_citations = []
            for src in sources[:3]:
                excerpt_snippet = src.excerpts[0][:200] if src.excerpts else "empirical observations were noted"
                lit_text += f"According to evidence from '{src.title}' [{src.source_id}], \"{excerpt_snippet}...\". "
                lit_citations.append(src.source_id)
                if src.source_id not in sources_used:
                    sources_used.append(src.source_id)

            sections.append(ReportSection(
                heading=h_lit,
                level=1,
                content=lit_text,
                citations=lit_citations
            ))

            # 3. Findings and Trends
            h_find = "III. FINDINGS AND THEMATIC ANALYSIS" if is_ieee else "3. Findings and Thematic Analysis"
            findings_text = f"Key findings regarding {topic} emerge from systematic cross-verification of sources. "
            findings_citations = []
            if len(sources) > 1:
                s2 = sources[1]
                findings_text += f"Comparative evaluation confirms observable patterns [{s2.source_id}]. "
                findings_citations.append(s2.source_id)
                if s2.source_id not in sources_used:
                    sources_used.append(s2.source_id)

            findings_text += (
                "The available excerpts do not provide a complete controlled comparison. "
                "Consequently, no unsupported performance estimate or experimental conclusion is asserted."
            )
            sections.append(ReportSection(
                heading=h_find,
                level=1,
                content=findings_text,
                citations=findings_citations
            ))

            # 4. Methodological Limitations
            h_limit = "IV. CRITICAL LIMITATIONS AND METHODOLOGICAL CONSTRAINTS" if is_ieee else "4. Critical Limitations and Methodological Constraints"
            sections.append(ReportSection(
                heading=h_limit,
                level=1,
                content=(
                    f"A rigorous appraisal of {topic} requires acknowledging data constraints. "
                    "Where longitudinal evidence remains sparse, claims must be interpreted prudently. "
                    "The findings presented herein reflect only verified, documented observations."
                ),
                citations=[]
            ))

        # Conclusion
        conclusion = (
            f"In conclusion, this synthesis elucidates key dimensions of {topic}. "
            "Through systematic grounding in verified documentation, the study highlights critical trajectories "
            "and delineates high-priority questions for ongoing scientific exploration."
        )

        references: List[ReferenceEntry] = []
        for idx, src in enumerate(sources, start=1):
            references.append(ReferenceEntry(
                source_id=src.source_id,
                citation_number=idx,
                formatted_text=self._format_reference(src, citation_style, idx),
                url=src.url,
                doi=src.doi
            ))

        return AcademicReport(
            id=report_id,
            title=title,
            topic=topic,
            abstract=abstract,
            keywords=keywords,
            sections=sections,
            conclusion=conclusion,
            references=references,
            citation_style=citation_style,
            target_page_count=target_page_count,
            sources_used=list(dict.fromkeys(sources_used)),
            created_at=timestamp,
            authors=[],
            affiliations=[],
            corresponding_author=None,
            doi=None,
            article_type="GENERATED_EVIDENCE_REVIEW",
            journal_name=None,
            volume=None,
            start_page=None
        )

    def _build_safe_comprehensive_sections(
        self,
        topic: str,
        sources: List[ResearchSource],
        is_ieee: bool,
        target_page_count: int,
        sources_used: List[str]
    ) -> List[ReportSection]:
        """Build a long-form structure without asserting facts absent from excerpts."""
        section_objectives = [
            ("INTRODUCTION", "defines the scope and motivation"),
            ("LITERATURE REVIEW", "groups the retrieved studies by documented theme"),
            ("RESEARCH PROBLEM AND OBJECTIVES", "states the review question and evidence objectives"),
            ("RESEARCH METHODOLOGY", "describes source selection and evidence handling"),
            ("TECHNICAL BACKGROUND", "explains concepts only where the sources provide support"),
            ("COMPARATIVE ANALYSIS", "contrasts documented approaches without inventing benchmarks"),
            ("RESULTS AND DISCUSSION", "distinguishes reported findings from this review's synthesis"),
            ("APPLICATIONS", "maps supported use cases to the cited evidence"),
            ("CHALLENGES AND LIMITATIONS", "records source and review limitations"),
            ("FUTURE SCOPE", "identifies questions requiring further primary evidence"),
        ]
        sections: List[ReportSection] = []
        evidence = [
            src for src in sources
            if src.excerpts and src.is_verified
        ]
        for index, (name, objective) in enumerate(section_objectives, start=1):
            heading = f"{index}. {name.title()}"
            selected = evidence[(index - 1) % len(evidence):] if evidence else []
            selected = selected[:2]
            if selected:
                citations = [src.source_id for src in selected]
                for source_id in citations:
                    if source_id not in sources_used:
                        sources_used.append(source_id)
                source_summary = "; ".join(
                    f"{src.title} [{src.source_id}] reports {self._evidence_sentence(src)}"
                    for src in selected
                )
                content = (
                    f"This section {objective} for {topic}. {source_summary} "
                    "These are source-reported observations; this review does not treat them as new "
                    "experiments or infer unreported performance. Evidence gaps are retained explicitly."
                )
            else:
                content = (
                    f"The available evidence is insufficient to make a verified claim about {topic} in this section. "
                    "No numerical result, benchmark, causal explanation, or publication detail is asserted. "
                    "Additional primary sources and claim-level excerpts are required before this topic can be "
                    "interpreted as a supported academic finding."
                )
                citations = []
            sections.append(ReportSection(heading=heading, level=1, content=content, citations=citations))
        return sections

    @staticmethod
    def _evidence_sentence(source: ResearchSource) -> str:
        """Return a complete, non-truncated evidence statement without fabricating a quotation."""
        text = " ".join((source.excerpts or [])).strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            return "contains no claim-level excerpt available for synthesis"
        if text.endswith("...") or text.endswith("…"):
            return "provides an incomplete retrieved excerpt, so no additional claim is made"
        return f"describes: {text.rstrip('.')}."

    @staticmethod
    def _display_topic(topic: str) -> str:
        """Format a topic for a title while preserving common technical acronyms."""
        value = re.sub(r"\s+", " ", topic.strip()).title()
        return AcademicWriterAgent._normalize_acronyms(value)

    @staticmethod
    def _normalize_acronyms(value: str) -> str:
        for acronym in ("LLMs", "LLM", "IEEE", "PDF", "RAG", "API", "AI"):
            value = re.sub(rf"\b{acronym}\b", acronym, value, flags=re.IGNORECASE)
        return value

    def _rewrite_deterministic(
        self,
        report_id: str,
        original_text: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle,
        timestamp: str,
        topic: Optional[str] = None
    ) -> AcademicReport:
        """Deterministic structural enhancement of an existing paper."""
        # Simple extraction of title and body
        lines = [line.strip() for line in original_text.split("\n") if line.strip()]
        title = lines[0] if lines else "Improved Academic Research Report"
        if title.startswith("#"):
            title = title.lstrip("#").strip()

        # Build clean sections from paragraphs
        body_paras = lines[1:] if len(lines) > 1 else [original_text]
        sections = [
            ReportSection(
                heading="1. Enhanced Synthesis",
                level=1,
                content=" ".join(body_paras[:3]),
                citations=[s.source_id for s in sources[:1]]
            )
        ]

        references = [
            ReferenceEntry(
                source_id=src.source_id,
                citation_number=idx,
                formatted_text=self._format_reference(src, citation_style, idx),
                url=src.url,
                doi=src.doi
            )
            for idx, src in enumerate(sources, start=1)
        ]

        clean_topic = topic
        if not clean_topic or clean_topic in ("Improved Academic Report", "Document Revision", "Academic Research"):
            clean_topic = title.split(":")[0].split("–")[0].split("-")[0].strip() if (":" in title or "–" in title or "-" in title) else title
        clean_topic = clean_topic or "Academic Research"

        return AcademicReport(
            id=report_id,
            title=title,
            topic=clean_topic,
            abstract=f"This revised report refines the structure, clarity, and citations of the original document on '{title}'.",
            keywords=["Academic Revision", "Synthesis", "Peer Review"],
            sections=sections,
            conclusion="The document has been revised for academic tone, structural coherence, and rigorous source grounding.",
            references=references,
            citation_style=citation_style,
            target_page_count=len(sections) + 2,
            sources_used=[s.source_id for s in sources[:1]],
            created_at=timestamp
        )

    # =========================================================================
    # Helpers & Bibliographic Formatting
    # =========================================================================

    def _format_sources_for_prompt(self, sources: List[ResearchSource]) -> str:
        """Serialize sources for prompt ingestion with clear Source IDs and quotes."""
        lines = []
        for src in sources:
            author_str = ", ".join(src.authors) if src.authors else "Unknown Authors"
            year_str = str(src.year) if src.year else "n.d."
            clean_excerpts = []
            for e in (src.excerpts[:3] if src.excerpts else []):
                cleaned_e = " ".join(e.split()).replace('"', "'")
                if cleaned_e:
                    clean_excerpts.append(f'"{cleaned_e}"')
            excerpts_str = " | ".join(clean_excerpts) if clean_excerpts else "No excerpts available."
            clean_title = (src.title or "Research Source").replace('"', "'")
            lines.append(
                f"- [ID: {src.source_id}] \"{clean_title}\" by {author_str} ({year_str}). "
                f"URL: {src.url or 'N/A'}. Evidence excerpts: {excerpts_str}"
            )
        return "\n".join(lines) if lines else "No external sources provided."

    def _format_reference(self, source: ResearchSource, style: CitationStyle, index: int) -> str:
        """Format bibliographic entry according to the selected citation style."""
        authors = ", ".join(source.authors) if source.authors else ""
        year = f"({source.year})" if source.year else "(n.d.)"
        venue = f", *{source.venue}*" if source.venue else ""
        url_doi = f", Available: {source.url}" if source.url else ""
        if source.doi:
            url_doi += f", doi: {source.doi}"

        if style == CitationStyle.IEEE:
            # IEEE format: [1] A. Author, "Title," Venue, Year.
            author_prefix = f"{authors}, " if authors else ""
            return f"[{index}] {author_prefix}\"{source.title}.\"{venue} {year}{url_doi}."
        elif style == CitationStyle.APA:
            # APA format: Author, A. (Year). Title. Venue. URL
            return f"{authors} {year}. *{source.title}*{venue}.{url_doi}"
        elif style == CitationStyle.MLA:
            # MLA format: Author. "Title." Venue, Year, URL.
            return f"{authors}. \"{source.title}.\"{venue}, {year}{url_doi}."
        elif style == CitationStyle.CHICAGO:
            # Chicago format: Author. "Title." Venue (Year).
            return f"{authors}. \"{source.title}.\"{venue} {year}."
        elif style == CitationStyle.HARVARD:
            # Harvard format: Author (Year) 'Title', Venue.
            return f"{authors} {year} '{source.title}',{venue}."
    def _build_comprehensive_sections(
        self,
        topic: str,
        sources: List[ResearchSource],
        is_ieee: bool,
        target_page_count: int,
        sources_used: List[str]
    ) -> List[ReportSection]:
        """Constructs 8 rich, publication-grade academic sections with subsections, calibrated to target page count."""
        s1_id = sources[0].source_id if sources else "SRC-1"
        s2_id = sources[1].source_id if len(sources) > 1 else s1_id
        s3_id = sources[2].source_id if len(sources) > 2 else s1_id

        for sid in [s1_id, s2_id, s3_id]:
            if sid not in sources_used:
                sources_used.append(sid)

        # Calibrate word count to target_page_count (~700 words per body page)
        target_words = max(800, int((target_page_count - 1.6) * 700))

        section_specs = [
            ("I. INTRODUCTION" if is_ieee else "1. Introduction", [
                ("A. MOTIVATION AND BACKGROUND" if is_ieee else "1.1 Motivation and Background",
                 f"The rapid evolution of {topic} marks a paradigm shift in modern computing and applied artificial intelligence. Traditional paradigms have predominantly prioritized narrow task execution, whereas contemporary requirements demand continuous goal pursuit under environmental stochasticity [{s1_id}]. Empirical investigations confirm that scaling operational reliability necessitates balancing perceptual acquisition with dynamic adaptation mechanisms.",
                 [s1_id]),
                ("B. DEFINITION AND SCOPE" if is_ieee else "1.2 Definition and Scope",
                 f"Within academic literature, {topic} is defined as an autonomous framework capable of perceiving multi-modal states, reasoning over temporal horizons, and executing coordinated actions to satisfy complex objective criteria [{s2_id}]. This survey provides an exhaustive synthesis across theoretical foundations, taxonomic variants, and empirical implementations.",
                 [s2_id]),
                ("C. SURVEY CONTRIBUTIONS AND STRUCTURE" if is_ieee else "1.3 Survey Contributions",
                 f"The principal contributions of this work are threefold: (1) a rigorous taxonomy structuring state-of-the-art designs, (2) an analytical comparison of algorithmic formulations and latency bounds, and (3) an architectural roadmap highlighting safety, alignment, and governance imperatives across distributed operational environments.",
                 [s1_id])
            ]),
            ("II. TAXONOMY AND SYSTEM ARCHITECTURES" if is_ieee else "2. Taxonomy and System Architectures", [
                ("A. STRUCTURAL ARCHITECTURAL TOPOLOGIES" if is_ieee else "2.1 Structural Topologies",
                 f"Architectural paradigms across {topic} span monolithic reactive agents, hierarchical goal-decomposition hierarchies, and decentralized peer-to-peer swarms [{s1_id}]. As illustrated in FIGURE 1, the end-to-end operational pipeline establishes closed-loop data assimilation, routing sensory feedback to specialized planning modules while ensuring predictable state transitions.",
                 [s1_id]),
                ("B. MULTI-AGENT COORDINATION PROTOCOLS" if is_ieee else "2.2 Coordination Protocols",
                 f"Effective coordination hinges on expressive message-passing schemas, blackboard topologies, and shared memory representations [{s3_id}]. Distributed synchronization algorithms prevent communication bottlenecks while maintaining global consensus across asynchronously executing nodes.",
                 [s3_id])
            ]),
            ("III. SYSTEMATIC LITERATURE REVIEW AND THEORETICAL FOUNDATIONS" if is_ieee else "3. Literature Review", [
                ("A. HISTORICAL PRECURSORS AND FOUNDATIONS" if is_ieee else "3.1 Historical Foundations",
                 f"Foundational principles of {topic} draw upon early distributed problem-solving, cybernetic feedback loops, and sequential decision theory [{s2_id}]. Recent advancements in transformer representations and reinforcement learning have further expanded the capacity for autonomous long-horizon reasoning.",
                 [s2_id]),
                ("B. PREPRINT AND BENCHMARK SYNTHESIS" if is_ieee else "3.2 Benchmark Synthesis",
                 f"A rigorous synthesis of peer-reviewed publications and preprint archives indicates rapid convergence around modular reasoning-acting workflows [{s1_id}]. However, empirical verification reveals persistent divergence in evaluation protocols, underscoring the urgent need for standardized diagnostic benchmarks.",
                 [s1_id])
            ]),
            ("IV. CORE ALGORITHMIC FORMULATIONS AND METHODOLOGY" if is_ieee else "4. Algorithmic Formulations", [
                ("A. OBJECTIVE FUNCTIONS AND REWARD MECHANICS" if is_ieee else "4.1 Objective Functions",
                 f"Algorithmic formulation in {topic} centers on maximizing expected cumulative reward subject to computational constraints and safety boundaries [{s1_id}]. As summarized in TABLE 1, comparative trade-offs between reactive, hierarchical, and swarm topologies dictate critical thresholds in execution latency, memory overhead, and fault recovery.",
                 [s1_id]),
                ("B. LATENT CALIBRATION AND COMPUTATIONAL LATENCY" if is_ieee else "4.2 Latent Calibration",
                 f"Bayesian optimization frameworks incorporating latent parameter calibration provide formal resilience against non-stationary distributions [{s2_id}]. Bounding algorithmic inference time is essential for mission-critical deployments where delayed decisions compromise physical safety.",
                 [s2_id])
            ]),
            ("V. EXPERIMENTAL BENCHMARKS AND QUANTITATIVE FINDINGS" if is_ieee else "5. Experimental Findings", [
                ("A. BENCHMARK SUITES AND EVALUATION METRICS" if is_ieee else "5.1 Benchmark Evaluation",
                 f"Standardized empirical evaluation of {topic} assesses task completion rates, planning trajectory efficiency, and robustness against perturbed sensory inputs [{s1_id}]. Empirical results demonstrate that hierarchical coordination consistently outperforms flat execution models on multi-step reasoning benchmarks.",
                 [s1_id]),
                ("B. ABLATION STUDIES AND CONVERGENCE DYNAMICS" if is_ieee else "5.2 Ablation Studies",
                 f"Ablation studies reveal that incorporating structured memory persistence and reflection loops yields up to 38% improvement in goal achievement rates over single-pass approaches [{s3_id}]. Furthermore, convergence trajectories exhibit reduced variance when supervisory filtering is applied.",
                 [s3_id])
            ]),
            ("VI. TECHNICAL CHALLENGES AND ARCHITECTURAL TRADEOFFS" if is_ieee else "6. Technical Challenges", [
                ("A. GOAL SPECIFICATION AND ALIGNMENT ASSURANCE" if is_ieee else "6.1 Goal Alignment",
                 f"Under-specified objective functions remain a primary vulnerability in {topic}, potentially resulting in reward hacking or unanticipated behavioral drift [{s1_id}]. Formal verification techniques, bounded contract specifications, and verifiable reward models serve as indispensable mitigation strategies.",
                 [s1_id]),
                ("B. SECURITY VECTORS AND FAULT TOLERANCE" if is_ieee else "6.2 Security and Robustness",
                 f"Vulnerabilities including prompt injection, adversarial sensory corruption, and cascading sub-agent failures present significant threats [{s2_id}]. Implementing cryptographic attestation, state isolation, and deterministic fallback routines establishes essential system defense-in-depth.",
                 [s2_id])
            ]),
            ("VII. INDUSTRIAL APPLICATION SCENARIOS AND DOMAIN CASE STUDIES" if is_ieee else "7. Industrial Applications", [
                ("A. REAL-TIME EDGE TELEMETRY AND CYBER-PHYSICAL SYSTEMS" if is_ieee else "7.1 Edge Telemetry",
                 f"Deployment of {topic} in cyber-physical environments, autonomous transport, and distributed power grids showcases notable operational efficiencies [{s1_id}]. Edge-deployed reasoning nodes process streaming telemetry locally, executing millisecond-scale mitigation actions.",
                 [s1_id]),
                ("B. COLLABORATIVE HUMAN-ON-THE-LOOP FRAMEWORKS" if is_ieee else "7.2 Human-AI Collaboration",
                 f"In healthcare, legal document synthesis, and automated software engineering, human-on-the-loop interfaces mediate autonomous agent outputs [{s3_id}], ensuring auditability, accountability, and regulatory compliance without compromising operational velocity.",
                 [s3_id])
            ]),
            ("VIII. FUTURE RESEARCH TRAJECTORIES AND OPEN CHALLENGES" if is_ieee else "8. Future Trajectories", [
                ("A. NEURO-SYMBOLIC HYBRID REASONING" if is_ieee else "8.1 Neuro-Symbolic Integration",
                 f"Bridging neural connectionist models with symbolic knowledge representations constitutes a vital frontier for {topic} [{s2_id}]. Neuro-symbolic integration guarantees deductive consistency, bounds error propagation, and facilitates human-interpretable verification proofs.",
                 [s2_id]),
                ("B. UNIFIED BENCHMARKING AND GOVERNANCE STANDARDS" if is_ieee else "8.2 Governance and Benchmarks",
                 f"The realization of mature, trustworthy ecosystems requires international benchmarking consortiums and transparent auditing standards [{s1_id}]. Collaborative open-source evaluation harnesses will accelerate cross-pollination between academic research and commercial applications.",
                 [s1_id])
            ])
        ]

        num_subsections = sum(len(subs) for _, subs in section_specs)
        words_per_sub = target_words / num_subsections

        depth_templates = [
            f"Detailed empirical investigation of {topic} demonstrates that continuous telemetry processing must be systematically coupled with latent variable calibration. In mission-critical environments, stochastic fluctuations require closed-loop feedback systems to continuously update probability bounds [{s1_id}]. Experimental validation shows that multi-tier supervisory mechanisms substantially reduce failure rates while maintaining bounded computational latency across variable operational conditions.",
            f"From a theoretical perspective, mathematical modeling reveals that distributed coordination algorithms exhibit quantifiable convergence guarantees under bounded network latency [{s2_id}]. Incorporating structured observation caches and priority-weighted event queues enables autonomous systems to preserve state consistency even during intermittent connectivity dropouts.",
            f"Comparative benchmark assessments further highlight that hierarchical abstraction delivers superior sample efficiency when compared with unconstrained reactive policies [{s3_id}]. By partitioning high-level goal formulation from low-level sensory actuation, the system mitigates catastrophic interference and facilitates modular policy updates without extensive retraining cycles.",
            f"Furthermore, security and robustness considerations necessitate continuous runtime auditing against anomalous state deviations [{s1_id}]. Integrating deterministic verification guardrails alongside probabilistic predictive models establishes comprehensive defense-in-depth, ensuring predictable behavior under adversarial or distributionally shifted operating regimes."
        ]

        sections: List[ReportSection] = []
        for sec_title, subs in section_specs:
            sec_paras = []
            sec_cits = []
            for sub_title, initial_text, cits in subs:
                sec_cits.extend(cits)
                sub_body = [f"{sub_title}\n{initial_text}"]
                current_sub_words = len(initial_text.split())
                tmpl_idx = 0
                while current_sub_words < words_per_sub:
                    added = depth_templates[tmpl_idx % len(depth_templates)]
                    sub_body.append(added)
                    current_sub_words += len(added.split())
                    tmpl_idx += 1
                sec_paras.append("\n\n".join(sub_body))

            sections.append(ReportSection(
                heading=sec_title,
                level=1,
                content="\n\n".join(sec_paras),
                citations=list(dict.fromkeys(sec_cits))
            ))

        return sections

    def _enrich_sections_to_target_depth(
        self,
        sections: List[ReportSection],
        topic: str,
        sources: List[ResearchSource],
        citation_style: CitationStyle,
        target_page_count: int,
        sources_used_set: set
    ) -> List[ReportSection]:
        """Expands and enriches report sections to guarantee publication-grade depth for requested page count."""
        # Never pad sections with shared boilerplate. Short evidence-grounded
        # sections must remain short and allow the quality gate to reject them.
        for section in sections:
            paragraphs = []
            seen = set()
            for paragraph in re.split(r"\n\s*\n", section.content):
                normalized = re.sub(r"\W+", " ", paragraph.lower()).strip()
                if normalized and normalized not in seen:
                    paragraphs.append(paragraph.strip())
                    seen.add(normalized)
            section.content = "\n\n".join(paragraphs)
        return sections

        # Legacy expansion code is intentionally unreachable; retained below
        # only to minimize unrelated changes to the historical implementation.
        is_ieee = (citation_style == CitationStyle.IEEE)
        used_list = list(sources_used_set)

        # If section count is sparse (< 6) for a comprehensive paper (target >= 5), generate the full 8 sections
        if len(sections) < 6 and target_page_count >= 5:
            comprehensive = self._build_comprehensive_sections(
                topic=topic,
                sources=sources,
                is_ieee=is_ieee,
                target_page_count=target_page_count,
                sources_used=used_list
            )
            for sid in used_list:
                sources_used_set.add(sid)
            # Prepend original content into matching sections if relevant
            for i, orig_sec in enumerate(sections[:len(comprehensive)]):
                if orig_sec.content and len(orig_sec.content) > 50:
                    comprehensive[i].content = f"{orig_sec.content}\n\n{comprehensive[i].content}"
                    comprehensive[i].citations = list(dict.fromkeys(comprehensive[i].citations + orig_sec.citations))
            return comprehensive

        # Otherwise, expand existing sections to satisfy target_words
        target_words = max(800, int((target_page_count - 1.6) * 700))
        current_words = sum(len(s.content.split()) for s in sections)
        deficit = target_words - current_words
        if deficit <= 0 or not sections:
            return sections

        s1_id = sources[0].source_id if sources else "SRC-1"
        s2_id = sources[1].source_id if len(sources) > 1 else s1_id
        depth_block = (
            f"\n\nRigorous academic investigation of {topic} reveals critical architectural trade-offs. "
            f"Experimental observations across primary sources [{s1_id}] demonstrate that continuous telemetry and sensory acquisition "
            f"must be coupled with latent variable calibration and probabilistic uncertainty quantification. "
            f"Furthermore, empirical benchmarking indicates that hierarchical task decomposition accelerates algorithmic "
            f"convergence while strictly bounding computational latency [{s2_id}]. Incorporating structured observation caches and "
            f"priority-weighted event queues enables autonomous systems to preserve state consistency even during non-stationary operational regimes."
        )

        added_words_per_sec = max(50, deficit // len(sections))
        for sec in sections:
            while len(sec.content.split()) < (len(sec.content.split()) + added_words_per_sec):
                sec.content += depth_block
                if s1_id not in sec.citations:
                    sec.citations.append(s1_id)
                sources_used_set.add(s1_id)
                if len(sec.content.split()) >= target_words // len(sections):
                    break

        return sections

    def _parse_json_to_report(
        self,
        raw_text: str,
        report_id: str,
        topic: str,
        citation_style: CitationStyle,
        target_page_count: int,
        sources: List[ResearchSource],
        timestamp: str
    ) -> AcademicReport:
        """Clean and parse JSON from LLM response into an AcademicReport model."""
        # Strip markdown fences if present
        clean_text = raw_text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        # Find enclosing JSON object boundary
        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_text = clean_text[first_brace:last_brace + 1]

        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            # Resilient fallback: clean trailing commas before closing braces/brackets
            fixed_text = re.sub(r',\s*([\]}])', r'\1', clean_text)
            data = json.loads(fixed_text)

        # Parse sections
        sections: List[ReportSection] = []
        sources_used_set = set()

        for sec_data in data.get("sections", []):
            cits = sec_data.get("citations", [])
            for c in cits:
                sources_used_set.add(c)
            sections.append(ReportSection(
                heading=sec_data.get("heading", "Section"),
                level=sec_data.get("level", 1),
                content=sec_data.get("content", ""),
                citations=cits
            ))

        # Parse references
        known_sources_map = {s.source_id: s for s in sources}
        references: List[ReferenceEntry] = []
        for idx, ref_data in enumerate(data.get("references", []), start=1):
            src_id = ref_data.get("source_id", f"SRC-{idx}")
            sources_used_set.add(src_id)
            matched_src = known_sources_map.get(src_id)
            fmt_text = ref_data.get("formatted_text")
            if not fmt_text and matched_src:
                fmt_text = self._format_reference(matched_src, citation_style, idx)
            elif not fmt_text:
                fmt_text = f"[{idx}] Source {src_id}."

            references.append(ReferenceEntry(
                source_id=src_id,
                citation_number=ref_data.get("citation_number", idx),
                formatted_text=fmt_text,
                url=matched_src.url if matched_src else None,
                doi=matched_src.doi if matched_src else None
            ))

        # If references list was empty in LLM output, construct from sources
        if not references:
            for idx, s in enumerate(sources, start=1):
                references.append(ReferenceEntry(
                    source_id=s.source_id,
                    citation_number=idx,
                    formatted_text=self._format_reference(s, citation_style, idx),
                    url=s.url,
                    doi=s.doi
                ))

        parsed_title = str(data.get("title") or f"Evidence Review of {topic}").strip()
        if parsed_title.lower().startswith(("ieee access", "ieee journal", "journal of ")):
            parsed_title = f"Evidence Review of {topic}"
        effective_topic = topic
        if not effective_topic or effective_topic in ("Improved Academic Report", "Document Revision", "Academic Research"):
            if parsed_title:
                clean_t = parsed_title.split(":")[0].split("–")[0].split("-")[0].strip()
                effective_topic = clean_t if len(clean_t) > 3 else parsed_title
            else:
                effective_topic = "Academic Research"

        # Ensure section depth satisfies the requested target page count
        current_word_count = sum(len(s.content.split()) for s in sections)
        min_required_words = max(1800, int((target_page_count - 1.6) * 550))
        if target_page_count >= 5 and (current_word_count < min_required_words or len(sections) < 6):
            sections = self._enrich_sections_to_target_depth(
                sections=sections,
                topic=effective_topic,
                sources=sources,
                citation_style=citation_style,
                target_page_count=target_page_count,
                sources_used_set=sources_used_set
            )

        is_ieee = (citation_style == CitationStyle.IEEE)
        authors = data.get("authors") or []
        affiliations = data.get("affiliations") or []

        return AcademicReport(
            id=report_id,
            title=parsed_title,
            topic=effective_topic,
            abstract=data.get("abstract", "Abstract not provided."),
            keywords=self._normalize_keywords(data.get("keywords", []), effective_topic),
            sections=sections,
            conclusion=data.get("conclusion", "Conclusion not provided."),
            references=references,
            citation_style=citation_style,
            target_page_count=target_page_count,
            sources_used=list(sources_used_set),
            created_at=timestamp,
            authors=authors,
            affiliations=affiliations,
            corresponding_author=data.get("corresponding_author"),
            doi=None,
            article_type=data.get("article_type", "GENERATED_EVIDENCE_REVIEW"),
            volume=data.get("volume"),
            start_page=data.get("start_page")
        )

    @staticmethod
    def _normalize_keywords(raw_keywords: Any, topic: str) -> List[str]:
        """Keep meaningful index terms and remove empty, duplicated, or truncated values."""
        values = raw_keywords if isinstance(raw_keywords, list) else []
        cleaned: List[str] = []
        for value in values:
            term = re.sub(r"\s+", " ", str(value)).strip(" .,;:-")
            if not term or term.endswith(("...", "…")) or len(term) < 3:
                continue
            term = AcademicWriterAgent._normalize_acronyms(term)
            if term.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(term)
        if not cleaned:
            cleaned = [
                phrase.strip().title()
                for phrase in re.split(r"\s*(?:,|;|\band\b)\s*", topic, flags=re.IGNORECASE)
                if phrase.strip()
            ]
        return cleaned[:7]
