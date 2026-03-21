import logging
import threading
import time
from pathlib import Path
from datetime import datetime


# ANSI color codes
class _Colors:
    RESET   = "\033[0m"
    GREY    = "\033[38;5;240m"
    CYAN    = "\033[36m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    BOLD_RED = "\033[1;31m"
    GREEN   = "\033[32m"
    BLUE    = "\033[34m"


_LEVEL_COLORS = {
    logging.DEBUG:    _Colors.GREY,
    logging.INFO:     _Colors.GREEN,
    logging.WARNING:  _Colors.YELLOW,
    logging.ERROR:    _Colors.RED,
    logging.CRITICAL: _Colors.BOLD_RED,
}


class _ColorFormatter(logging.Formatter):
    """Console formatter with colors and aligned level names."""

    FMT = "{color}[{levelname:<8}]{reset} {grey}{asctime}{reset}  {name}  {message}"

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, _Colors.RESET)
        formatter = logging.Formatter(
            fmt=self.FMT.format(
                color=color,
                levelname=record.levelname,
                reset=_Colors.RESET,
                grey=_Colors.GREY,
                asctime="%(asctime)s",
                name=f"{_Colors.CYAN}%(name)s{_Colors.RESET}",
                message="%(message)s",
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
            style="%",
        )
        return formatter.format(record)


class _PlainFormatter(logging.Formatter):
    """Plain formatter for file output (no ANSI codes)."""

    FMT = "[%(levelname)-8s] %(asctime)s  %(name)s  %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.FMT, datefmt="%Y-%m-%d %H:%M:%S")


class FitAgentLogger:
    """
    Singleton logger factory for the fit-agent project.

    Usage:
        from src.utils.logger import get_logger
        log = get_logger(__name__)
        log.info("Starting agent")
        log.warning("Low memory")
    """

    _lock = threading.Lock()
    _initialized = False
    _log_dir: Path = Path("logs")
    _level: int = logging.DEBUG

    @classmethod
    def setup(
        cls,
        level: int = logging.DEBUG,
        log_dir: str | Path | None = "logs",
        log_to_file: bool = True,
    ) -> None:
        """Configure root handlers once. Safe to call multiple times."""
        with cls._lock:
            if cls._initialized:
                return

            cls._level = level
            root = logging.getLogger()
            root.setLevel(level)

            # Remove any existing handlers added by libraries
            root.handlers.clear()

            # Console handler
            console = logging.StreamHandler()
            console.setLevel(level)
            console.setFormatter(_ColorFormatter())
            root.addHandler(console)

            # File handler (optional)
            if log_to_file and log_dir is not None:
                cls._log_dir = Path(log_dir)
                cls._log_dir.mkdir(parents=True, exist_ok=True)
                log_file = cls._log_dir / f"fitagent_{datetime.now():%Y%m%d}.log"
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setLevel(level)
                file_handler.setFormatter(_PlainFormatter())
                root.addHandler(file_handler)

            cls._initialized = True


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Return a logger for the given name.
    Calls FitAgentLogger.setup() with defaults on first use.
    """
    if not FitAgentLogger._initialized:
        FitAgentLogger.setup()

    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger
