from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# backend/.env, resolved absolutely so settings load regardless of the working
# directory (uvicorn from repo root, the eval harness from eval/, etc.).
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str
    redis_url: str = "redis://localhost:6379"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    # LangSmith tracing (optional). Set langchain_api_key to enable observability:
    # every RAG chain and judge call is traced to LangSmith for inspection.
    langchain_api_key: str = ""
    langchain_project: str = "financial-rag-eval"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    class Config:
        env_file = str(ENV_FILE)
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
