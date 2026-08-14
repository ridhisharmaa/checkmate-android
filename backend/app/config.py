from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_keys: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    database_url: str = "sqlite+aiosqlite:///./checkmate.db"
    storage_root: str = "./storage"
    worker_count: int = 2
    model_registry_path: str = "./app/routing/model_registry.yaml"

    @property
    def gemini_keys(self) -> list[str]:
        return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]

    @property
    def storage_root_path(self) -> Path:
        p = Path(self.storage_root)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    # No provider validation here deliberately — this is read by db.py/storage/etc.
    # too, which have nothing to do with model routing. The "at least one Gemini key"
    # requirement is enforced in registry.build_router(), the actual place it's needed.
    return Settings()
