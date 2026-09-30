# Codex Integration

## Add MCP Server

### Option 1: Global Config

Edit `~/.codex/config.toml`:

```toml
[mcpServers.job-search-agent]
command = "/path/to/JOB-Agent/.venv/bin/python"
args = ["-m", "job_search_agent.server"]
env = { "DATABASE_URL" = "sqlite+aiosqlite:///./jobagent.db" }
```

Replace `/path/to/JOB-Agent` with the actual path to this repository.

### Option 2: Project Config

Create `.codex/config.toml` in your project root:

```toml
[mcpServers.job-search-agent]
command = "/path/to/JOB-Agent/.venv/bin/python"
args = ["-m", "job_search_agent.server"]
```

## Verify

Start a Codex session and ask:

```
What MCP tools do you have available?
```

You should see the `job-search-agent` tools listed.

## Example Usage

```
Find AI Engineer jobs matching my resume from the last 24 hours.
```

```
Analyze this job: https://boards.greenhouse.io/anthropic/jobs/12345
```

```
Show me my top 10 opportunities.
```

## AGENTS.md

Copy `AGENTS.md` from this repository to your project root. It tells Codex when and how to use the job-search-agent tools.
