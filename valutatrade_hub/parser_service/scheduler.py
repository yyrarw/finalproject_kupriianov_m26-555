"""Периодический запуск обновления курсов."""

import argparse
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater


class RatesScheduler:
    """Запускает RatesUpdater.run_update() каждые interval_seconds секунд."""

    def __init__(self, updater: RatesUpdater, interval_seconds: int):
        if interval_seconds <= 0:
            raise ValueError("Интервал обновления должен быть положительным")
        self.updater = updater
        self.interval_seconds = interval_seconds

    def run(self, iterations: int | None = None) -> None:
        """Обновляет курсы iterations раз (или бесконечно) до Ctrl+C."""
        completed = 0
        try:
            while iterations is None or completed < iterations:
                try:
                    self.updater.run_update()
                except ApiRequestError as error:
                    self.updater.logger.error(f"Update failed: {error.reason}")
                completed += 1
                if iterations is None or completed < iterations:
                    time.sleep(self.interval_seconds)
        except KeyboardInterrupt:
            self.updater.logger.info("Scheduler stopped")


def main() -> None:
    """Точка входа: valutatrade-parser [--interval N] [--iterations N]."""
    parser = argparse.ArgumentParser(description="Периодическое обновление курсов")
    parser.add_argument(
        "--interval",
        type=int,
        default=ParserConfig().UPDATE_INTERVAL_SECONDS,
        help="интервал между обновлениями, секунды",
    )
    parser.add_argument(
        "--iterations", type=int, default=None, help="сколько раз обновить"
    )
    args = parser.parse_args()
    RatesScheduler(RatesUpdater(), args.interval).run(args.iterations)


if __name__ == "__main__":
    main()
