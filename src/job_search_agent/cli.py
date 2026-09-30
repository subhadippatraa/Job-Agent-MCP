"""Developer CLI for testing and debugging."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from job_search_agent.config import get_settings
from job_search_agent.logging import setup_logging


@click.group()
def cli() -> None:
    """Job Search Agent — developer CLI."""
    settings = get_settings()
    setup_logging(level=settings.log_level, fmt="console")


@cli.command()
@click.option("--roles", "-r", multiple=True, help="Target roles to search")
@click.option("--location", "-l", default=None, help="Location filter")
@click.option("--remote", is_flag=True, help="Remote only")
@click.option("--limit", default=10, help="Max results")
@click.option("--hours", default=24, help="Posted within hours")
def search(roles: tuple, location: str | None, remote: bool, limit: int, hours: int) -> None:
    """Search for jobs across providers."""
    from job_search_agent.tools.search import search_jobs

    result = asyncio.run(search_jobs(
        roles=list(roles) if roles else None,
        location=location,
        remote_only=remote,
        limit=limit,
        posted_within_hours=hours,
    ))

    jobs = result.get("jobs", [])
    click.echo(f"\n{'='*60}")
    click.echo(f"Found {result.get('total_found', 0)} jobs, {result.get('new_jobs', 0)} new")
    click.echo(f"Providers: {', '.join(result.get('providers_used', []))}")
    click.echo(f"{'='*60}\n")

    for i, job in enumerate(jobs, 1):
        score = job.get("match_score", "—")
        click.echo(f"{i:3d}. [{score}] {job['company']} — {job['title']}")
        if job.get("location"):
            click.echo(f"     📍 {job['location']}")
        if job.get("source_url"):
            click.echo(f"     🔗 {job['source_url']}")
        click.echo()

    if result.get("errors"):
        click.echo("⚠️  Errors:")
        for err in result["errors"]:
            click.echo(f"  - {err}")


@cli.command()
@click.argument("url")
def analyze(url: str) -> None:
    """Analyze a job posting URL."""
    from job_search_agent.tools.analyze import analyze_job_url

    result = asyncio.run(analyze_job_url(url))

    if "error" in result:
        click.echo(f"❌ {result['error']}")
        sys.exit(1)

    job = result.get("job", {})
    click.echo(f"\n{'='*60}")
    click.echo(f"📋 {job.get('company', 'Unknown')} — {job.get('title', 'Unknown')}")
    click.echo(f"{'='*60}")
    click.echo(f"📍 Location: {job.get('location', 'Not specified')}")
    click.echo(f"🏠 Remote: {job.get('remote_type', 'unknown')}")
    click.echo(f"💼 Type: {job.get('employment_type', 'unknown')}")
    click.echo(f"📅 Experience: {job.get('min_experience', '?')}-{job.get('max_experience', '?')} years")

    if job.get("required_skills"):
        click.echo(f"🔧 Required: {', '.join(job['required_skills'][:10])}")
    if job.get("preferred_skills"):
        click.echo(f"✨ Preferred: {', '.join(job['preferred_skills'][:10])}")
    if job.get("salary_min"):
        click.echo(f"💰 Salary: {job.get('salary_currency', '')} {job['salary_min']}-{job.get('salary_max', '?')}")

    click.echo(f"🔗 ATS: {job.get('ats_provider', 'unknown')}")
    click.echo(f"🆔 ID: {job.get('id', '—')}")


@cli.command("match")
@click.argument("job_id")
def match_job(job_id: str) -> None:
    """Match a job against the candidate profile."""
    from job_search_agent.tools.match import match_job_to_candidate

    result = asyncio.run(match_job_to_candidate(job_id=job_id))

    if "error" in result:
        click.echo(f"❌ {result['error']}")
        sys.exit(1)

    click.echo(f"\n{'='*60}")
    click.echo(f"Match Score: {result['score']}/100 — {result['recommendation']}")
    click.echo(f"{'='*60}")

    if result.get("matched_skills"):
        click.echo(f"✅ Matched: {', '.join(result['matched_skills'][:8])}")
    if result.get("missing_required_skills"):
        click.echo(f"❌ Missing required: {', '.join(result['missing_required_skills'][:5])}")
    if result.get("strengths"):
        click.echo("\n💪 Strengths:")
        for s in result["strengths"]:
            click.echo(f"  • {s}")
    if result.get("concerns"):
        click.echo("\n⚠️  Concerns:")
        for c in result["concerns"]:
            click.echo(f"  • {c}")

    if result.get("breakdown"):
        bd = result["breakdown"]
        click.echo(f"\n📊 Breakdown:")
        click.echo(f"  Required Skills:  {bd['required_skills_score']:5.1f} × {bd['required_skills_weight']:.0%} — {bd['required_skills_detail']}")
        click.echo(f"  Preferred Skills: {bd['preferred_skills_score']:5.1f} × {bd['preferred_skills_weight']:.0%} — {bd['preferred_skills_detail']}")
        click.echo(f"  Experience:       {bd['experience_score']:5.1f} × {bd['experience_weight']:.0%} — {bd['experience_detail']}")
        click.echo(f"  Role Similarity:  {bd['role_similarity_score']:5.1f} × {bd['role_similarity_weight']:.0%} — {bd['role_similarity_detail']}")
        click.echo(f"  Location:         {bd['location_score']:5.1f} × {bd['location_weight']:.0%} — {bd['location_detail']}")
        click.echo(f"  Domain:           {bd['domain_score']:5.1f} × {bd['domain_weight']:.0%} — {bd['domain_detail']}")


@cli.command()
def stats() -> None:
    """Show job search statistics."""
    from job_search_agent.tools.stats import get_job_stats

    result = asyncio.run(get_job_stats())
    click.echo(json.dumps(result, indent=2, default=str))


@cli.command()
@click.option("--status", "-s", default=None)
@click.option("--company", "-c", default=None)
@click.option("--days", "-d", type=int, default=None)
def apps(status: str | None, company: str | None, days: int | None) -> None:
    """List applications."""
    from job_search_agent.tools.applications import get_applications

    result = asyncio.run(get_applications(status=status, company=company, days=days))

    apps_list = result.get("applications", [])
    click.echo(f"\n📋 {len(apps_list)} applications found\n")
    for app_data in apps_list:
        app = app_data.get("application", {})
        job = app_data.get("job", {})
        click.echo(f"  [{app.get('status', '?')}] {job.get('company', '?')} — {job.get('title', '?')}")
        if app.get("applied_at"):
            click.echo(f"    Applied: {app['applied_at']}")


@cli.command()
def serve() -> None:
    """Start the MCP server (STDIO transport)."""
    from job_search_agent.server import main
    main()


@cli.command()
def init_db() -> None:
    """Initialize the database tables."""
    from job_search_agent.database import init_db as _init
    asyncio.run(_init())
    click.echo("✅ Database initialized")


if __name__ == "__main__":
    cli()
