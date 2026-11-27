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
        http_options=types.HttpOptions(
        timeout=60_000,  # ms; never wait forever, but allow for slow calls
        retry_options=types.HttpRetryOptions(
        attempts=3, initial_delay=1.0, max_delay=10.0,  # exponential backoff
        http_status_codes=[429, 500, 502, 503, 504],     # temporary errors only, never 400/403
        ),
        ),

    )

def embed(texts: list[str], task_type: str = "SEMANTIC_SIMILARITY", dims: int = 768) -> list[list[float]]:
    """One vector PER text. Each text must be its own Content - a plain list of strings
    is treated as ONE multimodal input by gemini-embedding-2 (returns a single vector!)."""
    s = get_settings()
    r = client().models.embed_content(
        model=s.embedding_model,
        contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in texts],
        config=types.EmbedContentConfig(output_dimensionality=dims, task_type=task_type),
    )
    vectors = [e.values for e in r.embeddings]
    if len(vectors) != len(texts):  # never trust, always verify
        raise RuntimeError(f"expected {len(texts)} embeddings, got {len(vectors)}")
    return vectors
