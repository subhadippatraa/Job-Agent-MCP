# Job Search Agent 🔍

AI-powered job search MCP server — discover, match, score, and track job applications from any MCP-compatible client.

## What It Does

A standalone **Model Context Protocol (MCP) server** that automates the job search workflow:

```
Discovery → Normalization → Deduplication → Matching → Scoring → Ranking → Shortlisting → Application Prep → Tracking
```

Connect it to **Codex**, **Claude Code**, **Antigravity**, **Cursor**, or any MCP client and say:

> "Find AI jobs matching my resume from the last 24 hours."

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  MCP Clients                                             │
│  ┌────────┐ ┌───────────┐ ┌─────────────┐ ┌──────────┐  │
│  │ Codex  │ │ Claude    │ │ Antigravity │ │ Cursor   │  │
│  │ CLI    │ │ Code      │ │ IDE         │ │ / Other  │  │
│  └───┬────┘ └─────┬─────┘ └──────┬──────┘ └────┬─────┘  │
│      └─────────┬──┴──────────────┴──────────────┘        │
│                │  STDIO Transport                        │
│  ┌─────────────▼──────────────────────────────────────┐  │
│  │  job-search-agent MCP Server                       │  │
│  │                                                    │  │
│  │  16 Tools:                                         │  │
│  │  search_jobs · search_jobs_for_candidate           │  │
│  │  get_job · analyze_job_url · check_duplicate_job   │  │
│  │  match_job_to_candidate · rank_jobs                │  │
│  │  save_job · shortlist_job · skip_job               │  │
│  │  prepare_application · record_application          │  │
│  │  update_application_status · get_applications      │  │
│  │  get_job_stats · get_daily_job_digest              │  │
│  │                                                    │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────┐  │  │
│  │  │ Providers  │ │  Matching  │ │  Application   │  │  │
│  │  │ Greenhouse │ │  Engine    │ │  Tracker       │  │  │
│  │  │ Lever      │ │ (determin- │ │                │  │  │
│  │  │ Ashby      │ │  istic)    │ │                │  │  │
│  │  │ Generic    │ │            │ │                │  │  │
│  │  └────────────┘ └────────────┘ └────────────────┘  │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │  PostgreSQL / SQLite                               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Features

- **Multi-provider job search**: Greenhouse, Lever, Ashby (all public APIs, no auth needed)
- **Deterministic matching**: Explainable scores with configurable weights
- **Resume parsing**: PDF text extraction with skill→evidence mapping
- **Application tracking**: Full lifecycle from discovery to offer
- **LLM optional**: Core works without API keys; LLM enhances analysis when available
- **Human approval required**: Never auto-submits applications
- **Security**: Job descriptions treated as untrusted data

## Quick Start

### 1. Clone & Install

