
from .models import Anomaly, Event, ReconciliationResult


def reconcile(
    events: list[Event],
    validation_anomalies: list[Anomaly] | None = None,
    integrity_failed: bool = False,
) -> ReconciliationResult:
    """
    Deterministically reconcile checkout and payment events.

    The function does not use an LLM. It only trusts validated
    checkout and payment records.
    """
    anomalies = list(validation_anomalies or [])
    evidence_ids = set()

    def add_anomaly(code, message, event_ids=None):
        anomalies.append(Anomaly(
            code=code,
            message=message,
            severity="CRITICAL",
            event_ids=sorted(set(event_ids or [])),
        ))

    def unknown(reason):
        return ReconciliationResult(
            status="UNKNOWN",
            captured_cents=None,
            refunded_cents=None,
            net_paid_cents=None,
            anomalies=anomalies,
            evidence_event_ids=sorted(evidence_ids),
            explanation=reason,
            confidence="LOW",
        )

    # A reconciliation call must contain exactly one tenant/order.
    scopes = {(e.tenant_id, e.order_id) for e in events}

    if len(scopes) > 1:
        add_anomaly(
            "MIXED_ORDER_SCOPE",
            "Events from multiple tenants or orders were supplied together.",
        )
        return unknown("Cannot reconcile mixed tenant/order records.")

    # Only checkout and payment events are financial evidence.
    financial_events = [
        e for e in events
        if e.source in {"checkout", "payments"}
    ]

    # Find the checkout order definition.
    order_events = [
        e for e in financial_events
        if e.source == "checkout" and e.type == "ORDER_CREATED"
    ]

    if not order_events:
        add_anomaly(
            "MISSING_ORDER_DEFINITION",
            "No valid checkout ORDER_CREATED event was provided.",
        )
        return unknown("The expected order amount and currency are unknown.")

    definitions = {
        (e.amount_cents, e.currency.upper() if e.currency else None)
        for e in order_events
    }

    if len(definitions) != 1:
        add_anomaly(
            "CONFLICTING_ORDER_DEFINITIONS",
            "Checkout records disagree about the expected amount or currency.",
            [e.event_id for e in order_events],
        )
        return unknown(
            "Conflicting checkout definitions prevent reconciliation."
        )

    expected_cents, currency = next(iter(definitions))

    if (
        not isinstance(expected_cents, int)
        or isinstance(expected_cents, bool)
        or expected_cents <= 0
        or not currency
    ):
        add_anomaly(
            "INVALID_ORDER_DEFINITION",
            "Checkout order amount or currency is invalid.",
            [e.event_id for e in order_events],
        )
        return unknown("The checkout order definition is invalid.")

    evidence_ids.update(e.event_id for e in order_events)

    # Any critical validation issue means the financial history
    # cannot safely be treated as complete and trustworthy.
    if integrity_failed or any(
        a.severity == "CRITICAL" for a in anomalies
    ):
        return unknown(
            "Critical validation or integrity issues were detected."
        )

    payment_events = [
        e for e in financial_events if e.source == "payments"
    ]

    captures = {}
    refunds = {}
    chargebacks = []
    has_payment_failure = False

    # Process in a stable order so input ordering cannot change results.
    for event in sorted(payment_events, key=lambda e: e.event_id):

        # Preserve evidence even when this event causes an anomaly.
        evidence_ids.add(event.event_id)

        if event.type == "PAYMENT_FAILED":
            has_payment_failure = True

        elif event.type == "PAYMENT_CAPTURED":
            capture_id = event.capture_id
            signature = (event.amount_cents, event.currency.upper())

            if capture_id in captures:
                if captures[capture_id]["signature"] != signature:
                    add_anomaly(
                        "CAPTURE_ID_CONFLICT",
                        f"Capture ID {capture_id} was reused with different values.",
                        [captures[capture_id]["event_id"], event.event_id],
                    )
                continue

            captures[capture_id] = {
                "signature": signature,
                "amount": event.amount_cents,
                "currency": event.currency.upper(),
                "event_id": event.event_id,
            }

        elif event.type == "REFUND_ISSUED":
            refund_id = event.refund_id
            signature = (
                event.capture_id,
                event.amount_cents,
                event.currency.upper(),
            )

            if refund_id in refunds:
                if refunds[refund_id]["signature"] != signature:
                    add_anomaly(
                        "REFUND_ID_CONFLICT",
                        f"Refund ID {refund_id} was reused with different values.",
                        [refunds[refund_id]["event_id"], event.event_id],
                    )
                continue

            refunds[refund_id] = {
                "signature": signature,
                "capture_id": event.capture_id,
                "amount": event.amount_cents,
                "currency": event.currency.upper(),
                "event_id": event.event_id,
            }

        elif event.type == "CHARGEBACK_OPENED":
            chargebacks.append(event)

    if any(a.severity == "CRITICAL" for a in anomalies):
        return unknown("Conflicting transaction identities were detected.")

    # Validate captures against the checkout definition.
    for capture_id, capture in captures.items():
        if capture["currency"] != currency:
            add_anomaly(
                "CAPTURE_CURRENCY_MISMATCH",
                f"Capture {capture_id} uses a different currency from checkout.",
                [capture["event_id"]],
            )

    captured_total = sum(c["amount"] for c in captures.values())

    if captured_total > expected_cents:
        add_anomaly(
            "CAPTURE_EXCEEDS_ORDER",
            "Total captured amount exceeds the expected checkout amount.",
            [c["event_id"] for c in captures.values()],
        )

    # Validate refunds against their original captures.
    refunded_by_capture = {}
    valid_refunds = []

    for refund in refunds.values():
        capture_id = refund["capture_id"]

        if capture_id not in captures:
            add_anomaly(
                "REFUND_UNKNOWN_CAPTURE",
                f"Refund references unknown capture {capture_id}.",
                [refund["event_id"]],
            )
            continue

        capture = captures[capture_id]

        if refund["currency"] != capture["currency"]:
            add_anomaly(
                "REFUND_CURRENCY_MISMATCH",
                "Refund currency differs from its capture currency.",
                [refund["event_id"], capture["event_id"]],
            )
            continue

        refunded_by_capture[capture_id] = (
            refunded_by_capture.get(capture_id, 0) + refund["amount"]
        )
        valid_refunds.append(refund)

    for capture_id, refunded_amount in refunded_by_capture.items():
        if refunded_amount > captures[capture_id]["amount"]:
            add_anomaly(
                "REFUND_EXCEEDS_CAPTURE",
                f"Refund total exceeds capture {capture_id}.",
                [
                    captures[capture_id]["event_id"],
                    *[
                        r["event_id"] for r in valid_refunds
                        if r["capture_id"] == capture_id
                    ],
                ],
            )

    # A chargeback must refer to a known capture.
    valid_chargeback = False

    for chargeback in chargebacks:
        if chargeback.capture_id not in captures:
            add_anomaly(
                "CHARGEBACK_UNKNOWN_CAPTURE",
                "Chargeback references an unknown capture.",
                [chargeback.event_id],
            )
        else:
            valid_chargeback = True

    if any(a.severity == "CRITICAL" for a in anomalies):
        return unknown(
            "Invalid financial references or amounts were detected."
        )

    # All financial checks passed. Calculate totals.
    refunded_total = sum(r["amount"] for r in valid_refunds)
    captured_total = sum(c["amount"] for c in captures.values())

    net_paid = captured_total - refunded_total

    # Determine status using the required precedence.
    if valid_chargeback:
        status = "DISPUTED"
        explanation = (
            "A valid open chargeback references a recorded payment capture."
        )

    elif captured_total == 0 and has_payment_failure:
        status = "UNPAID"
        explanation = (
            "No payment was captured; a payment failure was recorded."
        )

    elif captured_total > 0 and refunded_total == captured_total:
        status = "REFUNDED"
        explanation = "All captured funds have been refunded."

    elif refunded_total > 0:
        status = "PARTIALLY_REFUNDED"
        explanation = "Some captured funds have been refunded."

    elif captured_total == expected_cents:
        status = "PAID"
        explanation = "The captured amount matches the checkout amount."

    elif 0 < captured_total < expected_cents:
        status = "PARTIALLY_PAID"
        explanation = (
            "The captured amount is less than the checkout amount."
        )

    else:
        status = "UNKNOWN"
        explanation = (
            "Available records do not establish a payment outcome."
        )

    confidence = "LOW" if status == "UNKNOWN" else "HIGH"

    return ReconciliationResult(
        status=status,
        captured_cents=captured_total,
        refunded_cents=refunded_total,
        net_paid_cents=net_paid,
        anomalies=anomalies,
        evidence_event_ids=sorted(evidence_ids),
        explanation=explanation,
        confidence=confidence,
    )
