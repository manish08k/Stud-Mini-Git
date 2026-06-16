from typing import List, Optional

from .client import LLMClient, Message

SYSTEM = (
    "You are an expert software engineer. Generate concise, imperative git commit messages "
    "following the Conventional Commits specification. Respond with only the commit message, "
    "no explanation, no markdown, no quotes."
)


def generate_commit_message(diff: str, context: Optional[str] = None,
                              client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = f"Generate a commit message for this diff:\n\n{diff}"
    if context:
        prompt = f"{context}\n\n{prompt}"
    return client.ask(prompt, system=SYSTEM, max_tokens=256, temperature=0.2).strip()


def generate_commit_message_from_changes(changed_files: List[str], diff: str,
                                          client: Optional[LLMClient] = None) -> str:
    file_list = "\n".join(f"  - {f}" for f in changed_files)
    prompt = f"Changed files:\n{file_list}\n\nDiff:\n{diff}"
    return generate_commit_message(prompt, client=client)
