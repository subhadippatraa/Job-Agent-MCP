from job_search_agent.providers.generic import GenericProvider


def test_parse_browser_text():
    job = GenericProvider().parse_text(
        "https://example.com/job",
        "Experience: 2+ years building RAG applications with Python, FastAPI, LangChain and PostgreSQL.",
        title="Generative AI Engineer",
        company="Acme",
        location="Remote",
    )

    assert job.company == "Acme"
    assert job.min_experience == 2
    assert job.remote_type == "remote"
    assert {"Python", "FastAPI", "LangChain", "PostgreSQL"} <= set(job.required_skills)
