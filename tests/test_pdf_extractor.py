"""Unit tests for PDF extraction service."""

import io
import pytest
import pypdf
from reportlab.pdfgen import canvas
from services.pdf_extractor import PdfExtractor, PdfExtractionError


def test_empty_pdf_bytes():
    """Verify empty bytes raise PdfExtractionError."""
    with pytest.raises(PdfExtractionError) as exc_info:
        PdfExtractor.extract_from_bytes(b"", "empty.pdf")
    assert "empty" in str(exc_info.value).lower()


def test_invalid_pdf_header():
    """Verify non-PDF file raises PdfExtractionError."""
    with pytest.raises(PdfExtractionError) as exc_info:
        PdfExtractor.extract_from_bytes(b"This is a plaintext file not a PDF", "plain.txt")
    assert "not a valid pdf" in str(exc_info.value).lower()


def test_corrupted_pdf_structure():
    """Verify corrupted PDF bytes trigger handled exception."""
    corrupt_bytes = b"%PDF-1.4\n%corrupted garbage data without trailer or xref"
    with pytest.raises(PdfExtractionError):
        PdfExtractor.extract_from_bytes(corrupt_bytes, "corrupt.pdf")


def test_valid_pdf_extraction():
    """Generate a real valid PDF in-memory and verify text extraction."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Academic Research Assistant Test Document.")
    c.drawString(100, 730, "Testing multi-agent extraction capabilities with high precision.")
    c.save()

    pdf_bytes = buf.getvalue()
    result = PdfExtractor.extract_from_bytes(pdf_bytes, "test_doc.pdf")

    assert result["total_pages"] == 1
    assert "Academic Research Assistant Test Document" in result["text"]
    assert result["char_count"] > 20
    assert not result["is_scanned"]


def test_scanned_pdf_heuristic():
    """Verify that a multi-page PDF with no extractable text triggers the scanned PDF notice."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    # Draw empty page with no text (simulate pure scan/image)
    c.rect(50, 50, 400, 400)
    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()
    with pytest.raises(PdfExtractionError) as exc_info:
        PdfExtractor.extract_from_bytes(pdf_bytes, "scanned_doc.pdf")
    assert exc_info.value.is_scanned or "scanned" in str(exc_info.value).lower() or "ocr" in str(exc_info.value).lower()
