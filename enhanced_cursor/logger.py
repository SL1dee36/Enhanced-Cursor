import os
import sys
import logging
from logging.handlers import RotatingFileHandler

_logger = None
_log_file_path = None


def get_app_dir() -> str:
    """Returns the base data directory for EnhancedCursor in APPDATA."""
    appdata = os.environ.get("APPDATA")
    if appdata and os.path.isdir(appdata):
        base = os.path.join(appdata, "EnhancedCursor")
    else:
        # Fallback to current directory or exe folder
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base


def setup_logger() -> logging.Logger:
    global _logger, _log_file_path
    if _logger is not None:
        return _logger

    app_dir = get_app_dir()
    logs_dir = os.path.join(app_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    _log_file_path = os.path.join(logs_dir, "enhanced_cursor.log")

    logger = logging.getLogger("EnhancedCursor")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid adding handlers if already present
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            _log_file_path,
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=2,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Optional console handler when running from source
        if not getattr(sys, "frozen", False):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    _logger = logger
    return _logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return setup_logger()
    return _logger


def get_log_file_path() -> str:
    global _log_file_path
    if _log_file_path is None:
        setup_logger()
    return _log_file_path


def open_log_file() -> bool:
    """Opens log file in standard Windows text viewer."""
    path = get_log_file_path()
    try:
        if os.path.exists(path):
            os.startfile(path)
            return True
    except Exception as e:
        if _logger:
            _logger.error(f"Failed to open log file: {e}")
    return False

