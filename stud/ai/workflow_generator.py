from typing import Optional

from .client import LLMClient

SYSTEM = (
    "You are a DevOps expert. Generate Stud workflow YAML files based on the user's description. "
    "Output only valid YAML. Use 'on', 'jobs', 'steps' with 'run' or 'uses' fields. "
    "Supported triggers: push, commit, schedule, manual. "
    "Do not include any explanation or markdown code fences."
)


def generate_workflow(description: str, project_type: Optional[str] = None,
                       client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = f"Generate a Stud workflow YAML for: {description}"
    if project_type:
        prompt += f"\nProject type: {project_type}"
    return client.ask(prompt, system=SYSTEM, max_tokens=2048, temperature=0.2).strip()


def suggest_workflow_improvements(workflow_yaml: str,
                                   client: Optional[LLMClient] = None) -> str:
    client = client or LLMClient()
    prompt = (
        f"Review this Stud workflow YAML and suggest improvements:\n\n{workflow_yaml}\n\n"
        "Focus on: missing steps, error handling, caching, parallelism, security."
    )
    return client.ask(prompt, system=SYSTEM, max_tokens=1024, temperature=0.3)
