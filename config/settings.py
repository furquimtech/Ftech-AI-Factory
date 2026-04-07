"""
FTech AI Factory - Central configuration
Reads from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ftechai:ftechai@localhost:5432/ftechai_factory",
)

# ── LLM providers (one per agent role) ────────────────────────────────────────
LLM_DEV: str = os.getenv("LLM_DEV", "llama")
LLM_QA: str = os.getenv("LLM_QA", "llama")
LLM_DOC: str = os.getenv("LLM_DOC", "llama")
LLM_KNOWLEDGE: str = os.getenv("LLM_KNOWLEDGE", "llama")

# LLaMA local endpoint (e.g. llama.cpp server or Ollama)
LLAMA_BASE_URL: str = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
LLAMA_MODEL: str = os.getenv("LLAMA_MODEL", "llama3")

# ── Azure DevOps ───────────────────────────────────────────────────────────────
AZURE_DEVOPS_ORG: str = os.getenv("AZURE_DEVOPS_ORG", "")
AZURE_DEVOPS_PROJECT: str = os.getenv("AZURE_DEVOPS_PROJECT", "")
AZURE_DEVOPS_PAT: str = os.getenv("AZURE_DEVOPS_PAT", "")

# ── GitHub ─────────────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")  # owner/repo

# ── Orchestrator ───────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
MAX_PARALLEL_AGENTS: int = int(os.getenv("MAX_PARALLEL_AGENTS", "4"))

# Scheduler interval in seconds
SCHEDULER_INTERVAL: int = int(os.getenv("SCHEDULER_INTERVAL", "30"))

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR: Path = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Task retry ─────────────────────────────────────────────────────────────────
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
