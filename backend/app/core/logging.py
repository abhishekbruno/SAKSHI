"""
Structured application logging for SAKSHI Case Management Service.
Emits JSON-formatted audit events without leaking sensitive credentials or evidence contents.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON for SIEM / audit analysis."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event_type"):
            log_obj["event_type"] = record.event_type
        if hasattr(record, "case_id"):
            log_obj["case_id"] = record.case_id
        if hasattr(record, "investigator_id"):
            log_obj["investigator_id"] = record.investigator_id
        if hasattr(record, "extra_data") and record.extra_data:
            log_obj["metadata"] = record.extra_data
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def get_logger(name: str = "sakshi.mod01") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
    return logger


logger = get_logger()


def log_event(
    event_type: str,
    message: str,
    case_id: Optional[str] = None,
    investigator_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO
) -> None:
    """Helper to emit standard SAKSHI audit/lifecycle logs."""
    extra = {
        "event_type": event_type,
        "case_id": case_id,
        "investigator_id": investigator_id,
        "extra_data": extra_data or {}
    }
    logger.log(level, message, extra=extra)
