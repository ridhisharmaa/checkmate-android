import base64

import httpx
from pydantic import BaseModel

from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError


class OllamaProvider(ModelProvider):
    """Local model via a running Ollama instance. Never counts as a quota failure —
    if it fails, it's a real local problem (model not pulled, server not running).
    """

    is_local = True

    def __init__(self, base_url: str, model_name: str, candidate_id: str, capability: Capability):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.candidate_id = candidate_id
        self.capabilities = {capability}

    async def generate(
        self, prompt: str, images: list[bytes] | None, response_schema: type[BaseModel]
    ) -> BaseModel:
        message: dict = {"role": "user", "content": prompt}
        if images:
            message["images"] = [base64.b64encode(img).decode() for img in images]

        payload = {
            "model": self.model_name,
            "messages": [message],
            "format": response_schema.model_json_schema(),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError(f"ollama ({self.model_name}) request failed: {e}") from e

        raw_content = data.get("message", {}).get("content", "")
        try:
            parsed = response_schema.model_validate_json(raw_content)
        except Exception as e:
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError(
                f"ollama ({self.model_name}) output failed schema validation: {e}"
            ) from e

        cooldown.mark_success(self.candidate_id)
        return parsed
