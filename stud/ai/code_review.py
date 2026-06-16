from dataclasses import dataclass, field
from typing import List, Optional

from .client import LLMClient, Message

SYSTEM = (
    "You are a senior software engineer performing a code review. "
    "Identify bugs, security issues, performance problems, and style issues. "
    "Be specific, actionable, and concise. Format as a numbered list."
)


@dataclass
class ReviewComment:
    severity: str  # "bug", "security", "performance", "style", "info"
    message: str
    line: Optional[int] = None
    file: Optional[str] = None


@dataclass
class CodeReview:
    summary: str
    comments: List[ReviewComment] = field(default_factory=list)
    approved: bool = False


def review_diff(diff: str, context: Optional[str] = None,
                client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = f"Review this diff and list issues:\n\n{diff}"
    if context:
        prompt = f"Context: {context}\n\n{prompt}"
    return client.ask(prompt, system=SYSTEM, max_tokens=2048, temperature=0.2)


def review_file(filename: str, content: str,
                client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = f"Review this file ({filename}):\n\n```\n{content}\n```"
    return client.ask(prompt, system=SYSTEM, max_tokens=2048, temperature=0.2)
