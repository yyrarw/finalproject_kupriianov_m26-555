"""Командный интерфейс ValutaTrade Hub: разбор команд и вывод результатов."""

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.models import DEFAULT_BASE_CURRENCY
from valutatrade_hub.core.utils import (
    format_amount,
    format_rate,
    format_timestamp,
    parse_amount,
)

PROMPT = "> "
OPTION_PREFIX = "--"
SEPARATOR_LINE = "-" * 33
HELP_TEXT = """Доступные команды:
  register --username <имя> --password <пароль>   регистрация
  login --username <имя> --password <пароль>      вход
  logout                                          выход из аккаунта
  show-portfolio [--base <валюта>]                портфель и его стоимость
  deposit --currency <код> --amount <сумма>       пополнить кошелек
  buy --currency <код> --amount <количество>      купить валюту за USD
  sell --currency <код> --amount <количество>     продать валюту за USD
  get-rate --from <код> --to <код>                курс валюты
  help                                            справка
  exit                                            выход из программы"""


class CommandError(Exception):
    """Ошибка в синтаксисе команды или ее аргументах."""


def parse_command(line: str) -> tuple[str, dict[str, str]]:
    """Разбирает строку "cmd --key value ..." на команду и словарь опций."""
    try:
        tokens = shlex.split(line)
    except ValueError as error:
        raise CommandError(f"Не удалось разобрать команду: {error}") from None
    command, rest = tokens[0], tokens[1:]
    if len(rest) % 2:
        raise CommandError("Каждая опция должна иметь значение: --имя значение")
    options = {}
    for name, value in zip(rest[::2], rest[1::2]):
        if not name.startswith(OPTION_PREFIX) or len(name) == len(OPTION_PREFIX):
            raise CommandError(f"Ожидалась опция вида --имя, получено '{name}'")
        options[name[len(OPTION_PREFIX) :]] = value
    return command, options


def take_options(options: dict, required=(), optional=()) -> dict:
    """Проверяет, что переданы все обязательные и нет лишних опций."""
    unknown = set(options) - set(required) - set(optional)
    if unknown:
        raise CommandError(f"Неизвестная опция --{sorted(unknown)[0]}")
    missing = [name for name in required if name not in options]
    if missing:
        raise CommandError(f"Не указана обязательная опция --{missing[0]}")
    return options


def print_changes(changes) -> None:
    """Печатает изменения балансов "было → стало"."""
    print("Изменения в портфеле:")
    for code, before, after in changes:
        print(
            f"- {code}: было {format_amount(code, before)} "
            f"→ стало {format_amount(code, after)}"
        )


