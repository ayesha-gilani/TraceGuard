
from dataclasses import dataclass, field
from typing import Any, Literal


# Supported financial investigation statuses
Status = Literal[
    "PAID",
    "UNPAID",
    "PARTIALLY_PAID",
    "PARTIALLY_REFUNDED",
    "REFUNDED",
    "DISPUTED",
    "UNKNOWN",
]

Confidence = Literal["HIGH", "MEDIUM", "LOW"]

Severity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class Event:
    """
    Represents one event received from checkout,
    payments, or customer support systems.
    """

    tenant_id: str
    order_id: str
    event_id: str
    source: str
    type: str

    occurred_at: str
    ingested_at: str

    attempt_id: str | None = None
    capture_id: str | None = None
    refund_id: str | None = None

    amount_cents: int | None = None
    currency: str | None = None
    text: str | None = None

    # Original input line for debugging and traceability.
    line_number: int | None = None

    def identity(self) -> tuple[str, str]:
        """Return the event's tenant-scoped identity."""
        return (self.tenant_id, self.event_id)

    def substantive_data(self) -> dict[str, Any]:
        """
        Return fields used to detect conflicting event IDs.

        ingested_at and line_number are deliberately excluded.
        """
        return {
            "tenant_id": self.tenant_id,
            "order_id": self.order_id,
            "event_id": self.event_id,
            "source": self.source,
            "type": self.type,
            "occurred_at": self.occurred_at,
            "attempt_id": self.attempt_id,
            "capture_id": self.capture_id,
            "refund_id": self.refund_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "text": self.text,
        }


@dataclass
class Anomaly:
    """Represents an integrity, validation, or investigation issue."""

    code: str
    message: str
    severity: Severity = "WARNING"
    event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "event_ids": self.event_ids,
        }


@dataclass
class IngestionIssue:
    """Represents a problem encountered while reading JSONL."""

    line_number: int
    error: str
    raw_line: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "error": self.error,
        }


@dataclass
class ReconciliationResult:
    """Stores the final deterministic financial assessment."""

    status: Status = "UNKNOWN"

    captured_cents: int | None = None
    refunded_cents: int | None = None
    net_paid_cents: int | None = None

    anomalies: list[Anomaly] = field(default_factory=list)
    evidence_event_ids: list[str] = field(default_factory=list)

    explanation: str = ""
    confidence: Confidence = "LOW"

    def to_dict(self) -> dict[str, Any]:
        """Convert the result into the required JSON structure."""

        return {
            "status": self.status,
            "captured_cents": self.captured_cents,
            "refunded_cents": self.refunded_cents,
            "net_paid_cents": self.net_paid_cents,
            "anomalies": [
                anomaly.code for anomaly in self.anomalies
            ],
            "evidence_event_ids": self.evidence_event_ids,
            "explanation": self.explanation,
            "confidence": self.confidence,
        }
