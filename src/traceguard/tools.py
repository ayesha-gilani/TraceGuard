
from collections.abc import Callable
from typing import TypeVar

from .models import Event
from .repository import EventRepository

T = TypeVar("T")


class ToolUnavailable(Exception):
    """Raised when a tool fails after permitted retries."""


def get_order(
    repository: EventRepository,
    tenant_id: str,
    order_id: str,
) -> list[Event]:
    return repository.get_order(tenant_id, order_id)


def get_payment_events(
    repository: EventRepository,
    tenant_id: str,
    order_id: str,
) -> list[Event]:
    return repository.get_payment_events(tenant_id, order_id)


def get_support_notes(
    repository: EventRepository,
    tenant_id: str,
    order_id: str,
) -> list[Event]:
    return repository.get_support_notes(tenant_id, order_id)


def call_with_retry(
    tool: Callable[..., T],
    *args,
    retries: int = 1,
) -> T:
    if retries < 0:
        raise ValueError("retries cannot be negative")

    for attempt in range(retries + 1):
        try:
            return tool(*args)
        except Exception as exc:
            if attempt == retries:
                raise ToolUnavailable(
                    f"Tool failed after {attempt + 1} attempts: {exc}"
                ) from exc

    raise ToolUnavailable("Tool failed unexpectedly.")
