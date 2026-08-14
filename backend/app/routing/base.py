from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class Capability(str, Enum):
    VISION = "vision"
    TEXT = "text"


class ProviderError(Exception):
    """Raised by a provider adapter when a single generation attempt fails.

    is_quota_related distinguishes rate-limit/quota/503-style failures (short
    cooldown, definitely transient) from everything else (auth errors, malformed
    responses, network blips — still cooled down, but the router logs these louder
    since they're more likely to indicate a real misconfiguration).
    """

    def __init__(self, message: str, *, is_quota_related: bool = False):
        super().__init__(message)
        self.is_quota_related = is_quota_related


class ModelProvider(ABC):
    """One (provider, model) pair capable of vision and/or text structured generation.

    Concrete providers may internally round-robin multiple API keys — that's an
    implementation detail of the provider, invisible to the router/pipeline above it.
    """

    #: capabilities this provider instance can serve
    capabilities: set[Capability]
    #: True for locally-hosted models (Ollama) — never selected for OCR unless every
    #: cloud vision candidate has been exhausted.
    is_local: bool = False

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        images: list[bytes] | None,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Run one structured-output generation. Raises ProviderError on failure."""
        raise NotImplementedError
