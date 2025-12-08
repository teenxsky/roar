import sys

from loguru import logger

from src.config import config


def setup_logging() -> None:
    """Инициализирует логирование."""
    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            '<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>'
        ),
        level=config.LOG_LEVEL,
    )
