# Product feedback and friction log — RoamReady AI

Draft based on this implementation and local build; edit to reflect the entrant's own hackathon experience before submission.

| Tool / component | Use | What worked | Friction / follow-up |
|---|---|---|---|
| MCP Python SDK / FastMCP | Self-hosted Streamable HTTP server, typed tools, resources | Local `initialize`, `tools/list`, `tools/call` worked end-to-end; generated tool schemas made the new tools immediately discoverable | Pin/verify exact runtime version at release; remote OAuth onboarding and hosting security need a separate production review |
| Streamable HTTP MCP client | Browser simulator connects to MCP and renders resources/results | The same user request and result can be inspected in the visible trace | Cross-origin deployment needs exact host/origin allow-lists and secret configuration |
| SQLite | Per-user profiles, price watches and saved trips | Simple durable local state without an AWS account | SQLite is single-node state; migrate for multiple replicas |
| Trip Scout upstream search engines | Flight and hotel search-result lookups | Reuses an existing, MIT-licensed implementation without API keys | These are unofficial search-result integrations, not official licensed provider APIs. Review applicable terms and use authorized feeds before production; results are volatile and network-dependent |
| Native browser speech APIs | Optional mic and spoken replies | Degrades to typed input if recognition is unavailable | Recognition/voice availability varies by browser and OS |
| RoamReady deterministic catalog | Reproducible local itinerary/rescue demo | Works without live services and clearly labels illustrative data | Replace with licensed venue, routing, opening-hours, accessibility and alert feeds before real-world trip use |

This project did not integrate an AWS service or Alexa+ private preview tools. Do not submit feedback as if those services were tested.
