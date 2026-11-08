"""Координация обновления курсов: опрос клиентов, объединение, сохранение."""

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import to_iso, utc_now
from valutatrade_hub.logging_config import get_parser_logger
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinbaseClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage, make_record_id

# Порядок важен: если пару вернули несколько источников, берется первый
# (CoinGecko — основной для криптовалют, Coinbase — резервный)
CLIENTS_BY_SOURCE = {
    "coingecko": CoinGeckoClient,
    "exchangerate": ExchangeRateApiClient,
    "coinbase": CoinbaseClient,
}


def build_clients(
    source: str | None = None, config: ParserConfig | None = None
) -> list[BaseApiClient]:
    """Клиенты всех источников или одного (coingecko / exchangerate)."""
    config = config or ParserConfig()
    if source is None:
        return [client_class(config) for client_class in CLIENTS_BY_SOURCE.values()]
    source = source.lower()
    if source not in CLIENTS_BY_SOURCE:
        raise ValueError(
            f"Неизвестный источник '{source}'. "
            f"Доступны: {', '.join(CLIENTS_BY_SOURCE)}"
        )
    return [CLIENTS_BY_SOURCE[source](config)]


class RatesUpdater:
    """Опрашивает API-клиентов и сохраняет курсы в rates.json и историю."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
    ):
        self.clients = clients if clients is not None else build_clients()
        self.storage = storage or RatesStorage()
        self.logger = get_parser_logger()

    def run_update(self) -> dict:
        """Обновляет курсы; сбой одного клиента не останавливает остальных.

        Возвращает сводку: число обновленных курсов, ошибки, last_refresh.
        Если ни один источник не ответил, бросает ApiRequestError.
        """
        self.logger.info("Starting rates update...")
        pairs, history, errors = {}, [], []
        for client in self.clients:
            self.logger.info(f"Fetching from {client.SOURCE}...")
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                self.logger.error(
                    f"Failed to fetch from {client.SOURCE}: {error.reason}"
                )
                errors.append(f"{client.SOURCE}: {error.reason}")
                continue
            fetched_at = to_iso(utc_now())
            self.logger.info(f"{client.SOURCE}: OK ({len(rates)} rates)")
            for key, rate in rates.items():
                pairs.setdefault(
                    key,
                    {"rate": rate, "updated_at": fetched_at, "source": client.SOURCE},
                )
                history.append(self._history_record(client, key, rate, fetched_at))

        if not pairs:
            raise ApiRequestError("; ".join(errors) or "нет настроенных источников")

        last_refresh = to_iso(utc_now())
        self.logger.info(f"Writing {len(pairs)} rates to {self.storage.rates_path}...")
        self.storage.save_snapshot(pairs, last_refresh)
        added = self.storage.append_history(history)
        self.logger.info(f"History: {added} new records")
        return {"updated": len(pairs), "errors": errors, "last_refresh": last_refresh}

    @staticmethod
    def _history_record(client, key: str, rate: float, timestamp: str) -> dict:
        """Запись для exchange_rates.json с метаданными запроса."""
        from_code, to_code = key.split("_", 1)
        meta = dict(client.last_meta)
        if key in client.raw_ids:
            meta["raw_id"] = client.raw_ids[key]
        return {
            "id": make_record_id(from_code, to_code, timestamp),
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "timestamp": timestamp,
            "source": client.SOURCE,
            "meta": meta,
        }
