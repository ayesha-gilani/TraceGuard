
from traceguard.models import Event
from traceguard.reconciliation import reconcile


def make_event(event_id, source, event_type, **kwargs):
    data = {
        "tenant_id": "T1",
        "order_id": "O1",
        "event_id": event_id,
        "source": source,
        "type": event_type,
        "occurred_at": "2026-11-06T10:00:00Z",
        "ingested_at": "2026-11-06T10:01:00Z",
    }
    data.update(kwargs)
    return Event(**data)


def checkout():
    return make_event(
        "E1", "checkout", "ORDER_CREATED",
        amount_cents=10000, currency="USD",
    )


def capture(event_id="E2", amount=10000, capture_id="C1"):
    return make_event(
        event_id, "payments", "PAYMENT_CAPTURED",
        capture_id=capture_id,
        amount_cents=amount,
        currency="USD",
    )


def refund(event_id="E3", amount=3000, refund_id="R1"):
    return make_event(
        event_id, "payments", "REFUND_ISSUED",
        capture_id="C1",
        refund_id=refund_id,
        amount_cents=amount,
        currency="USD",
    )


def test_full_payment_is_paid():
    result = reconcile([checkout(), capture()])
    assert result.status == "PAID"
    assert result.captured_cents == 10000
    assert result.refunded_cents == 0
    assert result.net_paid_cents == 10000


def test_partial_payment():
    result = reconcile([checkout(), capture(amount=6000)])
    assert result.status == "PARTIALLY_PAID"
    assert result.net_paid_cents == 6000


def test_failed_attempt_does_not_cancel_successful_capture():
    failed = make_event(
        "E3", "payments", "PAYMENT_FAILED", attempt_id="A1"
    )
    result = reconcile([checkout(), failed, capture()])
    assert result.status == "PAID"


def test_partial_refund():
    result = reconcile([checkout(), capture(), refund()])
    assert result.status == "PARTIALLY_REFUNDED"
    assert result.refunded_cents == 3000
    assert result.net_paid_cents == 7000


def test_full_refund():
    result = reconcile([
        checkout(), capture(),
        refund(amount=10000),
    ])
    assert result.status == "REFUNDED"
    assert result.net_paid_cents == 0


def test_no_capture_and_failure_is_unpaid():
    failed = make_event(
        "E2", "payments", "PAYMENT_FAILED", attempt_id="A1"
    )
    result = reconcile([checkout(), failed])
    assert result.status == "UNPAID"


def test_missing_checkout_is_unknown():
    result = reconcile([capture()])
    assert result.status == "UNKNOWN"
    assert result.captured_cents is None


def test_capture_above_order_is_unknown():
    result = reconcile([checkout(), capture(amount=12000)])
    assert result.status == "UNKNOWN"


def test_refund_without_capture_is_unknown():
    result = reconcile([checkout(), refund()])
    assert result.status == "UNKNOWN"


def test_chargeback_is_disputed():
    chargeback = make_event(
        "E3", "payments", "CHARGEBACK_OPENED",
        capture_id="C1",
    )
    result = reconcile([checkout(), capture(), chargeback])
    assert result.status == "DISPUTED"


def test_mixed_tenants_are_rejected():
    other = make_event(
        "E2", "payments", "PAYMENT_CAPTURED",
        capture_id="C2", amount_cents=10000, currency="USD",
    )
    other = Event(**{
        **other.__dict__,
        "tenant_id": "T2",
    })

    result = reconcile([checkout(), other])
    assert result.status == "UNKNOWN"


def test_input_order_does_not_change_result():
    events = [checkout(), capture(), refund()]
    first = reconcile(events)
    second = reconcile(list(reversed(events)))

    assert first.status == second.status
    assert first.captured_cents == second.captured_cents
    assert first.refunded_cents == second.refunded_cents
    assert first.evidence_event_ids == second.evidence_event_ids
