import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = os.environ.get("TOJI_LOG_FILE", "tojifushiguro.log")
LOG_LEVEL = getattr(logging, os.environ.get("TOJI_LOG_LEVEL", "INFO").upper(), logging.INFO)

def setup_logger() -> logging.Logger:
    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("TojiFushiguro")

    root.setLevel(LOG_LEVEL)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    fmt = logging.Formatter(
        "%(asctime)s - [TojiFushiguro] >> %(levelname)s << %(message)s",
        datefmt="[%d/%m/%Y %H:%M:%S]",
    )

    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(LOG_LEVEL)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(LOG_LEVEL)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    return logging.getLogger("TojiFushiguro")

logger = setup_logger()
logger.info("TojiFushiguro logging initialized successfully.")
