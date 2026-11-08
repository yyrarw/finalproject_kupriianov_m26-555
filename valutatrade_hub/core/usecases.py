"""Бизнес-логика: регистрация, вход, портфель, сделки и курсы валют."""

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import convert, format_timestamp, is_fresh
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

RATE_PAIR_SEPARATOR = "_"


def base_currency() -> str:
    """Базовая валюта расчетов из настроек (по умолчанию USD)."""
    return SettingsLoader().get("default_base_currency")


# --- Пользователи -----------------------------------------------------------


def load_users() -> list[User]:
    """Загружает всех пользователей из users.json."""
    return [User.from_dict(item) for item in DatabaseManager().read("users")]


def find_user(users: list[User], username: str) -> User | None:
    """Ищет пользователя по имени."""
    return next((user for user in users if user.username == username), None)


@log_action("REGISTER")
def register_user(username: str, password: str) -> User:
    """Регистрирует пользователя и создает ему пустой портфель."""
    users = load_users()
    username = username.strip()
    if find_user(users, username) is not None:
        raise ValueError(f"Имя пользователя '{username}' уже занято")
    user_id = max((user.user_id for user in users), default=0) + 1
    user = User.create(user_id, username, password)
    DatabaseManager().update("users", lambda items: items.append(user.to_dict()))
    save_portfolio(Portfolio(user.user_id, user=user))
    return user


@log_action("LOGIN")
def login_user(username: str, password: str) -> User:
    """Проверяет имя и пароль и возвращает пользователя."""
    user = find_user(load_users(), username)
    if user is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


# --- Портфели ---------------------------------------------------------------


def load_portfolio(user: User) -> Portfolio:
    """Загружает портфель пользователя (пустой, если записи нет)."""
    for item in DatabaseManager().read("portfolios"):
        if item["user_id"] == user.user_id:
            return Portfolio.from_dict(item, user)
    return Portfolio(user.user_id, user=user)


