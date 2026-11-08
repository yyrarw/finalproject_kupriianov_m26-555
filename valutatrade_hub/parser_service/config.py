"""Конфигурация Parser Service: API, списки валют, пути и сетевые параметры."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader

ENV_FILE = ".env"
API_KEY_ENV_VAR = "EXCHANGERATE_API_KEY"


def load_env_file(path: str = ENV_FILE) -> None:
    """Загружает переменные из .env (KEY=VALUE), не перезаписывая окружение."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _api_key() -> str | None:
    """API-ключ ExchangeRate-API из окружения или файла .env (не из кода)."""
    load_env_file()
    return os.getenv(API_KEY_ENV_VAR) or None


@dataclass(frozen=True)
class ParserConfig:
    """Все изменяемые параметры Parser Service в одном месте."""

    # Ключ загружается из переменной окружения или .env (файл в .gitignore)
    EXCHANGERATE_API_KEY: str | None = field(default_factory=_api_key)

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # Пути (берутся из SettingsLoader, чтобы Core и Parser читали одни файлы)
    RATES_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().data_path("rates_file")
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().data_path("exchange_rates_file")
    )

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 300
