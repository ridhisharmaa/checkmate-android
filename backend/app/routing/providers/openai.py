import base64

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError

_QUOTA_STATUS_CODES = {429, 503}


class OpenAIProvider(ModelProvider):
    capabilities = {Capability.VISION, Capability.TEXT}

    def __init__(self, api_key: str, model_name: str, candidate_id: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name
        self.candidate_id = candidate_id

    async def generate(
        self, prompt: str, images: list[bytes] | None, response_schema: type[BaseModel]
    ) -> BaseModel:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for img in images or []:
            b64 = base64.b64encode(img).decode()
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            )

        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[{"role": "user", "content": content}],
                response_format=response_schema,
            )
        # APIError, not APIStatusError: connection errors and timeouts are siblings of
        # APIStatusError, not subclasses, so catching the narrower type let a dropped
        # network escape as a non-ProviderError. The router only catches ProviderError,
        # so that killed the whole stage instead of falling through to the next model —
        # defeating the fallback chain in exactly the situation it exists for.
        except APIError as e:
            status = getattr(e, "status_code", None)  # absent on connection errors
            is_quota = status in _QUOTA_STATUS_CODES
            cooldown.mark_failure(self.candidate_id, is_quota_related=is_quota)
            raise ProviderError(f"openai failed: {e}", is_quota_related=is_quota) from e
        except Exception as e:  # malformed response, unexpected SDK error, ...
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError(f"openai failed unexpectedly: {e}") from e

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError("openai returned no parsed output")

        cooldown.mark_success(self.candidate_id)
        return parsed
