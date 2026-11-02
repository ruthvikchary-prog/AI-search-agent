"""
Module 1 - Research Analyst Agent (Student: Karthik)
Project: Multi-Agent Academic Research Assistant using CrewAI

Usage:
    python research_analyst.py "Federated learning in healthcare"

Output:
    outputs/research_<topic>.json  -> hand-off file for the Source Reviewer agent
"""
import json
import os
import re
import sys
import subprocess
import tempfile
import time
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import urlparse

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from services.metadata import enrich_source_metadata
from services.groq import (
    disable_unsupported_cache_breakpoints,
    get_active_model,
    preflight,
)

load_dotenv()


# ----------------------------------------------------------------------------
# 1. Output schema (this is the contract with the Source Reviewer agent)
# ----------------------------------------------------------------------------
class Source(BaseModel):
    title: str
    url: str
    snippet: str = Field(description="Short text from the search result")
    source_type: str = Field(default="article", description="paper | article | report | website | news")
    published: Optional[str] = Field(default=None, description="Date/year if visible")
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    metadata_status: str = "unavailable"


class Finding(BaseModel):
    subtopic: str
    summary: str = Field(description="2-3 sentence summary of what the sources say")
    source_urls: List[str]


class ResearchOutput(BaseModel):
    topic: str
    subtopics: List[str]
    sources: List[Source]
    findings: List[Finding]
    execution_mode: str = "unknown"
    fallback_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    preflight_ok: bool = False


# ----------------------------------------------------------------------------
# 2. Web search tool (Serper -> DuckDuckGo -> Free arXiv Academic Repository)
# ----------------------------------------------------------------------------
def _serper_search(query: str, n: int = 8):
    import requests

    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
        json={"q": query, "num": n},
        timeout=20,
    )
    r.raise_for_status()
    return [
        {"title": x.get("title", ""), "url": x.get("link", ""), "snippet": x.get("snippet", "")}
        for x in r.json().get("organic", [])
    ]


def _ddg_search(query: str, n: int = 8):
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    try:
        with DDGS(timeout=5) as d:
            items = list(d.text(query, max_results=n))
            if items:
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", "") or r.get("link", ""),
                        "snippet": r.get("body", "") or r.get("snippet", ""),
                    }
                    for r in items
                ]
    except Exception:
        pass
    return []


def _arxiv_search(query: str, n: int = 5):
    """Reliable academic repository search for peer-reviewed preprints."""
    try:
        clean_q = re.sub(r"[^a-zA-Z0-9\s]", " ", query).strip()
        encoded = urllib.parse.quote_plus(clean_q)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={n}"
        req = urllib.request.urlopen(url, timeout=10)
        root = ET.fromstring(req.read())
        results = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            link = entry.find("atom:id", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            published = entry.find("atom:published", ns)
            pub_year = published.text[:4] if published is not None and published.text else "2024"
            results.append({
                "title": title,
                "url": link,
                "snippet": summary[:300] + "...",
                "published": pub_year
            })
        return results
    except Exception:
        return []


def multi_source_search(query: str, n: int = 6) -> List[dict]:
    """Hierarchical search: Serper -> DDG -> arXiv."""
    if os.getenv("SERPER_API_KEY"):
        try:
            res = _serper_search(query, n)
            if res:
                return res
        except Exception:
            pass

    ddg_res = _ddg_search(query, n)
    if ddg_res:
        return ddg_res

    arxiv_res = _arxiv_search(query, n)
    if arxiv_res:
        return arxiv_res

    return []


@tool("web_search")
def web_search(query: str) -> str:
    """Search the web for scientific literature. Input is a search query.
    Returns numbered results with title, URL, and snippet."""
    results = multi_source_search(query, n=2)
    if not results:
        return "No results found."
    return "\n\n".join(
        f"[{i}] {r['title']}\nURL: {r['url']}\nSnippet: {r.get('snippet', '')}"
        for i, r in enumerate(results, 1)
    )


# ----------------------------------------------------------------------------
# 3. LLM selection (Groq / NVIDIA NIM / OpenAI)
# ----------------------------------------------------------------------------
def get_llm() -> LLM:
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "groq":
        disable_unsupported_cache_breakpoints()
        raw_model = get_active_model()
        model_name = raw_model if raw_model.startswith("groq/") else f"groq/{raw_model}"
        return LLM(
            model=model_name,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.2,
            max_tokens=900,
        )
    if provider == "nvidia":
        return LLM(
            model=os.getenv("LLM_MODEL", "nvidia_nim/meta/llama-3.1-70b-instruct"),
            api_key=os.getenv("NVIDIA_NIM_API_KEY"),
            temperature=0.2,
        )
    return LLM(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.2,
    )


# ----------------------------------------------------------------------------
# 4. Agent + Task
# ----------------------------------------------------------------------------
def build_crew(topic: str) -> Crew:
    analyst = Agent(
        role="Research Analyst",
        goal=(
            "Understand the research topic, search the web thoroughly, and collect "
            "relevant, recent and diverse information with source links."
        ),
        backstory=(
            "You are a careful academic research analyst. You break a topic into "
            "sub-topics, search each one, prefer recent papers, articles and reports, "
            "and never invent a source. Every URL you report must come from a search result."
        ),
        tools=[web_search],
        llm=get_llm(),
        allow_delegation=False,
        max_iter=1,
        verbose=True,
    )

    task = Task(
        description=(
            f"Research topic: {topic}\n\n"
            "Use one or two concise searches. Return at most four distinct sources "
            "with URLs that appeared in search results, two subtopics, and short "
            "findings tied to those URLs. Never invent metadata or citations."
        ),
        expected_output="A ResearchOutput object: topic, subtopics, sources and findings.",
        agent=analyst,
        output_pydantic=ResearchOutput,
    )

    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=True)


