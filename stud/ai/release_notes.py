from typing import List, Optional

from .client import LLMClient

SYSTEM = (
    "You are a technical writer. Generate clear, user-friendly release notes from commit messages. "
    "Group changes into: Features, Bug Fixes, Breaking Changes, and Other. "
    "Use markdown. Be concise and focus on user impact."
)


def generate_release_notes(commit_messages: List[str], version: str,
                             repo_name: Optional[str] = None,
                             client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    commits_text = "\n".join(f"- {msg}" for msg in commit_messages)
    header = f"Repository: {repo_name}\n" if repo_name else ""
    prompt = (
        f"{header}Version: {version}\n\n"
        f"Commits:\n{commits_text}\n\n"
        "Generate release notes for this version."
    )
    return client.ask(prompt, system=SYSTEM, max_tokens=2048, temperature=0.4)


def generate_changelog_entry(commit_messages: List[str], version: str,
                               date: str, client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    commits_text = "\n".join(f"- {msg}" for msg in commit_messages)
    prompt = (
        f"Generate a CHANGELOG.md entry.\nVersion: {version}\nDate: {date}\n\n"
        f"Commits:\n{commits_text}"
    )
    return client.ask(prompt, system=SYSTEM, max_tokens=1024, temperature=0.3)
