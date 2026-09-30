"""Developer CLI for testing and debugging — with rich output."""

from __future__ import annotations

import asyncio
import sys

import click

from job_search_agent.config import get_settings
from job_search_agent.logging import setup_logging

# ── Rich output helpers ──────────────────────────────────────────────────────

_SCORE_COLORS = {
    "exceptional_match": "bright_green",
    "strong_match": "green",
    "good_match": "yellow",
    "possible_match": "bright_yellow",
    "low_match": "red",
}


def _score_bar(score: float, width: int = 20) -> str:
    """Render a visual bar for a score 0-100."""
    filled = int(score / 100 * width)
    empty = width - filled
    if score >= 80:
        color = "🟢"
    elif score >= 60:
        color = "🟡"
    else:
        color = "🔴"
    return f"{color} {'█' * filled}{'░' * empty} {score:.0f}"


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _header(title: str, char: str = "═", width: int = 70) -> None:
    """Print a styled header."""
    click.echo(f"\n{char * width}")
    click.echo(f"  {title}")
    click.echo(f"{char * width}")


def _subheader(title: str) -> None:
    """Print a sub-section header."""
    click.echo(f"\n  ── {title} {'─' * max(1, 60 - len(title))}")


# ── CLI Group ────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version="0.1.0", prog_name="job-search-agent")
def cli() -> None:
    """🔍 Job Search Agent — AI-powered job search CLI.

    Search, analyze, match, compare, and track job applications.
    """
    settings = get_settings()
    setup_logging(level=settings.log_level, fmt="console")


# ── Search ───────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--roles", "-r", multiple=True, help="Target roles to search")
@click.option("--keywords", "-k", multiple=True, help="Search keywords")
@click.option("--location", "-l", default=None, help="Location filter")
@click.option("--remote", is_flag=True, help="Remote only")
@click.option("--limit", default=10, help="Max results")
@click.option("--hours", default=24, help="Posted within hours")
@click.option("--source", "-s", multiple=True, help="Providers (greenhouse, lever, ashby)")
def search(
    roles: tuple,
    keywords: tuple,
    location: str | None,
    remote: bool,
    limit: int,
    hours: int,
    source: tuple,
) -> None:
    """Search for jobs across all configured providers."""
    from job_search_agent.tools.search import search_jobs

    result = asyncio.run(
        search_jobs(
            roles=list(roles) if roles else None,
            keywords=list(keywords) if keywords else None,
            location=location,
            remote_only=remote,
            limit=limit,
            posted_within_hours=hours,
            sources=list(source) if source else None,
        )
    )

    jobs = result.get("jobs", [])
    total = result.get("total_found", 0)
    new = result.get("new_jobs", 0)
    providers = ", ".join(result.get("providers_used", []))
    dupes = result.get("duplicates_skipped", 0)

    _header(f"Search Results — {total} found, {new} new, {dupes} duplicates skipped")
    click.echo(f"  Providers: {providers or 'none configured'}")

    if not jobs:
        click.echo("\n  No jobs found. Try broadening your search.\n")
        return

    _subheader("Jobs")
    for i, job in enumerate(jobs, 1):
        score = job.get("match_score")
        score_str = f"{score:.0f}%" if score else " — "
        remote_badge = " 🏠" if job.get("remote_type") == "remote" else ""
        click.echo(
            f"  {i:3d}. [{score_str:>4s}] {job['company']:<20s} {_truncate(job['title'], 35)}{remote_badge}"
        )
        if job.get("location"):
            click.echo(f"       📍 {job['location']}")
        if job.get("id"):
            click.echo(f"       🆔 {job['id']}")

    if result.get("errors"):
        _subheader("Warnings")
        for err in result["errors"]:
            click.echo(f"  ⚠️  {err}")

    click.echo()


# ── Analyze ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("url")
def analyze(url: str) -> None:
    """Analyze a job posting from any URL."""
    from job_search_agent.tools.analyze import analyze_job_url

    click.echo(f"\n  ⏳ Fetching and analyzing {_truncate(url, 50)}...")
    result = asyncio.run(analyze_job_url(url))

    if "error" in result:
        click.echo(f"  ❌ {result['error']}")
        sys.exit(1)

    job = result.get("job", {})
    _header(f"{job.get('company', 'Unknown')} — {job.get('title', 'Unknown')}")

    click.echo(f"  📍 Location:   {job.get('location', 'Not specified')}")
    click.echo(f"  🏠 Remote:     {job.get('remote_type', 'unknown')}")
    click.echo(f"  💼 Type:       {job.get('employment_type', 'unknown')}")
    click.echo(
        f"  📅 Experience: {job.get('min_experience', '?')}-{job.get('max_experience', '?')} years"
    )
    click.echo(f"  🔗 ATS:        {job.get('ats_provider', 'unknown')}")
    click.echo(f"  🆔 ID:         {job.get('id', '—')}")

    if job.get("required_skills"):
        _subheader("Required Skills")
        for s in job["required_skills"][:12]:
            click.echo(f"    • {s}")

    if job.get("preferred_skills"):
        _subheader("Preferred Skills")
        for s in job["preferred_skills"][:8]:
            click.echo(f"    ○ {s}")

    if job.get("salary_min"):
        cur = job.get("salary_currency", "")
        click.echo(
            f"\n  💰 Salary: {cur} {job['salary_min']:,.0f} – {job.get('salary_max', '?'):,.0f}"
        )

    if result.get("note"):
        click.echo(f"\n  ℹ️  {result['note']}")

    click.echo()


