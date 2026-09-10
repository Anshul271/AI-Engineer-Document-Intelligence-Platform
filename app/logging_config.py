"""
Centralised logging setup. Every module gets a logger via get_logger(__name__).
Logs go to stdout (captured by the hosting platform) and to a rotating file
under ./logs for local debugging.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _build_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (avoid duplicate handlers on reload)

    root.setLevel(logging.INFO)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"), maxBytes=2_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


_build_root_logger()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
