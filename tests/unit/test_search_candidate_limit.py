from datetime import UTC, datetime, timedelta

from job_search_agent.tools.search import _prioritize_jobs, search_jobs_for_candidate


async def test_candidate_search_limit_is_capped():
    assert await search_jobs_for_candidate(0) == {"error": "limit must be between 1 and 300"}
    assert await search_jobs_for_candidate(301) == {"error": "limit must be between 1 and 300"}
    assert await search_jobs_for_candidate(1, 0) == {
        "error": "posted_within_days must be between 1 and 90"
    }


def test_daily_queue_prioritizes_fresh_matches_and_excludes_unusable_jobs():
    now = datetime(2026, 10, 2, tzinfo=UTC)
    jobs = [
        {
            "id": "older-fit",
            "match_score": 90,
            "min_experience": 2,
            "posted_at": now - timedelta(days=10),
        },
        {"id": "fresh-fit", "match_score": 88, "min_experience": 1, "posted_at": now},
        {"id": "unknown-age", "match_score": 85, "min_experience": 2, "posted_at": None},
        {
            "id": "too-old",
            "match_score": 99,
            "min_experience": 1,
            "posted_at": now - timedelta(days=31),
        },
        {"id": "already-applied", "match_score": 99, "min_experience": 1, "status": "applied"},
        {"id": "too-senior", "match_score": 99, "min_experience": 3, "posted_at": now},
        {"id": "unknown-experience", "match_score": 99, "posted_at": now},
        {"id": "weak", "match_score": 84, "min_experience": 1, "posted_at": now},
    ]

    ranked = _prioritize_jobs(jobs, min_score=85, posted_within_days=30, now=now)

    assert [job["id"] for job in ranked] == ["fresh-fit", "older-fit", "unknown-age"]
    assert ranked[0]["days_since_posted"] == 0
