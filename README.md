# ValutaTrade Hub

Консольная платформа для симуляции торговли фиатными и криптовалютами.
Пользователь регистрируется, пополняет виртуальный USD-кошелек, покупает и
продает валюты по актуальным курсам и следит за стоимостью портфеля.

Система состоит из двух сервисов:

- **Core Service** — CLI, пользователи, портфели, сделки, работа с кешем курсов;
- **Parser Service** — получает курсы из CoinGecko (криптовалюты),
  ExchangeRate-API (фиат) и Coinbase (резервный источник криптовалют),
  сохраняет снимок `data/rates.json` и историю `data/exchange_rates.json`.

Проект написан в объектно-ориентированном стиле: модели `User`, `Wallet`,
`Portfolio`, иерархия валют `Currency` → `FiatCurrency` / `CryptoCurrency`,
синглтоны `SettingsLoader` и `DatabaseManager`, клиенты API с общим базовым
классом `BaseApiClient`.

## Демонстрация

Полный сценарий: обновление курсов из трех источников (сбой CoinGecko
обрабатывается, курсы приходят из ExchangeRate-API и Coinbase), просмотр кеша,
регистрация, вход, пополнение, покупка и продажа BTC, обработка ошибок
(неизвестная валюта, недостаточно средств), портфель и курс валюты.

