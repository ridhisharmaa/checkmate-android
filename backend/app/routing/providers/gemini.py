import itertools

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel

from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError

_QUOTA_STATUS_CODES = {429, 503}


class GeminiProvider(ModelProvider):
    capabilities = {Capability.VISION, Capability.TEXT}

    def __init__(self, api_keys: list[str], model_name: str, candidate_id: str):
        if not api_keys:
            raise ValueError("GeminiProvider requires at least one API key")
        self._clients = [genai.Client(api_key=k) for k in api_keys]
        self._key_cycle = itertools.cycle(range(len(self._clients)))
        self.model_name = model_name
        self.candidate_id = candidate_id

    def _next_client(self) -> tuple[int, genai.Client]:
        # Round-robin, skipping any key currently in cooldown, so one exhausted
        # key doesn't block the others.
        for _ in range(len(self._clients)):
            idx = next(self._key_cycle)
            key_id = f"{self.candidate_id}:key{idx}"
            if not cooldown.is_cooling_down(key_id):
                return idx, self._clients[idx]
        # every key cooling down — return the next one anyway, let the caller fail fast
        idx = next(self._key_cycle)
        return idx, self._clients[idx]

    async def generate(
        self, prompt: str, images: list[bytes] | None, response_schema: type[BaseModel]
    ) -> BaseModel:
        idx, client = self._next_client()
        key_id = f"{self.candidate_id}:key{idx}"

        parts: list[types.Part | str] = [prompt]
        if images:
            parts.extend(types.Part.from_bytes(data=img, mime_type="image/png") for img in images)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        try:
            response = await client.aio.models.generate_content(
                model=self.model_name, contents=parts, config=config
            )
        except APIError as e:
            is_quota = getattr(e, "code", None) in _QUOTA_STATUS_CODES
            cooldown.mark_failure(key_id, is_quota_related=is_quota)
            raise ProviderError(f"gemini key {idx} failed: {e}", is_quota_related=is_quota) from e
        except Exception as e:
            # Transport-level failures (DNS, dropped connection, timeout) surface from
            # the underlying HTTP client, not as APIError. Without this they escape as
            # non-ProviderError and skip the router's remaining candidates entirely.
            cooldown.mark_failure(key_id, is_quota_related=False)
            raise ProviderError(f"gemini key {idx} failed unexpectedly: {e}") from e

        if response.parsed is None:
            cooldown.mark_failure(key_id, is_quota_related=False)
            raise ProviderError(
                f"gemini key {idx} returned no parsed output (raw: {response.text[:200] if response.text else 'empty'})"
            )

        cooldown.mark_success(key_id)
        return response.parsed
