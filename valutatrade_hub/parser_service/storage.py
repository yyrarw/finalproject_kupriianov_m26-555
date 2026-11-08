"""Хранилище Parser Service: история exchange_rates.json и снимок rates.json."""

import json

from valutatrade_hub.core.utils import parse_iso
from valutatrade_hub.infra.database import write_json_atomic
from valutatrade_hub.parser_service.config import ParserConfig

FILE_ENCODING = "utf-8"


def read_json(path: str, default):
    """Читает JSON-файл; если файла нет, возвращает default."""
    try:
        with open(path, encoding=FILE_ENCODING) as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def make_record_id(from_code: str, to_code: str, timestamp: str) -> str:
    """Уникальный id замера: BTC_USD_2025-10-10T12:00:00Z."""
    return f"{from_code}_{to_code}_{timestamp}"


class RatesStorage:
    """Чтение и атомарная запись файлов с курсами."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    @property
    def rates_path(self) -> str:
        return self.config.RATES_FILE_PATH

    def load_snapshot(self) -> dict:
        """Текущий снимок курсов: {"pairs": {...}, "last_refresh": ...}."""
        snapshot = read_json(self.rates_path, {})
        snapshot.setdefault("pairs", {})
        snapshot.setdefault("last_refresh", None)
        return snapshot

    def save_snapshot(self, pairs: dict, last_refresh: str) -> int:
        """Обновляет пары, если новые данные свежее; возвращает число обновлений."""
        snapshot = self.load_snapshot()
        updated = 0
        for key, entry in pairs.items():
            current = snapshot["pairs"].get(key)
            is_newer = current is None or parse_iso(entry["updated_at"]) >= parse_iso(
                current["updated_at"]
            )
            if is_newer:
                snapshot["pairs"][key] = entry
                updated += 1
        snapshot["last_refresh"] = last_refresh
        write_json_atomic(self.rates_path, snapshot)
        return updated

    def append_history(self, records: list[dict]) -> int:
        """Добавляет замеры в историю, пропуская уже записанные id."""
        history = read_json(self.config.HISTORY_FILE_PATH, [])
        known_ids = {record["id"] for record in history}
        new_records = [record for record in records if record["id"] not in known_ids]
        if new_records:
            write_json_atomic(self.config.HISTORY_FILE_PATH, history + new_records)
        return len(new_records)
