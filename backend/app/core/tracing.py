"""Optional LangSmith tracing.

LangChain emits traces to LangSmith when the LANGCHAIN_* environment variables
are present. pydantic-settings reads them from backend/.env into the Settings
object but does not export them to os.environ, so this helper pushes them out so
the LangChain tracer picks them up.

No-op (returns False) when no langchain_api_key is configured, so the app and the
eval harness run unchanged without a LangSmith account.
"""
import os
from typing import Optional

from app.core.config import get_settings


def enable_langsmith(project: Optional[str] = None) -> bool:
    """Turn on LangSmith tracing if an API key is configured. Returns whether it
    was enabled. Safe to call more than once."""
    settings = get_settings()
    if not settings.langchain_api_key:
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    os.environ["LANGCHAIN_PROJECT"] = project or settings.langchain_project
    return True
