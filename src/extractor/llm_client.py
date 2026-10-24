"""Model-client interfaces and safe, content-free client errors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ModelClientError(RuntimeError):
    """A model call failed; messages deliberately exclude prompt/response data."""


class ModelClient(Protocol):
    """Minimal injectable interface required by ClaimExtractor."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str | Mapping[str, Any]:
        """Return model text or raise a sanitized client error."""


class NemotronConfigurationError(RuntimeError):
    """Nemotron configuration or its optional SDK is unavailable."""