[![asciicast](https://asciinema.org/a/V2H4qz7nHmkl6ISK.svg)](https://asciinema.org/a/V2H4qz7nHmkl6ISK)

## Структура проекта

```
finalproject_kupriianov_m26-555/
├── data/
│   ├── users.json              # пользователи
│   ├── portfolios.json         # портфели и кошельки
│   ├── rates.json              # кеш последних курсов (Core Service)
│   └── exchange_rates.json     # история замеров (Parser Service)
├── valutatrade_hub/
│   ├── logging_config.py       # формат логов и ротация файлов
│   ├── decorators.py           # @log_action
│   ├── core/
│   │   ├── currencies.py       # Currency, FiatCurrency, CryptoCurrency, get_currency
│   │   ├── exceptions.py       # InsufficientFunds, CurrencyNotFound, ApiRequest
│   │   ├── models.py           # User, Wallet, Portfolio
│   │   ├── usecases.py         # бизнес-логика
│   │   └── utils.py            # валидация, конвертация, форматирование
│   ├── infra/
│   │   ├── settings.py         # Singleton SettingsLoader
│   │   └── database.py         # Singleton DatabaseManager (JSON-хранилище)
│   ├── parser_service/
│   │   ├── config.py           # ParserConfig: API, валюты, пути, таймауты
│   │   ├── api_clients.py      # BaseApiClient и клиенты CoinGecko, ExchangeRate-API, Coinbase
│   │   ├── updater.py          # RatesUpdater
│   │   ├── storage.py          # запись rates.json и exchange_rates.json
│   │   └── scheduler.py        # периодическое обновление
│   └── cli/
│       └── interface.py        # команды
├── main.py
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Установка

Нужен [uv](https://docs.astral.sh/uv/) 0.5+ (Python 3.12 uv скачает сам).

```bash
make install        # или: uv sync
```

Сборка и установка как отдельной команды:

```bash
make build          # uv build
make check-dist     # uvx twine check dist/*
make package-install  # uv tool install --force dist/*.whl
```

## Настройка API-ключа

Курсы фиатных валют берутся из ExchangeRate-API, для него нужен бесплатный
ключ: зарегистрируйтесь на https://www.exchangerate-api.com/ и подтвердите email.
Ключ **не хранится в коде**. Передайте его одним из способов:

```bash
export EXCHANGERATE_API_KEY=ваш_ключ        # переменная окружения
echo "EXCHANGERATE_API_KEY=ваш_ключ" > .env  # или файл .env в корне проекта
```

Файл `.env` добавлен в `.gitignore`. CoinGecko и Coinbase используются без ключа.

## Запуск

```bash
make project        # или: uv run valutatrade-hub, или: python main.py
```

Откроется интерактивная консоль с приглашением `>`. `help` — список команд,
`exit` или Ctrl+D — выход.

## Команды CLI

| Команда | Описание |
|---|---|
| `register --username <имя> --password <пароль>` | регистрация (пароль от 4 символов) |
| `login --username <имя> --password <пароль>` | вход |
| `logout` | выход из аккаунта |
| `show-portfolio [--base <код>]` | кошельки и стоимость в базовой валюте |
| `deposit --currency <код> --amount <сумма>` | пополнить кошелек (например, USD) |
| `buy --currency <код> --amount <количество>` | купить валюту за USD |
| `sell --currency <код> --amount <количество>` | продать валюту за USD |
| `get-rate --from <код> --to <код>` | курс одной валюты к другой |
| `update-rates [--source coingecko\|exchangerate\|coinbase]` | обновить курсы из API |
| `show-rates [--currency <код>] [--top <N>] [--base <код>]` | курсы из кеша |

Поддерживаемые валюты: USD, EUR, GBP, RUB (фиат), BTC, ETH, SOL (крипто).
При покупке стоимость списывается с USD-кошелька, при продаже выручка
зачисляется на него, поэтому сначала пополните USD через `deposit`.

### Пример сеанса

```
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****
> login --username alice --password 1234
Вы вошли как 'alice'
> deposit --currency USD --amount 5000
Кошелек USD пополнен
Изменения в портфеле:
- USD: было 0.00 → стало 5000.00
> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 59337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
- USD: было 5000.00 → стало 2033.14
Оценочная стоимость покупки: 2,966.86 USD
> sell --currency BTC --amount 0.01
Продажа выполнена: 0.0100 BTC по курсу 59337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0500 → стало 0.0400
- USD: было 2033.14 → стало 2626.51
Оценочная выручка: 593.37 USD
> show-portfolio
Портфель пользователя 'alice' (база: USD):
- USD: 2626.51  → 2626.51 USD
- BTC: 0.0400  → 2373.49 USD
---------------------------------
ИТОГО: 5,000.00 USD
> get-rate --from USD --to BTC
Курс USD→BTC: 0.00001685 (обновлено: 2026-11-08 18:27:35)
Обратный курс BTC→USD: 59337.21
> show-rates --top 2
Rates from cache (updated at 2026-11-08T18:27:35Z):
+---------+----------+---------------------+-----------+
|   Pair  |     Rate |      Updated at     |   Source  |
+---------+----------+---------------------+-----------+
| BTC_USD | 59337.21 | 2026-11-08 18:27:35 | CoinGecko |
| ETH_USD |  3720.00 | 2026-11-08 18:27:35 | CoinGecko |
+---------+----------+---------------------+-----------+
```

### Сообщения об ошибках

| Ситуация | Сообщение |
|---|---|
| команда без входа | `Сначала выполните login` |
| имя занято / короткий пароль | `Имя пользователя 'alice' уже занято` / `Пароль должен быть не короче 4 символов` |
| неверный вход | `Пользователь 'alice' не найден` / `Неверный пароль` |
| некорректная сумма | `'amount' должен быть положительным числом` |
| нехватка средств | `Недостаточно средств: доступно 0.0400 BTC, требуется 0.0500 BTC` |
| нет кошелька при продаже | `У вас нет кошелька 'BTC'. Добавьте валюту: она создаётся автоматически при первой покупке.` |
| неизвестная валюта | `Неизвестная валюта 'XYZ'` + список поддерживаемых кодов |
| неизвестная база | `Неизвестная базовая валюта 'ABC'` |
| сбой API | `Ошибка при обращении к внешнему API: ...` + совет повторить позже |
| пустой кеш | `Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.` |

## Кеш курсов и TTL

Core Service читает курсы только из `data/rates.json`:

```json
{
  "pairs": {
    "EUR_USD": {"rate": 1.0787, "updated_at": "2025-10-10T12:00:00Z", "source": "ExchangeRate-API"},
    "BTC_USD": {"rate": 59337.21, "updated_at": "2025-10-10T12:00:00Z", "source": "CoinGecko"}
  },
  "last_refresh": "2025-10-10T12:00:01Z"
}
```

Все курсы хранятся к USD, кросс-курсы (например, EUR→RUB) считаются через USD.
Срок годности курса — `rates_ttl_seconds` (по умолчанию 300 секунд). Если курс
старше TTL или отсутствует, `get-rate`, `buy`, `sell` и `show-portfolio` сами
запускают обновление через Parser Service. Если обновить не удалось, команда
сообщает, что курс устарел или недоступен, и предлагает выполнить `update-rates`.

`updated_at` — момент получения курса нашим сервисом (время публикации у
ExchangeRate-API сохраняется в `meta.provider_time` истории).

## Parser Service

- `update-rates` в CLI — немедленное обновление из всех источников или одного
  (`--source coingecko` / `--source exchangerate` / `--source coinbase`);
- `valutatrade-parser --interval 300 [--iterations N]` — периодическое
  обновление (планировщик, остановка Ctrl+C).

Источники:

| Источник | Валюты | Ключ | Роль |
|---|---|---|---|
| CoinGecko | BTC, ETH, SOL | не нужен | основной для криптовалют |
| ExchangeRate-API | EUR, GBP, RUB | `EXCHANGERATE_API_KEY` | фиат |
| Coinbase | BTC, ETH, SOL | не нужен | резервный для криптовалют |

Как это работает:

1. `RatesUpdater` опрашивает клиентов по порядку. Сбой одного источника
   логируется и не мешает остальным; если не ответил ни один — `ApiRequestError`.
   Если пару вернули несколько источников, в кеш идет первый (CoinGecko
   приоритетнее Coinbase), а в историю пишутся замеры всех источников.
2. Курсы приводятся к формату `{"BTC_USD": 59337.21}`. ExchangeRate-API и
   Coinbase отдают «1 USD = X валюты», поэтому курс к USD считается как 1 / X.
3. `data/rates.json` обновляется: пара заменяется, только если новые данные
   свежее. Запись атомарная: временный файл → `os.replace`.
4. В `data/exchange_rates.json` добавляются записи истории с id вида
   `BTC_USD_2025-10-10T12:00:00Z` (дубликаты пропускаются) и метаданными
   запроса: `raw_id`, `request_ms`, `status_code`, `etag`.

Клиенты различают ошибки: таймаут, сетевой сбой, 401/403 (ключ), 429 (лимит),
5xx (сервер), перенаправление (сайт заблокирован сетью) и ответ не в JSON.

Параметры (URL, списки валют, `CRYPTO_ID_MAP`, таймаут, пути) — в
`valutatrade_hub/parser_service/config.py`.

## Конфигурация

`SettingsLoader` читает секцию `[tool.valutatrade]` в `pyproject.toml`
(если файла нет, используются значения по умолчанию):

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `data_dir` | `data` | каталог JSON-файлов |
| `rates_ttl_seconds` | `300` | срок годности курсов |
| `default_base_currency` | `USD` | базовая валюта |
| `log_dir` | `logs` | каталог логов |
| `log_level` | `INFO` | уровень логов (`DEBUG` для отладки) |
| `log_max_bytes`, `log_backup_count` | `1000000`, `3` | ротация логов |

## Логирование

- `logs/actions.log` — операции REGISTER, LOGIN, DEPOSIT, BUY, SELL
  (декоратор `@log_action`, при ошибке — `result=ERROR` с типом и текстом,
  исключение пробрасывается дальше; пароли не логируются):
  ```
  INFO 2026-11-08T21:24:14 BUY user='alice' currency='BTC' amount=0.0500 rate=59300.00 base='USD' changes='BTC:0.0000->0.0500; USD:5000.0000->2035.0000' result=OK
  ```
- `logs/parser.log` — шаги Parser Service; те же сообщения выводятся в консоль
  при `update-rates`.

Ротация по размеру (`RotatingFileHandler`), формат строковый.

## Проверка качества

```bash
make lint           # uv run ruff check .
```

## Ограничения сети

Если CoinGecko недоступен (например, заблокирован корпоративным прокси),
`update-rates` сообщит о сбое, а курсы криптовалют будут получены из Coinbase.
Если недоступны оба источника, операции с криптовалютами вернут понятную
ошибку «курс недоступен».
