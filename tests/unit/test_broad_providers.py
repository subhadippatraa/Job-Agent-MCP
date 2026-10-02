from job_search_agent.providers.adzuna import AdzunaProvider
from job_search_agent.providers.remoteok import RemoteOKProvider, _open_to_india


def test_remoteok_requires_explicit_india_eligibility():
    assert _open_to_india({"location": "Worldwide", "tags": []})
    assert _open_to_india({"location": "", "tags": ["APAC", "Python"]})
    assert not _open_to_india({"location": "United States", "tags": ["Python"]})
    assert not _open_to_india({"location": "Remote", "tags": ["Python"]})


def test_remoteok_normalizes_job():
    job = RemoteOKProvider()._normalize(
        {
            "id": "123",
            "company": "Acme",
            "position": "AI Engineer",
            "location": "Worldwide",
            "description": "<p>Build RAG systems with Python and FastAPI.</p>",
            "url": "https://remoteok.com/remote-jobs/123",
            "apply_url": "https://acme.example/apply",
            "date": "2026-10-01T10:00:00+00:00",
        }
    )
    assert job.remote_type == "remote"
    assert job.application_url == "https://acme.example/apply"
    assert "Python" in job.required_skills


def test_adzuna_normalizes_india_job(monkeypatch):
    provider = AdzunaProvider()
    provider.country = "in"
    job = provider._normalize(
        {
            "id": "456",
            "company": {"display_name": "Acme India"},
            "title": "Generative AI Engineer",
            "description": "1-3 years of experience with Python, RAG, and LangChain.",
            "location": {"display_name": "Bengaluru, Karnataka"},
            "redirect_url": "https://www.adzuna.in/jobs/details/456",
            "created": "2026-10-01T10:00:00Z",
            "contract_time": "full_time",
        }
    )
    assert job.country == "India"
    assert job.min_experience == 1
    assert job.max_experience == 3
