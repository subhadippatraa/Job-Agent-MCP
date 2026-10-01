# Codex Integration

## Add MCP Server

### Option 1: Global Config

Edit `~/.codex/config.toml`:

```toml
[mcp_servers.job-search-agent]
command = "/path/to/JOB-Agent/.venv/bin/python"
args = ["-m", "job_search_agent.server"]
cwd = "/path/to/JOB-Agent"
```

Replace `/path/to/JOB-Agent` with the actual path to this repository.

### Option 2: Project Config

Create `.codex/config.toml` in your project root:

```toml
[mcp_servers.job-search-agent]
command = "/path/to/JOB-Agent/.venv/bin/python"
args = ["-m", "job_search_agent.server"]
cwd = "/path/to/JOB-Agent"
```

## Verify

Run `codex mcp list`, then start a new Codex session and ask:

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
