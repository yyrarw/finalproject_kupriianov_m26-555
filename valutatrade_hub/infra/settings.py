"""Единая конфигурация приложения (Singleton SettingsLoader)."""

import os
import tomllib
from typing import Any

PYPROJECT_FILE = "pyproject.toml"
CONFIG_SECTION = ("tool", "valutatrade")

DEFAULT_SETTINGS = {
    "data_dir": "data",
    "users_file": "users.json",
    "portfolios_file": "portfolios.json",
    "rates_file": "rates.json",
    "exchange_rates_file": "exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "actions_log_file": "actions.log",
    "parser_log_file": "parser.log",
    "log_level": "INFO",
    "log_format": "%(levelname)s %(asctime)s %(message)s",
    "log_date_format": "%Y-%m-%dT%H:%M:%S",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 3,
}


class SettingsLoader:
    """Загружает настройки из [tool.valutatrade] в pyproject.toml.

    Singleton реализован через __new__: это самый короткий и читаемый способ —
    класс сам хранит единственный экземпляр, метакласс для этого не нужен.
    Повторные вызовы SettingsLoader() и импорты возвращают тот же объект.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Перечитывает настройки: значения по умолчанию + pyproject.toml."""
        settings = dict(DEFAULT_SETTINGS)
        settings.update(self._read_pyproject())
        self._settings = settings

    @staticmethod
    def _read_pyproject() -> dict:
        """Читает секцию [tool.valutatrade], если pyproject.toml доступен."""
        try:
            with open(PYPROJECT_FILE, "rb") as file:
                data = tomllib.load(file)
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            return {}
        for key in CONFIG_SECTION:
            data = data.get(key, {})
        return data

    def get(self, key: str, default: Any = None) -> Any:
        """Значение настройки по ключу."""
        return self._settings.get(key, default)

    def data_path(self, file_key: str) -> str:
        """Полный путь к файлу данных по ключу настройки, например rates_file."""
        return os.path.join(self.get("data_dir"), self.get(file_key))
