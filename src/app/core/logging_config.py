import logging  # noqa: TID251
import sys
from typing import Any

import structlog

from .config import get_config

# Check for rich availability at module level
_RICH_AVAILABLE = False
try:
    import rich  # type: ignore

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

# Check for colorama availability at module level
_COLORAMA_AVAILABLE = False
try:
    import colorama

    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False

level_mapping = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_structlog() -> None:
    """
    Configure structlog for structured JSON logging based on application configuration.

    Uses the centralized configuration system to load logging settings from .env file.
    """
    # Prevent multiple configurations
    if hasattr(configure_structlog, "_configured"):
        return
    configure_structlog._configured = True

    if _COLORAMA_AVAILABLE:
        colorama.init()

    # Get configuration
    config = get_config()
    log_level = level_mapping.get(config.logging.level, logging.INFO)
    log_format = config.logging.format.lower()
    include_caller = config.logging.include_caller
    disabled_loggers = config.logging.disabled_loggers or ["ddtrace", "uvicorn.access"]
    noisy_loggers = config.logging.noisy_loggers or [
        "boto3",
        "botocore",
        "urllib3",
        "httpx",
        "psycopg",
        "langchain",
    ]
    clear_loggers = config.logging.clear_loggers or []

    # Build processor chains
    core_processors = _build_core_processors(log_format, include_caller)
    structlog_processors = core_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    formatter_processors = _build_formatter_processors(log_format)

    # Configure structlog
    structlog.configure(
        processors=structlog_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure logging handler
    _configure_logging_handler(core_processors, formatter_processors, log_level)

    # Configure third-party loggers
    configure_third_party_loggers(disabled_loggers, noisy_loggers, clear_loggers)


def _build_core_processors(log_format: str, include_caller: bool) -> list[Any]:
    """Build the core processor chain shared by both structlog and stdlib logs."""
    core_processors = [
        structlog.contextvars.merge_contextvars,  # Include context variables from bind_contextvars
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(
            fmt="iso" if log_format == "json" else "%Y-%m-%d %H:%M:%S"
        ),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add caller info if requested (before StackInfoRenderer)
    if include_caller:
        core_processors.insert(
            -1,  # Insert before StackInfoRenderer
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
        )

    return core_processors


def _build_formatter_processors(log_format: str) -> list[Any]:
    """Build the final formatter processor chain for ProcessorFormatter."""
    base_processors = [structlog.stdlib.ProcessorFormatter.remove_processors_meta]

    if _RICH_AVAILABLE:
        exception_formatter = structlog.dev.RichTracebackFormatter(
            max_frames=5,
            show_locals=False,
        )
    else:
        exception_formatter = structlog.dev.plain_traceback

    if log_format == "json":
        return base_processors + [
            structlog.processors.format_exc_info,  # JSON needs formatted strings
            structlog.processors.JSONRenderer(),
        ]
    else:
        return base_processors + [
            # ConsoleRenderer handles exc_info natively for Rich pretty-printing
            structlog.dev.ConsoleRenderer(
                colors=_COLORAMA_AVAILABLE,
                exception_formatter=exception_formatter,
            )
        ]


def _configure_logging_handler(
    core_processors: list[Any], formatter_processors: list[Any], log_level: int
) -> None:
    """Configure the logging handler with ProcessorFormatter."""
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=core_processors,
        processors=formatter_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


def configure_logger_hierarchy(logger_name: str, configure_func) -> None:
    """Configure a logger and all its children efficiently.

    Args:
        logger_name: Name of the parent logger
        configure_func: Function to apply to each logger (parent and children)
    """
    # Configure the parent logger
    logger = logging.getLogger(logger_name)
    configure_func(logger)

    # Only check loggers that could be children - create snapshot to avoid concurrent modification
    prefix = f"{logger_name}."
    logger_names = list(logging.Logger.manager.loggerDict.keys())

    for name in logger_names:
        if name.startswith(prefix):
            child_logger = logging.getLogger(name)
            configure_func(child_logger)


def configure_third_party_loggers(
    disabled_loggers: list[str], noisy_loggers: list[str], clear_loggers: list[str]
) -> None:
    """Configure third-party library loggers to reduce noise.

    Args:
        disabled_loggers: List of logger names to completely disable
        noisy_loggers: List of logger names to set to WARNING level
        clear_loggers: List of logger names to clear handlers and force propagation
    """

    # Set noisy loggers to WARNING level
    def set_warning_level(logger):
        logger.setLevel(logging.WARNING)

    for logger_name in noisy_loggers:
        configure_logger_hierarchy(logger_name, set_warning_level)

    # Clear handlers for specified loggers to force them through root logger
    def clear_handlers_and_propagate(logger):
        logger.handlers.clear()  # Clear their own handlers
        logger.propagate = True  # Ensure they propagate to root logger

    for logger_name in clear_loggers:
        configure_logger_hierarchy(logger_name, clear_handlers_and_propagate)

    # Completely disable specified loggers
    def disable_logger(logger):
        logger.handlers.clear()  # Clear handlers, as some libraries register their own
        logger.disabled = True
        logger.propagate = False

    for logger_name in disabled_loggers:
        configure_logger_hierarchy(logger_name, disable_logger)


def get_logger(name: str, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger with optional initial context.

    Args:
        name: Logger name (defaults to caller's module)
        **initial_values: Initial context values to bind to logger

    Returns:
        Configured structlog logger

    Example:
        logger = get_logger(__name__, service="agents", version="1.0.0")
        logger.info("Processing request", user_id=123, action="query")
    """
    logger = structlog.get_logger(name)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger
