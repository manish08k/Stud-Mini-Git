import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    pass


class AnthropicProvider:
    API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 60.0):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout

    def complete(self, messages: List[Message], system: Optional[str] = None,
                 max_tokens: int = 2048, temperature: float = 0.3) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"Anthropic API error {e.code}: {e.read().decode()}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"Anthropic API unreachable: {e}") from e

        content = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            raw=data,
        )


class OpenAIProvider:
    API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 60.0):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout

    def complete(self, messages: List[Message], system: Optional[str] = None,
                 max_tokens: int = 2048, temperature: float = 0.3) -> LLMResponse:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend({"role": m.role, "content": m.content} for m in messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"OpenAI API error {e.code}: {e.read().decode()}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"OpenAI API unreachable: {e}") from e

        content = data["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            raw=data,
        )


class LLMClient:
    """Provider-agnostic LLM client."""

    def __init__(self, provider: str = "anthropic", **kwargs):
        if provider == "anthropic":
            self._provider = AnthropicProvider(**kwargs)
        elif provider == "openai":
            self._provider = OpenAIProvider(**kwargs)
        else:
            raise LLMError(f"unknown provider: {provider}")

    def complete(self, messages: List[Message], system: Optional[str] = None,
                 max_tokens: int = 2048, temperature: float = 0.3) -> LLMResponse:
        return self._provider.complete(messages, system=system,
                                        max_tokens=max_tokens, temperature=temperature)

    def ask(self, prompt: str, system: Optional[str] = None,
            max_tokens: int = 2048, temperature: float = 0.3) -> str:
        response = self.complete(
            [Message(role="user", content=prompt)],
            system=system, max_tokens=max_tokens, temperature=temperature,
        )
        return response.content
