
import json

from src.traceguard.ingestion import load_jsonl
from src.traceguard.models import Event


def make_event():
    return {
        "tenant_id": "T1",
        "order_id": "O-201",
        "event_id": "E1",
        "source": "checkout",
        "type": "ORDER_CREATED",
        "occurred_at": "2026-11-06T10:00:00Z",
        "ingested_at": "2026-11-06T10:01:00Z",
        "amount_cents": 10000,
        "currency": "PKR",
    }


def test_valid_jsonl_event(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(make_event()), encoding="utf-8")

    events, issues = load_jsonl(path)

    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert events[0].order_id == "O-201"
    assert events[0].amount_cents == 10000
    assert issues == []


def test_malformed_json_does_not_crash(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"tenant_id": broken json\n'
        + json.dumps(make_event()),
        encoding="utf-8",
    )

    events, issues = load_jsonl(path)

    assert len(events) == 1
    assert len(issues) == 1
    assert issues[0].line_number == 1


def test_missing_required_field(tmp_path):
    data = make_event()
    del data["event_id"]

    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(data), encoding="utf-8")

    events, issues = load_jsonl(path)

    assert events == []
    assert len(issues) == 1
    assert "event_id" in issues[0].error


def test_boolean_amount_rejected(tmp_path):
    data = make_event()
    data["amount_cents"] = True

    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(data), encoding="utf-8")

    events, issues = load_jsonl(path)

    assert events == []
    assert len(issues) == 1
    assert "integer" in issues[0].error


def test_blank_lines_ignored(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n" + json.dumps(make_event()) + "\n\n",
        encoding="utf-8",
    )

    events, issues = load_jsonl(path)

    assert len(events) == 1
    assert issues == []