```bash
git clone <repo-url> job-search-agent
cd job-search-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

### 2. Configure

```bash
cp .env.example .env
cp profile/candidate.example.yaml profile/candidate.yaml
# Edit profile/candidate.yaml with your details
# Place your resume as resume/master_resume.pdf
```

### 3. Database

**SQLite (easiest, for development):**
Already configured in `.env.example`. No setup needed.

**PostgreSQL (production):**
```bash
docker compose up -d
# Update DATABASE_URL in .env to:
# postgresql+asyncpg://jobagent:jobagent@localhost:5432/jobagent
```

Initialize tables:
```bash
python -m job_search_agent init-db
```

### 4. Configure Job Sources

Edit `.env` with company board tokens:
```bash
GREENHOUSE_BOARDS=anthropic,openai,stripe,figma
LEVER_COMPANIES=openai,anthropic,databricks
ASHBY_BOARDS=anthropic,descript
```

### 5. Start MCP Server

```bash
python -m job_search_agent.server
```

## Client Integration

### Codex

Add to `~/.codex/config.toml`:
```toml
[mcpServers.job-search-agent]
command = "/path/to/job-search-agent/.venv/bin/python"
args = ["-m", "job_search_agent.server"]
```

### Claude Code

```bash
claude mcp add job-search-agent -- /path/to/.venv/bin/python -m job_search_agent.server
```

### Antigravity

Create `.agents/mcp_config.json`:
```json
{
  "mcpServers": {
    "job-search-agent": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "job_search_agent.server"]
    }
  }
}
```

See `docs/` for detailed integration guides.

## Example Prompts

| Prompt | Tool Called |
|--------|-----------|
| "Find jobs for me" | `search_jobs_for_candidate` |
| "Only remote ones" | `search_jobs(remote_only=true)` |
| "Show me the best 10" | `get_daily_job_digest` |
| "Why is job 4 only 71%?" | `match_job_to_candidate` |
| "Have I applied to Acme?" | `get_applications(company="Acme")` |
| "Prepare application for job 2" | `prepare_application` |
| "Show applications from last 30 days" | `get_applications(days=30)` |
| "How is my search going?" | `get_job_stats` |
| "Analyze this URL" | `analyze_job_url` |

## Matching Algorithm

Deterministic, configurable weights:

| Category | Weight | Description |
|----------|--------|-------------|
| Required Skills | 35% | Exact, alias, and partial skill matching |
| Experience | 20% | Graceful gap handling (1.8yr vs 2yr = minor penalty) |
| Role Similarity | 15% | Title matching with synonym groups |
| Preferred Skills | 10% | Nice-to-have skills |
| Location/Remote | 10% | Location and remote preference alignment |
| Domain Relevance | 10% | Industry/domain interest matching |

Score labels:
- 90-100: Exceptional match
- 80-89: Strong match
- 70-79: Good match
- 60-69: Possible/stretch match
- Below 60: Low match

## Security Model

- Job descriptions are **DATA**, never instructions
- Applications require **explicit user approval**
- Sensitive screening questions return `requires_user_input`
- No shell commands, email sending, or code execution from job content
- No CAPTCHA bypassing or authentication circumvention
- No automated LinkedIn scraping

## Dev CLI

```bash
python -m job_search_agent search -r "AI Engineer" --remote --limit 10
python -m job_search_agent analyze https://boards.greenhouse.io/company/jobs/123
python -m job_search_agent match <job-id>
python -m job_search_agent stats
python -m job_search_agent apps --status applied
python -m job_search_agent init-db
```

## Testing

```bash
pytest tests/ -v
pytest tests/ -v --cov=job_search_agent
```

## Project Structure

```
job-search-agent/
├── src/job_search_agent/
│   ├── server.py          # MCP server (entry point)
│   ├── config.py          # Configuration
│   ├── cli.py             # Dev CLI
│   ├── tools/             # MCP tool implementations
│   │   ├── search.py      # search_jobs, search_jobs_for_candidate
│   │   ├── analyze.py     # get_job, analyze_job_url, check_duplicate
│   │   ├── match.py       # match_job_to_candidate, rank_jobs
│   │   ├── applications.py # prepare, record, update, get
│   │   └── stats.py       # get_job_stats, get_daily_job_digest
│   ├── providers/         # Job source adapters
│   │   ├── base.py        # Abstract provider interface
│   │   ├── greenhouse.py  # Greenhouse API
│   │   ├── lever.py       # Lever API
│   │   ├── ashby.py       # Ashby API
│   │   └── generic.py     # Generic URL analyzer
│   ├── matching/          # Scoring engine
│   │   ├── scorer.py      # Composite scorer
│   │   ├── skills.py      # Skill matching + aliases
│   │   ├── experience.py  # Experience gap handling
│   │   └── titles.py      # Title similarity
│   ├── resume/            # Resume processing
│   │   ├── parser.py      # PDF text extraction
│   │   └── evidence.py    # Skill evidence mapping
│   ├── database/          # Persistence
│   │   ├── models.py      # SQLAlchemy ORM models
│   │   └── repository.py  # Async CRUD operations
│   ├── llm/               # Optional LLM integration
│   │   ├── base.py        # Abstract LLM interface
│   │   ├── openai.py      # OpenAI adapter
│   │   └── anthropic.py   # Anthropic adapter
│   └── models/            # Pydantic domain models
│       ├── job.py         # Canonical Job schema
│       ├── candidate.py   # Candidate profile
│       ├── application.py # Application tracking
│       └── match.py       # Match results
├── profile/
│   └── candidate.example.yaml
├── resume/
│   └── README.md
├── tests/
│   └── unit/
├── docs/
│   ├── codex.md
│   ├── claude-code.md
│   ├── antigravity.md
│   └── playwright-integration.md
├── AGENTS.md              # Instructions for Codex
├── CLAUDE.md              # Instructions for Claude Code
├── docker-compose.yml     # PostgreSQL
├── pyproject.toml
└── .env.example
```

## Limitations

- Providers require pre-configured company board tokens (no global job aggregation)
- Experience extraction from job descriptions is regex-based (LLM can enhance)
- Resume parsing is text-only (no layout/formatting analysis)
- No automated LinkedIn integration (by design — respects ToS)
- LLM features require API keys (core works without them)

## License

MIT
