from datetime import UTC, datetime, timedelta

from job_search_agent.models.job import Job, RemoteType
from job_search_agent.providers.base import SearchQuery, matches_query


def test_all_search_filters_are_applied():
    job = Job(
        company="Acme",
        title="AI Engineer",
        description="Build retrieval systems with Python",
        location="Bengaluru, India",
        country="India",
        remote_type=RemoteType.HYBRID,
        min_experience=3,
        required_skills=["Python", "RAG"],
        posted_at=datetime.now(UTC) - timedelta(hours=2),
    )

    assert matches_query(
        job,
        SearchQuery(
            keywords=["retrieval"],
            country="India",
            experience_min=2,
            experience_max=3,
            posted_within_hours=24,
            skills=["Python", "RAG"],
        ),
    )
    assert not matches_query(job, SearchQuery(country="US"))
    assert not matches_query(job, SearchQuery(experience_min=4))
    assert not matches_query(job, SearchQuery(posted_within_hours=1))
    assert not matches_query(job, SearchQuery(skills=["Go"]))
