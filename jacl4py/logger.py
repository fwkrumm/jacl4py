"""
Logging utilities: ``JacLogger`` subclass with project-specific levels and
a ``get_logger`` factory that attaches console + rotating file handlers.
"""
import logging
import os
import re
import tempfile
import warnings
from enum import Enum
from functools import wraps
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from threading import RLock
from uuid import uuid4

import coloredlogs

from . import __version__ as __version__
from .exceptions import ResourceNotInitializedError

INTERNAL_DEBUG = 5
INTERNAL_INFO = 7
logging.addLevelName(INTERNAL_DEBUG, "INTERNAL_DEBUG")
logging.addLevelName(INTERNAL_INFO, "INTERNAL_INFO")


class LogDir(Enum):
    """Special log directory settings."""

    DEFAULT = "default"


class JacLogger(logging.Logger):
    """Logger subclass that adds INTERNAL_INFO (7) and INTERNAL_DEBUG (5) levels below DEBUG."""

    _deleted: bool = False

    def isEnabledFor(self, level: int) -> bool:
        """Check the level, raising ResourceNotInitializedError after deletion."""
        if self._deleted:
            raise ResourceNotInitializedError(
                f"Logger '{self.name}' has been deleted. "
                "Obtain a new logger with get_logger() before logging."
            )
        return super().isEnabledFor(level)

    def iinfo(self, message, *args, **kwargs):
        """Log at INTERNAL_INFO level (7) --- framework lifecycle events, below DEBUG."""
        if self.isEnabledFor(INTERNAL_INFO):
            self._log(INTERNAL_INFO, message, args, **kwargs)

    def idebug(self, message, *args, **kwargs):
        """
        Log at INTERNAL_DEBUG level (5) --- fine-grained framework tracing, below INTERNAL_INFO.
        """
        if self.isEnabledFor(INTERNAL_DEBUG):
            self._log(INTERNAL_DEBUG, message, args, **kwargs)


_manager = logging.Manager(logging.root)
_manager.setLoggerClass(JacLogger)
_lifecycle_lock = RLock()


def _after_fork() -> None:
    global _manager, _lifecycle_lock
    for logger in _manager.loggerDict.values():
        if isinstance(logger, JacLogger):
            logger._deleted = True  # pylint: disable=protected-access
            logger.disabled = True
    _manager = logging.Manager(logging.root)
    _manager.setLoggerClass(JacLogger)
    _lifecycle_lock = RLock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


def _synchronized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _lifecycle_lock:
            return function(*args, **kwargs)
    return wrapped


def _create_log_path(name: str, log_dir: str | Path | LogDir) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name).strip(".")[:64] or "logger"
    if log_dir is not LogDir.DEFAULT:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
    while True:
        identifier = safe_name + uuid4().hex[:8]
        try:
            if log_dir is LogDir.DEFAULT:
                directory = Path(tempfile.gettempdir()) / identifier
                directory.mkdir(mode=0o700)
                return directory / f"{safe_name}.log"
            filename = directory / f"{identifier}.log"
            with filename.open("x", encoding="utf-8"):
                pass
            return filename
        except FileExistsError:
            continue


@_synchronized
def delete_logger(name: str = "default") -> bool:
    """Close and unregister a package logger, keeping existing log files.

    Return False if no named logger exists. Deleted JacLogger references
    raise ResourceNotInitializedError when used to log;
    package child loggers remain usable. Standard logging loggers are untouched.
    """
    manager = _manager
    logger = manager.loggerDict.get(name)
    if not isinstance(logger, logging.Logger):
        return False

    if isinstance(logger, JacLogger):
        logger._deleted = True  # pylint: disable=protected-access
    logger.disabled = True
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    del manager.loggerDict[name]
    for child in list(manager.loggerDict.values()):
        if isinstance(child, logging.Logger) and child.parent is logger:
            manager._fixupParents(child)  # pylint: disable=protected-access
    return True


@_synchronized
def get_logger(  # pylint: disable=too-many-arguments
    name: str = "default",
    *,
    console_log_level: int | None = logging.INFO,
    log_dir: str | Path | LogDir | None = LogDir.DEFAULT,
    file_log_level: int | None = INTERNAL_DEBUG,
    use_colored_output: bool = True,
    reinit_if_exists: bool = False
) -> JacLogger:
    """
    Get or create a configured logger instance.

    Parameters
    ----------
    name : str
        Logger name (default: "default")
    console_log_level : int | None
        Console handler level. Set to None to disable console logging.
    log_dir : str | Path | LogDir | None
        Directory for log files. LogDir.DEFAULT uses the system temp directory
        under the sanitized name plus eight UUID4 hex characters. Explicit
        directories use a unique filename. Set to None to disable file logging.
    file_log_level : int | None
        File handler level. Set to None to disable file logging.
    use_colored_output : bool
        Whether to use colored console output (default: True)
    reinit_if_exists : bool
        Delete an existing named logger and apply new settings (default: False).
        Existing log files are preserved.

    Returns
    -------
    JacLogger
        Configured package-owned logger, separate from logging.getLogger(name).
        After fork, obtain a fresh logger in the child with get_logger().
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Logger name must be a non-empty string.")
    if reinit_if_exists:
        delete_logger(name)
    logger = _manager.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        warnings.warn(
            f"Logger '{name}' already configured; returning cached logger "\
                "and ignoring new settings.",
            stacklevel=2
        )
        return logger

    # Logger level must be INTERNAL to allow file handler to capture everything
    # Individual handlers control their own output levels
    logger.setLevel(INTERNAL_DEBUG)
    logger.propagate = False

    # Create file formatter
    file_formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler with coloredlogs
    if console_log_level is not None:
        if use_colored_output:
            # coloredlogs installs directly on the logger with field-level colors
            coloredlogs.install(
                level=console_log_level,
                logger=logger,
                fmt="%(asctime)s.%(msecs)03d %(hostname)s %(name)s[%(process)d] "\
                    "%(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                level_styles={
                    "internal_debug": {"color": "blue"},
                    "internal_info": {"color": "white"},
                    "debug": {"color": "cyan"},
                    "info": {"color": "green"},
                    "warning": {"color": "yellow", "bold": True},
                    "error": {"color": "red", "bold": True},
                    "critical": {"color": "red", "bold": True, "background": "white"}
                },
                field_styles={
                    "asctime": {"color": "white", "bold": True},
                    "hostname": {"color": "magenta"},
                    "levelname": {"color": "white", "bold": True},
                    "name": {"color": "cyan"},
                    "programname": {"color": "cyan"},
                    "process": {"color": "magenta"}
                }
            )
        else:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_log_level)
            console_handler.setFormatter(file_formatter)
            logger.addHandler(console_handler)

    # File handler with rotation
    if log_dir is not None and file_log_level is not None:
        try:
            log_filename = _create_log_path(name, log_dir)
            file_handler = TimedRotatingFileHandler(
                log_filename,
                when="midnight",
                interval=1,
                backupCount=30,
                encoding="utf-8"
            )
            file_handler.setLevel(file_log_level)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            logger.info("Logging files to %s", log_filename.parent)

        except (PermissionError, OSError) as e:
            warnings.warn(
                f"Could not create log file for '{name}' in {log_dir!r}: {e}. "
                "File logging disabled.",
                stacklevel=2
            )

    return logger
