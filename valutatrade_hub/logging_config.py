"""Настройка логирования: строковый формат и ротация файлов по размеру."""

import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

ACTIONS_LOGGER = "valutatrade.actions"
PARSER_LOGGER = "valutatrade.parser"
CONSOLE_FORMAT = "%(levelname)s: %(message)s"
FILE_ENCODING = "utf-8"


def _file_handler(file_key: str) -> RotatingFileHandler:
    """Файловый обработчик с ротацией: log_max_bytes, log_backup_count копий."""
    settings = SettingsLoader()
    log_dir = settings.get("log_dir")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(log_dir, settings.get(file_key)),
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding=FILE_ENCODING,
    )
    handler.setFormatter(
        logging.Formatter(settings.get("log_format"), settings.get("log_date_format"))
    )
    return handler


def _configure(name: str, file_key: str, console: bool) -> logging.Logger:
    """Настраивает логгер один раз; повторные вызовы ничего не меняют."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(SettingsLoader().get("log_level"))
    logger.propagate = False
    logger.addHandler(_file_handler(file_key))
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        logger.addHandler(stream)
    return logger


def get_actions_logger() -> logging.Logger:
    """Логгер доменных операций: logs/actions.log."""
    return _configure(ACTIONS_LOGGER, "actions_log_file", console=False)


def get_parser_logger() -> logging.Logger:
    """Логгер Parser Service: logs/parser.log и вывод шагов в консоль."""
    return _configure(PARSER_LOGGER, "parser_log_file", console=True)
