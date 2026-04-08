"""
Abstract base for all LLM providers.
New providers (OpenAI, Gemini, Mistral …) simply inherit this class.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Send a prompt and return the model's text response.
        kwargs may include: temperature, max_tokens, stop, etc.
        """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Return the embedding vector for the given text.
        Vector size depends on the model (e.g. 4096 for LLaMA 3).
        """
