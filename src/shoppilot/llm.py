"""The single place where we create the LLM client.
Later modules add routing, caching, cost tracking and a gateway HERE, not all over the codebase."""
from functools import lru_cache

from google import genai
from google.genai import types

from shoppilot.config import get_settings


@lru_cache
def client() -> genai.Client:
    s = get_settings()
    return genai.Client(
        vertexai=True,  # use Vertex AI (IAM, quotas, billing in YOUR project), not the public API key flavour
        project=s.project_id,
        location=s.llm_location,
        http_options=types.HttpOptions(timeout=30_000),  # milliseconds; never wait forever
    )
