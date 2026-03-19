# Documentation Agent

A durable AI agent that monitors pull requests on [dapr/dapr-agents](https://github.com/dapr/dapr-agents), 
generates updated documentation, and opens a corresponding PR on [dapr/docs](https://github.com/dapr/docs).

Built with [Dapr Agents' `DurableAgent`](https://docs.dapr.io/developing-ai/dapr-agents/) — all GitHub interactions go through the GitHub MCP server, 
and every tool call and LLM step is checkpointed as a durable workflow activity.

If the process crashes mid-run, restart it and it picks up exactly where it left off.

Adapt the environment variables and prompt to use this Documentation Agent for any repository!

## Prerequisites

| Tool | Install |
|---|---|
| Python 3.11–3.13 | [python.org](https://www.python.org/downloads/) |
| Dapr CLI | `wget -q https://raw.githubusercontent.com/dapr/cli/master/install/install.sh -O - \| /bin/bash` |
| Docker | Required by `dapr init` (Redis) and to run the GitHub MCP server |

The GitHub MCP server runs as a Docker container (`ghcr.io/github/github-mcp-server`) via stdio — no separate install needed beyond Docker.

## Setup

### 1. Initialize Dapr

```bash
dapr init
```

### 2. Install Python dependencies

```bash
uv venv
source .venv/bin/activate
uv sync
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in. Key variables:

| Variable | Required | Description |
|---|---|---|
| `GITHUB_PAT` | Yes | GitHub Personal Access Token |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `SOURCE_REPO_OWNER` | Yes | Owner of the source repo to watch (e.g. `dapr`) |
| `SOURCE_REPO_NAME` | Yes | Source repo name (e.g. `dapr-agents`) |
| `DOCS_REPO_OWNER` | Yes | Owner of the docs repo (e.g. `dapr`) |
| `DOCS_REPO_NAME` | Yes | Docs repo name (e.g. `docs`) |
| `DOCS_REPO_BRANCH` | Yes | Base branch in docs repo (e.g. `v1.17`) |
| `DOCS_CONTENT_PATH` | Yes | Path within docs repo to explore (e.g. `daprdocs/content/en/developing-ai/dapr-agents`) |
| `PR_NUMBER` | No | PR number to process (can also be passed inline or as CLI arg) |
| `DRY_RUN` | No | Set to `true` to print proposed changes without opening a PR (default: `true`) |
| `DAPR_GRPC_TIMEOUT_SECONDS` | No | Increase gRPC timeout for long-running agent operations |

> **GitHub token requirements:** The token is passed to the GitHub MCP server (`ghcr.io/github/github-mcp-server`) running locally via Docker.
A classic PAT with `repo` scope is sufficient:
> - Source repo — read access to fetch PR details and diffs
> - Docs repo — read + write access to create branches, commit files, and open PRs

### 4. Export secrets for the Dapr sidecar

The Dapr sidecar reads environment variables from the shell at startup — `python-dotenv` handles `.env` for the Python process,
but you also need the variables in your shell for the `llm-provider` component to pick up `OPENAI_API_KEY`:

```bash
export GITHUB_PAT=$(grep GITHUB_PAT .env | cut -d= -f2)
export OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d= -f2)
export PR_NUMBER=$(grep PR_NUMBER .env | cut -d= -f2)
```

Alternatively, you can update the `catalyst.yaml` and/or the `resources/` values accordingly.

## Run the agent

### Option 1
```bash
dapr run \
  --app-id docs-agent \
  --resources-path resources \
  -- python agent/app.py
```

### Option 2

Create a project in the [Catalyst UI](https://catalyst.r1.diagrid.io/dashboard) and leverage it to run your agent:

```bash
diagrid dev run -f catalyst.yaml --project docsagent
```

The agent will:
1. Connect to the GitHub MCP server and load tools
2. Fetch the PR from the dapr agents repo
3. Search the docs repository for affected documentation files
4. Generate updated doc content via the LLM Provider specified
5. Create a branch + commit + open a PR on the docs repository
6. Print the docs PR URL on completion

### Dry run (check proposed changes without creating a PR)

Set `DRY_RUN=true` in your `.env` (or inline) to have the agent print the proposed documentation changes to stdout instead of opening a PR.
In dry-run mode the agent's instructions omit the steps for creating a branch, committing files, and opening a PR — it outputs the proposed changes to stdout only.

```bash
DRY_RUN=true dapr run \
  --app-id docs-agent \
  --resources-path resources \
  -- python agent/app.py
```

The agent will output — for each affected doc file — the file path, a summary of what changed, and the full proposed updated content.

### Pass a different PR number without editing `.env`

```bash
PR_NUMBER=5678 dapr run \
  --app-id docs-agent \
  --resources-path resources \
  -- python agent/app.py
```

## Inspect what's happening

### View workflow state in Redis

```bash
# List all keys stored by the agent
docker exec -it dapr_redis redis-cli keys "*docs-agent*"
```

### Dapr dashboard

```bash
dapr dashboard
```

Opens at `http://localhost:8080` — shows running actors, workflow instances, and component status.

Reference the documentation for additional insights on the [Diagrid Dashboard](https://docs.diagrid.io/develop/diagrid-dashboard).

### Logs

The agent logs to stdout. Key log lines to watch for:

```
Yayyyy we created the agent           # DurableAgent and AgentRunner initialized
Agent run completed. Result: ...      # final result (PR URL in non-dry-run mode)
```

## Durability demo

This shows the core value of `DurableAgent` — crash recovery without lost work.

1. Start the agent with a real PR number
2. While it's running (e.g. during an LLM call), press `Ctrl+C`
3. Verify the workflow state is still in Redis:
   ```bash
   docker exec -it dapr_redis redis-cli keys "*docs-agent*"
   ```
4. Restart with the exact same command
5. Watch the logs — already-completed tool calls are **skipped**, the agent resumes from the last checkpoint

## MCP tool names

The agent loads all tools from the GitHub MCP server via `client.get_all_tools()` in [agent/app.py](agent/app.py).
The tool names referenced in the agent instructions (e.g. `GithubPullRequestRead`, `GithubGetFileContents`, `GithubCreateBranch`) must match the names exposed by the server version you're running.
If the names differ, update the instruction strings in `app.py` accordingly.