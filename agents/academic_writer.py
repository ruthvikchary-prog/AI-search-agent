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
            f"3. In-text citations MUST reference the provided Source IDs (e.g., [SRC-1] for IEEE, or (Author, Year) [SRC-1] for APA).\n"
            "4. Every cited source ID MUST match one of the provided Source IDs.\n"
            "5. Do not cite any source not provided in the sources list.\n"
            "6. Output MUST be a single valid JSON object following the requested schema precisely without extra text.\n"
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

Output a single JSON object with these EXACT keys:
{{
  "title": "Clear, professional academic paper title",
  "abstract": "Comprehensive abstract summarizing objective, methodology/evidence, and findings (200-300 words)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "sections": [
    {{
      "heading": "1. Introduction",
      "level": 1,
      "content": "Introduction text with in-text citations like [SRC-1]...",
      "citations": ["SRC-1"]
    }},
    {{
      "heading": "2. Literature Review and Evidence Base",
      "level": 1,
      "content": "Detailed review of sources...",
      "citations": ["SRC-1", "SRC-2"]
    }},
    {{
      "heading": "3. Findings and Thematic Analysis",
      "level": 1,
      "content": "Detailed discussion of research findings grounded in evidence...",
      "citations": ["SRC-2"]
    }},
    {{
      "heading": "4. Trends, Applications, and Limitations",
      "level": 1,
      "content": "Analysis of trends and methodological limitations...",
      "citations": ["SRC-1"]
    }}
  ],
  "conclusion": "Rigorous academic conclusion synthesizing findings and future research directions.",
  "references": [
    {{
      "source_id": "SRC-1",
      "citation_number": 1,
      "formatted_text": "Bibliographic entry in {citation_style.value} style"
    }}
  ]
}}
"""

        # Call Groq API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=6000
            )
            raw_text = response.choices[0].message.content or ""
            return self._parse_json_to_report(raw_text, report_id, topic, citation_style, target_page_count, sources, timestamp)
        except Exception as e:
            logger.warning(f"Primary model {self.model} failed: {e}. Trying fallback model {self.fallback_model}...")
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=5000
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
            temperature=0.2,
            max_tokens=6000
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
        title = f"Investigation and Synthesis of {topic.title()}: A Structured Evidence Review"
        
        # Build keywords
        words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", topic) if w.lower() not in {"study", "overview", "analysis"}]
        keywords = list(dict.fromkeys(words[:5])) or ["Research", "Methodology", "Evidence-Based Analysis"]

        # Build Abstract
        source_count = len(sources)
        abstract = (
            f"This academic report presents a structured analysis of {topic}. Drawing on {source_count} "
            f"primary and secondary research source{'s' if source_count != 1 else ''}, this paper synthesizes "
            f"empirical observations, methodological paradigms, and conceptual implications. The findings indicate "
            f"significant developments within the domain while highlighting critical limitations in current evidence. "
            f"Recommendations for future academic inquiry and empirical validation are proposed."
        )

        sections: List[ReportSection] = []
        sources_used: List[str] = []

        # 1. Introduction
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
        sections.append(ReportSection(heading="1. Introduction", level=1, content=intro_text, citations=intro_citations))

        # 2. Evidence Base & Literature Synthesis
        lit_text = f"An examination of primary materials provides grounded perspectives on {topic}. "
        lit_citations = []
        for src in sources[:3]:
            excerpt_snippet = src.excerpts[0][:200] if src.excerpts else "empirical observations were noted"
            lit_text += f"According to evidence from '{src.title}' [{src.source_id}], \"{excerpt_snippet}...\". "
            lit_citations.append(src.source_id)
            if src.source_id not in sources_used:
                sources_used.append(src.source_id)

        sections.append(ReportSection(
            heading="2. Literature Review and Evidence Base",
            level=1,
            content=lit_text,
            citations=lit_citations
        ))

        # 3. Findings and Trends
        findings_text = f"Key findings regarding {topic} emerge from systematic cross-verification of sources. "
        findings_citations = []
        if len(sources) > 1:
            s2 = sources[1]
            findings_text += f"Comparative evaluation confirms observable patterns [{s2.source_id}]. "
            findings_citations.append(s2.source_id)
            if s2.source_id not in sources_used:
                sources_used.append(s2.source_id)

        findings_text += (
            "Furthermore, thematic cross-referencing indicates reproducible outcomes across tested parameters, "
            "though variations in implementation context necessitate calibrated interpretation."
        )
        sections.append(ReportSection(
            heading="3. Findings and Thematic Analysis",
            level=1,
            content=findings_text,
            citations=findings_citations
        ))

        # 4. Methodological Limitations
        sections.append(ReportSection(
            heading="4. Critical Limitations and Methodological Constraints",
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

        # Build References
        references: List[ReferenceEntry] = []
        for idx, src in enumerate(sources, start=1):
            ref_text = self._format_reference(src, citation_style, idx)
            references.append(ReferenceEntry(
                source_id=src.source_id,
                citation_number=idx,
                formatted_text=ref_text,
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
            created_at=timestamp
        )

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
            excerpts_str = " | ".join(f'"{e}"' for e in src.excerpts[:3]) if src.excerpts else "No excerpts available."
            lines.append(
                f"- [ID: {src.source_id}] \"{src.title}\" by {author_str} ({year_str}). "
                f"URL: {src.url or 'N/A'}. Evidence excerpts: {excerpts_str}"
            )
        return "\n".join(lines) if lines else "No external sources provided."

    def _format_reference(self, source: ResearchSource, style: CitationStyle, index: int) -> str:
        """Format bibliographic entry according to the selected citation style."""
        authors = ", ".join(source.authors) if source.authors else "Anonymous"
        year = f"({source.year})" if source.year else "(n.d.)"
        venue = f", *{source.venue}*" if source.venue else ""
        url_doi = f", Available: {source.url}" if source.url else (f", doi: {source.doi}" if source.doi else "")

        if style == CitationStyle.IEEE:
            # IEEE format: [1] A. Author, "Title," Venue, Year.
            return f"[{index}] {authors}, \"{source.title},\"{venue} {year}{url_doi}."
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
        else:
            return f"[{index}] {authors}, \"{source.title},\" {year}."

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

        data = json.loads(clean_text)

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

        parsed_title = data.get("title", f"Academic Report: {topic.title()}")
        effective_topic = topic
        if not effective_topic or effective_topic in ("Improved Academic Report", "Document Revision", "Academic Research"):
            if parsed_title:
                clean_t = parsed_title.split(":")[0].split("–")[0].split("-")[0].strip()
                effective_topic = clean_t if len(clean_t) > 3 else parsed_title
            else:
                effective_topic = "Academic Research"

        return AcademicReport(
            id=report_id,
            title=parsed_title,
            topic=effective_topic,
            abstract=data.get("abstract", "Abstract not provided."),
            keywords=data.get("keywords", []),
            sections=sections,
            conclusion=data.get("conclusion", "Conclusion not provided."),
            references=references,
            citation_style=citation_style,
            target_page_count=target_page_count,
            sources_used=list(sources_used_set),
            created_at=timestamp
        )
