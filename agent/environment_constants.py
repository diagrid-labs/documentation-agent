from dataclasses import dataclass


@dataclass(frozen=True)
class _EnvVars:
    PAT: str = "GITHUB_PAT"
    PR_NUMBER: str = "PR_NUMBER"
    SOURCE_REPO_OWNER: str = "SOURCE_REPO_OWNER"
    SOURCE_REPO_NAME: str = "SOURCE_REPO_NAME"
    DOCS_REPO_OWNER: str = "DOCS_REPO_OWNER"
    DOCS_REPO_NAME: str = "DOCS_REPO_NAME"
    DOCS_REPO_BRANCH: str = "DOCS_REPO_BRANCH"  # base branch in docs repo, e.g. "v1.17"
    DOCS_CONTENT_PATH: str = "DOCS_CONTENT_PATH"  # path within docs repo where content lives, e.g. "daprdocs/content/en/developing-ai/dapr-agents"
    OPENAI_API_KEY: str = "OPENAI_API_KEY"
    DRY_RUN: str = (
        "DRY_RUN"  # set to "true" to print proposed changes without creating a PR
    )


ENV_VARS = _EnvVars()
