import logging
import json
import sys
from datetime import datetime, timezone
from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="sys-init")


class JSONLogFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production observability.
    Includes correlation ID, timestamp, logger name, and severity.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": correlation_id_ctx.get(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logger(name: str = "depoii_engine", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONLogFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logger()
