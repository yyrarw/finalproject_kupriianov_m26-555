"""Клиенты внешних API курсов с единым интерфейсом fetch_rates()."""

import math
import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

HTTP_OK = 200
HTTP_REDIRECT_MIN = 300
HTTP_REDIRECT_MAX = 399
HTTP_SERVER_ERROR_MIN = 500
MS_IN_SECOND = 1000
HTTP_ERROR_REASONS = {
    401: "неверный API-ключ",
    403: "доступ запрещен (проверьте API-ключ)",
    404: "ресурс не найден",
    429: "превышен лимит запросов, повторите позже",
}
EXCHANGERATE_ERROR_REASONS = {
    "invalid-key": "неверный API-ключ",
    "inactive-account": "аккаунт не активирован (подтвердите email)",
    "quota-reached": "исчерпан лимит запросов тарифа",
    "unsupported-code": "неподдерживаемый код валюты",
}


def is_valid_rate(value) -> bool:
    """Курс должен быть конечным положительным числом."""
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return is_number and math.isfinite(value) and value > 0


class BaseApiClient(ABC):
    """Общий интерфейс клиента: fetch_rates() -> {"BTC_USD": 59337.21, ...}."""

    SOURCE = "unknown"

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.last_meta: dict = {}
        self.raw_ids: dict[str, str] = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает курсы в формате {"<FROM>_<TO>": rate}."""

    def pair(self, code: str) -> str:
        """Ключ пары к базовой валюте: BTC_USD."""
        return f"{code}_{self.config.BASE_CURRENCY}"

    def get_json(self, url: str, params: dict | None = None) -> dict:
        """GET-запрос с таймаутом; все сбои превращаются в ApiRequestError."""
        started = time.monotonic()
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"превышено время ожидания ({self.config.REQUEST_TIMEOUT} с)"
            ) from None
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"сетевая ошибка ({type(error).__name__})") from None

        self.last_meta = {
            "request_ms": round((time.monotonic() - started) * MS_IN_SECOND),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        self.check_response(response)
        try:
            return response.json()
        except ValueError:
            raise ApiRequestError("ответ не в формате JSON") from None

    def check_response(self, response) -> None:
        """Переводит HTTP-статус ошибки в понятное сообщение."""
        status_code = response.status_code
        if status_code == HTTP_OK:
            return
        if HTTP_REDIRECT_MIN <= status_code <= HTTP_REDIRECT_MAX:
            reason = "запрос перенаправлен, возможно, сайт заблокирован сетью"
        elif status_code >= HTTP_SERVER_ERROR_MIN:
            reason = "сервер недоступен"
        else:
            reason = HTTP_ERROR_REASONS.get(status_code, "неожиданный ответ сервера")
        raise ApiRequestError(f"{reason} (HTTP {status_code})")


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют из CoinGecko (по ID монет из CRYPTO_ID_MAP)."""

    SOURCE = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        """Курсы BTC_USD, ETH_USD, SOL_USD из /simple/price."""
        ids = {
            code: self.config.CRYPTO_ID_MAP[code]
            for code in self.config.CRYPTO_CURRENCIES
        }
        vs_currency = self.config.BASE_CURRENCY.lower()
        data = self.get_json(
            self.config.COINGECKO_URL,
            {"ids": ",".join(ids.values()), "vs_currencies": vs_currency},
        )
        rates = {}
        for code, coin_id in ids.items():
            value = data.get(coin_id, {}).get(vs_currency)
            if is_valid_rate(value):
                rates[self.pair(code)] = float(value)
                self.raw_ids[self.pair(code)] = coin_id
        if not rates:
            raise ApiRequestError("в ответе нет курсов")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют из ExchangeRate-API (ключ в URL)."""

    SOURCE = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        """Курсы EUR_USD, GBP_USD, RUB_USD из /latest/USD."""
        key = self.config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError(
                "не задан ключ EXCHANGERATE_API_KEY (переменная окружения или .env)"
            )
        base = self.config.BASE_CURRENCY
        data = self.get_json(f"{self.config.EXCHANGERATE_API_URL}/{key}/latest/{base}")
        if data.get("result") != "success":
            self.raise_api_error(data)

        self.last_meta["provider_time"] = data.get("time_last_update_utc")
        rates = {}
        for code in self.config.FIAT_CURRENCIES:
            base_to_code = data.get("rates", {}).get(code)
            # API отдает "1 USD = X EUR"; в кеше храним "1 EUR = Y USD", Y = 1 / X
            if is_valid_rate(base_to_code):
                rates[self.pair(code)] = 1 / base_to_code
        if not rates:
            raise ApiRequestError("в ответе нет курсов")
        return rates

    def check_response(self, response) -> None:
        """При ошибке берет точную причину из поля error-type тела ответа."""
        if response.status_code != HTTP_OK:
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and "error-type" in data:
                self.raise_api_error(data, response.status_code)
        super().check_response(response)

    def raise_api_error(self, data: dict, status_code: int | None = None) -> None:
        """Бросает ApiRequestError с причиной из ответа ExchangeRate-API."""
        error_type = data.get("error-type", "unknown")
        reason = EXCHANGERATE_ERROR_REASONS.get(error_type, error_type)
        status = f" (HTTP {status_code})" if status_code else ""
        raise ApiRequestError(f"{reason}{status}")


class CoinbaseClient(BaseApiClient):
    """Резервные курсы криптовалют из публичного API Coinbase (без ключа)."""

    SOURCE = "Coinbase"

    def fetch_rates(self) -> dict[str, float]:
        """Курсы BTC_USD, ETH_USD, SOL_USD из /v2/exchange-rates?currency=USD."""
        data = self.get_json(
            self.config.COINBASE_URL, {"currency": self.config.BASE_CURRENCY}
        )
        quotes = data.get("data", {}).get("rates", {})
        rates = {}
        for code in self.config.CRYPTO_CURRENCIES:
            # API отдает "1 USD = X BTC" строкой; в кеше храним "1 BTC = Y USD"
            try:
                base_to_code = float(quotes[code])
            except (KeyError, TypeError, ValueError):
                continue
            if is_valid_rate(base_to_code):
                rates[self.pair(code)] = 1 / base_to_code
        if not rates:
            raise ApiRequestError("в ответе нет курсов")
        return rates