# ── Match ────────────────────────────────────────────────────────────────────


@cli.command("match")
@click.argument("job_id")
def match_job(job_id: str) -> None:
    """Score a job against your candidate profile."""
    from job_search_agent.tools.match import match_job_to_candidate

    result = asyncio.run(match_job_to_candidate(job_id=job_id))

    if "error" in result:
        click.echo(f"  ❌ {result['error']}")
        sys.exit(1)

    score = result["score"]
    rec = result["recommendation"]
    _header(f"Match Score: {score}/100 — {rec.replace('_', ' ').title()}")

    # Visual score bar
    click.echo(f"\n  {_score_bar(score, 30)}")

    if result.get("matched_skills"):
        _subheader("Matched Skills")
        click.echo(f"    {', '.join(result['matched_skills'][:10])}")

    if result.get("missing_required_skills"):
        _subheader("Missing Required Skills")
        click.echo(f"    {', '.join(result['missing_required_skills'][:8])}")

    if result.get("strengths"):
        _subheader("Strengths")
        for s in result["strengths"]:
            click.echo(f"    💪 {s}")

    if result.get("concerns"):
        _subheader("Concerns")
        for c in result["concerns"]:
            click.echo(f"    ⚠️  {c}")

    if result.get("breakdown"):
        bd = result["breakdown"]
        _subheader("Score Breakdown")

        rows = [
            (
                "Required Skills",
                bd["required_skills_score"],
                bd["required_skills_weight"],
                bd["required_skills_detail"],
            ),
            (
                "Preferred Skills",
                bd["preferred_skills_score"],
                bd["preferred_skills_weight"],
                bd["preferred_skills_detail"],
            ),
            (
                "Experience",
                bd["experience_score"],
                bd["experience_weight"],
                bd["experience_detail"],
            ),
            (
                "Role Similarity",
                bd["role_similarity_score"],
                bd["role_similarity_weight"],
                bd["role_similarity_detail"],
            ),
            ("Location", bd["location_score"], bd["location_weight"], bd["location_detail"]),
            ("Domain", bd["domain_score"], bd["domain_weight"], bd["domain_detail"]),
        ]

        click.echo(f"    {'Category':<20s} {'Score':>6s} {'Weight':>7s}  {'Detail'}")
        click.echo(f"    {'─' * 20} {'─' * 6} {'─' * 7}  {'─' * 35}")
        for name, sc, wt, detail in rows:
            click.echo(f"    {name:<20s} {sc:5.1f}  {wt:5.0%}    {_truncate(detail, 35)}")

    click.echo()


# ── Compare ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("job_id_a")
@click.argument("job_id_b")
def compare(job_id_a: str, job_id_b: str) -> None:
    """Compare two jobs side-by-side."""
    from job_search_agent.tools.enhance import compare_jobs

    click.echo("\n  ⏳ Comparing jobs...")
    result = asyncio.run(compare_jobs(job_id_a=job_id_a, job_id_b=job_id_b))

    if "error" in result:
        click.echo(f"  ❌ {result['error']}")
        sys.exit(1)

    ja = result["job_a"]
    jb = result["job_b"]

    _header("Job Comparison")

    # Side by side
    click.echo(f"\n  {'':>4s} {'Job A':^32s} │ {'Job B':^32s}")
    click.echo(f"  {'':>4s} {'─' * 32} │ {'─' * 32}")
    click.echo(f"  {'Co.':<4s} {ja['company']:<32s} │ {jb['company']:<32s}")
    click.echo(
        f"  {'Role':<4s} {_truncate(ja['title'], 32):<32s} │ {_truncate(jb['title'], 32):<32s}"
    )
    click.echo(
        f"  {'Loc.':<4s} {_truncate(ja.get('location', '—') or '—', 32):<32s} │ {_truncate(jb.get('location', '—') or '—', 32):<32s}"
    )

    # Scores
    _subheader("Scores")
    click.echo(f"    Job A: {_score_bar(ja['score'])}")
    click.echo(f"    Job B: {_score_bar(jb['score'])}")

    winner = result.get("deterministic_winner", "tie")
    diff = result.get("score_difference", 0)
    if winner == "tie":
        click.echo(f"\n    ⚖️  Tied (difference: {diff:.1f})")
    else:
        click.echo(f"\n    🏆 Winner: Job {winner} (by {diff:.1f} points)")

    # LLM analysis
    if result.get("has_llm_analysis"):
        llm = result["llm_analysis"]
        _subheader("LLM Analysis")
        click.echo(f"    Recommendation: {llm.get('recommendation', '—')}")
        click.echo(f"    Reasoning: {llm.get('reasoning', '—')}")
        if llm.get("growth_potential"):
            click.echo(f"    Growth: {llm['growth_potential']}")
    else:
        click.echo("\n    ℹ️  LLM not configured — showing deterministic comparison only")

    click.echo()


