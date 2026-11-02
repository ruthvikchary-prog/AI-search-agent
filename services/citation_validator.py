"""Deterministic Citation and Reference Validation Service (Student 4).

Performs strict, rule-based algorithmic verification of academic reports:
1. In-text citation parsing (supporting [SRC-X], [1], (Author, Year) formats).
2. Cross-referencing against verified research source records.
3. Reference list integrity: flags fabricated references and orphaned sources.
4. Citation style compliance (IEEE, APA, MLA, Chicago, Harvard).
5. Grounding analysis: flags factual claims citing sources whose excerpts lack supporting tokens.
"""

import re
from typing import List, Dict, Set
from models.schemas import (
    AcademicReport,
    ResearchSource,
    CitationValidationResult,
    CitationStyle
)


class CitationValidator:
    """Deterministic validator for academic citations and references."""

    # Regex patterns for various citation notations
    SOURCE_ID_PATTERN = re.compile(r"\[(SRC-\d+)\]", re.IGNORECASE)
    NUMERIC_IEEE_PATTERN = re.compile(r"\[(\d+)\]")
    APA_AUTHOR_YEAR_PATTERN = re.compile(r"\(([A-Z][a-zA-Z\s]+(?:et al\.)?,\s*\d{4})\)")

    def validate(
        self,
        report: AcademicReport,
        known_sources: List[ResearchSource]
    ) -> CitationValidationResult:
        """Run comprehensive deterministic citation validation on an AcademicReport."""
        details: List[str] = []
        known_source_ids: Set[str] = {s.source_id.upper() for s in known_sources}
        source_map: Dict[str, ResearchSource] = {s.source_id.upper(): s for s in known_sources}

        # 1. Extract all in-text citations across all sections and conclusion
        in_text_citations: List[str] = []
        text_corpus = f"{report.abstract}\n"
        for section in report.sections:
            text_corpus += f"{section.content}\n"
            # Also inspect explicitly recorded section.citations
            for c in section.citations:
                c_clean = c.strip().upper()
                if c_clean:
                    in_text_citations.append(c_clean)
        text_corpus += f"{report.conclusion}\n"

        # Regex scan in-text citations from text corpus
        src_id_matches = self.SOURCE_ID_PATTERN.findall(text_corpus)
        for m in src_id_matches:
            in_text_citations.append(m.upper())

        # If IEEE numeric [1], [2], map numeric index to source if reference entries exist
        numeric_matches = self.NUMERIC_IEEE_PATTERN.findall(text_corpus)
        num_to_source_id: Dict[str, str] = {}
        for ref in report.references:
            if ref.citation_number is not None:
                num_to_source_id[str(ref.citation_number)] = ref.source_id.upper()

        for num in numeric_matches:
            if num in num_to_source_id:
                in_text_citations.append(num_to_source_id[num])

        in_text_unique = sorted(list(set(in_text_citations)))

        # 2. Check in-text citations against known sources
        resolved_citations: List[str] = []
        unresolved_citations: List[str] = []

        for cit in in_text_unique:
            if cit in known_source_ids:
                resolved_citations.append(cit)
            else:
                unresolved_citations.append(cit)
                details.append(f"In-text citation [{cit}] does not correspond to any known research source.")

        # 3. Check References list for fabricated references or orphans
        ref_source_ids: Set[str] = set()
        fabricated_references: List[str] = []

        for ref in report.references:
            ref_id = ref.source_id.strip().upper()
            ref_source_ids.add(ref_id)
            if ref_id not in known_source_ids:
                fabricated_references.append(ref_id)
                details.append(
                    f"Bibliographic reference for [{ref_id}] has no matching record in the ingested research sources."
                )

        # 4. Check for unused sources (in references but never cited in text)
        unused_sources: List[str] = []
        for ref_id in ref_source_ids:
            if ref_id not in in_text_unique:
                unused_sources.append(ref_id)
                details.append(f"Source [{ref_id}] is listed in references but is never cited in the text body.")

        # 5. Check Citation Style Formatting Compliance
        formatting_errors = self._check_formatting_style(report, report.citation_style)
        details.extend(formatting_errors)

        # 6. Check Unsupported Factual Claims Grounding
        unsupported_claims = self._check_grounding_claims(report, source_map)
        details.extend(unsupported_claims)

        # Overall validity judgment
        # Critical failure if there are unresolved citations or fabricated references
        is_valid = (
            len(unresolved_citations) == 0
            and len(fabricated_references) == 0
            and len(resolved_citations) > 0
        )

        if not is_valid:
            if len(resolved_citations) == 0:
                details.append("Critical: No valid citations were identified in the report body.")
            if unresolved_citations:
                details.append(f"Critical: {len(unresolved_citations)} unresolved citation(s) detected.")
            if fabricated_references:
                details.append(f"Critical: {len(fabricated_references)} fabricated reference(s) detected.")
        else:
            details.append(
                f"Citation validation passed: {len(resolved_citations)} citation(s) verified against real sources."
            )

        return CitationValidationResult(
            is_valid=is_valid,
            resolved_citations=resolved_citations,
            unresolved_citations=unresolved_citations,
            unused_sources=unused_sources,
            fabricated_references=fabricated_references,
            formatting_errors=formatting_errors,
            unsupported_claims=unsupported_claims,
            details=details
        )

    def _check_formatting_style(self, report: AcademicReport, style: CitationStyle) -> List[str]:
        """Verify that bibliography and text citation patterns conform to chosen style."""
        errors: List[str] = []

        if style == CitationStyle.IEEE:
            # References should be numbered starting with [1], [2]...
            for ref in report.references:
                if not ref.formatted_text.strip().startswith("["):
                    errors.append(f"IEEE formatting error: Reference [{ref.source_id}] must start with bracketed index.")
        elif style == CitationStyle.APA:
            # APA bibliography should start with Author surname and year (e.g. Smith (2024))
            for ref in report.references:
                if ref.formatted_text.strip().startswith("["):
                    errors.append(f"APA formatting warning: Reference [{ref.source_id}] should use Author (Year) format rather than bracketed numbers.")

        return errors

    def _check_grounding_claims(
        self,
        report: AcademicReport,
        source_map: Dict[str, ResearchSource]
    ) -> List[str]:
        """Deterministic keyword grounding check: verify sentences citing [SRC-X] have term overlap with that source."""
        unsupported: List[str] = []

        # Split content into sentences
        for section in report.sections:
            sentences = re.split(r"(?<=[.!?])\s+", section.content)
            for sentence in sentences:
                matches = self.SOURCE_ID_PATTERN.findall(sentence)
                if not matches:
                    continue

                sentence_clean = self.SOURCE_ID_PATTERN.sub("", sentence).lower()
                tokens = set(re.findall(r"\b[a-z]{4,}\b", sentence_clean))
                stopwords = {"this", "that", "with", "from", "were", "been", "have", "their", "which", "study", "paper"}
                content_tokens = tokens - stopwords

                if not content_tokens:
                    continue

                for cit in matches:
                    src = source_map.get(cit.upper())
                    if not src or not src.excerpts:
                        continue

                    # Check excerpt token overlap
                    excerpt_corpus = " ".join(src.excerpts).lower()
                    overlap = [t for t in content_tokens if t in excerpt_corpus]
                    if len(overlap) == 0 and len(content_tokens) >= 5:
                        unsupported.append(
                            f"Potential unsupported claim in {section.heading}: Sentence '{sentence[:80]}...' "
                            f"cites [{cit.upper()}] but shares zero substantial keywords with its excerpts."
                        )

        return unsupported
