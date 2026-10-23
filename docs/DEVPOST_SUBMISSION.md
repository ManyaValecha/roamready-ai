# Devpost Official Submission Package — RoamReady AI

## Project Name
**RoamReady AI — Autonomous Itinerary & Rescue Agent (Streamable HTTP MCP)**

## Elevate Pitch / One-Liner
An Alexa+ integrated travel agent built with Streamable HTTP MCP that plans optimized multi-day itineraries, tracks flight prices, and instantly executes budget rescues when flight delays or travel disruptions occur.

## Inspiration
Travel planning is fragmented, and flight disruptions cost travelers hours of stress. Traditional assistants provide static text suggestions; RoamReady AI leverages the Model Context Protocol (MCP) to perform deterministic cost calculations, route comparisons, and automated itinerary rescues directly through natural voice/chat tools.

## What It Does
- **Multi-Day Itinerary Planning:** Generates complete travel itineraries within strict daily budgets and preferences.
- **Flight & Hotel Package Search:** Compares round-trip fares across custom travel windows and matches well-rated hotels.
- **Live Price Watches:** Tracks price drops across routes and notifies travelers when fares cross target thresholds.
- **Instant Itinerary Rescue:** Recalculates cost and time metrics during flight delays or missed connections, providing a side-by-side before/after comparison.
- **Alexa+ & MCP Native Integration:** Exposes all capabilities as Streamable HTTP MCP tools compliant with open standards.

## How We Built It
- **MCP Server:** FastMCP & Starlette transport delivering Streamable HTTP tools with optional Bearer token security.
- **State & Memory Management:** SQLite persistent storage for traveler profiles, saved trips, and active price watches.
- **Web Simulator UI:** Custom Starlette/HTML5 web interface mimicking the Alexa+ Agent Skill execution environment.
- **Testing & Security:** 43 automated regression tests covering numeric validation (`math.isfinite`), exception masking, and HTTP auth middleware.

## Challenges We Ran Into
Handling ephemeral storage in serverless deployment environments (Vercel) required clear architecture separation between in-memory/demo states and local SQLite persistence. Standardizing MCP progress reporting across asynchronous tool invocations also required robust transport handling.

## Accomplishments That We're Proud Of
- 100% test coverage across numeric boundary checks, auth security, and tool serialization.
- Fully operational Streamable HTTP MCP server adhering to the open Model Context Protocol spec.
- Seamless before/after budget metrics execution in the rescue flow.

## What We Learned
Designing agentic skills around open MCP standards significantly simplifies multi-tool coordination and enables seamless deployment across both simulated web clients and real hardware devices.

## GitHub Collaborators Required by Amazon Track
Ensure these handles are added in Repository Settings -> Collaborators:
- `knmeiss`
- `giolaq`
- `anishamalde`
- `mosesroth`
- `emersonsklar`
