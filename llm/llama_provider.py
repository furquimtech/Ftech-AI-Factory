"""
LLaMA provider – talks to a local Ollama instance (default)
or any OpenAI-compatible local server (llama.cpp, LM Studio, etc.).

Environment variables:
  LLAMA_BASE_URL  – base URL of the local inference server  (default: http://localhost:11434)
  LLAMA_MODEL     – model tag to use                        (default: llama3)
"""
from __future__ import annotations

import httpx

from config.settings import LLAMA_BASE_URL, LLAMA_MODEL
from config.logging_config import get_logger
from llm.base_provider import LLMProvider

logger = get_logger("llm.llama")

# Ollama endpoints
_GENERATE_PATH = "/api/generate"
_EMBED_PATH = "/api/embeddings"

# Timeout for long generation calls (seconds)
_TIMEOUT = 120


class LlamaProvider(LLMProvider):
    """
    Thin HTTP wrapper around Ollama's REST API.
    Compatible with llama.cpp server when LLAMA_BASE_URL points to it
    (adjust _GENERATE_PATH / _EMBED_PATH accordingly).
    """

    def __init__(
        self,
        base_url: str = LLAMA_BASE_URL,
        model: str = LLAMA_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=_TIMEOUT)

    # ── LLMProvider interface ─────────────────────────────────────────────────

    def generate(self, prompt: str, **kwargs) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", 2048),
            },
        }
        logger.debug(f"generate → model={self.model} prompt_len={len(prompt)}")
        resp = self._client.post(f"{self.base_url}{_GENERATE_PATH}", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        logger.debug(f"embed → model={self.model} text_len={len(text)}")
        resp = self._client.post(f"{self.base_url}{_EMBED_PATH}", json=payload)
        resp.raise_for_status()
        return resp.json().get("embedding", [])

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