# ── Enhance ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("job_id")
def enhance(job_id: str) -> None:
    """Run LLM-enhanced deep analysis on a job."""
    from job_search_agent.tools.enhance import enhance_job_analysis

    click.echo("\n  ⏳ Running enhanced analysis...")
    result = asyncio.run(enhance_job_analysis(job_id=job_id))

    if "error" in result:
        click.echo(f"  ❌ {result['error']}")
        sys.exit(1)

    _header(f"{result.get('company', '?')} — {result.get('title', '?')}")
    click.echo(f"  Enhanced: {'✅ LLM-powered' if result.get('enhanced') else '📝 Regex-only'}")

    if result.get("summary"):
        _subheader("Summary")
        click.echo(f"    {result['summary']}")

    _subheader("Required Skills")
    for s in result.get("required_skills", [])[:15]:
        click.echo(f"    • {s}")

    if result.get("preferred_skills"):
        _subheader("Preferred Skills")
        for s in result["preferred_skills"][:10]:
            click.echo(f"    ○ {s}")

    meta = result.get("llm_metadata", {})
    if meta:
        if meta.get("seniority_level"):
            click.echo(f"\n  📊 Seniority: {meta['seniority_level']}")
        if meta.get("tech_stack"):
            _subheader("Tech Stack")
            click.echo(f"    {', '.join(meta['tech_stack'][:12])}")
        if meta.get("responsibilities"):
            _subheader("Key Responsibilities")
            for r in meta["responsibilities"][:5]:
                click.echo(f"    • {r}")
        if meta.get("red_flags"):
            _subheader("Red Flags ⚠️")
            for rf in meta["red_flags"]:
                click.echo(f"    🚩 {rf}")
        if meta.get("ai_ml_relevance") is not None:
            click.echo(f"\n  🤖 AI/ML Relevance: {meta['ai_ml_relevance']}/100")
        if meta.get("llm_only_required_skills"):
            _subheader("Skills Found Only by LLM")
            click.echo(f"    {', '.join(meta['llm_only_required_skills'])}")

    click.echo()


# ── Prepare ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("job_id")
def prepare(job_id: str) -> None:
    """Prepare an application package for a job."""
    from job_search_agent.tools.applications import prepare_application

    click.echo("\n  ⏳ Preparing application...")
    result = asyncio.run(prepare_application(job_id=job_id))

    if "error" in result:
        click.echo(f"  ❌ {result['error']}")
        sys.exit(1)

    _header(f"Application Prep: {result.get('company', '?')} — {result.get('title', '?')}")

    score = result.get("match_score", 0)
    click.echo(f"\n  Score: {_score_bar(score, 25)}")
    click.echo(f"  Recommendation: {result.get('recommendation', '—')}")

    if result.get("important_requirements"):
        _subheader("Key Requirements")
        for r in result["important_requirements"]:
            click.echo(f"    📌 {r}")

    if result.get("skills_to_emphasize"):
        _subheader("Skills to Emphasize")
        click.echo(f"    {', '.join(result['skills_to_emphasize'][:8])}")

    if result.get("potential_gaps"):
        _subheader("Gaps to Address")
        for g in result["potential_gaps"]:
            click.echo(f"    ⚠️  {g}")

    if result.get("relevant_resume_bullets"):
        _subheader("Relevant Resume Bullets")
        for b in result["relevant_resume_bullets"][:5]:
            click.echo(f"    ✏️  {_truncate(b, 70)}")

    if result.get("likely_screening_questions"):
        _subheader("Likely Screening Questions")
        for q in result["likely_screening_questions"][:5]:
            click.echo(f"    ❓ {q}")

    if result.get("requires_user_input"):
        _subheader("Requires Your Input")
        for field in result["requires_user_input"]:
            click.echo(f"    📝 {field.replace('_', ' ').title()}")

    if result.get("suggested_recruiter_message"):
        _subheader("Suggested Recruiter Message")
        click.echo(f"    {result['suggested_recruiter_message']}")

    if result.get("application_url"):
        click.echo(f"\n  🔗 Apply: {result['application_url']}")

    if result.get("application_checklist"):
        _subheader("Checklist")
        for item in result["application_checklist"]:
            click.echo(f"    ☐ {item}")

    click.echo()


