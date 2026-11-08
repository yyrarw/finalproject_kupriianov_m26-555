"""Бизнес-логика: регистрация, вход, портфель, покупка, продажа, курсы."""

from valutatrade_hub.core.models import DEFAULT_BASE_CURRENCY, Portfolio, User
from valutatrade_hub.core.utils import (
    PORTFOLIOS_FILE,
    RATES_FILE,
    USERS_FILE,
    normalize_currency_code,
    read_json,
    write_json,
)

# --- Пользователи -----------------------------------------------------------


def load_users() -> list[User]:
    """Загружает всех пользователей из users.json."""
    return [User.from_dict(item) for item in read_json(USERS_FILE, [])]


def save_users(users: list[User]) -> None:
    """Сохраняет пользователей в users.json."""
    write_json(USERS_FILE, [user.to_dict() for user in users])


def find_user(users: list[User], username: str) -> User | None:
    """Ищет пользователя по имени."""
    return next((user for user in users if user.username == username), None)


def register_user(username: str, password: str) -> User:
    """Регистрирует пользователя и создает ему пустой портфель."""
    users = load_users()
    if find_user(users, username.strip()) is not None:
        raise ValueError(f"Имя пользователя '{username.strip()}' уже занято")
    user_id = max((user.user_id for user in users), default=0) + 1
    user = User.create(user_id, username, password)
    users.append(user)
    save_users(users)
    save_portfolio(Portfolio(user.user_id))
    return user


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
    for item in read_json(PORTFOLIOS_FILE, []):
        if item["user_id"] == user.user_id:
            return Portfolio.from_dict(item, user)
    return Portfolio(user.user_id, user=user)


def save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель, заменяя прежнюю запись пользователя."""
    items = [
        item
        for item in read_json(PORTFOLIOS_FILE, [])
        if item["user_id"] != portfolio.user_id
    ]
    items.append(portfolio.to_dict())
    write_json(PORTFOLIOS_FILE, items)


def get_or_create_wallet(portfolio: Portfolio, currency_code: str):
    """Возвращает кошелек валюты, создавая его при отсутствии."""
    return portfolio.get_wallet(currency_code) or portfolio.add_currency(
        currency_code
    )


# --- Курсы ------------------------------------------------------------------


def load_rate_pairs() -> dict:
    """Возвращает пары из кеша rates.json: {"BTC_USD": {"rate": ...}, ...}."""
    return read_json(RATES_FILE, {}).get("pairs", {})


def rate_to_usd(code: str, pairs: dict) -> tuple[float, str | None]:
    """Курс валюты к USD и время его обновления."""
    if code == DEFAULT_BASE_CURRENCY:
        return 1.0, None
    pair = pairs.get(f"{code}_{DEFAULT_BASE_CURRENCY}")
    if pair is None:
        raise LookupError(code)
    return pair["rate"], pair["updated_at"]


def get_rate(from_code: str, to_code: str) -> tuple[float, str | None]:
    """Курс from→to через USD и время обновления (самое старое из двух)."""
    from_code = normalize_currency_code(from_code)
    to_code = normalize_currency_code(to_code)
    pairs = load_rate_pairs()
    try:
        from_rate, from_time = rate_to_usd(from_code, pairs)
        to_rate, to_time = rate_to_usd(to_code, pairs)
    except LookupError:
        raise ValueError(
            f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        ) from None
    times = [time for time in (from_time, to_time) if time]
    return from_rate / to_rate, min(times) if times else None


def usd_rates_for(codes, base_currency: str) -> dict[str, float]:
    """Курсы вида {"BTC_EUR": ...} для перевода кошельков в base_currency."""
    rates = {}
    for code in codes:
        if code != base_currency:
            rates[f"{code}_{base_currency}"], _ = get_rate(code, base_currency)
    return rates


# --- Операции с портфелем ---------------------------------------------------


def get_portfolio_summary(user: User, base_currency: str = DEFAULT_BASE_CURRENCY):
    """Строки портфеля (код, баланс, стоимость в базе) и итоговая стоимость."""
    base_currency = normalize_currency_code(base_currency)
    pairs = load_rate_pairs()
    try:
        rate_to_usd(base_currency, pairs)
    except LookupError:
        raise ValueError(f"Неизвестная базовая валюта '{base_currency}'") from None

    portfolio = load_portfolio(user)
    wallets = portfolio.wallets
    rates = usd_rates_for(wallets, base_currency)
    rows = []
    for code, wallet in wallets.items():
        rate = 1.0 if code == base_currency else rates[f"{code}_{base_currency}"]
        rows.append((code, wallet.balance, wallet.balance * rate))
    total = portfolio.get_total_value(base_currency, rates)
    return rows, total


def deposit(user: User, currency_code: str, amount: float) -> tuple[float, float]:
    """Пополняет кошелек; возвращает баланс до и после."""
    currency_code = normalize_currency_code(currency_code)
    portfolio = load_portfolio(user)
    wallet = get_or_create_wallet(portfolio, currency_code)
    before = wallet.balance
    wallet.deposit(amount)
    save_portfolio(portfolio)
    return before, wallet.balance


def trade_rate(currency_code: str) -> float:
    """Курс валюты к USD для сделки."""
    try:
        rate, _ = get_rate(currency_code, DEFAULT_BASE_CURRENCY)
    except ValueError:
        raise ValueError(
            f"Не удалось получить курс для {currency_code}→{DEFAULT_BASE_CURRENCY}"
        ) from None
    return rate


def check_trade_currency(currency_code: str) -> str:
    """Проверяет код валюты сделки: торговать USD за USD нельзя."""
    currency_code = normalize_currency_code(currency_code)
    if currency_code == DEFAULT_BASE_CURRENCY:
        raise ValueError(
            f"Операции с {DEFAULT_BASE_CURRENCY} выполняются через deposit"
        )
    return currency_code


def buy(user: User, currency_code: str, amount: float) -> dict:
    """Покупает валюту за USD: списывает USD, пополняет кошелек валюты."""
    currency_code = check_trade_currency(currency_code)
    rate = trade_rate(currency_code)
    cost = amount * rate

    portfolio = load_portfolio(user)
    usd_wallet = get_or_create_wallet(portfolio, DEFAULT_BASE_CURRENCY)
    target = get_or_create_wallet(portfolio, currency_code)
    usd_before, target_before = usd_wallet.balance, target.balance
    usd_wallet.withdraw(cost)
    target.deposit(amount)
    save_portfolio(portfolio)
    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "value": cost,
        "changes": [
            (currency_code, target_before, target.balance),
            (DEFAULT_BASE_CURRENCY, usd_before, usd_wallet.balance),
        ],
    }


def sell(user: User, currency_code: str, amount: float) -> dict:
    """Продает валюту за USD: списывает валюту, начисляет USD."""
    currency_code = check_trade_currency(currency_code)
    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency_code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency_code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    rate = trade_rate(currency_code)
    revenue = amount * rate

    usd_wallet = get_or_create_wallet(portfolio, DEFAULT_BASE_CURRENCY)
    before, usd_before = wallet.balance, usd_wallet.balance
    wallet.withdraw(amount)
    usd_wallet.deposit(revenue)
    save_portfolio(portfolio)
    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "value": revenue,
        "changes": [
            (currency_code, before, wallet.balance),
            (DEFAULT_BASE_CURRENCY, usd_before, usd_wallet.balance),
        ],
    }
