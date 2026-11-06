
from .models import Anomaly, ReconciliationResult
from .repository import EventRepository
from .tools import (
    ToolUnavailable,
    call_with_retry,
    get_order,
    get_payment_events,
    get_support_notes,
)
from .validators import validate_events
from .reconciliation import reconcile


def investigate(
    repository: EventRepository,
    tenant_id: str,
    order_id: str,
) -> ReconciliationResult:
    """
    Investigate one order using the three required tools.

    Checkout and payment failures prevent a reliable financial decision.
    Support-note failures do not change financial truth.
    """

    anomalies = []

    # Tool 1: checkout order definition.
    try:
        order_events = call_with_retry(
            get_order, repository, tenant_id, order_id
        )
    except ToolUnavailable as exc:
        return ReconciliationResult(
            explanation=f"Checkout tool unavailable: {exc}",
            anomalies=[Anomaly(
                code="ORDER_TOOL_FAILURE",
                message=str(exc),
                severity="CRITICAL",
            )],
        )

    # Tool 2: payment events.
    try:
        payment_events = call_with_retry(
            get_payment_events, repository, tenant_id, order_id
        )
    except ToolUnavailable as exc:
        return ReconciliationResult(
            explanation=f"Payment tool unavailable: {exc}",
            anomalies=[Anomaly(
                code="PAYMENT_TOOL_FAILURE",
                message=str(exc),
                severity="CRITICAL",
            )],
        )

    # Tool 3: support notes. These are optional context, not evidence.
    try:
        support_notes = call_with_retry(
            get_support_notes, repository, tenant_id, order_id
        )
    except ToolUnavailable as exc:
        support_notes = []
        anomalies.append(Anomaly(
            code="SUPPORT_TOOL_FAILURE",
            message=f"Support notes unavailable: {exc}",
            severity="WARNING",
        ))

    target_events = order_events + payment_events

    # Detect event identity conflicts across the entire tenant.
    # A conflicting identity involving this order invalidates this
    # investigation, even if the other record belongs to another order.
    tenant_events = repository.get_tenant_events(tenant_id)
    target_identities = {
        event.identity() for event in target_events
    }

    identity_groups = {}

    for event in tenant_events:
        if event.identity() in target_identities:
            identity_groups.setdefault(event.identity(), []).append(event)

    cross_order_conflict = False

    for identity, group in identity_groups.items():
        substantive_versions = {
            str(sorted(event.substantive_data().items()))
            for event in group
        }

        if len(substantive_versions) > 1:
            cross_order_conflict = True
            anomalies.append(Anomaly(
                code="TENANT_EVENT_ID_CONFLICT",
                message=(
                    f"Event identity {identity} has conflicting "
                    "records in tenant history."
                ),
                severity="CRITICAL",
                event_ids=sorted({event.event_id for event in group}),
            ))

    # Validate and deduplicate the target order's financial events.
    valid_events, validation_anomalies, integrity_failed = (
        validate_events(target_events)
    )

    anomalies.extend(validation_anomalies)

    # Reconcile only validated records.
    result = reconcile(
        valid_events,
        validation_anomalies=anomalies,
        integrity_failed=(
            integrity_failed or cross_order_conflict
        ),
    )

    # Support notes are deliberately not passed to reconciliation.
    # Their text cannot alter financial status or totals.
    #
    # Keep this count available for future evidence/context reporting.
    _support_note_count = len(support_notes)

    return result
