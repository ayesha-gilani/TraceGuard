
from hypothesis import given, settings, strategies as st

from traceguard.models import Event
from traceguard.validators import validate_events
from traceguard.reconciliation import reconcile
from traceguard.repository import EventRepository
from traceguard.investigator import investigate


def make_event(
    event_id,
    source,
    event_type,
    amount=None,
    currency=None,
    capture_id=None,
    text=None,
    tenant="T1",
    order="O-1",
):
    return Event(
        tenant_id=tenant,
        order_id=order,
        event_id=event_id,
        source=source,
        type=event_type,
        occurred_at="2026-11-06T10:00:00Z",
        ingested_at="2026-11-06T10:01:00Z",
        amount_cents=amount,
        currency=currency,
        capture_id=capture_id,
        text=text,
    )


BASE_EVENTS = [
    make_event(
        "E1", "checkout", "ORDER_CREATED",
        amount=10000, currency="USD"
    ),
    make_event(
        "E2", "payments", "PAYMENT_CAPTURED",
        amount=10000, currency="USD", capture_id="C1"
    ),
]


def validated_result(events):
    valid, anomalies, integrity_failed = validate_events(events)

    return reconcile(
        valid,
        validation_anomalies=anomalies,
        integrity_failed=integrity_failed,
    ).to_dict()


# Property 1: Event processing order must not change the result.
@settings(max_examples=30)
@given(st.permutations(BASE_EVENTS))
def test_event_order_does_not_change_result(shuffled_events):
    expected = validated_result(BASE_EVENTS)
    actual = validated_result(list(shuffled_events))

    assert actual == expected


# Property 2: Adding an identical duplicate must not change totals or status.
@settings(max_examples=30)
@given(st.sampled_from(BASE_EVENTS))
def test_duplicate_insertion_does_not_change_result(event):
    original = validated_result(BASE_EVENTS)
    duplicated = validated_result(BASE_EVENTS + [event])

    assert duplicated == original


# Property 3: Support-note text must never affect financial truth.
@settings(max_examples=50)
@given(st.text(max_size=300))
def test_support_note_text_cannot_change_financial_result(note_text):
    note = make_event(
        "E3",
        "support",
        "NOTE",
        text=note_text,
    )

    original = validated_result(BASE_EVENTS)
    with_note = validated_result(BASE_EVENTS + [note])

    assert with_note == original


# Property 4: Records belonging to another tenant must not
# change the investigation result for the requested tenant.
@settings(max_examples=30)
@given(
    st.integers(min_value=1, max_value=100000),
    st.integers(min_value=1, max_value=100000),
)
def test_unrelated_tenant_events_do_not_change_result(
    other_order_amount,
    other_capture_amount,
):
    original = investigate(
        EventRepository(BASE_EVENTS),
        tenant_id="T1",
        order_id="O-1",
    ).to_dict()

    other_tenant_events = [
        make_event(
            "E1",
            "checkout",
            "ORDER_CREATED",
            amount=other_order_amount,
            currency="USD",
            tenant="T2",
            order="O-1",
        ),
        make_event(
            "E2",
            "payments",
            "PAYMENT_CAPTURED",
            amount=other_capture_amount,
            currency="USD",
            capture_id="C1",
            tenant="T2",
            order="O-1",
        ),
    ]

    combined = investigate(
        EventRepository(BASE_EVENTS + other_tenant_events),
        tenant_id="T1",
        order_id="O-1",
    ).to_dict()

    assert combined == original
