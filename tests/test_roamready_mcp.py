"""End-to-end offline Streamable HTTP MCP test for the new rescue workflow."""
import asyncio
import os
import subprocess
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_mcp_plan_and_rescue_tools_over_streamable_http():
    asyncio.run(_exercise_server())

async def _exercise_server():
    env = dict(os.environ, TRIP_SCOUT_HOST="127.0.0.1", TRIP_SCOUT_PORT="8876", PORT="8876",
               TRIP_SCOUT_ALLOWED_HOSTS="127.0.0.1:8876,localhost:8876",
               TRIP_SCOUT_ALLOWED_ORIGINS="http://127.0.0.1:8876", TRIP_SCOUT_DB="/private/tmp/roamready-mcp-test.db")
    proc = subprocess.Popen([sys.executable, "-m", "trip_scout.server"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                async with streamable_http_client("http://127.0.0.1:8876/mcp") as (read, write, _):
                    async with ClientSession(read, write) as session:
                        initialized = await session.initialize()
                        assert initialized.protocolVersion >= "2025-11-25"
                        tools = {t.name for t in (await session.list_tools()).tools}
                        assert {"plan_demo_trip", "rescue_demo_trip_tool", "simulate_provider_failure"} <= tools
                        plan = await session.call_tool("plan_demo_trip", {"days":4,"travelers":2,"trip_budget_eur":1800,"interests":["architecture","art","food"]})
                        p = plan.structuredContent
                        assert p["kind"] == "demo-trip" and p["estimatedTotal"] <= 1800
                        assert p["costBreakdown"]["airfare"] + p["costBreakdown"]["lodging"] + p["costBreakdown"]["meals"] + p["costBreakdown"]["localTransport"] + p["costBreakdown"]["activities"] == p["estimatedTotal"]
                        saved = await session.call_tool("save_demo_trip_tool", {"trip": p})
                        trip_id = saved.structuredContent["trip"]["id"]
                        listed = await session.call_tool("list_saved_trips", {})
                        assert any(t["id"] == trip_id for t in listed.structuredContent["trips"])
                        deleted = await session.call_tool("delete_saved_trip_tool", {"trip_id": trip_id})
                        assert not deleted.isError
                        listed = await session.call_tool("list_saved_trips", {})
                        assert all(t["id"] != trip_id for t in listed.structuredContent["trips"])
                        rescue = await session.call_tool("rescue_demo_trip_tool", {"days":4,"travelers":2,"trip_budget_eur":1800,"interests":["architecture","art","food"],"disruption":"Sagrada Família closure"})
                        r = rescue.structuredContent
                        assert r["kind"] == "demo-rescue" and r["after"]["estimatedTotal"] <= 1800
                        before_names = [s["name"] for d in r["before"]["itinerary"]["days"] for s in d["stops"]]
                        after_names = [s["name"] for d in r["after"]["itinerary"]["days"] for s in d["stops"]]
                        assert "Sagrada Família" in before_names and "Sagrada Família" not in after_names
                        fallback = await session.call_tool("simulate_provider_failure", {"days":4,"travelers":2,"trip_budget_eur":1800})
                        assert fallback.structuredContent["recoveredOffline"] is True
                        return
            except Exception:
                await asyncio.sleep(0.1)
        raise AssertionError("MCP server did not start")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
