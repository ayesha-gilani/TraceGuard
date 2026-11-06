from traceguard.models import Event
from traceguard.validators import validate_event, validate_events


def make_event(**overrides):
    data = {
        "tenant_id": "T1",
        "order_id": "O1",
        "event_id": "E1",
        "source": "payments",
        "type": "PAYMENT_CAPTURED",
        "occurred_at": "2026-11-06T10:00:00Z",
        "ingested_at": "2026-11-06T10:01:00Z",
        "capture_id": "C1",
        "amount_cents": 10000,
        "currency": "USD",
    }
    data.update(overrides)
    return Event(**data)


def test_valid_capture_has_no_anomalies():
    assert validate_event(make_event()) == []


def test_timezone_naive_financial_timestamp_is_rejected():
    anomalies = validate_event(
        make_event(occurred_at="2026-11-06T10:00:00")
    )
    assert "INVALID_OCCURRED_AT" in [a.code for a in anomalies]


def test_invalid_source_type_is_rejected():
    anomalies = validate_event(
        make_event(source="support", type="PAYMENT_CAPTURED")
    )
    assert "INVALID_SOURCE_TYPE" in [a.code for a in anomalies]


def test_zero_amount_is_rejected():
    anomalies = validate_event(make_event(amount_cents=0))
    assert "INVALID_AMOUNT" in [a.code for a in anomalies]


def test_capture_without_capture_id_is_rejected():
    anomalies = validate_event(make_event(capture_id=None))
    assert "MISSING_CAPTURE_ID" in [a.code for a in anomalies]


def test_identical_duplicate_is_counted_once():
    first = make_event()
    duplicate = make_event(ingested_at="2026-11-06T11:00:00Z")

    valid, anomalies, failed = validate_events([first, duplicate])

    assert len(valid) == 1
    assert not failed
    assert "EVENT_ID_CONFLICT" not in [a.code for a in anomalies]


def test_conflicting_event_identity_causes_integrity_failure():
    first = make_event()
    conflicting = make_event(amount_cents=9000)

    valid, anomalies, failed = validate_events([first, conflicting])

    assert failed
    assert "EVENT_ID_CONFLICT" in [a.code for a in anomalies]


def test_refund_requires_capture_and_refund_ids():
    refund = make_event(
        type="REFUND_ISSUED",
        capture_id=None,
        refund_id=None,
    )

    anomalies = validate_event(refund)
    assert "MISSING_REFUND_REFERENCE" in [a.code for a in anomalies]