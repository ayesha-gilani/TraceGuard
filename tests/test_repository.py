
from traceguard.models import Event
from traceguard.repository import EventRepository


def make_event(
    tenant="T1",
    order="O1",
    source="payments",
    event_type="PAYMENT_CAPTURED",
):
    return Event(
        tenant_id=tenant,
        order_id=order,
        event_id=f"{tenant}-{order}-{source}-{event_type}",
        source=source,
        type=event_type,
        occurred_at="2026-11-06T10:00:00Z",
        ingested_at="2026-11-06T10:01:00Z",
        capture_id="C1" if source == "payments" else None,
        amount_cents=10000 if source == "payments" else None,
        currency="USD" if source == "payments" else None,
        text="Customer says payment is missing."
        if source == "support" else None,
    )


def test_get_order_returns_checkout_records():
    events = [
        make_event(source="checkout", event_type="ORDER_CREATED"),
        make_event(),
    ]
    repo = EventRepository(events)

    result = repo.get_order("T1", "O1")

    assert len(result) == 1
    assert result[0].type == "ORDER_CREATED"


def test_get_payment_events_excludes_support_notes():
    events = [
        make_event(),
        make_event(source="support", event_type="NOTE"),
    ]
    repo = EventRepository(events)

    result = repo.get_payment_events("T1", "O1")

    assert len(result) == 1
    assert result[0].source == "payments"


def test_get_support_notes_returns_only_notes():
    events = [
        make_event(),
        make_event(source="support", event_type="NOTE"),
    ]
    repo = EventRepository(events)

    result = repo.get_support_notes("T1", "O1")

    assert len(result) == 1
    assert result[0].type == "NOTE"


def test_tenant_isolation():
    events = [
        make_event(tenant="T1"),
        make_event(tenant="T2"),
    ]
    repo = EventRepository(events)

    result = repo.get_payment_events("T1", "O1")

    assert len(result) == 1
    assert result[0].tenant_id == "T1"


def test_order_isolation():
    events = [
        make_event(order="O1"),
        make_event(order="O2"),
    ]
    repo = EventRepository(events)

    result = repo.get_payment_events("T1", "O1")

    assert len(result) == 1
    assert result[0].order_id == "O1"


def test_get_tenant_events_includes_all_tenant_orders():
    events = [
        make_event(order="O1"),
        make_event(order="O2"),
        make_event(tenant="T2"),
    ]
    repo = EventRepository(events)

    result = repo.get_tenant_events("T1")

    assert len(result) == 2
    assert all(event.tenant_id == "T1" for event in result)
