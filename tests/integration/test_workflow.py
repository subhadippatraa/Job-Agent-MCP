import yaml

from job_search_agent.config import reset_settings
from job_search_agent.database import close_db, get_session, init_db
from job_search_agent.database.repository import JobRepository
from job_search_agent.server import record_application
from job_search_agent.tools.applications import (
    get_applications,
    prepare_application,
    update_application_status,
)
from job_search_agent.tools.match import match_job_to_candidate, rank_jobs
from job_search_agent.tools.stats import get_job_stats


async def test_application_workflow(tmp_path, monkeypatch, sample_candidate, ai_engineer_job):
    database = tmp_path / "jobagent.db"
    profile = tmp_path / "candidate.yaml"
    profile.write_text(yaml.safe_dump(sample_candidate.model_dump(mode="json")))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("CANDIDATE_PROFILE_PATH", str(profile))
    monkeypatch.setenv("RESUME_PATH", str(tmp_path / "missing.pdf"))

    await close_db()
    reset_settings()
    await init_db()
    session = await get_session()
    try:
        await JobRepository(session).save(ai_engineer_job)
        await session.commit()
    finally:
        await session.close()

    match = await match_job_to_candidate(job_id=ai_engineer_job.id)
    assert match["score"] >= 70

    changed_candidate = sample_candidate.model_copy(
        update={
            "target_roles": ["Accountant"],
            "skills": [],
            "primary_skills": [],
            "secondary_skills": [],
        }
    )
    profile.write_text(yaml.safe_dump(changed_candidate.model_dump(mode="json")))
    reranked = await rank_jobs([ai_engineer_job.id])
    assert reranked["ranked_jobs"][0]["score"] < match["score"]
    profile.write_text(yaml.safe_dump(sample_candidate.model_dump(mode="json")))

    prep = await prepare_application(ai_engineer_job.id)
    assert prep["company"] == ai_engineer_job.company
    assert "work_authorization" in prep["requires_user_input"]

    denied = await record_application(ai_engineer_job.id)
    assert denied["error"] == "Human approval required"
    recorded = await record_application(ai_engineer_job.id, user_confirmed=True)
    assert recorded["status"] == "recorded"

    updated = await update_application_status(ai_engineer_job.id, "interview")
    assert updated["new_status"] == "interview"
    applications = await get_applications(status="interview")
    assert applications["total"] == 1
    stats = await get_job_stats()
    assert stats["applications"]["by_status"]["interview"] == 1
    duplicate = await record_application(ai_engineer_job.id, user_confirmed=True)
    assert duplicate["error"] == "Application already recorded for this job"
    assert (await get_applications())["total"] == 1

    await close_db()
    reset_settings()
