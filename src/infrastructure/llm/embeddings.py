"""Embeddings — text-embedding-3-small."""
from __future__ import annotations

from typing import Any, List

from langchain_openai import OpenAIEmbeddings

from infrastructure.config import EMBEDDING_MODEL, EMBED_PROVIDER, OPENROUTER_BASE_URL, get_api_key


def get_embeddings(**kwargs: Any) -> OpenAIEmbeddings:
    opts: dict[str, Any] = {"model": EMBEDDING_MODEL, **kwargs}
    if EMBED_PROVIDER == "openrouter":
        opts["openai_api_base"] = OPENROUTER_BASE_URL
        opts["openai_api_key"] = get_api_key("openrouter")
    else:
        opts["openai_api_key"] = get_api_key("openai")
    return OpenAIEmbeddings(**opts)


def embed_texts(texts: List[str]) -> List[List[float]]:
    return get_embeddings().embed_documents(texts)
