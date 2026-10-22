"""End-to-end smoke test: real MCP client -> Streamable HTTP -> Trip Scout server -> live Google data."""
import asyncio
import datetime as dt
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
D = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()


async def main():
    async with streamablehttp_client(URL, headers={"x-user-id": "smoke-test"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            print("protocol:", init.protocolVersion, "| server:", init.serverInfo.name)
            tools = await s.list_tools()
            print("tools:", [(t.name, bool((t.meta or {}).get("ui"))) for t in tools.tools])
            res = await s.read_resource("ui://roamready-ai/view.html")
            c = res.contents[0]
            print("view:", c.mimeType, len(c.text), "chars")

            async def call(name, **args):
                t = time.time()
                out = await s.call_tool(name, args)
                sc = out.structuredContent or {}
                print(f"\n[{name}] {round(time.time() - t, 1)}s error={out.isError} kind={sc.get('kind')}")
                print("  speech:", sc.get("speech") or out.content[0].text)
                return sc

            await call("set_travel_profile", home_airport="New York", adults=2, currency="USD")
            f = await call("search_flights", destination="London", departure_date=D(30), return_date=D(35))
            print("  flights:", len(f.get("flights", [])), "first:", (f.get("flights") or [{}])[0].get("airlines"))
            c = await call("find_cheapest_dates", destination="Lisbon", when=f"{D(40)} to {D(53)}", trip_length_nights=4)
            print("  dates:", [(x["departureDate"], x["price"]) for x in c.get("results", [])][:5])
            h = await call("search_hotels", city="Lisbon", check_in=D(40), nights=3)
            print("  hotels:", [(x["name"], x["pricePerNight"], x["rating"]) for x in h.get("hotels", [])][:3])
            p = await call("plan_trip", destination="Barcelona", when=f"{D(45)} to {D(58)}", nights=3, budget=2500)
            for pk in p.get("packages", []):
                print("  pkg:", pk["departureDate"], pk["total"], pk["flight"]["airlines"], pk["hotel"]["name"], pk["hotel"]["rating"])
            print("  steps:", p.get("steps"))
            wch = await call("watch_price", destination="Barcelona", departure_date=D(45), return_date=D(48))
            await call("check_price_watches")
            await call("search_flights", destination="Atlantis Nowhere", departure_date=D(30))


asyncio.run(main())