# ----------------------------------------------------------------------------
# 5. Module metrics from the slides
# ----------------------------------------------------------------------------
def compute_metrics(out: ResearchOutput) -> dict:
    n = len(out.sources)
    domains = {urlparse(s.url).netloc.replace("www.", "") for s in out.sources}
    keywords = {w for w in re.findall(r"[a-z0-9]+", out.topic.lower()) if len(w) > 3}

    def is_relevant(s: Source) -> bool:
        text = f"{s.title} {s.snippet}".lower()
        return any(k in text for k in keywords)

    relevance = (sum(is_relevant(s) for s in out.sources) / n * 100) if n else 0.0

    known_urls = {s.url for s in out.sources}
    covered = {
        f.subtopic
        for f in out.findings
        if any(u in known_urls for u in f.source_urls)
    }
    coverage = (len(covered) / len(out.subtopics) * 100) if out.subtopics else 0.0

    return {
        "number_of_sources_found": n,
        "unique_domains": len(domains),
        "search_relevance_percent": round(relevance, 1),
        "information_coverage_percent": round(coverage, 1),
    }


def dedupe_sources(out: ResearchOutput) -> ResearchOutput:
    seen, seen_titles, unique = set(), set(), []
    for s in out.sources:
        canonical_url = s.url.strip().lower().rstrip("/")
        canonical_title = re.sub(r"[^a-z0-9]+", " ", s.title.lower()).strip()
        if not canonical_url or canonical_url in seen or (
            canonical_title and canonical_title in seen_titles
        ):
            continue
        seen.add(canonical_url)
        if canonical_title:
            seen_titles.add(canonical_title)
        unique.append(s)
    out.sources = unique
    return out


# ----------------------------------------------------------------------------
# 6. Execution Runner
# ----------------------------------------------------------------------------
def _run_crewai_research(topic: str) -> ResearchOutput:
    """Run the real CrewAI analyst. Called inside the isolated M1 worker."""
    preflight_ok = False
    check = preflight()
    if not check.real_request_ok:
        raise RuntimeError(f"Groq preflight failed: {check.reason}")
    os.environ["GROQ_ACTIVE_MODEL"] = check.active_model or check.configured_model
    preflight_ok = True
    if check.recommended_env_change:
        print(f"[Groq] Recommended environment change: {check.recommended_env_change}")
    result = build_crew(topic).kickoff()
    out = result.pydantic
    if out is None:
        out = ResearchOutput(**json.loads(result.raw))
    out.execution_mode = "crewai"
    out.preflight_ok = preflight_ok
    out.provider = os.getenv("LLM_PROVIDER", "groq")
    out.model = get_active_model()
    return out


