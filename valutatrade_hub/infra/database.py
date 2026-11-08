"""Доступ к JSON-хранилищу (Singleton DatabaseManager)."""

import json
import os
from collections.abc import Callable
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader

FILE_ENCODING = "utf-8"
JSON_INDENT = 2
TMP_SUFFIX = ".tmp"

COLLECTIONS = {
    "users": ("users_file", list),
    "portfolios": ("portfolios_file", list),
    "rates": ("rates_file", dict),
    "exchange_rates": ("exchange_rates_file", list),
}


class DatabaseManager:
    """Абстракция над JSON-файлами в data/.

    Singleton через __new__ (как и SettingsLoader): одно хранилище на всё
    приложение. Запись атомарная: временный файл, затем os.replace.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def path(collection: str) -> str:
        """Путь к файлу коллекции (users, portfolios, rates, exchange_rates)."""
        file_key, _ = COLLECTIONS[collection]
        return SettingsLoader().data_path(file_key)

    def read(self, collection: str) -> Any:
        """Читает коллекцию; если файла нет, возвращает пустую структуру."""
        _, empty_factory = COLLECTIONS[collection]
        try:
            with open(self.path(collection), encoding=FILE_ENCODING) as file:
                return json.load(file)
        except FileNotFoundError:
            return empty_factory()

    def write(self, collection: str, data: Any) -> None:
        """Атомарно записывает коллекцию."""
        write_json_atomic(self.path(collection), data)

    def update(self, collection: str, modify: Callable[[Any], Any]) -> Any:
        """Чтение → модификация → запись; возвращает результат modify."""
        data = self.read(collection)
        result = modify(data)
        self.write(collection, data)
        return result


def write_json_atomic(path: str, data: Any) -> None:
    """Пишет JSON во временный файл и переименовывает его поверх целевого."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + TMP_SUFFIX
    with open(tmp_path, "w", encoding=FILE_ENCODING) as file:
        json.dump(data, file, ensure_ascii=False, indent=JSON_INDENT)
    os.replace(tmp_path, path)
