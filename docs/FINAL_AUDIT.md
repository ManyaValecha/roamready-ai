# Final audit — 22 October 2026

## Scope and outcome

Inspected `README.md`, `FEATURE_MATRIX.md`, `DEMO.md`, `SUBMISSION.md`, `.env.example`, `.gitignore`, `requirements.txt`, `run_demo.py`, unit and MCP tests, MCP server/tools, browser simulator, and Trip Scout flight/hotel search modules. The prior project baseline was reported as 13 passing tests; the final locally verified suite is recorded below.

## Commands and results

Environment used Python 3.12 in `/private/tmp/roamready-venv`; dependencies were installed from `requirements.txt`. The repository's clean-environment setup is:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m pytest -p no:capture -q tests/test_units.py tests/test_roamready_mcp.py
python run_demo.py
```

The exact local test command was `/private/tmp/roamready-venv/bin/python -m pytest -p no:capture -q tests/test_units.py tests/test_roamready_mcp.py`. It passed 16 tests (unit, mock provider, MCP Streamable HTTP and integration coverage). `-p no:capture` is required in this environment because pytest's default capture plugin failed in the installed runtime; this does not skip tests.

Launched the documented app with `TRIP_SCOUT_DB=/private/tmp/roamready-release-demo.db /private/tmp/roamready-venv/bin/python run_demo.py --no-browser`. The local web simulator completed plan → rescue → provider outage → reset. The MCP handshake negotiated protocol version `2025-11-25`; `tools/list` exposed the demo tools; `tools/call` returned structured plan, rescue comparison, and fallback results.

Observed deterministic two-person, four-day result: €620 airfare + €480 lodging + €280 meals + €80 local transport + €252 activities = €1,712 total of €1,800, €88 remaining, 159 estimated local-travel minutes. On the simulated Sagrada Família closure, the replanned estimate was €1,638 (−€74), €162 remaining (+€74), and 127 minutes (−32). The simulated provider 503 was caught and the offline planner returned successfully. Reset cleared the session and per-user demo memory.

## Flight and hotel search path

Reviewed `trip_scout/flights.py` and `trip_scout/hotels.py` along with their callers. Both use unofficial web search integrations and are network-dependent; they do not claim a provider API or guaranteed live availability. Added/verified mocked success and provider-503 tests for the provider adapter path and fallback handling. No live search request was sent: no authorized credentials or permission to contact/charge providers were supplied, and these unofficial sources should not be exercised against external services for this audit. `tests/smoke_mcp.py` was not run because it intentionally makes external requests.

## Integrity and claims

- No committed `.env` file or hardcoded API key was found. `.env` is ignored; `.env.example` contains placeholders/configuration only.
- The repo reports no real flight/hotel quotes, booking, official Amazon certification, restricted Alexa+ preview access, public deployment, or physical Alexa device integration.
- MCP server path uses MCP spec `2025-11-25` over Streamable HTTP. Simulator is a locally hosted browser MCP client.
- Demo data and disruption/provider failure are explicitly simulated. Booking and live availability are outside scope.
- Upstream Trip Scout files and their license/attribution are preserved. The separate unlicensed Alexa Trip Planner repository was not copied into this product.

## Remaining limits

No public hosting account, external API authorization, or credentials were available or needed for the local demo. The `curl_cffi` binary wheel did not load in this environment; the flight/hotel modules now fall back to `requests`. Integration results use mocks and local loopback, not live supplier evidence. Before real deployment, add authenticated access, strict host/origin controls, production persistence, licensed data feeds and a fresh legal/terms review.
