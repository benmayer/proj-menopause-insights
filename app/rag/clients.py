import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
EMBED_MODEL = "text-embedding-3-small"  # 1536 dims, matches vector(1536)


@lru_cache
def openai_client() -> OpenAI:
    return OpenAI()


@lru_cache
def supabase_client() -> Client:
    # Secret key: server-side only. Never ship to the UI.
    return create_client(os.environ["SUPABASE_PROJECT_URL"], os.environ["SUPABASE_API_KEY"])


def embed(texts: list[str]) -> list[list[float]]:
    resp = openai_client().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]
