# Competition readiness audit — 22 October 2026

## Scope

Inspected source and docs rather than relying on the prior audit: `README.md`, `FEATURE_MATRIX.md`, `DEMO.md`, `SUBMISSION.md`, `.env.example`, `.gitignore`, `requirements.txt`, `run_demo.py`, both pytest modules, MCP implementation/client, browser simulator, reset flow, and `trip_scout/engines/flights.py` / `hotels.py`. Rechecked the current [official rules](https://amazonappdev2026.devpost.com/rules) and [FAQ](https://amazonappdev2026.devpost.com/details/faqs).

## Fresh setup and tests

A new Python 3.14.8 environment at `/private/tmp/roamready-comp-venv` installed `requirements.txt` successfully, including MCP Python SDK 1.30.0. Commands:

```sh
python3 -m venv /private/tmp/roamready-comp-venv
/private/tmp/roamready-comp-venv/bin/python -m pip install -r requirements.txt
/private/tmp/roamready-comp-venv/bin/python -m pytest -q tests/test_units.py tests/test_roamready_mcp.py
```

Result: **16 passed in 0.73 seconds, no warnings** after migrating the integration test from deprecated `streamablehttp_client` to `streamable_http_client`. Both the standard pytest capture run and the prior `-p no:capture` run passed; the current documented command is the standard pytest form. Provider success/503 tests are mocked and make no external request.

The clean demo was launched after copying/sourcing `.env.example` with an isolated `/private/tmp/roamready-competition-demo.db`:

```sh
cp .env.example .env
set -a; source .env; set +a
TRIP_SCOUT_DB=/private/tmp/roamready-competition-demo.db /private/tmp/roamready-comp-venv/bin/python run_demo.py --no-browser
```

Observed MCP server at `http://127.0.0.1:8765/mcp` and browser simulator at `http://127.0.0.1:8770`. In the browser, I ran the plan, closure rescue, simulated outage, and reset chips in sequence. The accessible tree showed the user prompt, `tools/call` names and JSON arguments, structured results, both comparison cards, explicit `€1,712 → €1,638 (€74 less)`, remaining budget `€88 → €162 (€74 more)`, and local travel `159 → 127 min (32 min fewer)`. Cost assumptions expand on demand. Reset returned the app to the problem statement and cleared the current session/memory.

MCP integration test uses the `mcp` Python SDK client against the locally started server; it asserted protocol version `2025-11-25` or later, tool discovery and structured calls to `plan_demo_trip`, `rescue_demo_trip_tool`, and `simulate_provider_failure`. The server source uses FastMCP and `transport="streamable-http"`; the browser invokes initialize, `tools/list` and `tools/call` over its MCP client transport. This is source-level and loopback verification, not Amazon Alexa connectivity.

## Material improvements in this readiness pass

- Changed the landing screen to state the traveler problem and plan-recovery value immediately.
- Replaced generic chip spans with keyboard-operable buttons; named the input/mic, added focus rings and polite status/log announcements.
- Made network/HTTP errors and browser speech failures fall back to clear typed-input instructions; reset success and failure are announced.
- Made before/after totals, remaining budgets and travel times include values and plain-language direction; exposed the fixed simulated cost assumptions.
- Removed the dated package-search screenshot because its price cards could be mistaken for current quotes; README tells the entrant to capture current UI from the backend run.
- Corrected the configured SQLite example path to match the code fallback and corrected stale “live results verified” wording in the feature matrix.
- Migrated the deprecated MCP Python client helper, eliminating all four warnings.
- Reworked the demo run-of-show to cold-open on the rescue result and complete the flow under three minutes.

## Search paths and limits

Inspected the optional flight/hotel engines and callers. They parse public Google Travel result pages via unofficial integrations. This audit did **not** make live flight/hotel requests: no supplier authorization/credentials or terms review was available. Mocked success and 503 responses verify transport handling only, not provider availability or legal permission. `tests/smoke_mcp.py` was intentionally not run because it makes external search requests. No charges were incurred.

Secret scan performed over source with patterns for Google API keys, AWS access IDs, OpenAI-style keys and literal API-key assignments; no matches were returned. `find` found no committed `.env`, PEM or key files. `.env.example` contains empty optional LLM/token fields and sample configuration; `.env` is ignored. A temporary ignored `.env` was created only to run the documented setup and will be removed from the working tree after audit.

No real quote, confirmed venue opening, booking, purchase, Alexa device, restricted Alexa+ preview, official certification, AWS integration, or public deployment was verified or is claimed. Upstream MIT notices are preserved. The other cloned source project had no license and was not copied. Old dated package screenshot was removed rather than presented as current visual evidence.

## Rules and submission checks

Rules currently show the deadline as **October 23, 2026 at 12:00 p.m. PDT**. They require a GitHub repository, a text project description, a public YouTube/Vimeo demo under three minutes, Product Feedback for each tool/API/SDK, and primary/mini-challenge selections; optional friction logs can add up to 10% judging. Public source must include a visible open-source license; private source must be shared with the listed reviewers. Existing projects must have a significant update after the submission period begins and explain/demo it. The FAQ says local runnable source plus video suffices, no public hosting is required, and a self-built web MCP client is allowed. Do not claim mini-challenge or preview eligibility without evidence.

## Remaining limitations

The plan catalog and all cost/hour/routing/closure data are illustrative; no licensed venue/routing/alert feeds. Optional supplier results are unofficial and unvalidated. Production deployment would require access controls, HTTPS, strict host/origin settings, durable multi-instance storage and legal/terms review. The repo has no current backend-generated UI screenshot because the previous screenshot was stale and potentially misleading; record a fresh current view for the entry video/media. Entrant must verify team eligibility, update timing/provenance, own GitHub/Devpost/media accounts, and final form fields before submitting.
