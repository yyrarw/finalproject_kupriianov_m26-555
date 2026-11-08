"""Иерархия валют и реестр поддерживаемых валют."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

CODE_MIN_LENGTH = 2
CODE_MAX_LENGTH = 5


class Currency(ABC):
    """Абстрактная валюта: человекочитаемое имя и код (тикер)."""

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        is_valid_code = (
            isinstance(code, str)
            and CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH
            and code.isalnum()
            and code == code.upper()
        )
        if not is_valid_code:
            raise ValueError(
                f"Код валюты должен состоять из {CODE_MIN_LENGTH}–{CODE_MAX_LENGTH} "
                "символов в верхнем регистре без пробелов"
            )
        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для интерфейса и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта, выпускаемая государством или валютной зоной."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        """Пример: [FIAT] USD — US Dollar (Issuing: United States)."""
        return (
            f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"
        )


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом консенсуса и рыночной капитализацией."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        """Пример: [CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)."""
        market_cap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {market_cap})"
        )


_CURRENCIES = {
    currency.code: currency
    for currency in (
        FiatCurrency("US Dollar", "USD", "United States"),
        FiatCurrency("Euro", "EUR", "Eurozone"),
        FiatCurrency("British Pound", "GBP", "United Kingdom"),
        FiatCurrency("Russian Ruble", "RUB", "Russia"),
        CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
        CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
        CryptoCurrency("Solana", "SOL", "Proof of History", 6.8e10),
    )
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту по коду или бросает CurrencyNotFoundError."""
    normalized = code.strip().upper() if isinstance(code, str) else code
    try:
        return _CURRENCIES[normalized]
    except (KeyError, TypeError):
        raise CurrencyNotFoundError(str(code)) from None


def supported_codes() -> list[str]:
    """Коды всех поддерживаемых валют."""
    return sorted(_CURRENCIES)
