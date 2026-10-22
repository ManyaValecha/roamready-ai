# Hackathon submission packet

## Official rules checked 22 October 2026

- Deadline: **October 23, 2026 at 12:00 p.m. Pacific Daylight Time** (19:00 UTC; **October 24 at 12:30 a.m. India Standard Time**).
- Submit through the Devpost entry form. Include project title/description, GitHub repository URL, project media/screenshots, a publicly viewable YouTube or Vimeo demo video under 3 minutes, product feedback about developer tools/products used, and the applicable challenge/track selections. Complete the team/representative information the live form requests.
- Public GitHub repositories need a visible open-source license. A private repository is permitted if it is shared with the Amazon and Devpost reviewers specified in the rules. This repository includes the preserved MIT license and attribution for Trip Scout-derived work.
- The Alexa+ MCP path requires MCP specification version **2025-11-25 or later** over **Streamable HTTP**. RoamReady's server advertises 2025-11-25; the local simulator is an allowed simulated web client. The demo demonstrates actual initialize, tools/list and tools/call traffic.
- The official FAQ describes Alexa+ toolkit access as preview-only for selected partners, permits a self-built web MCP client simulation, and says public hosting is not required. This entry makes no restricted preview, certification, live Alexa device or public deployment claim.
- Product feedback is required. Use/adapt the factual observations in [docs/FEEDBACK.md](docs/FEEDBACK.md); entrant should confirm they reflect their own experience.
- Do not select an AWS Builder mini-challenge (no AWS integration) or Open Source mini-challenge (no distinct qualifying contribution documented) unless the entrant independently verifies eligibility.

Official references: [Devpost rules](https://amazonappdev2026.devpost.com/rules) · [Devpost FAQ](https://amazonappdev2026.devpost.com/details/faqs). Recheck the live form immediately before submitting in case its fields/rules have changed.

## Submission-ready copy

**Title:** RoamReady AI — Budget-first city trips, ready for a change of plans

**Short description:** A local web MCP travel agent that turns a party size, interests and a strict budget into a four-day Barcelona itinerary, then replans when a simulated disruption hits—showing every cost and travel-time change.

**Problem and users:** Travelers planning short city breaks often have to reconcile competing interests, a fixed budget and a last-minute closure across disconnected tools. RoamReady is for independent travelers who want a useful first itinerary and a clear recovery option without opaque recommendations.

**Solution and distinctive contribution:** RoamReady combines the preserved Trip Scout planning/search foundation with an Alexa+-style local web simulator, a real Streamable HTTP MCP server, structured itinerary and cost output, and a deterministic disruption rescue workflow. The added demo mode gives judges a repeatable four-day, two-person €1,800 Barcelona scenario, a before/after rescue comparison, transparent simulated costs and a provider-outage recovery path. All demo prices, venue availability and travel times are estimates; no booking is made.

**How MCP is used:** The browser simulator acts as an MCP client. It initializes a Streamable HTTP session, discovers tools with `tools/list`, and calls `plan_demo_trip`, `rescue_demo_trip_tool`, and `simulate_provider_failure` via `tools/call`. The server returns structured results rendered in the itinerary view and visible activity trace. It targets MCP 2025-11-25.

**Built With:** Python, FastMCP / MCP Python SDK, Streamable HTTP, Starlette, SQLite, vanilla JavaScript/HTML/CSS, pytest, and the MIT-licensed Trip Scout source foundation.

**Demo video plan (2:30):** 0:00 identify local simulation/MCP; 0:20 submit Barcelona request and show tool call, structured itinerary and €1,712 breakdown; 1:05 trigger clearly simulated Sagrada Família closure and show €74/32-minute reduction; 1:45 inject simulated provider 503 and show offline recovery; 2:15 reset and disclose no live quotes/bookings/device integration. Keep under three minutes and publish viewable on YouTube or Vimeo.

## Entrant checklist

- [ ] Review final rules and complete the Devpost form before deadline.
- [ ] Create a public GitHub repository (or share a private repository with the designated reviewers); confirm LICENSE, source, screenshot, setup and attribution are visible.
- [ ] Upload a publicly viewable demo video under 3 minutes; paste URL into entry.
- [ ] Add screenshots/project media from the running app.
- [ ] Fill product feedback based on entrant's actual use of the tools.
- [ ] Enter team and representative information as requested by the form.
- [ ] Select the appropriate Alexa+ track; only claim mini-challenges with evidence.
- [ ] Verify repository URL, video URL, screenshots, team fields and final Devpost confirmation receipt.

The repository is not published and the submission has not been filed. Those steps require the entrant's accounts and final review.
