from datetime import datetime, timezone

from .models import Event, Anomaly


ALLOWED_SOURCE_TYPES = {
    "checkout": {"ORDER_CREATED"},
    "payments": {
        "PAYMENT_FAILED",
        "PAYMENT_CAPTURED",
        "REFUND_ISSUED",
        "CHARGEBACK_OPENED",
    },
    "support": {"NOTE"},
}


def valid_timestamp(value: str) -> bool:
    """Return True only for timezone-aware ISO timestamps."""
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError):
        return False


def validate_event(event: Event) -> list[Anomaly]:
    """Validate one event without changing it."""
    anomalies = []

    allowed_types = ALLOWED_SOURCE_TYPES.get(event.source)

    if allowed_types is None or event.type not in allowed_types:
        anomalies.append(Anomaly(
            code="INVALID_SOURCE_TYPE",
            message=f"Unsupported source/type combination: {event.source}/{event.type}",
            severity="ERROR",
            event_ids=[event.event_id],
        ))
        return anomalies

    # Financial event timestamps must be valid.
    if event.source in {"checkout", "payments"}:
        if not valid_timestamp(event.occurred_at):
            anomalies.append(Anomaly(
                code="INVALID_OCCURRED_AT",
                message="Financial event has an invalid or timezone-naive occurred_at.",
                severity="CRITICAL",
                event_ids=[event.event_id],
            ))

    if not valid_timestamp(event.ingested_at):
        anomalies.append(Anomaly(
            code="INVALID_INGESTED_AT",
            message="Event has an invalid or timezone-naive ingested_at.",
            severity="WARNING",
            event_ids=[event.event_id],
        ))

    if event.type in {"ORDER_CREATED", "PAYMENT_CAPTURED", "REFUND_ISSUED"}:
        if event.amount_cents is None or event.amount_cents <= 0:
            anomalies.append(Anomaly(
                code="INVALID_AMOUNT",
                message=f"{event.type} requires a positive amount_cents.",
                severity="CRITICAL",
                event_ids=[event.event_id],
            ))

        if not event.currency or not event.currency.strip():
            anomalies.append(Anomaly(
                code="MISSING_CURRENCY",
                message=f"{event.type} requires a currency.",
                severity="CRITICAL",
                event_ids=[event.event_id],
            ))

    if event.type == "PAYMENT_CAPTURED" and not event.capture_id:
        anomalies.append(Anomaly(
            code="MISSING_CAPTURE_ID",
            message="Payment capture requires capture_id.",
            severity="CRITICAL",
            event_ids=[event.event_id],
        ))

    if event.type == "REFUND_ISSUED":
        if not event.capture_id or not event.refund_id:
            anomalies.append(Anomaly(
                code="MISSING_REFUND_REFERENCE",
                message="Refund requires both capture_id and refund_id.",
                severity="CRITICAL",
                event_ids=[event.event_id],
            ))

    if event.type == "CHARGEBACK_OPENED" and not event.capture_id:
        anomalies.append(Anomaly(
            code="MISSING_CHARGEBACK_CAPTURE",
            message="Chargeback requires capture_id.",
            severity="CRITICAL",
            event_ids=[event.event_id],
        ))

    if event.type == "PAYMENT_FAILED" and not event.attempt_id:
        anomalies.append(Anomaly(
            code="MISSING_ATTEMPT_ID",
            message="Payment failure should identify its attempt.",
            severity="WARNING",
            event_ids=[event.event_id],
        ))

    return anomalies


def validate_events(
    events: list[Event],
) -> tuple[list[Event], list[Anomaly], bool]:
    """
    Validate events and deduplicate identical event identities.

    Returns:
        valid_events: Events eligible for further processing.
        anomalies: All validation and integrity anomalies.
        integrity_failed: Whether a critical integrity issue was found.
    """
    anomalies = []
    valid_events = []
    integrity_failed = False

    seen = {}

    for event in events:
        identity = event.identity()

        if identity in seen:
            previous = seen[identity]

            if previous.substantive_data() == event.substantive_data():
                # ingested_at differences alone do not create new events.
                continue

            anomalies.append(Anomaly(
                code="EVENT_ID_CONFLICT",
                message=(
                    f"Event identity {identity} was reused with "
                    "different substantive data."
                ),
                severity="CRITICAL",
                event_ids=[previous.event_id, event.event_id],
            ))
            integrity_failed = True
            continue

        seen[identity] = event

        event_anomalies = validate_event(event)
        anomalies.extend(event_anomalies)

        if any(a.severity == "CRITICAL" for a in event_anomalies):
            integrity_failed = True
            continue

        valid_events.append(event)

    return valid_events, anomalies, integrity_failed