class CommandLineInterface:
    """Интерактивная консоль: хранит сессию и вызывает usecases."""

    def __init__(self):
        self.current_user = None
        self.handlers = {
            "register": self.handle_register,
            "login": self.handle_login,
            "logout": self.handle_logout,
            "show-portfolio": self.handle_show_portfolio,
            "deposit": self.handle_deposit,
            "buy": self.handle_buy,
            "sell": self.handle_sell,
            "get-rate": self.handle_get_rate,
            "help": self.handle_help,
        }

    def require_login(self):
        """Возвращает текущего пользователя или сообщает о необходимости входа."""
        if self.current_user is None:
            raise CommandError("Сначала выполните login")
        return self.current_user

    def handle_register(self, options: dict) -> None:
        """register --username <имя> --password <пароль>"""
        take_options(options, required=("username", "password"))
        user = usecases.register_user(options["username"], options["password"])
        print(
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {user.username} --password ****"
        )

    def handle_login(self, options: dict) -> None:
        """login --username <имя> --password <пароль>"""
        take_options(options, required=("username", "password"))
        self.current_user = usecases.login_user(
            options["username"], options["password"]
        )
        print(f"Вы вошли как '{self.current_user.username}'")

    def handle_logout(self, options: dict) -> None:
        """logout"""
        take_options(options)
        user = self.require_login()
        self.current_user = None
        print(f"Пользователь '{user.username}' вышел из системы")

    def handle_show_portfolio(self, options: dict) -> None:
        """show-portfolio [--base <валюта>]"""
        take_options(options, optional=("base",))
        user = self.require_login()
        base = options.get("base", DEFAULT_BASE_CURRENCY).upper()
        rows, total = usecases.get_portfolio_summary(user, base)
        if not rows:
            print(f"Портфель пользователя '{user.username}' пуст")
            return
        print(f"Портфель пользователя '{user.username}' (база: {base}):")
        for code, balance, value in rows:
            print(f"- {code}: {format_amount(code, balance)}  → {value:.2f} {base}")
        print(SEPARATOR_LINE)
        print(f"ИТОГО: {total:,.2f} {base}")

    def handle_deposit(self, options: dict) -> None:
        """deposit --currency <код> --amount <сумма>"""
        take_options(options, required=("currency", "amount"))
        user = self.require_login()
        code = options["currency"].upper()
        before, after = usecases.deposit(
            user, code, parse_amount(options["amount"])
        )
        print(f"Кошелек {code} пополнен")
        print_changes([(code, before, after)])

    def handle_buy(self, options: dict) -> None:
        """buy --currency <код> --amount <количество>"""
        take_options(options, required=("currency", "amount"))
        user = self.require_login()
        result = usecases.buy(
            user, options["currency"], parse_amount(options["amount"])
        )
        code = result["currency"]
        print(
            f"Покупка выполнена: {format_amount(code, result['amount'])} {code} "
            f"по курсу {result['rate']:.2f} {DEFAULT_BASE_CURRENCY}/{code}"
        )
        print_changes(result["changes"])
        print(f"Оценочная стоимость покупки: {result['value']:,.2f} USD")

    def handle_sell(self, options: dict) -> None:
        """sell --currency <код> --amount <количество>"""
        take_options(options, required=("currency", "amount"))
        user = self.require_login()
        result = usecases.sell(
            user, options["currency"], parse_amount(options["amount"])
        )
        code = result["currency"]
        print(
            f"Продажа выполнена: {format_amount(code, result['amount'])} {code} "
            f"по курсу {result['rate']:.2f} {DEFAULT_BASE_CURRENCY}/{code}"
        )
        print_changes(result["changes"])
        print(f"Оценочная выручка: {result['value']:,.2f} USD")

    def handle_get_rate(self, options: dict) -> None:
        """get-rate --from <код> --to <код>"""
        take_options(options, required=("from", "to"))
        from_code, to_code = options["from"].upper(), options["to"].upper()
        rate, updated_at = usecases.get_rate(from_code, to_code)
        updated = format_timestamp(updated_at) if updated_at else "—"
        print(f"Курс {from_code}→{to_code}: {format_rate(rate)} (обновлено: {updated})")
        print(f"Обратный курс {to_code}→{from_code}: {format_rate(1 / rate)}")

    def handle_help(self, options: dict) -> None:
        """help"""
        take_options(options)
        print(HELP_TEXT)

    def execute(self, line: str) -> bool:
        """Выполняет одну команду; возвращает False, если нужно выйти."""
        command, options = parse_command(line)
        if command == "exit":
            return False
        handler = self.handlers.get(command)
        if handler is None:
            raise CommandError(
                f"Неизвестная команда '{command}'. Введите help для справки"
            )
        handler(options)
        return True

    def run(self) -> None:
        """Основной цикл: читает команды до exit или Ctrl+D."""
        print("ValutaTrade Hub. Введите help для списка команд.")
        while True:
            try:
                line = input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            try:
                if not self.execute(line):
                    break
            except (CommandError, ValueError, TypeError) as error:
                print(error)


def main():
    """Точка входа CLI."""
    CommandLineInterface().run()