def _run_fallback_research(topic: str, reason: str, preflight_ok: bool) -> ResearchOutput:
    print(f"[M1 SEARCH START] Searching web sources for '{topic}'...")
    results = multi_source_search(topic, n=6)
    print(f"[M1 SEARCH DONE] Search returned {len(results)} candidate sources.")
    sources = []
    for index, r in enumerate(results):
        title = str(r.get("title") or "").strip()
        url = str(r.get("url") or r.get("link") or "").strip()
        snippet = str(r.get("snippet") or r.get("body") or "").strip()
        if not title or not url or not snippet:
            continue
        metadata = {}
        if index < 3:
            print(f"[M1 METADATA] Enriching source {index + 1}/3...")
            metadata = enrich_source_metadata(url, title)
        sources.append(Source(
            title=title,
            url=url,
            snippet=snippet,
            source_type="paper",
            published=r.get("published"),
            authors=metadata.get("authors", []),
            venue=metadata.get("venue"),
            doi=metadata.get("doi"),
            abstract=metadata.get("abstract"),
            metadata_status=metadata.get("metadata_status", "unavailable"),
        ))
    topic_terms = [w for w in re.findall(r"[A-Za-z]{4,}", topic)][:3]
    topic_label = " ".join(topic_terms) or topic
    subtopics = [
        f"Scope and evidence on {topic_label}",
        f"Methods and documented applications of {topic_label}",
        f"Challenges and limitations reported for {topic_label}",
    ]
    findings = []
    for index, subtopic in enumerate(subtopics):
        group = sources[index::len(subtopics)]
        if not group:
            continue
        evidence = " ".join(
            re.sub(r"\s+", " ", source.snippet).strip()
            for source in group[:2]
            if source.snippet
        )[:500]
        findings.append(Finding(
            subtopic=subtopic,
            summary=(
                f"Retrieved evidence for {topic_label}: {evidence}"
                if evidence else
                f"No claim-level excerpt was available for {topic_label}; additional verification is required."
            ),
            source_urls=[source.url for source in group[:2]]
        ))
    out = ResearchOutput(
        topic=topic,
        subtopics=subtopics,
        sources=sources,
        findings=findings,
        execution_mode="deterministic_fallback",
        fallback_reason=reason,
        provider=os.getenv("LLM_PROVIDER", "groq"),
        model=get_active_model(),
        preflight_ok=preflight_ok,
    )

    return dedupe_sources(out)


def run_research_analyst(topic: str) -> ResearchOutput:
    """Run M1 with a hard parent deadline around the real CrewAI attempt."""
    started = time.monotonic()
    reason = ""
    preflight_ok = False
    if os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY"):
        result_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".m1.json", delete=False, encoding="utf-8"
        )
        result_path = result_file.name
        result_file.close()
        worker = subprocess.Popen(
            [sys.executable, "-m", "research_analyst_worker"],
            cwd=str(Path(__file__).resolve().parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            worker.stdin.write(json.dumps({"topic": topic, "result_path": result_path}))
            worker.stdin.close()
            worker.wait(timeout=45)
            if worker.returncode == 0:
                with open(result_path, "r", encoding="utf-8") as result_handle:
                    data = json.load(result_handle)
                out = ResearchOutput(**data)
                return dedupe_sources(out)
            reason = f"M1 worker exited with code {worker.returncode}."
        except subprocess.TimeoutExpired:
            reason = "M1 CrewAI worker exceeded the 45-second hard deadline and was terminated."
            worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            reason = f"Invalid M1 worker response: {type(exc).__name__}: {exc}"
        finally:
            try:
                os.unlink(result_path)
            except FileNotFoundError:
                pass
    else:
        reason = "No configured LLM credential."

    fallback_reason = reason or "M1 CrewAI execution failed."
    result_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".m1-fallback.json", delete=False, encoding="utf-8"
    )
    result_path = result_file.name
    result_file.close()
    worker = subprocess.Popen(
        [sys.executable, "-m", "research_analyst_worker"],
        cwd=str(Path(__file__).resolve().parent),
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        worker.stdin.write(json.dumps({
            "topic": topic,
            "result_path": result_path,
            "mode": "fallback",
            "reason": fallback_reason,
            "preflight_ok": preflight_ok,
        }))
        worker.stdin.close()
        worker.wait(timeout=35)
        if worker.returncode == 0:
            with open(result_path, "r", encoding="utf-8") as result_handle:
                return dedupe_sources(ResearchOutput(**json.load(result_handle)))
        fallback_reason = f"Fallback worker exited with code {worker.returncode}."
    except subprocess.TimeoutExpired:
        fallback_reason = "M1 fallback worker exceeded the 35-second hard deadline."
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        fallback_reason = f"Invalid M1 fallback response: {type(exc).__name__}: {exc}"
    finally:
        try:
            os.unlink(result_path)
        except FileNotFoundError:
            pass

    return ResearchOutput(
        topic=topic,
        subtopics=[],
        sources=[],
        findings=[],
        execution_mode="failed",
        fallback_reason=fallback_reason,
        provider=os.getenv("LLM_PROVIDER", "groq"),
        model=get_active_model(),
        preflight_ok=preflight_ok,
    )


def main():
    topic = " ".join(sys.argv[1:]).strip() or input("Enter research topic: ").strip()
    if not topic:
        sys.exit("A research topic is required.")

    out = run_research_analyst(topic)
    metrics = compute_metrics(out)

    os.makedirs("outputs", exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:50]
    path = f"outputs/research_{slug}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**out.model_dump(), "metrics": metrics}, f, indent=2, ensure_ascii=False)

    print("\n=== RESEARCH ANALYST METRICS (Karthik - Module 1) ===")
    for k, v in metrics.items():
        print(f"{k}: {v}")
    print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
