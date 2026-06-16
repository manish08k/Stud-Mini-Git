from typing import Dict, Optional

from .client import LLMClient

SYSTEM = (
    "You are a software dependency expert. Advise on package choices, version constraints, "
    "alternatives, and security considerations. Be direct and practical."
)


def advise_dependency(name: str, constraint: str, language: str = "python",
                       client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = (
        f"Package: {name}\nConstraint: {constraint}\nLanguage: {language}\n\n"
        "Advise on: 1) whether this is a good choice, 2) known security issues, "
        "3) recommended alternatives, 4) suggested version constraint."
    )
    return client.ask(prompt, system=SYSTEM, max_tokens=1024, temperature=0.3)


def advise_all_dependencies(dependencies: Dict[str, str], language: str = "python",
                              client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    dep_list = "\n".join(f"  {k}: {v}" for k, v in dependencies.items())
    prompt = (
        f"Review these {language} dependencies and highlight any concerns:\n\n{dep_list}\n\n"
        "Focus on: security issues, deprecated packages, better alternatives, "
        "version conflicts, and overall health of the dependency tree."
    )
    return client.ask(prompt, system=SYSTEM, max_tokens=2048, temperature=0.3)
