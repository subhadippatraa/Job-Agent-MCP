# Antigravity Integration

## Workspace Configuration

Create `.agents/mcp_config.json` in your project root:

```json
{
  "mcpServers": {
    "job-search-agent": {
      "command": "/path/to/JOB-Agent/.venv/bin/python",
      "args": ["-m", "job_search_agent.server"],
      "env": {
        "DATABASE_URL": "sqlite+aiosqlite:///./jobagent.db"
      }
    }
  }
}
```

Replace `/path/to/JOB-Agent` with the actual path.

## Global Configuration

Alternatively, add to `~/.gemini/config/mcp_config.json` for all projects.

## Verify

1. Open the **Agent Manager** in Antigravity IDE
2. Click **... → Manage MCP Servers → Refresh**
3. The `job-search-agent` server should appear with its tools

## Usage

Ask in the Antigravity chat:

```
Find AI jobs matching my resume.
```

```
Analyze this job URL: https://boards.greenhouse.io/company/jobs/123
```
