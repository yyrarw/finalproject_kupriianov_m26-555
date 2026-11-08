"""Доменные модели: пользователь, кошелек и портфель."""

import hashlib
import hmac
import math
import secrets
from datetime import datetime

MIN_PASSWORD_LENGTH = 4
SALT_BYTES = 8
DEFAULT_BASE_CURRENCY = "USD"


class User:
    """Пользователь системы с хешированным паролем и солью."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создает нового пользователя: генерирует соль и хеширует пароль."""
        cls.validate_password(password)
        salt = secrets.token_hex(SALT_BYTES)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=cls.hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now().replace(microsecond=0),
        )

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Односторонний хеш: sha256(password + salt)."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @staticmethod
    def validate_password(password: str) -> None:
        """Проверяет, что пароль — строка не короче MIN_PASSWORD_LENGTH символов."""
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> str:
        """Возвращает информацию о пользователе без пароля и соли."""
        registered = self._registration_date.isoformat(sep=" ")
        return (
            f"Пользователь '{self._username}' (id={self._user_id}), "
            f"зарегистрирован: {registered}"
        )

    def change_password(self, new_password: str) -> None:
        """Меняет пароль: новая соль и новый хеш."""
        self.validate_password(new_password)
        self._salt = secrets.token_hex(SALT_BYTES)
        self._hashed_password = self.hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет пароль, сравнивая хеши за постоянное время."""
        candidate = self.hash_password(password, self._salt)
        return hmac.compare_digest(candidate, self._hashed_password)

    def to_dict(self) -> dict:
        """Сериализует пользователя для users.json (дата в ISO-формате)."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Восстанавливает пользователя из записи users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


def validate_amount(amount: float) -> float:
    """Проверяет, что сумма — конечное положительное число."""
    is_number = isinstance(amount, (int, float)) and not isinstance(amount, bool)
    if not is_number or not math.isfinite(amount) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


class Wallet:
    """Кошелек пользователя в одной валюте."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Баланс должен быть числом")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс на положительную сумму."""
        self.balance = self._balance + validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Списывает сумму, если на балансе достаточно средств."""
        amount = validate_amount(amount)
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} {self.currency_code}"
            )
        self.balance = self._balance - amount

    def get_balance_info(self) -> str:
        """Возвращает строку с текущим балансом."""
        return f"{self.currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict:
        """Сериализует кошелек для portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Все кошельки одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ):
        self._user_id = user_id
        self._wallets = dict(wallets or {})
        self._user = user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def user(self) -> User | None:
        """Владелец портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков: изменить портфель через нее нельзя."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Создает кошелек для новой валюты; код должен быть уникальным."""
        if currency_code in self._wallets:
            raise ValueError(f"Кошелек '{currency_code}' уже есть в портфеле")
        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелек по коду валюты или None."""
        return self._wallets.get(currency_code)

    def get_total_value(
        self,
        base_currency: str = DEFAULT_BASE_CURRENCY,
        exchange_rates: dict[str, float] | None = None,
    ) -> float:
        """Суммарная стоимость кошельков в base_currency.

        exchange_rates — курсы вида {"BTC_USD": 59337.21}: сколько единиц
        второй валюты стоит одна единица первой.
        """
        rates = exchange_rates or {}
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
                continue
            pair = f"{code}_{base_currency}"
            if pair not in rates:
                raise ValueError(f"Нет курса для пары {pair}")
            total += wallet.balance * rates[pair]
        return total

    def to_dict(self) -> dict:
        """Сериализует портфель для portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Восстанавливает портфель из записи portfolios.json."""
        wallets = {
            code: Wallet(code, wallet_data["balance"])
            for code, wallet_data in data.get("wallets", {}).items()
        }
        return cls(data["user_id"], wallets, user)
