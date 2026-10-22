# Hackathon submission packet

## Official requirements rechecked 22 October 2026

- **Deadline:** October 23, 2026 at 12:00 p.m. PDT (19:00 UTC; October 24 at 12:30 a.m. IST).
- **Track:** Alexa+. Eligible implementation paths include a working Agent Skill or a self-hosted MCP server using MCP 2025-11-25 or later over Streamable HTTP; an own-web-client simulated experience is also permitted. Source and demonstration must prove the chosen path. The code imports and calls FastMCP and the browser client performs actual protocol calls; local integration test negotiated 2025-11-25.
- **Required entry material:** project text description; GitHub repository URL with source, assets and setup instructions; public YouTube or Vimeo video under three minutes showing the project running on its intended platform; Product Feedback for each tool/API/SDK used; primary track and mini-challenge selection. Team entrants appoint an authorized representative. The actual logged-in form may expose additional fields; inspect it before submit.
- **GitHub:** Rules require a GitHub repository. Public repository must include an open-source license visible at the top/About. Private repository must be shared with the listed Devpost address and Amazon reviewers `knmeiss`, `giolaq`, `anishamalde`, `mosesroth`, and `emersonsklar`; invitees must accept. This repo has an MIT LICENSE. The maintainer must ensure the GitHub About/license metadata also displays correctly after publishing.
- **Demo video:** publicly viewable on YouTube or Vimeo, under 3:00, show the functioning project, and exclude third-party trademarks/copyrighted media unless rights are held.
- **Optional fields:** feature requests and friction-log entries. The rules say friction logs can add up to 10% to judging; a factual, evidenced entry is drafted in [docs/FEEDBACK.md](docs/FEEDBACK.md). Do not copy it unless it matches the entrant's own experience.
- **New/existing work:** if this project existed before the Submission Period began, rules require significant updates after August 31, 2026 and an explanation/demo of those changes. RoamReady updates made for this entry add the four-day constrained demo, personalized interests/party size, simulated total-budget breakdown, structured MCP disruption-rescue comparison, provider-failure fallback, reproducible reset, and tested simulator flow. The entrant should confirm project provenance/timing and describe the update truthfully.
- **No AWS Builder claim:** no AWS service or Kiro Crew integration is present. No Open Source mini-challenge claim is prepared: no separate qualifying public-repository contribution during the window is documented.
- **No restricted access claims:** Alexa+ add-on tools are preview-only for select partners according to the FAQ; its guidance explicitly permits a self-built web MCP client. Hosting is not required. This project does not claim Alexa+ preview access, Amazon certification, Alexa device connection, public deployment, live travel quotes or bookings.

Official references: [Devpost rules](https://amazonappdev2026.devpost.com/rules) · [Devpost FAQ](https://amazonappdev2026.devpost.com/details/faqs). Recheck both and the logged-in submission form immediately before filing.

## Submission-ready drafts

**Project title**

RoamReady AI — A city trip that adapts when plans change

**Short description**

RoamReady is a local travel-planning agent for people balancing interests, a hard trip budget and unexpected closures. It builds a four-day Barcelona itinerary for two, then replans after a simulated landmark closure and shows the before/after budget and local travel-time changes. A browser MCP client calls a self-hosted Streamable HTTP server and renders its structured results. The demo is deterministic; prices, venue details, disruption and travel times are simulated estimates, and no reservation is made.

**Problem / target user**

Independent travelers planning short city breaks have to fit activities, meals, lodging and transport inside a budget, then manually rebuild plans when an attraction becomes unavailable. RoamReady demonstrates a clear plan-and-recovery workflow for travelers who want to inspect both recommendations and tradeoffs.

**What is original / what changed**

Built on the MIT-licensed Trip Scout foundation, RoamReady adds an offline, deterministic Barcelona scenario; party-size and interest-aware day planning; a complete simulated trip cost breakdown; a simulated disruption rescue with original/revised itinerary and cost/time deltas; local provider-failure recovery; and an Alexa+-style browser host that visibly makes real MCP calls. This distinct conversational rescue flow and its repeatable UI were implemented for the hackathon entry; the entrant should verify dates/provenance before making a personal authorship statement.

**How the required technology is used**

The local browser simulator is an MCP client. It initializes a Streamable HTTP connection to the self-hosted FastMCP server, discovers tools with `tools/list`, and invokes `plan_demo_trip`, `rescue_demo_trip_tool`, and `simulate_provider_failure` with `tools/call`. The server returns structured content used by the itinerary and comparison cards. The integration test verifies protocol version `2025-11-25`. The simulator is not an Amazon Alexa device or the gated Alexa+ preview client.

**Built With**

Python, MCP Python SDK / FastMCP, MCP Streamable HTTP, Starlette, Uvicorn, SQLite, HTML/CSS/JavaScript, pytest, and the MIT-licensed Trip Scout foundation. No AWS service or Alexa+ preview SDK was used.

**Friction log**

Use the single factual MCP SDK deprecation entry in [docs/FEEDBACK.md](docs/FEEDBACK.md) only if the entrant confirms it reflects their own work.

**Demo video**

Record to the 2:40 run-of-show in [DEMO.md](DEMO.md), publish publicly on YouTube or Vimeo, verify the final duration is under three minutes, and paste the video URL in the form.

## Manual publishing and submission checklist

- [ ] Confirm entrant eligibility, team representative authority, repository provenance and hackathon-period update dates.
- [ ] Review latest rules and actual logged-in Devpost fields; submit before the deadline.
- [ ] Create/publish the GitHub repository. Choose public with MIT license visible in the About area, or private and share with the exact Devpost/Amazon reviewers; verify invitations are accepted.
- [ ] Confirm source, tests, screenshot/media, attribution, setup docs and local demo are included; paste GitHub URL.
- [ ] Record the working UI and MCP trace, publish video publicly to YouTube/Vimeo, and paste its URL.
- [ ] Add current screenshots/media to Devpost; avoid presenting old package-result sample cards as live prices.
- [ ] Fill Product Feedback from the entrant's actual experience and attach only factual friction entries.
- [ ] Select Alexa+ primary track; select no mini-challenge unless eligibility is independently supported.
- [ ] Complete title, project description, team/representative and any additional fields shown in the form.
- [ ] Review all links and disclosures, submit, and retain the confirmation page/email.

The repository is not published and the entry is not filed. Those steps require the entrant's GitHub/Devpost/YouTube or Vimeo accounts and final approval.
