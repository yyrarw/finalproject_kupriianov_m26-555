"""Вспомогательные функции: JSON-файлы, валидация и форматирование."""

import json
import os
from datetime import datetime

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")
FILE_ENCODING = "utf-8"
JSON_INDENT = 2
CRYPTO_CODES = ("BTC", "ETH", "SOL")
FIAT_PRECISION = 2
CRYPTO_PRECISION = 4


def read_json(path: str, default):
    """Читает JSON-файл; если файла нет, возвращает default."""
    try:
        with open(path, encoding=FILE_ENCODING) as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def write_json(path: str, data) -> None:
    """Записывает JSON атомарно: во временный файл, затем переименование."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding=FILE_ENCODING) as file:
        json.dump(data, file, ensure_ascii=False, indent=JSON_INDENT)
    os.replace(tmp_path, path)


def normalize_currency_code(code: str) -> str:
    """Приводит код валюты к верхнему регистру и проверяет, что он не пустой."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def parse_amount(value: str) -> float:
    """Превращает строку из командной строки в число."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None


def format_amount(code: str, amount: float) -> str:
    """Форматирует сумму: 4 знака для криптовалют, 2 — для фиата."""
    precision = CRYPTO_PRECISION if code in CRYPTO_CODES else FIAT_PRECISION
    return f"{amount:.{precision}f}"


def format_rate(rate: float) -> str:
    """Форматирует курс: крупные значения с 2 знаками, мелкие — с 8."""
    return f"{rate:.2f}" if rate >= 1 else f"{rate:.8f}"


def format_timestamp(value: str) -> str:
    """Показывает ISO-время в виде "2025-10-09 00:03:22"."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%Y-%m-%d %H:%M:%S")
