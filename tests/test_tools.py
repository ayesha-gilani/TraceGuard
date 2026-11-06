
import pytest

from traceguard.tools import (
    ToolUnavailable,
    call_with_retry,
)


def test_tool_succeeds_first_attempt():
    def tool():
        return "success"

    assert call_with_retry(tool) == "success"


def test_tool_succeeds_after_one_retry():
    calls = {"count": 0}

    def unstable_tool():
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("Temporary timeout")
        return "success"

    result = call_with_retry(unstable_tool)

    assert result == "success"
    assert calls["count"] == 2


def test_tool_failure_after_retry_is_controlled():
    calls = {"count": 0}

    def failing_tool():
        calls["count"] += 1
        raise ConnectionError("Service unavailable")

    with pytest.raises(ToolUnavailable):
        call_with_retry(failing_tool)

    assert calls["count"] == 2


def test_retry_limit_can_be_zero():
    calls = {"count": 0}

    def failing_tool():
        calls["count"] += 1
        raise TimeoutError("Timeout")

    with pytest.raises(ToolUnavailable):
        call_with_retry(failing_tool, retries=0)

    assert calls["count"] == 1
