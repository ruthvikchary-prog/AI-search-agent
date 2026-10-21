# Multi-Agent Academic Research Assistant

A complete, production-grade web application and multi-agent system designed for automated, evidence-grounded academic research synthesis, deterministic citation validation, multi-dimensional quality evaluation, and publication-ready PDF generation.

---

## 1. Architectural Overview & Student 4 Modules

The system is partitioned into specialized, testable modules with explicit Pydantic boundaries.

### Primary Assigned Modules (Student 4: Academic Report Writer & Evaluation):
1. **`agents/academic_writer.py`**
   - Synthesizes research evidence into formal academic documents (Title, Abstract, Keywords, Numbered Sections, Findings & Thematic Analysis, Conclusion, and References).
   - In-text citations strictly use verified Source IDs (e.g. `[SRC-1]`).
   - Grounded rewrite engine for improving existing reports without altering core empirical findings.
   - Injectable LLM client with Groq API integration and deterministic fallback for unit tests.

2. **`services/report_formatter.py`**
   - Document structure management and ReportLab PDF compilation.
   - Professional academic layout: running headers, footers with dynamic `"Page X of Y"` via a two-pass `NumberedCanvas`, standard margins, and hanging-indent bibliographies.
   - Exports clean Markdown and interactive HTML previews with citation badges.

3. **`agents/evaluation.py`**
   - 8-dimension grading scorecard:
     * Structural Completeness (15%)
     * Evidence Support & Grounding (20%)
     * Citation Consistency (15%)
     * Topic Relevance (15%)
     * Academic Tone & Clarity (10%)
     * Logical Organization (10%)
     * Reference Integrity (10%)
     * Formatting Correctness (5%)
   - **Hard Quality Gates**: Fabricated references or ungrounded claims trigger immediate failure regardless of writing score.
   - Diagnostic separation of Critical Errors vs. Warnings, providing actionable feedback for iterative correction.

4. **`services/citation_validator.py`**
   - Deterministic algorithmic cross-referencing of in-text citations against verified research source records.
   - Detects fabricated references, unresolved citation tags, orphaned bibliography items, and lexical grounding discrepancies.

### Supporting Orchestration & Infrastructure:
- **`agents/orchestrator.py`**: Coordinates Stages 1 through 9 with a **bounded correction loop** (strictly limited to $\le 3$ retries, eliminating infinite loops).
- **`agents/source_verifier.py`**: Evaluates source existence (URL/DOI syntax, PDF provenance) and domain credibility (`.edu`, `.gov`, `arxiv.org`, `ieee.org`, etc.).
- **`services/pdf_extractor.py`**: Robust PDF text extraction (PyMuPDF / pypdf) with graceful handling for corrupt, encrypted, scanned, and oversized documents.
- **`services/search_service.py`**: Pluggable online literature search (DuckDuckGo, Tavily).
- **`services/job_manager.py`**: Asynchronous thread-safe task queue with real-time stage progression.
- **`services/storage.py`**: Filesystem persistence with path traversal sanitization.
- **`app.py`**: RESTful Flask web service.

---

## 2. Visual Design System

The frontend features a distinctive scientific computing aesthetic:
- **Palette**: Dark navy (`#050B16`), panel blue (`#0B172A`), electric blue (`#3B82F6`), cyan (`#22D3EE`), violet (`#8B5CF6`).
- **Dynamic Neural Network Visualization (`static/js/neural_net.js`)**: Real SVG graph connecting the 5 agents:
  1. Research Agent
  2. Source Verification Agent
  3. Academic Writer Agent
  4. Evaluation Module
  5. Final Report Generator
- Active stages pulse with animated gradient flow; completed nodes glow emerald with checkmarks; failed nodes display alert styling. Stops animations upon completion and respects `prefers-reduced-motion`.
- **Academic Document Reader (`#view-results`)**: High-contrast, clean academic presentation distinct from the futuristic dashboard frame to ensure reading comfort.

---

## 3. Setup and Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- pip

### Installation Steps
```bash
# 1. Clone repository & navigate to workspace
cd "academic-assistant"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
copy .env.example .env
# Edit .env and enter your GROQ_API_KEY
```

---

## 4. Configuration Settings (.env)

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API Key for LLM inference | Required |
| `GROQ_MODEL` | Primary LLM model ID | `openai/gpt-oss-120b` |
| `GROQ_FALLBACK_MODEL` | Fallback model ID | `qwen/qwen3.8-27b` |
| `SEARCH_PROVIDER` | Web search provider | `duckduckgo` |
| `FLASK_PORT` | Port for the web application | `5000` |
| `UPLOAD_MAX_FILE_SIZE_MB`| Max PDF upload size | `25` |
| `DEFAULT_CITATION_STYLE` | Default citation format | `IEEE` |
| `MAX_CORRECTION_ATTEMPTS`| Bounded correction retry limit | `3` |
| `EVALUATION_PASSING_SCORE`| Quality gate passing threshold | `75.0` |

---

## 5. Running the Application

```bash
python app.py
```
Open your browser to: **`http://localhost:5000`**

---

## 6. Testing Guide

Run automated unit and integration tests:
```bash
# Run all unit and integration tests (excluding real LLM network calls)
pytest

# Run tests with verbose output
pytest -v

# Run real LLM smoke test (requires live Groq API key)
pytest -m llm
```

---

## 7. REST API Endpoints

- `GET /api/health` — System health and configured providers.
- `POST /api/reports/generate` — Start new report generation workflow (accepts multipart PDF or JSON).
- `POST /api/reports/improve` — Start report improvement and citation validation workflow.
- `GET /api/jobs/<job_id>` — Poll live workflow stage, progress (0-100%), and status.
- `GET /api/reports` — List real saved reports.
- `GET /api/reports/<report_id>` — Retrieve structured report, 8-dimension scorecard, and HTML preview.
- `GET /api/reports/<report_id>/download` — Stream publication-ready PDF for download.
- `POST /api/teammate/submit-research` — Ingest structured research sources from connected teammate agents.
- `GET /api/settings` & `POST /api/settings` — Get or update runtime defaults.
