from os import environ
import sys
from dotenv import load_dotenv
from environment_constants import ENV_VARS
from dapr_agents.tool.mcp.client import MCPClient
from dapr_agents import DurableAgent
from dapr_agents.llm import DaprChatClient
from dapr_agents.workflow.runners import AgentRunner
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.memory import ConversationDaprStateMemory
from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
    AgentExecutionConfig,
)

load_dotenv()


def get_required_env(env_var_name: str) -> str:
    value = environ.get(env_var_name)
    if not value:
        raise ValueError(
            f"Environment variable {env_var_name} is required but not set."
        )
    return value


async def _load_mcp_tools(dry_run: bool):
    client = MCPClient()
    pat_token = environ.get(ENV_VARS.PAT)

    await client.connect_stdio(
        server_name="github",
        command="docker",
        args=[
            "run",
            "-i",
            "--rm",
            "-e",
            f"GITHUB_PERSONAL_ACCESS_TOKEN={pat_token}",
            "ghcr.io/github/github-mcp-server",
        ],
    )
    all_tools = client.get_all_tools()
    return all_tools


async def main():
    get_required_env(ENV_VARS.PAT)  # ensure required env vars are set
    pr_number = environ.get(
        ENV_VARS.PR_NUMBER
    )  # optional, only needed if updating an existing PR
    source_repo_owner = get_required_env(ENV_VARS.SOURCE_REPO_OWNER)
    source_repo_name = get_required_env(ENV_VARS.SOURCE_REPO_NAME)
    docs_repo_owner = get_required_env(ENV_VARS.DOCS_REPO_OWNER)
    docs_repo_name = get_required_env(ENV_VARS.DOCS_REPO_NAME)
    docs_branch = get_required_env(ENV_VARS.DOCS_REPO_BRANCH)
    docs_content_path = get_required_env(ENV_VARS.DOCS_CONTENT_PATH)
    openai_api_key = get_required_env(ENV_VARS.OPENAI_API_KEY)
    dry_run = environ.get(ENV_VARS.DRY_RUN, "true").lower() == "true"

    tools = await _load_mcp_tools(dry_run)

    shared_docs_explore_steps = [
        f"  3. Use GithubGetFileContents with owner='{docs_repo_owner}', repo='{docs_repo_name}', path='{docs_content_path}', ref='{docs_branch}' to list all files in the dapr-agents docs directory.",
        f"  4. Read 2-3 existing files from '{docs_content_path}' to understand the established tone, frontmatter format, heading structure, and code sample style used in this section.",
        f"  5. Use GithubSearchCode to find any additional markdown files referencing the changed class or function names. Pass the search string as the 'query' parameter in the format: '<keyword> repo:{docs_repo_owner}/{docs_repo_name} extension:md'. Always include 'repo:{docs_repo_owner}/{docs_repo_name}' — never search without it.",
        f"  6. Use GithubGetFileContents with owner='{docs_repo_owner}', repo='{docs_repo_name}' to read any additional relevant doc files found by search.",
        "     IMPORTANT: GithubGetFileContents returns content as a base64-encoded string. Always decode it to plain text before reading or editing it. Never pass a base64 blob as file content to any write tool.",
    ]

    if dry_run:
        instructions = [
            "You are a technical documentation writer for the Dapr project.",
            f"Your job is to analyze what changes would be needed in {docs_repo_name} based on code changes in {source_repo_name}.",
            "When given a PR number, follow these steps in order:",
            f"  1. Use GithubPullRequestRead with method='get', owner='{source_repo_owner}', repo='{source_repo_name}', pullNumber={pr_number} to fetch the PR title and description.",
            f"  2. Use GithubPullRequestRead with method='get_files', owner='{source_repo_owner}', repo='{source_repo_name}', pullNumber={pr_number} to list all changed files.",
            *shared_docs_explore_steps,
            "  7. Generate the updated documentation content that would be needed to reflect the code changes.",
            f"     - Match the frontmatter, heading structure, and code sample style of existing files in '{docs_content_path}'.",
            "     - Update code samples, parameter names, class names, and descriptions as needed.",
            "     - Do not invent features not present in the PR diff.",
            "  8. Print a clear summary of your proposed changes. For each doc file, output:",
            "     - The file path in the docs repo",
            "     - A brief description of what changed and why",
            "     - The full updated file content (as a markdown code block)",
            "Do NOT create any branches, commits, or pull requests. This is a dry run — output only.",
            "Only propose changes to sections genuinely affected by the diff. Be precise.",
        ]
    else:
        instructions = [
            "You are a technical documentation writer for the Dapr project.",
            f"Your job is to keep {docs_repo_name} in sync with code changes in {source_repo_name}.",
            "When given a PR number, follow these steps in order:",
            f"  1. Use GithubPullRequestRead with method='get', owner='{source_repo_owner}', repo='{source_repo_name}', pullNumber={pr_number} to fetch the PR title and description.",
            f"  2. Use GithubPullRequestRead with method='get_files', owner='{source_repo_owner}', repo='{source_repo_name}', pullNumber={pr_number} to list all changed files.",
            *shared_docs_explore_steps,
            "  7. Generate updated documentation content that accurately reflects the code changes.",
            f"     - Match the frontmatter, heading structure, and code sample style of existing files in '{docs_content_path}'.",
            "     - Update code samples, parameter names, class names, and descriptions as needed.",
            "     - Do not invent features not present in the PR diff.",
            f"  8. Use GithubCreateBranch with owner='{docs_repo_owner}', repo='{docs_repo_name}', branch='{docs_branch}', using '{docs_branch}' as the base.",
            f"  9. Use GithubCreateOrUpdateFile with owner='{docs_repo_owner}', repo='{docs_repo_name}', branch='{docs_branch}' for each changed doc file. Pass content as plain UTF-8 text — never as a base64 string.",
            f"  10. Use GithubCreatePullRequest with owner='{docs_repo_owner}', repo='{docs_repo_name}', head='{docs_branch}', base='{docs_branch}'.",
            f"      - Title format: 'docs: update for dapr-agents #{pr_number} - <pr title>'",
            "      - Body should summarize which dapr-agents PR triggered the change and what was updated.",
            "Only update sections genuinely affected by the diff. Be precise.",
        ]

    llm = DaprChatClient(component_name="llm-provider")

    # registry = AgentRegistryConfig(
    #     store=StateStoreService(
    #         store_name=("agent-registry")
    #     ),
    #     team_name="ai",
    # )

    # state = AgentStateConfig(
    #     store=StateStoreService(store_name="agent-workflow")
    # )
    # memory = AgentMemoryConfig(
    #     store=ConversationDaprStateMemory(
    #         store_name="agent-memory",
    #     )
    # )

    agent = DurableAgent(
        role="Documentation Writer",
        name="DocsAgent",
        instructions=instructions,
        goal="Keep the Dapr documentation in sync with dapr-agents code changes",
        tools=tools,
        llm=llm,
        # registry=registry,
        # state=state,
        # memory=memory,
    )
    print("Yayyyy we created the agent")

    runner = AgentRunner()

    try:
        result = await runner.run(
            agent,
            payload={
                "task": f"Process PR #{pr_number} from {source_repo_owner}/{source_repo_name}and propose necessary documentation updates in {docs_repo_owner}/{docs_repo_name}.",
            },
        )
        print(f"Agent run completed. Result: {result}")
    except Exception as e:
        print(f"Agent run failed with error: {e}")
    finally:
        try:
            runner.shutdown(agent)
        except Exception as e:
            print(f"Error during agent shutdown: {e}")


if __name__ == "__main__":
    try:
        import asyncio

        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except BaseException as e:
        print(f"Agent encountered an error: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)
