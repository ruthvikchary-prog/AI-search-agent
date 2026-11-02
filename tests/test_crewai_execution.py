from agents import report_writer, source_reviewer
import research_analyst as m1


def test_m1_fallback_is_explicit(monkeypatch):
    class BrokenCrew:
        def kickoff(self):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(m1, "build_crew", lambda topic: BrokenCrew())
    monkeypatch.setattr(m1, "multi_source_search", lambda topic, n: [])
    output = m1.run_research_analyst("speech recognition")
    assert output.execution_mode == "deterministic_fallback"
    assert "model unavailable" in output.fallback_reason


def test_m2_never_promotes_rejected_sources(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    result = source_reviewer.run({
        "topic": "speech recognition",
        "sources": [{
            "title": "Untrusted post",
            "url": "https://medium.com/example",
            "snippet": "speech recognition",
        }],
        "findings": [],
    })
    assert result["execution_mode"] == "deterministic_fallback"
    rejected_ids = {item["id"] for item in result["rejected_sources"]}
    verified_ids = {item["id"] for item in result["verified_sources"]}
    assert not rejected_ids.intersection(verified_ids)


def test_m3_without_credentials_is_explicit_and_section_specific(monkeypatch):
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "NVIDIA_NIM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    result = report_writer.run({
        "topic": "speech recognition",
        "verified_sources": [{
            "id": "SRC-1",
            "title": "Speech paper",
            "url": "https://example.edu/paper",
            "snippet": "Deep learning models can represent acoustic features.",
            "credibility_score": 90,
            "metadata_status": "unavailable",
        }],
    })
    assert result["execution_mode"] == "deterministic_fallback"
    assert len(result["sections"]) == 10
    contents = [section["content"] for section in result["sections"]]
    assert len(set(contents)) == len(contents)
