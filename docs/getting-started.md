# Getting Started

## Prerequisites

- **Python 3.11+**
- **pip** or **uv** for dependency management
- (Optional) **Docker** for PostgreSQL
- (Optional) **OpenAI** or **Anthropic** API key for LLM-enhanced analysis

## 1. Clone & Install

```bash
git clone https://github.com/subhadippatraa/Job-Agent-MCP.git
cd Job-Agent-MCP
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

## 2. Configure

```bash
cp .env.example .env
cp profile/candidate.example.yaml profile/candidate.yaml
```

Edit `profile/candidate.yaml` with your details:
- Name, target roles, skills, experience
- Location preferences, remote preference
- Domain interests

Place your resume at `resume/master_resume.pdf`.

## 3. Database Setup

### SQLite (easiest — recommended for getting started)

In your `.env`, set:
```
DATABASE_URL=sqlite+aiosqlite:///./jobagent.db
```

### PostgreSQL (production)

```bash
docker compose up -d
```

Keep the default `.env` setting:
```
DATABASE_URL=postgresql+asyncpg://jobagent:jobagent@localhost:5432/jobagent
```

Then apply database migrations:
```bash
alembic upgrade head
```

For a database created by an older version, first run `alembic stamp 0001`,
then `alembic upgrade head`. Continue using `job-search-agent init-db` only for
throwaway SQLite development databases.

## 4. Configure Job Sources

In `.env`, add company board slugs (comma-separated):

```bash
GREENHOUSE_BOARDS=anthropic,openai,stripe,figma,vercel
LEVER_COMPANIES=openai,anthropic,databricks,notion
ASHBY_BOARDS=anthropic,descript,ramp
```

> **Tip**: These are public ATS APIs — no authentication needed. The slug is
> usually the company name in the board URL (e.g., `boards.greenhouse.io/anthropic`).

## 5. Optional: LLM for Enhanced Analysis

LLM is **optional**. The core scoring engine is fully deterministic. LLM adds:
- Deeper JD requirement extraction (skills regex may miss)
- Semantic job comparison
- JD summarization
- Seniority/red flag detection

```bash
# In .env:
LLM_PROVIDER=openai          # or "anthropic"
OPENAI_API_KEY=sk-...         # if using OpenAI
# ANTHROPIC_API_KEY=sk-ant-...  # if using Anthropic
```

## 6. Start the MCP Server

```bash
python -m job_search_agent.server
```

Or via the CLI:
```bash
job-search-agent serve
```

## 7. Connect to Your AI Client

See the integration guides:
- [Codex](codex.md)
- [Claude Code](claude-code.md)
- [Antigravity](antigravity.md)
- [Playwright MCP](playwright-integration.md)

## 8. Verify

In your AI client, ask:
```
What MCP tools do you have available?
```

You should see the `job-search-agent` tools listed. Then try:
```
Find AI jobs matching my resume.
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./jobagent.db` | Database connection |
| `CANDIDATE_PROFILE_PATH` | `profile/candidate.yaml` | Candidate profile |
| `RESUME_PATH` | `resume/master_resume.pdf` | Resume file |
| `GREENHOUSE_BOARDS` | *(empty)* | Greenhouse company slugs |
| `LEVER_COMPANIES` | *(empty)* | Lever company slugs |
| `ASHBY_BOARDS` | *(empty)* | Ashby board names |
| `DEFAULT_SEARCH_LIMIT` | `50` | Max results per search |
| `DEFAULT_POSTED_WITHIN_HOURS` | `24` | Time window for new jobs |
| `LLM_PROVIDER` | `none` | `openai`, `anthropic`, or `none` |
| `REQUIRE_HUMAN_APPROVAL` | `true` | Require user confirmation before recording applications |
| `MATCH_WEIGHT_*` | *(see .env.example)* | Matching algorithm weights |
| `LOG_LEVEL` | `INFO` | Logging level |
