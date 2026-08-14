import base64

from anthropic import AsyncAnthropic, APIStatusError
from pydantic import BaseModel

from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError

_QUOTA_STATUS_CODES = {429, 503, 529}
_TOOL_NAME = "emit_result"


class AnthropicProvider(ModelProvider):
    capabilities = {Capability.VISION, Capability.TEXT}

    def __init__(self, api_key: str, model_name: str, candidate_id: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        self.candidate_id = candidate_id

    async def generate(
        self, prompt: str, images: list[bytes] | None, response_schema: type[BaseModel]
    ) -> BaseModel:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for img in images or []:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(img).decode(),
                    },
                }
            )

        # Anthropic has no native response_schema param — force a single tool call
        # whose input_schema mirrors the pydantic model, and parse the tool input back.
        tool = {
            "name": _TOOL_NAME,
            "description": "Return the structured result.",
            "input_schema": response_schema.model_json_schema(),
        }

        try:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=8192,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": content}],
            )
        except APIStatusError as e:
            is_quota = e.status_code in _QUOTA_STATUS_CODES
            cooldown.mark_failure(self.candidate_id, is_quota_related=is_quota)
            raise ProviderError(f"anthropic failed: {e}", is_quota_related=is_quota) from e

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError("anthropic returned no tool_use block")

        try:
            parsed = response_schema.model_validate(tool_use.input)
        except Exception as e:
            cooldown.mark_failure(self.candidate_id, is_quota_related=False)
            raise ProviderError(f"anthropic tool_use input failed schema validation: {e}") from e

        cooldown.mark_success(self.candidate_id)
        return parsed
