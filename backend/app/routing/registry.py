"""Loads model_registry.yaml and builds the ModelRouter — the single entry point
the pipeline uses to get structured output from "the best available model for X".
"""
import logging

import yaml
from pydantic import BaseModel

from app.config import Settings
from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError
from app.routing.providers.anthropic import AnthropicProvider
from app.routing.providers.gemini import GeminiProvider
from app.routing.providers.ollama import OllamaProvider
from app.routing.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class RouterExhaustedError(Exception):
    """Raised when every candidate in a capability's chain failed. Callers should
    treat this as a total-stage failure, not degrade silently."""

    def __init__(self, capability: Capability, attempts: list[str]):
        self.capability = capability
        self.attempts = attempts
        super().__init__(
            f"All model candidates for capability={capability.value} failed: " + "; ".join(attempts)
        )


class _Candidate:
    def __init__(self, candidate_id: str, provider: ModelProvider, tier: str):
        self.candidate_id = candidate_id
        self.provider = provider
        self.tier = tier  # "cloud" | "local"


class ModelRouter:
    def __init__(self, chains: dict[Capability, list[_Candidate]]):
        self._chains = chains

    async def generate(
        self, capability: Capability, prompt: str, images: list[bytes] | None, response_schema: type[BaseModel]
    ) -> BaseModel:
        candidates = self._chains.get(capability, [])
        if not candidates:
            raise RouterExhaustedError(capability, ["no candidates configured"])

        cloud = [c for c in candidates if c.tier == "cloud"]
        local = [c for c in candidates if c.tier == "local"]
        # Vision: local is a genuine last resort, tried only after every cloud
        # candidate has been attempted (or is cooling down). Text: order from the
        # registry (quality_rank) already puts local last, so no special-casing needed.
        ordered = cloud + local if capability == Capability.VISION else candidates

        attempts: list[str] = []
        for candidate in ordered:
            if cooldown.is_cooling_down(candidate.candidate_id):
                attempts.append(f"{candidate.candidate_id}: cooling down, skipped")
                continue
            try:
                result = await candidate.provider.generate(prompt, images, response_schema)
                cooldown.mark_success(candidate.candidate_id)
                return result
            except ProviderError as e:
                logger.warning("model candidate %s failed: %s", candidate.candidate_id, e)
                cooldown.mark_failure(candidate.candidate_id, is_quota_related=e.is_quota_related)
                attempts.append(f"{candidate.candidate_id}: {e}")

        raise RouterExhaustedError(capability, attempts)


def build_router(settings: Settings) -> ModelRouter:
    with open(settings.model_registry_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    env_map = {
        "GEMINI_API_KEYS": settings.gemini_keys,
        "OPENAI_API_KEY": settings.openai_api_key,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
    }

    # Reuse one provider instance per (provider, model) across capabilities so
    # key-level cooldown state (e.g. a Gemini key hitting quota) is shared between
    # the OCR chain and the grading chain instead of tracked twice.
    provider_cache: dict[tuple[str, str], ModelProvider] = {}

    def _env_satisfied(requires: list[str]) -> bool:
        if not requires:
            return True
        return all(bool(env_map.get(name)) for name in requires)

    def _get_provider(provider_type: str, model: str, candidate_id: str, capability: Capability) -> ModelProvider:
        key = (provider_type, model)
        if key in provider_cache:
            return provider_cache[key]

        if provider_type == "gemini":
            instance: ModelProvider = GeminiProvider(settings.gemini_keys, model, candidate_id=f"gemini:{model}")
        elif provider_type == "openai":
            instance = OpenAIProvider(settings.openai_api_key, model, candidate_id=f"openai:{model}")
        elif provider_type == "anthropic":
            instance = AnthropicProvider(settings.anthropic_api_key, model, candidate_id=f"anthropic:{model}")
        elif provider_type == "ollama":
            instance = OllamaProvider(settings.ollama_base_url, model, candidate_id=f"ollama:{model}", capability=capability)
        else:
            raise ValueError(f"unknown provider type in model_registry.yaml: {provider_type}")

        provider_cache[key] = instance
        return instance

    chains: dict[Capability, list[_Candidate]] = {}
    for cap_name, entries in raw.items():
        capability = Capability(cap_name)
        entries_sorted = sorted(entries, key=lambda e: e["quality_rank"])
        candidates: list[_Candidate] = []
        for entry in entries_sorted:
            if not _env_satisfied(entry.get("requires_env", [])):
                logger.info(
                    "skipping model candidate %s: required env var(s) %s not set",
                    entry["id"], entry.get("requires_env"),
                )
                continue
            provider = _get_provider(entry["provider"], entry["model"], entry["id"], capability)
            candidates.append(_Candidate(entry["id"], provider, entry["tier"]))
        chains[capability] = candidates

    # Must be a *cloud* vision candidate, not merely any candidate. The local Ollama
    # entry declares no requires_env, so it is always present and would satisfy a bare
    # emptiness check — letting the server boot clean with no API keys at all and then
    # fail deep in the first grading run against an Ollama that usually isn't running.
    # Handwriting OCR is the accuracy-critical stage; refuse to start without a real one.
    if not [c for c in chains.get(Capability.VISION, []) if c.tier == "cloud"]:
        raise RuntimeError(
            "No cloud vision model is configured — handwriting OCR needs one. Set "
            "GEMINI_API_KEYS (or OPENAI_API_KEY / ANTHROPIC_API_KEY) in backend/.env. "
            "Copy backend/.env.example to backend/.env if you haven't yet."
        )

    return ModelRouter(chains)
