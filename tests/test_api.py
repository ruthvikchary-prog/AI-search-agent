"""Integration tests for Flask API endpoints and security boundaries."""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_check_endpoint(client):
    """Verify /api/health returns 200 and expected status keys."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "supported_citation_styles" in data
    assert "IEEE" in data["supported_citation_styles"]


def test_generate_report_valid_json(client):
    """Verify /api/reports/generate accepts valid JSON and returns 202 with job_id."""
    payload = {
        "topic": "Graph Neural Networks in Drug Discovery",
        "citation_style": "IEEE",
        "length": "brief",
        "target_page_count": 3,
        "source_preference": "online_only"
    }
    resp = client.post("/api/reports/generate", json=payload)
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["success"] is True
    assert "job_id" in data
    assert data["status"] == "pending"


def test_generate_report_validation_failure(client):
    """Verify /api/reports/generate rejects invalid input with HTTP 400."""
    payload = {
        "topic": "A",  # Too short, fails min_length=3
        "citation_style": "IEEE"
    }
    resp = client.post("/api/reports/generate", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_get_job_status(client):
    """Verify /api/jobs/<job_id> returns job state."""
    # First create a job
    post_resp = client.post("/api/reports/generate", json={
        "topic": "Autonomous Agent Tool Calling",
        "citation_style": "IEEE"
    })
    job_id = post_resp.get_json()["job_id"]

    # Poll status
    get_resp = client.get(f"/api/jobs/{job_id}")
    assert get_resp.status_code == 200
    data = get_resp.get_json()
    assert data["job_id"] == job_id
    assert "stage" in data


def test_nonexistent_job_returns_404(client):
    """Verify non-existent job ID returns 404."""
    resp = client.get("/api/jobs/non-existent-job-uuid-123")
    assert resp.status_code == 404


def test_path_traversal_protection(client):
    """Verify that path traversal attempts in report ID are safely sanitized."""
    resp = client.get("/api/reports/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (404, 400)


def test_teammate_research_submission(client):
    """Verify /api/teammate/submit-research endpoint ingests external agent data."""
    payload = {
        "agent_name": "Teammate-Agent-1",
        "topic": "Neuromorphic Computing",
        "sources": [
            {
                "source_id": "SRC-TM-1",
                "title": "Spiking Neural Networks",
                "authors": ["W. Gerstner"],
                "year": 2014,
                "venue": "Cambridge University Press",
                "url": "https://example.edu/snn",
                "excerpts": ["Spiking neurons communicate using discrete action potentials."],
                "source_type": "teammate"
            }
        ]
    }
    resp = client.post("/api/teammate/submit-research", json=payload)
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["success"] is True
    assert data["sources_received"] == 1


def test_recorrect_report_nonexistent(client):
    """Re-correct on nonexistent report returns 404."""
    resp = client.post("/api/reports/nonexistent-uuid-12345/re-correct", json={})
    assert resp.status_code == 404
