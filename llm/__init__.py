"""
LLM abstraction layer.
Usage:
    from llm import get_provider
    llm = get_provider("llama")
    text = llm.generate("Say hello")
    vec  = llm.embed("some text")
"""
from llm.base_provider import LLMProvider
from llm.llama_provider import LlamaProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    "llama": LlamaProvider,
}


def get_provider(name: str) -> LLMProvider:
    key = name.lower().strip()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"Unknown LLM provider '{name}'. Available: {list(_REGISTRY)}")
    return cls()


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Allow runtime registration of custom providers."""
    _REGISTRY[name.lower()] = cls


__all__ = ["LLMProvider", "get_provider", "register_provider"]
