
import json
from pathlib import Path
from typing import Any

from .models import Event, IngestionIssue


REQUIRED_FIELDS = {
    "tenant_id",
    "order_id",
    "event_id",
    "source",
    "type",
    "occurred_at",
    "ingested_at",
}

OPTIONAL_STRING_FIELDS = {
    "attempt_id",
    "capture_id",
    "refund_id",
    "currency",
    "text",
}

OPTIONAL_INTEGER_FIELDS = {
    "amount_cents",
}


def parse_event(data: dict[str, Any], line_number: int) -> Event:
    """Convert one JSON object into an Event."""

    missing = REQUIRED_FIELDS - data.keys()

    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(sorted(missing))}"
        )

    # Required fields must be non-empty strings.
    for field in REQUIRED_FIELDS:
        value = data[field]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Field '{field}' must be a non-empty string"
            )

    # Optional string fields must be strings or null.
    for field in OPTIONAL_STRING_FIELDS:
        value = data.get(field)

        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"Field '{field}' must be a string or null"
            )

    # bool is deliberately rejected even though bool is a subclass of int.
    for field in OPTIONAL_INTEGER_FIELDS:
        value = data.get(field)

        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ValueError(
                f"Field '{field}' must be an integer or null"
            )

    allowed_fields = (
        REQUIRED_FIELDS
        | OPTIONAL_STRING_FIELDS
        | OPTIONAL_INTEGER_FIELDS
    )

    unknown_fields = data.keys() - allowed_fields

    if unknown_fields:
        raise ValueError(
            f"Unsupported fields: {', '.join(sorted(unknown_fields))}"
        )

    return Event(
        tenant_id=data["tenant_id"],
        order_id=data["order_id"],
        event_id=data["event_id"],
        source=data["source"],
        type=data["type"],
        occurred_at=data["occurred_at"],
        ingested_at=data["ingested_at"],
        attempt_id=data.get("attempt_id"),
        capture_id=data.get("capture_id"),
        refund_id=data.get("refund_id"),
        amount_cents=data.get("amount_cents"),
        currency=data.get("currency"),
        text=data.get("text"),
        line_number=line_number,
    )


def load_jsonl(
    file_path: str | Path,
) -> tuple[list[Event], list[IngestionIssue]]:
    """
    Read a JSONL file.

    Valid records become Event objects.
    Invalid lines become IngestionIssue objects.
    One bad line does not stop the entire file.
    """

    events: list[Event] = []
    issues: list[IngestionIssue] = []

    path = Path(file_path)

    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, raw_line in enumerate(file, start=1):

                if not raw_line.strip():
                    continue

                try:
                    data = json.loads(raw_line)

                    if not isinstance(data, dict):
                        raise ValueError(
                            "Each JSONL line must contain a JSON object"
                        )

                    event = parse_event(data, line_number)
                    events.append(event)

                except (json.JSONDecodeError, ValueError) as exc:
                    issues.append(
                        IngestionIssue(
                            line_number=line_number,
                            error=str(exc),
                            raw_line=raw_line.rstrip("\n"),
                        )
                    )

    except OSError as exc:
        issues.append(
            IngestionIssue(
                line_number=0,
                error=f"Unable to read file: {exc}",
            )
        )

    return events, issues
