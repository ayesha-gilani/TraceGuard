from traceguard import investigator as investigator_module
from traceguard.models import Event
from traceguard.repository import EventRepository


def make_events():
    return [
        Event(
            tenant_id="T1",
            order_id="O-1",
            event_id="E1",
            source="checkout",
            type="ORDER_CREATED",
            occurred_at="2026-11-06T10:00:00Z",
            ingested_at="2026-11-06T10:01:00Z",
            amount_cents=10000,
            currency="USD",
        ),
        Event(
            tenant_id="T1",
            order_id="O-1",
            event_id="E2",
            source="payments",
            type="PAYMENT_CAPTURED",
            occurred_at="2026-11-06T10:02:00Z",
            ingested_at="2026-11-06T10:03:00Z",
            capture_id="C1",
            amount_cents=10000,
            currency="USD",
        ),
    ]


def test_payment_tool_failure_returns_unknown(monkeypatch):
    def failing_tool(*args, **kwargs):
        raise RuntimeError("Payment service unavailable")

    monkeypatch.setattr(
        investigator_module, "get_payment_events", failing_tool
    )

    result = investigator_module.investigate(
        EventRepository(make_events()), "T1", "O-1"
    )

    assert result.status == "UNKNOWN"
    assert any(
        anomaly.severity == "CRITICAL"
        for anomaly in result.anomalies
    )


def test_order_tool_failure_returns_unknown(monkeypatch):
    def failing_tool(*args, **kwargs):
        raise RuntimeError("Checkout service unavailable")

    monkeypatch.setattr(
        investigator_module, "get_order", failing_tool
    )

    result = investigator_module.investigate(
        EventRepository(make_events()), "T1", "O-1"
    )

    assert result.status == "UNKNOWN"
    assert any(
        anomaly.severity == "CRITICAL"
        for anomaly in result.anomalies
    )


def test_support_tool_failure_does_not_change_payment_status(monkeypatch):
    def failing_tool(*args, **kwargs):
        raise RuntimeError("Support service unavailable")

    monkeypatch.setattr(
        investigator_module, "get_support_notes", failing_tool
    )

    result = investigator_module.investigate(
        EventRepository(make_events()), "T1", "O-1"
    )

    assert result.status == "PAID"
    assert any(
        anomaly.severity == "WARNING"
        for anomaly in result.anomalies
    )