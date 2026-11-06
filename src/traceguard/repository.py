
from .models import Event


class EventRepository:
    """In-memory event repository with tenant isolation."""

    def __init__(self, events: list[Event]):
        self._events = list(events)

    def get_order(self, tenant_id: str, order_id: str) -> list[Event]:
        """Retrieve checkout order definitions."""
        return [
            event for event in self._events
            if event.tenant_id == tenant_id
            and event.order_id == order_id
            and event.source == "checkout"
            and event.type == "ORDER_CREATED"
        ]

    def get_payment_events(
        self, tenant_id: str, order_id: str
    ) -> list[Event]:
        """Retrieve payment records for one tenant and order."""
        return [
            event for event in self._events
            if event.tenant_id == tenant_id
            and event.order_id == order_id
            and event.source == "payments"
        ]

    def get_support_notes(
        self, tenant_id: str, order_id: str
    ) -> list[Event]:
        """Retrieve support notes. These are never financial evidence."""
        return [
            event for event in self._events
            if event.tenant_id == tenant_id
            and event.order_id == order_id
            and event.source == "support"
            and event.type == "NOTE"
        ]

    def get_tenant_events(self, tenant_id: str) -> list[Event]:
        """Retrieve all events for tenant-wide integrity checks."""
        return [
            event for event in self._events
            if event.tenant_id == tenant_id
        ]
