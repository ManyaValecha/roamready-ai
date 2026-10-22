# Verified feature integration matrix

| Capability | Original Alexa Trip Planner (`praveenvvstgy/trip-planner-alexa-skill`) | Trip Scout (`janik4321sdfa/trip-scout`) | RoamReady AI |
|---|---|---|---|
| Attraction itinerary | Verified: city attraction query, distance matrix, greedy TSP ordering and time-limited route in `planner.py`; requires Google/Foursquare credentials | Not part of implemented tool set; its planner focuses on flights/hotels | New deterministic Barcelona attraction plan; interest, estimated budget, step-free filter, opening-window checks and area travel-time ordering |
| Round-trip travel packages | Not found | Verified: date-window flight search + hotel matching + package ranking (`plan_trip`) | Retained from Trip Scout |
| Flight/hotel search | Not found | Source implements unofficial Google Travel result-page parsing | Retained experimental parsing; this audit tested transport with mocks only. No live supplier result/terms validation is claimed. |
| Persistent profile | Not found | Verified SQLite user profile and saved trip records | Retained, plus explicit delete-memory tool |
| Price tracking | Not found | Verified SQLite watches and history; a recheck calls the flight search | Retained |
| Alexa integration | Alexa Skills Kit Lambda request/response handler is implemented; no evidence of new Alexa+ MCP | MCP server and Alexa+-style web host; no private Alexa+ preview integration | Self-hosted MCP and web simulation, never represented as real device integration |
| MCP Streamable HTTP | Not found | Verified MCP server and dependencies/README specify 2025-11-25 + Streamable HTTP | Retained; adds itinerary and rescue tool calls |
| Disruption rescue | Not found | Not found | New deterministic closure/weather scenarios; no live alert feed |
| Explainability / budget | Route text/card, but not a budget optimizer | Package totals and budget ranking | Package totals retained; itinerary explains stop choices, estimates, travel time and budget changes |
| Confirmation / bookings | No booking implementation found | Search and watch tools only; no booking implementation found | No purchase/reservation tool; thus cannot claim a booking occurred |
| Source license | No LICENSE file found in clone. Source not copied. It also contains hardcoded third-party credentials that were not copied. | MIT (`LICENSE`) | Includes Trip Scout MIT notice. RoamReady additions are original. |

The originals were cloned separately under `work/originals/` and left unchanged. The older repository has vendored dependency source in its tree; it was not moved into the deliverable. Feature evidence was read from source files, not repository descriptions alone.
