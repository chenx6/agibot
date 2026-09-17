from logging import DEBUG, INFO, FileHandler, Formatter, StreamHandler, getLogger
from os import environ
from pathlib import Path
from sys import stderr


def get_logger(name: str | None = None):
    if not name:
        name = "agibot"
    logger = getLogger(name)
    level = DEBUG if environ.get("TEST") else INFO
    logger.setLevel(level)
    if not logger.handlers:
        fmt = Formatter(fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        stream = StreamHandler(stderr)
        stream.setLevel(level)
        stream.setFormatter(fmt)
        folder = Path("logs")
        if not folder.exists():
            folder.mkdir()
        file = FileHandler("logs/agi.log")
        file.setLevel(level)
        file.setFormatter(fmt)
        logger.addHandler(stream)
        logger.addHandler(file)
    return logger
