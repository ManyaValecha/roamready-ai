# Three-minute judge demo (2:30 target)

## Clean start

From the repository root, run:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python run_demo.py
```

Keep the defaults in `.env.example`: `ROAMREADY_DEMO_MODE=1`. The launcher starts the MCP server at `http://127.0.0.1:8765/mcp` and the browser simulator at `http://127.0.0.1:8770`. The simulator's **Reset demo** button clears its session and demo profile before each take. No API key is needed.

## Timed script

**0:00–0:20 — Set context.** Show the simulator's Alexa+ simulation label, MCP 2025-11-25 / Streamable HTTP indicator and activity trace. Say: “RoamReady turns a budget and travel preferences into a day-by-day city itinerary. This is a local web MCP client simulation, not an Alexa+ preview or Echo device.”

**0:20–1:05 — Plan.** Click **Reset demo**, then submit: “Plan a four-day Barcelona trip for two under €1,800; we love architecture, art and food.” Point to the actual `tools/call plan_demo_trip` trace, JSON arguments and structured result. The deterministic result is four days, €620 airfare, €480 lodging, €280 meals, €80 local transport and €252 activities: €1,712 estimated total, €88 remaining, and 159 estimated local-travel minutes. These are disclosed illustrative estimates, not live prices or availability.

**1:05–1:45 — Rescue.** Submit: “Sagrada Família is closed; replan the trip.” Say clearly that the closure is simulated. Show the MCP rescue tool and structured before/after itinerary. The revised result is €1,638, €74 less than before, €162 remaining, and 32 fewer estimated local-travel minutes. Show the removed Sagrada Família stop and replacement.

**1:45–2:15 — Provider failure.** Submit: “Simulate a flight provider failure and recover offline.” Show the injected simulated 503 and successful offline fallback in the tool trace. Explain that this test makes no external request.

**2:15–2:30 — Reset and close.** Press **Reset demo**, verify the initial state returns, and close: “The planner uses MCP tool calls and structured results; booking, live fare/hotel quoting and Amazon device integration are not represented.”

The result is deterministic with bundled demo data. Do not run `tests/smoke_mcp.py` as part of a recorded demo: it makes outbound provider requests. Keep the app label and simulated-data disclosures visible on screen.