# ── Digest ───────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--hours", "-h", default=24, help="Look back hours")
@click.option("--min-score", "-m", type=float, default=None, help="Minimum score")
@click.option("--limit", "-l", default=10, help="Max results")
def digest(hours: int, min_score: float | None, limit: int) -> None:
    """Show today's best job opportunities."""
    from job_search_agent.tools.stats import get_daily_job_digest

    result = asyncio.run(get_daily_job_digest(hours=hours, min_score=min_score, limit=limit))

    jobs = result.get("jobs", [])
    _header(f"Daily Digest — {result.get('digest_period', 'Last 24 hours')}")
    click.echo(f"  Since: {result.get('since', '—')}")
    click.echo(f"  Jobs: {result.get('total', 0)}")

    if not jobs:
        click.echo("\n  No new jobs matching your criteria.\n")
        return

    _subheader("Top Opportunities")
    for i, job in enumerate(jobs, 1):
        score = job.get("match_score")
        score_str = f"{score:.0f}%" if score else " — "
        remote_badge = " 🏠" if job.get("remote_type") == "remote" else ""
        click.echo(
            f"  {i:3d}. [{score_str:>4s}] {job['company']:<20s} {_truncate(job['title'], 30)}{remote_badge}"
        )
        if job.get("application_url"):
            click.echo(f"       🔗 {_truncate(job['application_url'], 55)}")

    click.echo()


# ── Stats ────────────────────────────────────────────────────────────────────


@cli.command()
def stats() -> None:
    """Show job search statistics dashboard."""
    from job_search_agent.tools.stats import get_job_stats

    result = asyncio.run(get_job_stats())
    summary = result.get("summary", {})

    _header("Job Search Dashboard")

    click.echo("\n  📊 Overview")
    click.echo(f"    Jobs Discovered:     {summary.get('total_jobs_discovered', 0):>5d}")
    click.echo(f"    Shortlisted:         {summary.get('jobs_shortlisted', 0):>5d}")
    click.echo(f"    Applications:        {summary.get('applications_submitted', 0):>5d}")
    click.echo(f"    Interviews:          {summary.get('interviews', 0):>5d}")
    click.echo(f"    Rejections:          {summary.get('rejections', 0):>5d}")
    click.echo(f"    Offers:              {summary.get('offers', 0):>5d}")

    avg = summary.get("average_match_score")
    if avg:
        click.echo(f"\n  📈 Average Match Score: {avg:.1f}/100")

    # Status breakdown
    job_stats = result.get("jobs", {}).get("by_status", {})
    if job_stats:
        _subheader("Jobs by Status")
        for status, count in sorted(job_stats.items()):
            if count > 0:
                bar = "█" * min(count, 30)
                click.echo(f"    {status:<15s} {count:>4d}  {bar}")

    click.echo()


# ── Apps ─────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--company", "-c", default=None, help="Filter by company")
@click.option("--days", "-d", type=int, default=None, help="Last N days")
def apps(status: str | None, company: str | None, days: int | None) -> None:
    """List tracked applications."""
    from job_search_agent.tools.applications import get_applications

    result = asyncio.run(get_applications(status=status, company=company, days=days))

    apps_list = result.get("applications", [])

    _header(f"Applications — {len(apps_list)} found")

    if not apps_list:
        click.echo("\n  No applications found.\n")
        return

    for app_data in apps_list:
        app = app_data if isinstance(app_data, dict) else {}
        app_inner = app.get("application", app)
        job = app.get("job", app)
        status_emoji = {
            "applied": "📤",
            "interview": "🎤",
            "offer": "🎉",
            "rejected": "❌",
            "withdrawn": "🚫",
            "shortlisted": "⭐",
        }
        emoji = status_emoji.get(app_inner.get("status", ""), "📋")
        click.echo(
            f"  {emoji} [{app_inner.get('status', '?'):<12s}] "
            f"{job.get('company', '?'):<18s} {_truncate(job.get('title', '?'), 30)}"
        )
        if app_inner.get("applied_at"):
            click.echo(f"     Applied: {app_inner['applied_at']}")

    click.echo()


# ── Serve ────────────────────────────────────────────────────────────────────


@cli.command()
def serve() -> None:
    """Start the MCP server (STDIO transport)."""
    from job_search_agent.server import main

    main()


# ── Init DB ──────────────────────────────────────────────────────────────────


@cli.command("init-db")
def init_db() -> None:
    """Initialize the database tables."""
    from job_search_agent.database import init_db as _init

    asyncio.run(_init())
    click.echo("  ✅ Database initialized successfully")


if __name__ == "__main__":
    cli()
