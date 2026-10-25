"""Optional OpenAI-compatible Nemotron client.

Configuration follows the repository's existing ``test_nemotron.py`` smoke
script: ``NVIDIA_API_KEY``, ``NVIDIA_BASE_URL``, and ``NEMOTRON_MODEL``. No
network request is made during construction. Unit tests should inject a fake
``ModelClient`` into ClaimExtractor instead of constructing this client.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Callable

from .llm_client import ModelClientError, NemotronConfigurationError


class NemotronClient:
    """Call the configured Nemotron chat-completions endpoint.

    The OpenAI SDK client can be injected, allowing deterministic tests and
    keeping SDK construction separate from claim parsing.
    """

    def __init__(self, client: Any, model: str) -> None:
        if not isinstance(model, str) or not model.strip():
            raise NemotronConfigurationError("NEMOTRON_MODEL must be configured")
        self._client = client
        self._model = model

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> "NemotronClient":
        """Build a client from the established environment-variable names."""
        if environ is None:
            from dotenv import load_dotenv

            load_dotenv()
            environ = os.environ

        names = ("NVIDIA_API_KEY", "NVIDIA_BASE_URL", "NEMOTRON_MODEL")
        missing = [name for name in names if not environ.get(name, "").strip()]
        if missing:
            raise NemotronConfigurationError(
                "Missing Nemotron configuration: " + ", ".join(missing)
            )

        if client_factory is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise NemotronConfigurationError(
                    "The optional openai package is required for Nemotron calls"
                ) from exc
            client_factory = OpenAI

        try:
            client = client_factory(
                api_key=environ["NVIDIA_API_KEY"],
                base_url=environ["NVIDIA_BASE_URL"],
                timeout=30.0,
                max_retries=0,
            )
        except Exception:
            raise NemotronConfigurationError(
                "Nemotron client could not be initialized"
            ) from None
        return cls(client, environ["NEMOTRON_MODEL"])

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return one text completion without logging sensitive prompt data."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1024,
                temperature=0,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = response.choices[0].message.content
        except Exception:
            raise ModelClientError("Nemotron request failed") from None
        if not isinstance(content, str) or not content.strip():
            raise ModelClientError("Nemotron returned no text content")
        return content
