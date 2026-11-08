"""Декоратор @log_action для логирования доменных операций."""

import functools
import inspect

from valutatrade_hub.core.utils import format_rate
from valutatrade_hub.logging_config import get_actions_logger

RESULT_OK = "OK"
RESULT_ERROR = "ERROR"


def _format_value(name: str, value) -> str:
    """Курс как в CLI (2 или 8 знаков), прочие числа с 4 знаками, строки в кавычках."""
    if name == "rate" and isinstance(value, float):
        return format_rate(value)
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, str) and name not in ("result", "error_type"):
        return f"'{value}'"
    return str(value)


def _call_context(func, args, kwargs) -> dict:
    """Поля лога из аргументов вызова: пользователь, валюта, сумма."""
    bound = inspect.signature(func).bind_partial(*args, **kwargs).arguments
    context = {}
    user = bound.get("user")
    username = getattr(user, "username", None) or bound.get("username")
    if username is not None:
        context["user"] = username
    for arg_name, field in (("currency_code", "currency"), ("amount", "amount")):
        if arg_name in bound:
            context[field] = bound[arg_name]
    return context


def log_action(action: str, verbose: bool = False):
    """Логирует операцию на уровне INFO и пробрасывает исключения дальше.

    Записывает действие, пользователя, валюту, сумму, курс и базу (если есть
    в результате) и итог OK/ERROR. При verbose=True добавляет изменения
    балансов "было→стало".
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_actions_logger()
            context = _call_context(func, args, kwargs)
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                context["result"] = RESULT_ERROR
                context["error_type"] = type(error).__name__
                context["error_message"] = str(error)
                logger.info(_format_record(action, context))
                raise
            if isinstance(result, dict):
                for field in ("rate", "base"):
                    if field in result:
                        context[field] = result[field]
                if verbose and "changes" in result:
                    context["changes"] = "; ".join(
                        f"{code}:{before:.4f}->{after:.4f}"
                        for code, before, after in result["changes"]
                    )
            context["result"] = RESULT_OK
            logger.info(_format_record(action, context))
            return result

        return wrapper

    return decorator


def _format_record(action: str, context: dict) -> str:
    """Строка лога: BUY user='alice' currency='BTC' amount=0.0500 ..."""
    fields = " ".join(
        f"{name}={_format_value(name, value)}" for name, value in context.items()
    )
    return f"{action} {fields}"
