# Claude Code Integration

## Add MCP Server

```bash
claude mcp add job-search-agent -- /path/to/JOB-Agent/.venv/bin/python -m job_search_agent.server
```

Replace `/path/to/JOB-Agent` with the actual path.

### With Environment Variables

```bash
claude mcp add job-search-agent \
  -e DATABASE_URL=sqlite+aiosqlite:///./jobagent.db \
  -- /path/to/JOB-Agent/.venv/bin/python -m job_search_agent.server
```

### Project Scope (default)

Saves to `.mcp.json` in the project root.

### User Scope (all projects)

```bash
claude mcp add --scope user job-search-agent -- ...
```

## Verify

```bash
claude mcp list
```

Or inside a Claude Code session, type `/mcp` to check server status.

## CLAUDE.md

Copy `CLAUDE.md` from this repository to your project root. It tells Claude when and how to use the job-search-agent tools.

## Example Prompts

```
Find the best new AI jobs for me.
Only remote positions.
Show me jobs scoring above 80.
Prepare an application for job 2.
Have I applied to Anthropic before?
Show applications from the last 30 days.
```
