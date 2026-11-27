from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads env vars (case-insensitive): PROJECT_ID -> project_id."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_id: str
    api_key: str = ""  # NO default on purpose: if the secret is missing, crash at startup (fail fast)
    env: str = "local"
    policies_bucket: str = ""
    llm_model: str = "gemini-3.8-flash"
    llm_location: str = "global"  # newer Gemini models are served from the global endpoint
    embedding_model: str = "gemini-embedding-2"


    @property
    def bucket(self) -> str:
        return self.policies_bucket or f"{self.project_id}-policies"


@lru_cache  # build Settings once, reuse everywhere
def get_settings() -> Settings:
    return Settings()
