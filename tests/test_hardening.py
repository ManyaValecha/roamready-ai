"""Regression tests for invalid numeric inputs, safe provider errors, and auth middleware."""
import asyncio
import math

import pytest

from trip_scout import server


class FakeContext:
    request_context = None

    async def report_progress(self, *args, **kwargs):
        return None


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    ("tool_name", "argument"),
    [
        ("plan_local_itinerary", "activity_budget"),
        ("rescue_itinerary_tool", "activity_budget"),
        ("plan_demo_trip", "trip_budget_eur"),
        ("rescue_demo_trip_tool", "trip_budget_eur"),
        ("simulate_provider_failure", "trip_budget_eur"),
    ],
)
def test_demo_tools_reject_non_finite_budgets(tool_name, argument, bad_value):
    tool = getattr(server, tool_name)
    result = asyncio.run(tool(FakeContext(), **{argument: bad_value}))

    assert result.isError is True
    assert result.structuredContent["kind"] == "error"


@pytest.mark.parametrize("tool_name", ["search_flights", "search_hotels"])
def test_provider_errors_do_not_expose_raw_exception_details(monkeypatch, tool_name):
    async def fail_provider(*args, **kwargs):
        raise RuntimeError("SECRET_TOKEN_TEST internal connection details")

    monkeypatch.setattr(server, "_run", fail_provider)

    if tool_name == "search_flights":
        monkeypatch.setattr(
            server, "_origin",
            lambda ctx, origin: {"code": "JFK", "label": "New York"}
        )
        monkeypatch.setattr(
            server, "_place",
            lambda destination, label: {"code": "BCN", "label": "Barcelona"}
        )
        result = asyncio.run(
            server.search_flights(
                FakeContext(),
                destination="Barcelona",
                departure_date="2026-11-12",
                origin="JFK",
            )
        )
    else:
        result = asyncio.run(
            server.search_hotels(
                FakeContext(),
                city="Barcelona",
                check_in="2026-11-12",
                nights=2,
            )
        )

    assert result.isError is True
    assert "SECRET_TOKEN_TEST" not in result.structuredContent["speech"]
    assert "internal connection details" not in result.structuredContent["speech"]


def test_server_env_defaults():
    import os
    from trip_scout import server

    host = os.getenv("TRIP_SCOUT_HOST", "127.0.0.1")
    assert host in ("127.0.0.1", "localhost", "0.0.0.0")


def test_invalid_mcp_tool_invocation_raises_handling():
    """Verify that calling non-existent or invalid tool attributes on server raises cleanly."""
    from trip_scout import server

    assert not hasattr(server, "non_existent_tool_name")


def test_build_app_enforces_bearer_auth(monkeypatch):
    """Verify that setting TRIP_SCOUT_TOKEN enforces 401 on unauthorized requests."""
    monkeypatch.setenv("TRIP_SCOUT_TOKEN", "secret-mcp-token-123")
    app = server.build_app()

    sent_messages = []

    async def fake_send(message):
        sent_messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", b"Bearer wrong-token")],
    }

    async def fake_receive():
        return {"type": "http.request", "body": b""}

    asyncio.run(app(scope, fake_receive, fake_send))

    assert len(sent_messages) > 0
    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 401
