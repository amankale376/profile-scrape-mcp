"""Logging configuration for the Profile Scraping MCP Server."""

import sys
from loguru import logger
from typing import Optional


def setup_logger(
    level: str = "INFO",
    format_string: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """
    Setup logger configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string
        log_file: Optional log file path
    """
    # Remove default logger
    logger.remove()
    
    # Default format
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    # Add console handler
    logger.add(
        sys.stdout,
        format=format_string,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # Add file handler if specified
    if log_file:
        logger.add(
            log_file,
            format=format_string,
            level=level,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )
    
    logger.info(f"Logger initialized with level: {level}")


def get_logger(name: str = __name__):
    """Get a logger instance with the specified name."""
    return logger.bind(name=name)


# Initialize default logger
setup_logger()