def save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель: чтение → замена записи пользователя → запись."""

    def replace(items: list) -> None:
        items[:] = [item for item in items if item["user_id"] != portfolio.user_id]
        items.append(portfolio.to_dict())

    DatabaseManager().update("portfolios", replace)


def get_or_create_wallet(portfolio: Portfolio, currency_code: str) -> Wallet:
    """Возвращает кошелек валюты, создавая его при отсутствии."""
    return portfolio.get_wallet(currency_code) or portfolio.add_currency(
        currency_code
    )


# --- Курсы ------------------------------------------------------------------


def refresh_rates() -> None:
    """Обновляет кеш курсов. Пока Parser Service не подключен — недоступно."""
    raise ApiRequestError("Parser Service не подключен")


def pair_key(from_code: str, to_code: str) -> str:
    """Ключ пары в rates.json: BTC_USD."""
    return f"{from_code}{RATE_PAIR_SEPARATOR}{to_code}"


def cached_rate(from_code: str, to_code: str) -> tuple[float, str | None] | None:
    """Курс from→to из кеша (через базовую валюту) или None, если пары нет."""
    pairs = DatabaseManager().read("rates").get("pairs", {})
    base = base_currency()
    legs = []
    for code in (from_code, to_code):
        if code == base:
            legs.append((1.0, None))
        elif pair_key(code, base) in pairs:
            entry = pairs[pair_key(code, base)]
            legs.append((entry["rate"], entry["updated_at"]))
        else:
            return None
    (from_rate, from_time), (to_rate, to_time) = legs
    times = [time for time in (from_time, to_time) if time]
    return from_rate / to_rate, min(times) if times else None


def get_rate(from_code: str, to_code: str) -> tuple[float, str | None]:
    """Курс from→to и время обновления с учетом TTL кеша.

    Свежий курс берется из rates.json. Если курса нет или он старше TTL,
    выполняется попытка обновления; при неудаче — ApiRequestError.
    """
    from_code = get_currency(from_code).code
    to_code = get_currency(to_code).code
    ttl = SettingsLoader().get("rates_ttl_seconds")

    cached = cached_rate(from_code, to_code)
    if cached is not None and is_fresh(cached[1], ttl):
        return cached
    try:
        refresh_rates()
    except ApiRequestError as error:
        reason = error.reason
    else:
        cached = cached_rate(from_code, to_code)
        if cached is not None and is_fresh(cached[1], ttl):
            return cached
        reason = "источник не вернул актуальный курс"

    pair = f"{from_code}→{to_code}"
    if cached is None:
        raise ApiRequestError(f"курс {pair} недоступен ({reason})")
    raise ApiRequestError(
        f"курс {pair} устарел (обновлено: {format_timestamp(cached[1])}) "
        f"и не обновился ({reason}). Выполните update-rates"
    )


# --- Операции с портфелем ---------------------------------------------------


def get_portfolio_summary(user: User, base: str | None = None):
    """Строки портфеля (код, баланс, стоимость в базе) и итоговая стоимость."""
    base = base or base_currency()
    try:
        base = get_currency(base).code
    except CurrencyNotFoundError:
        raise CurrencyNotFoundError(
            base, f"Неизвестная базовая валюта '{base.upper()}'"
        ) from None

    portfolio = load_portfolio(user)
    rates = {
        pair_key(code, base): get_rate(code, base)[0]
        for code in portfolio.wallets
        if code != base
    }
    rows = []
    for code, wallet in portfolio.wallets.items():
        rate = rates.get(pair_key(code, base), 1.0)
        rows.append((code, wallet.balance, convert(wallet.balance, rate)))
    return rows, portfolio.get_total_value(base, rates)


@log_action("DEPOSIT", verbose=True)
def deposit(user: User, currency_code: str, amount: float) -> dict:
    """Пополняет кошелек; возвращает изменение баланса."""
    currency_code = get_currency(currency_code).code
    portfolio = load_portfolio(user)
    wallet = get_or_create_wallet(portfolio, currency_code)
    before = wallet.balance
    wallet.deposit(amount)
    save_portfolio(portfolio)
    return {"changes": [(currency_code, before, wallet.balance)]}


def trade_currency(currency_code: str) -> str:
    """Проверяет валюту сделки: известна и не совпадает с базовой."""
    currency_code = get_currency(currency_code).code
    if currency_code == base_currency():
        raise ValueError(f"Операции с {currency_code} выполняются через deposit")
    return currency_code


def trade_rate(currency_code: str) -> float:
    """Курс валюты к базовой для сделки."""
    try:
        rate, _ = get_rate(currency_code, base_currency())
    except ApiRequestError as error:
        raise ApiRequestError(
            f"Не удалось получить курс для {currency_code}→{base_currency()}: "
            f"{error.reason}"
        ) from None
    return rate


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> dict:
    """Покупает валюту за базовую: списывает USD, пополняет кошелек валюты."""
    currency_code = trade_currency(currency_code)
    rate = trade_rate(currency_code)
    cost = convert(amount, rate)

    portfolio = load_portfolio(user)
    base_wallet = get_or_create_wallet(portfolio, base_currency())
    target = get_or_create_wallet(portfolio, currency_code)
    base_before, target_before = base_wallet.balance, target.balance
    base_wallet.withdraw(cost)
    target.deposit(amount)
    save_portfolio(portfolio)
    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "base": base_currency(),
        "value": cost,
        "changes": [
            (currency_code, target_before, target.balance),
            (base_currency(), base_before, base_wallet.balance),
        ],
    }


@log_action("SELL", verbose=True)
def sell(user: User, currency_code: str, amount: float) -> dict:
    """Продает валюту за базовую: списывает валюту, начисляет USD."""
    currency_code = trade_currency(currency_code)
    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency_code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency_code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    wallet.withdraw(amount)
    rate = trade_rate(currency_code)
    revenue = convert(amount, rate)

    base_wallet = get_or_create_wallet(portfolio, base_currency())
    before = wallet.balance + amount
    base_before = base_wallet.balance
    base_wallet.deposit(revenue)
    save_portfolio(portfolio)
    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "base": base_currency(),
        "value": revenue,
        "changes": [
            (currency_code, before, wallet.balance),
            (base_currency(), base_before, base_wallet.balance),
        ],
    }
