"""Пользовательские исключения ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке."""

    def __init__(self, available: str, required: str, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестный код валюты."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    """Сбой при обращении к внешнему API курсов."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
