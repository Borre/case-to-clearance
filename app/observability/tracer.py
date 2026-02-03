"""Structured logging and tracing for the application."""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """Configure application logging.

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, settings.app_log_level)

    # Create logs directory
    log_dir = Path(settings.app_env).joinpath("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with simpler format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler with JSON format
    log_file = log_dir.joinpath("run.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Configure specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger("app")


def log_trace(
    logger: logging.Logger,
    case_id: str,
    stage: str,
    model_used: str,
    inputs_summary: str,
    outputs_summary: str,
    **extra: Any,
) -> None:
    """Log a trace event.

    Args:
        logger: Logger instance
        case_id: Case identifier
        stage: Processing stage name
        model_used: Model or service name
        inputs_summary: Summary of inputs (redacted)
        outputs_summary: Summary of outputs
        **extra: Additional fields to log
    """
    logger.info(
        f"Trace: case={case_id} stage={stage} model={model_used}",
        extra={
            "extra_data": {
                "case_id": case_id,
                "stage": stage,
                "model_used": model_used,
                "inputs_redacted": inputs_summary,
                "outputs_summary": outputs_summary,
                **extra,
            }
        },
    )


def log_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = "",
    **tags: Any,
) -> None:
    """Log a metric value.

    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        **tags: Additional tags
    """
    logger.info(
        f"Metric: {metric_name}={value}{unit}",
        extra={
            "extra_data": {
                "metric_name": metric_name,
                "metric_value": value,
                "metric_unit": unit,
                "metric_tags": tags,
            }
        },
    )


def log_error(
    logger: logging.Logger,
    case_id: str,
    stage: str,
    error: Exception,
    **context: Any,
) -> None:
    """Log an error with context.

    Args:
        logger: Logger instance
        case_id: Case identifier
        stage: Processing stage where error occurred
        error: The exception
        **context: Additional context
    """
    logger.error(
        f"Error: case={case_id} stage={stage} error={type(error).__name__}: {error}",
        extra={
            "extra_data": {
                "case_id": case_id,
                "stage": stage,
                "error_type": type(error).__name__,
                "error_message": str(error),
                **context,
            }
        },
        exc_info=error,
    )


# Initialize app logger
app_logger = setup_logging()
