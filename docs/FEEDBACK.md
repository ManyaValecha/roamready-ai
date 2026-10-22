# Draft product feedback — RoamReady AI

These observations come from the local implementation and a clean Python 3.14.8 install/test run on 22 October 2026. The entrant should confirm they match their own development experience before copying into Devpost. We did not use AWS, an Amazon Alexa SDK, Alexa+ preview tools, or a real supplier API; no feedback is claimed for those.

| Tool / API / SDK | What it did | What worked and onboarding | What needs work / concrete suggestion | Use again? |
|---|---|---|---|---|
| MCP Python SDK (`mcp` 1.30.0), FastMCP and Streamable HTTP | Hosted typed tools and resources; browser app connected as an MCP client. | Fresh venv install from `requirements.txt` was straightforward. FastMCP exposed tool schemas and the local `initialize`, `tools/list`, and `tools/call` path passed in an integration test. | The SDK emitted a deprecation warning for `streamablehttp_client`; switching the test to the documented `streamable_http_client` removed all four warnings. Clearer migration notes and an explicit deprecation version would help. | Yes. The typed protocol and local transport make the workflow testable without claiming Alexa device access. |
| Starlette / Uvicorn | Served the local browser simulator and proxied MCP calls. | One command starts both local services; no cloud setup is needed for the deterministic demo. | The app owns user-facing request errors and cross-origin deployment configuration; local success does not prove hardened public deployment. A concise production security checklist for deployment would help. | Yes for a local prototype; reassess before public exposure. |
| SQLite (`sqlite3`) | Stored travel memory, saved trips and price watches. | Built-in Python support made local persistence easy to run and test. | Single-node persistence is not suitable for replicated deployment; a migration guide for shared storage would help. | Yes for a local/demo app. |
| pytest | Ran unit, mocked-provider and local MCP integration coverage. | Setup is in the same requirements file and tests are quick to run. | The client API deprecation warning was easy to miss in a green test run; make deprecations actionable in docs and examples. | Yes. |
| Requests / curl_cffi in retained Trip Scout search engines | HTTP transport for optional public Google Travel result-page parsing. | The code has a requests fallback; transport paths can be tested with mocks. | This is unofficial page parsing, not an authorized supplier API; no live requests were made in this audit, so there is no verified provider reliability/terms feedback. Prefer documented, licensed supplier feeds. | No for production until terms and a supported feed are verified; no live service recommendation is made. |

## Optional Devpost friction log entry

Rules list optional friction-log entries and say they may add up to 10% to judging. The following is based on a warning actually emitted in the MCP integration test, not on an unattempted preview signup or unverified provider call.

- **Task:** Run the Streamable HTTP MCP integration test.
- **Steps:** Install `requirements.txt` in a clean virtual environment; run `python -m pytest -q tests/test_units.py tests/test_roamready_mcp.py`.
- **Expected:** 16 tests pass without obsolete client API warnings.
- **Actual:** 16 tests passed, but the integration test emitted four `DeprecationWarning: Use streamable_http_client instead` warnings because it imported `streamablehttp_client`.
- **Severity:** Low; did not block test or demo execution.
- **Workaround:** Changed the test import and invocation to `streamable_http_client`; reran the suite with 16 passed and no warnings.
- **Actionable suggestion:** Add the replacement import and a migration example to the MCP Python SDK Streamable HTTP client docs; make deprecation behavior/version clear.
