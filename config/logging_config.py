"""
Structured logging configuration for FTech AI Factory.
Each agent writes to its own rotating log file + shared console output.
"""
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from config.settings import LOG_LEVEL, LOG_DIR


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with JSON output to file + INFO to console."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Rotating file handler (10 MB × 5 files)
    log_file = LOG_DIR / f"{name.replace('.', '_')}.log"
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s - %(message)s"))
    logger.addHandler(ch)

    return logger
