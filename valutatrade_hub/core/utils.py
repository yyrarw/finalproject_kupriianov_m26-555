"""Вспомогательные функции: валидация, конвертация, форматирование, время."""

from datetime import datetime, timezone

from valutatrade_hub.core.currencies import (
    CODE_MAX_LENGTH,
    CODE_MIN_LENGTH,
    CryptoCurrency,
    get_currency,
)
from valutatrade_hub.core.exceptions import CurrencyNotFoundError

FIAT_PRECISION = 2
CRYPTO_PRECISION = 4
LARGE_RATE_THRESHOLD = 1
LARGE_RATE_FORMAT = ".2f"
SMALL_RATE_FORMAT = ".8f"
DISPLAY_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
UTC_SUFFIX = "Z"


def validate_currency_code(code: str) -> str:
    """Приводит код к верхнему регистру и проверяет формат: 2–5 символов."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    code = code.strip().upper()
    if not (CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH and code.isalnum()):
        raise ValueError(
            f"Код валюты должен состоять из {CODE_MIN_LENGTH}–{CODE_MAX_LENGTH} "
            "букв или цифр без пробелов"
        )
    return code


def parse_amount(value: str) -> float:
    """Превращает строку из командной строки в число."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None


def convert(amount: float, rate: float) -> float:
    """Переводит сумму по курсу (сколько единиц цели за одну единицу исходной)."""
    return amount * rate


def is_crypto(code: str) -> bool:
    """Проверяет, что код принадлежит известной криптовалюте."""
    try:
        return isinstance(get_currency(code), CryptoCurrency)
    except CurrencyNotFoundError:
        return False


def format_amount(code: str, amount: float) -> str:
    """Форматирует сумму: 4 знака для криптовалют, 2 — для фиата."""
    precision = CRYPTO_PRECISION if is_crypto(code) else FIAT_PRECISION
    return f"{amount:.{precision}f}"


def format_rate(rate: float) -> str:
    """Форматирует курс: крупные значения с 2 знаками, мелкие — с 8."""
    fmt = LARGE_RATE_FORMAT if rate >= LARGE_RATE_THRESHOLD else SMALL_RATE_FORMAT
    return format(rate, fmt)


def utc_now() -> datetime:
    """Текущее время в UTC без микросекунд."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(moment: datetime) -> str:
    """UTC-время в ISO-формате с суффиксом Z: 2025-10-10T12:00:00Z."""
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", UTC_SUFFIX)


def parse_iso(value: str) -> datetime:
    """Разбирает ISO-время; время без часового пояса считается UTC."""
    moment = datetime.fromisoformat(value.replace(UTC_SUFFIX, "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def is_fresh(updated_at: str | None, ttl_seconds: int) -> bool:
    """Проверяет, что значение обновлено не раньше чем ttl_seconds назад."""
    if updated_at is None:
        return True
    return (utc_now() - parse_iso(updated_at)).total_seconds() <= ttl_seconds


def format_timestamp(value: str) -> str:
    """Показывает ISO-время в виде "2025-10-09 00:03:22"."""
    return parse_iso(value).strftime(DISPLAY_TIME_FORMAT)
