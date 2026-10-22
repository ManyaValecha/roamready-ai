"""Simulator reset must not erase persistent travel memory."""
import asyncio
import json
import os
import sys

from starlette.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_reset_clears_only_the_active_conversation(monkeypatch):
    from web import app as simulator

    simulator.SESSIONS["reset-test"] = [{"role": "user", "content": "hello"}]
    simulator.LAST["reset-test"] = {"destination": "BCN"}
    simulator.DEMO_TRIPS["reset-test"] = {"days": 4}

    async def unexpected_memory_delete(*_args, **_kwargs):
        raise AssertionError("Reset must not call the persistent memory deletion tool")

    monkeypatch.setattr(simulator, "mcp_call", unexpected_memory_delete)
    body = json.dumps({"session_id": "reset-test", "user_id": "demo-user"}).encode()
    messages = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive():
        return messages.pop(0)

    request = Request(
        {"type": "http", "method": "POST", "path": "/api/reset", "headers": []},
        receive,
    )
    response = asyncio.run(simulator.reset(request))

    assert response.status_code == 200
    assert json.loads(response.body) == {"reset": True}
    assert "reset-test" not in simulator.SESSIONS
    assert "reset-test" not in simulator.LAST
    assert "reset-test" not in simulator.DEMO_TRIPS
