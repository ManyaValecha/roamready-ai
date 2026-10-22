# Feature gap audit: RoamReady AI and reference projects

Audit date: 2026-10-22. This audit checks the checked-out `master` tree at `77c0154` before changes. Reference-project descriptions and license links were reviewed on GitHub; their README claims are not treated as independent verification of live service behavior.

## Gap matrix

| Capability | RoamReady status and local evidence | Trip Scout (`janik4321sdfa/trip-scout`) | Alexa Trip Planner (`Shriya-JB/Alexa_trip_planner`) |
|---|---|---|---|
| Traveler profile persistence and deletion | **Partial.** SQLite profile, saved trip and watch persistence; per-user deletion exists. Profile MCP handler accepts some unsupported/invalid values and clamps counts silently. See `trip_scout/store.py`, `trip_scout/server.py` (`set_travel_profile`, `forget_travel_memory`), `tests/test_units.py`. | README describes SQLite profiles and `set_travel_profile`/`get_travel_profile`; deletion details not described. See [README](https://github.com/janik4321sdfa/trip-scout#state). | README describes no persistent profile or deletion flow. See [README](https://github.com/Shriya-JB/Alexa_trip_planner#how-its-built). |
| Flight search and hotel search | **Partial.** Optional unofficial Google Travel result-page engines exist in `trip_scout/engines/flights.py` and `hotels.py`; safe unit tests cover mocked 503 handling. No live provider check is performed in this audit. | README claims Google Flights and Google Hotels result-page integrations; engine paths `trip_scout/engines/flights.py`, `trip_scout/engines/hotels.py`. | README describes Duffel test-mode flight search and mocked hotel data; `server.py` and `app.py`. |
| Multi-date fare comparison | **Partial.** `Planner.cheapest_dates` compares a capped date window and preserves failed dates; `find_cheapest_dates` exposes it. Optional external search only. `trip_scout/planner.py`, `trip_scout/server.py`. | README describes up to 14 departure dates in parallel; `trip_scout/planner.py`. | README does not describe date-window comparison. |
| Complete flight + hotel package ranking | **Partial.** `Planner.plan_trip` searches hotels for selected dates and ranks packages against budget; no safe offline fixture integration test for this optional live path. `trip_scout/planner.py`, `trip_scout/server.py`. | README describes date fan-out, hotel matching, package ranking; `trip_scout/planner.py`. | README describes one flight/hotel/itinerary orchestration path; no multi-option package ranking described. |
| Price watches and price history | **Partial.** SQLite baseline/latest/best/history fields and watch/list/check/stop tools exist. Refresh depends on optional provider calls; tests cover store history but not every MCP failure transition. `trip_scout/store.py`, `trip_scout/server.py`, `tests/test_units.py`. | README describes persistent watches and history across sessions; `trip_scout/store.py`. | README does not describe watches. |
| Airport and destination resolution | **Present for bundled dataset.** `trip_scout/places.py` resolves aliases, airport names, IATA codes and bundled city records; unit tests cover common cases. Dataset is `trip_scout/data/airports.json`. | README says `places.py` uses OurAirports-derived data and resolves examples such as Heathrow/New York. | No airport-resolution module described in README. |
| Natural-language dates | **Partial.** `trip_scout/dates.py` parses a limited set of absolute/relative date phrases and windows, covered by unit tests. Unsupported phrasing returns no match. | README describes common phrases such as “next Friday”, month names and weekends; `dates.py`. | README examples use natural-language trip requests, but no date parser detail is documented. |
| Alexa+ Agent Skill and voice-friendly responses | **Partial.** `skills/trip-scout/SKILL.md` exists; MCP result helper includes speech and structured content. The web simulator is not a real Alexa+ host. | README describes an Agent Skill and voice-ready `speech` fields. | README describes simulated Flask conversation and explicitly says it is not a published Alexa+ skill. |
| MCP Apps / structured screen results | **Present.** `trip_scout/server.py` registers `ui://roamready-ai/view.html` and attaches metadata to planning tools; `_result` returns `structuredContent`; view at `trip_scout/ui/view.html`. Actual host compatibility is not asserted here. | README describes a SEP-1865 MCP App resource and structured tool results. | README describes an MCP server and web chat UI, not MCP Apps. |
| MCP transport, error handling and request security | **Partial.** FastMCP Streamable HTTP and transport-security host/origin allow-lists are configured in `trip_scout/server.py`; deployment docs describe bearer auth. Local MCP integration tests cover initialize/list/call but no comprehensive malformed-request, rate-limit, or authentication matrix. | README describes Streamable HTTP, DNS-rebinding checks and optional bearer auth. | README describes MCP but not transport/security details. |
| Provider outage fallback | **Partial.** Deterministic demo recovery tool exercises a simulated 503; live search errors are handled by engines/planner, but end-to-end live-provider fallback is not claimed. `trip_scout/server.py`, `trip_scout/engines/`, tests. | README says rule-based simulator routing handles LLM outage and reports per-date/provider failure. | README documents Duffel test mode and mock hotels; no outage fallback documented. |
| Tests, README and deployment compatibility | **Partial.** Pytest suite, smoke scripts, setup README and Vercel ASGI entrypoint/config exist. Baseline test command crashed with exit 139 in this environment, so baseline is currently unverified; Vercel serverless persistence is temporary SQLite per `docs/VERCEL.md`. | README lists unit/MCP/conversation tests and local run instructions; no deployment verification in this audit. | README lists local Flask setup; no deployment instructions described. |

## License and reuse decision

Both reference repositories expose an MIT `LICENSE` in their GitHub repository listings. RoamReady also has an MIT `LICENSE`. This change uses the references for feature comparison only and introduces no copied reference code, so no new attribution notice is needed. Confirm license files again before any future code reuse.

Sources: [Trip Scout repository and README](https://github.com/janik4321sdfa/trip-scout), [Trip Scout MIT license](https://github.com/janik4321sdfa/trip-scout/blob/main/LICENSE), [Alexa Trip Planner repository and README](https://github.com/Shriya-JB/Alexa_trip_planner), [Alexa Trip Planner MIT license](https://github.com/Shriya-JB/Alexa_trip_planner/blob/main/LICENSE).

## First safe change selected

Harden profile writes before extending profile fields: validate currency shape, cabin class, passenger counts, hotel rating/stars, budget finiteness/range and interests before persisting. Invalid input must return a structured MCP error without partially changing saved preferences. This addresses an evidenced data-integrity gap while keeping the existing SQLite schema and tool arguments compatible.

## Baseline verification

Command attempted before edits: `.venv/bin/python -m pytest -q tests/test_units.py tests/test_roamready_mcp.py tests/test_web_reset.py`. The interpreter exited with status **139** and no pytest output. The system `python -m pytest` attempt also exited 139. This is an environment/runtime failure requiring diagnosis; it is not recorded as a passing or failing test assertion.

## Change and post-change verification

Changed `trip_scout/server.py` to validate preference inputs before calling SQLite, and added validation coverage in `tests/test_units.py`. No schema migration or reference-project source reuse was needed.

The environment's pytest capture plugin crashes while loading its native readline workaround; with capture disabled, the full local suite runs. The MCP integration test also needs permission to bind a loopback port; it passed after local network access was enabled.

Post-change command: `TRIP_SCOUT_DB=/private/tmp/roamready-test.db .venv/bin/python -m pytest -p no:capture -q tests/test_units.py tests/test_roamready_mcp.py tests/test_web_reset.py` — **23 passed**.

Live flight/hotel smoke calls were not run: those tools perform external requests, which are not necessary to validate this offline profile change. Vercel deployment was not invoked. Existing `.env` and SQLite demo database are ignored and are not tracked (`git ls-files .env .env.example roamready-demo.db` lists only the safe `.env.example`).
