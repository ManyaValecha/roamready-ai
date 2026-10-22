"""Trip Scout MCP server - MCP spec 2025-11-25 over Streamable HTTP, with an MCP Apps (SEP-1865) view.

Run:  python -m trip_scout.server            (listens on http://127.0.0.1:8765/mcp)
Env:  TRIP_SCOUT_PORT, TRIP_SCOUT_HOST, TRIP_SCOUT_TOKEN (optional bearer auth), TRIP_SCOUT_ALLOWED_HOSTS,
      TRIP_SCOUT_DB (SQLite path for profiles / price watches)
"""
import datetime as dt
import math
import os
import re

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .dates import parse_date, parse_window
from .places import Places
from .planner import Planner, _short_flight, _short_hotel
from .store import Store
from .roamready import build_demo_trip, build_itinerary, rescue_demo_trip, rescue_itinerary

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW_URI = "ui://roamready-ai/view.html"
UI_META = {"ui": {"resourceUri": VIEW_URI}}
PORT = int(os.environ.get("PORT", os.environ.get("TRIP_SCOUT_PORT", "8765")))
HOST = os.environ.get("TRIP_SCOUT_HOST", "127.0.0.1")

INSTRUCTIONS = """Trip Scout plans trips by voice. It searches real Google Flights and Google Hotels data.
- Use plan_trip when the user wants a whole trip (flights + hotel), especially with a budget or flexible dates.
- Use find_cheapest_dates when the user asks when it is cheapest to fly.
- Use search_flights / search_hotels for specific dates.
- Use watch_price to track a fare; check_price_watches reports drops across sessions.
- Remember the traveler's home airport and preferences with set_travel_profile; never ask for them again once saved.
Every tool returns a short `speech` field written for a voice assistant - read it out as is."""

places = Places()
store = Store()
planner = Planner()
security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=os.environ.get("TRIP_SCOUT_ALLOWED_HOSTS", f"127.0.0.1:{PORT},localhost:{PORT}").split(","),
    allowed_origins=os.environ.get("TRIP_SCOUT_ALLOWED_ORIGINS", f"http://127.0.0.1:{PORT},http://localhost:{PORT},http://127.0.0.1:8770,http://localhost:8770").split(","),
)
mcp = FastMCP("roamready-ai", instructions=INSTRUCTIONS, host=HOST, port=PORT, transport_security=security,
              stateless_http=os.environ.get("TRIP_SCOUT_STATELESS_HTTP") == "1")


# ------------------------------------------------------------------ helpers
def _user(ctx):
    try:
        req = ctx.request_context.request
        return (req.headers.get("x-user-id") or "default")[:64] if req is not None else "default"
    except Exception:
        return "default"


def _result(speech, data):
    data = dict(data, speech=speech)
    return CallToolResult(content=[TextContent(type="text", text=speech)], structuredContent=data)


def _error(speech):
    return CallToolResult(content=[TextContent(type="text", text=speech)], structuredContent={"kind": "error", "speech": speech}, isError=True)


@mcp.tool(title="Build a constraint-aware day plan", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def plan_local_itinerary(ctx: Context, days: int = 3, activity_budget: float = 120, interests: list[str] | None = None, step_free_access: bool = False) -> CallToolResult:
    """Create an illustrative Barcelona itinerary, balancing interests, activity budget, opening windows, travel time and step-free access. Demo catalog only."""
    if days < 1 or days > 7 or activity_budget < 0 or activity_budget > 100000:
        return _error("Choose 1–7 days and a non-negative activity budget.")
    data = build_itinerary(days, activity_budget, interests, step_free_access)
    return _result(f"I planned {days} days in Barcelona with estimated activities at ${data['estimatedActivityCost']:.0f}, leaving ${data['remainingBudget']:.0f} in the activity budget. These are illustrative estimates.", {"kind":"itinerary", **data})


@mcp.tool(title="Plan the Barcelona demo trip", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def plan_demo_trip(ctx: Context, days: int = 4, travelers: int = 2, trip_budget_eur: float | None = None,
                         interests: list[str] | None = None, step_free_access: bool | None = None) -> CallToolResult:
    """Build a reproducible four-day Barcelona demo for two travelers with a strict total EUR budget. ALL prices, hours and travel times are simulated estimates, never live quotes."""
    profile = store.get_profile(_user(ctx))
    trip_budget_eur = profile.get("tripBudgetEUR", 1800) if trip_budget_eur is None else trip_budget_eur
    interests = profile.get("interests") if interests is None else interests
    step_free_access = profile.get("stepFreeAccess", False) if step_free_access is None else step_free_access
    if days < 1 or days > 7 or travelers < 1 or travelers > 8 or trip_budget_eur < 0 or trip_budget_eur > 100000:
        return _error("Choose 1–7 days, 1–8 travelers and a non-negative EUR trip budget.")
    data = build_demo_trip(days, trip_budget_eur, travelers, interests, accessible=step_free_access)
    return _result(f"I built a {days}-day Barcelona estimate for {travelers} travelers: €{data['estimatedTotal']:.0f} of the €{trip_budget_eur:.0f} budget. This entire demo cost breakdown is simulated, not a live quote.", data)


@mcp.tool(title="Replan the Barcelona demo after a disruption", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def rescue_demo_trip_tool(ctx: Context, days: int = 4, travelers: int = 2, trip_budget_eur: float = 1800,
                               interests: list[str] | None = None, disruption: str = "Sagrada Família closure",
                               step_free_access: bool | None = None) -> CallToolResult:
    """Show before/after Barcelona itineraries and transparent estimated cost/time deltas after a simulated closure or weather disruption."""
    if days < 1 or days > 7 or travelers < 1 or travelers > 8 or trip_budget_eur < 0 or trip_budget_eur > 100000:
        return _error("Choose 1–7 days, 1–8 travelers and a non-negative EUR trip budget.")
    profile = store.get_profile(_user(ctx))
    interests = profile.get("interests") if interests is None else interests
    step_free_access = profile.get("stepFreeAccess", False) if step_free_access is None else step_free_access
    data = rescue_demo_trip(days, trip_budget_eur, travelers, interests, disruption, step_free_access)
    before, after, delta = data["before"], data["after"], data["changes"]
    travel_delta = delta["travelMinutesDelta"]
    travel_change = ("estimated travel time is unchanged" if travel_delta == 0 else
                     f"{abs(travel_delta)} estimated travel minutes {'fewer' if travel_delta < 0 else 'more'}")
    speech = (f"Simulated disruption: {disruption}. The revised trip estimate is €{after['estimatedTotal']:.0f}, "
              f"€{abs(delta['estimatedCostDelta']):.0f} {'less' if delta['estimatedCostDelta'] < 0 else 'more'} than before, "
              f"with {travel_change}. Both versions remain within the €{trip_budget_eur:.0f} limit.")
    return _result(speech, data)


@mcp.tool(title="Simulate a provider outage and recover offline", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def simulate_provider_failure(ctx: Context, days: int = 4, travelers: int = 2, trip_budget_eur: float = 1800,
                                    interests: list[str] | None = None, step_free_access: bool = False) -> CallToolResult:
    """Inject a local simulated provider 503, then recover with the offline demo planner. Makes no network requests; all returned costs are simulated."""
    if days < 1 or days > 7 or travelers < 1 or travelers > 8 or trip_budget_eur < 0 or trip_budget_eur > 100000:
        return _error("Choose 1–7 days, 1–8 travelers and a non-negative EUR trip budget.")
    try:
        raise RuntimeError("Injected simulated 503 provider outage")
    except RuntimeError as exc:
        data = build_demo_trip(days, trip_budget_eur, travelers, interests, accessible=step_free_access)
        data.update(kind="provider-fallback", providerStatus="simulated failure", failure=str(exc), recoveredOffline=True)
        return _result("The flight data provider is simulating an outage. I recovered using the offline Barcelona estimate; costs and availability are illustrative.", data)


@mcp.tool(title="Rescue an itinerary from a disruption", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def rescue_itinerary_tool(ctx: Context, days: int = 3, activity_budget: float = 120, interests: list[str] | None = None, step_free_access: bool = False, disruption: str = "Sagrada Família closed") -> CallToolResult:
    """Rebuild a demo Barcelona itinerary after a closure or weather disruption; estimates are simulated, not live alerts."""
    if days < 1 or days > 7 or activity_budget < 0 or activity_budget > 100000:
        return _error("Choose 1–7 days and a non-negative activity budget.")
    data = rescue_itinerary(days, activity_budget, interests, step_free_access, disruption)
    return _result(f"I replanned for {disruption}. Removed affected stops and rebuilt the schedule. Prices, status and timings in this demo are illustrative.", {"kind":"rescue", **data})


def _money(v, cur):
    if v is None:
        return "an unknown price"
    sym = {"USD": "$", "EUR": "€", "GBP": "£"}.get(cur)
    v = int(round(v))
    return f"{sym}{v:,}" if sym else f"{v:,} {cur}"


def _spoken_date(d):
    d = d if isinstance(d, dt.date) else dt.date.fromisoformat(d)
    return d.strftime("%A, %B ") + str(d.day)


def _place(text, what):
    p = places.resolve(text)
    if not p:
        raise ValueError(f"I couldn't find an airport for {text}. Could you name a nearby city?")
    return p


def _origin(ctx, origin):
    if origin:
        return _place(origin, "origin")
    home = store.get_profile(_user(ctx)).get("homeAirport")
    if home:
        return {"code": home, "label": places.label(home)}
    raise ValueError("Where will you be flying from? You can also say: my home airport is, for example, Chicago.")


async def _run(fn, *a, **kw):
    return await anyio.to_thread.run_sync(lambda: fn(*a, **kw))


# ------------------------------------------------------------------ MCP Apps view
@mcp.resource(VIEW_URI, name="trip_scout_view", title="RoamReady AI", description="Echo Show style cards for flights, cheapest dates, hotels, trip packages and price watches.",
              mime_type="text/html;profile=mcp-app", meta={"ui": {"prefersBorder": False, "csp": {"resourceDomains": ["https://lh3.googleusercontent.com", "https://*.gstatic.com"]}}})
def view() -> str:
    with open(os.path.join(HERE, "ui", "view.html"), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ profile (state across sessions)
def _validated_profile_changes(home_airport=None, currency=None, adults=None, children=None,
                               cabin_class=None, nonstop_only=None, min_hotel_rating=None,
                               hotel_stars=None, trip_budget_eur=None, interests=None,
                               step_free_access=None):
    """Validate a complete profile update before the caller writes any part of it."""
    changes = {}
    if home_airport is not None and home_airport != "":
        if not isinstance(home_airport, str):
            raise ValueError("Home airport must be a city, airport name, or IATA code.")
        changes["homeAirport"] = _place(home_airport, "home")["code"]
    if currency is not None:
        if not isinstance(currency, str):
            raise ValueError("Currency must be a three-letter code, such as EUR or USD.")
        normalized_currency = currency.upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
            raise ValueError("Currency must be a three-letter code, such as EUR or USD.")
        changes["currency"] = normalized_currency
    if adults is not None:
        if isinstance(adults, bool) or not isinstance(adults, int) or not 1 <= adults <= 9:
            raise ValueError("Choose 1–9 adults.")
        changes["adults"] = adults
    if children is not None:
        if isinstance(children, bool) or not isinstance(children, int) or not 0 <= children <= 8:
            raise ValueError("Choose 0–8 children.")
        changes["children"] = children
    if cabin_class is not None:
        normalized_cabin = str(cabin_class).lower().replace(" ", "_")
        if normalized_cabin not in {"economy", "premium_economy", "business", "first"}:
            raise ValueError("Choose economy, premium economy, business, or first class.")
        changes["cabinClass"] = normalized_cabin
    if nonstop_only is not None:
        if not isinstance(nonstop_only, bool):
            raise ValueError("Nonstop preference must be true or false.")
        changes["maxStops"] = 0 if nonstop_only else None
    if min_hotel_rating is not None:
        if isinstance(min_hotel_rating, bool) or not isinstance(min_hotel_rating, (int, float)) or not math.isfinite(min_hotel_rating) or not 0 <= min_hotel_rating <= 5:
            raise ValueError("Minimum hotel rating must be between 0 and 5.")
        changes["minHotelRating"] = float(min_hotel_rating)
    if hotel_stars is not None:
        if not isinstance(hotel_stars, list) or not hotel_stars or any(
                isinstance(star, bool) or not isinstance(star, int) or not 1 <= star <= 5
                for star in hotel_stars):
            raise ValueError("Choose one or more hotel star classes from 1 to 5.")
        changes["hotelClasses"] = list(dict.fromkeys(hotel_stars))
    if trip_budget_eur is not None:
        if isinstance(trip_budget_eur, bool) or not isinstance(trip_budget_eur, (int, float)) or not math.isfinite(trip_budget_eur) or not 0 <= trip_budget_eur <= 100000:
            raise ValueError("Choose a EUR trip budget from 0 to 100,000.")
        changes["tripBudgetEUR"] = float(trip_budget_eur)
    if interests is not None:
        allowed = {"architecture", "art", "food", "history", "outdoors"}
        if not isinstance(interests, list):
            raise ValueError("Interests must be a list of supported interests.")
        normalized = list(dict.fromkeys(str(item).lower() for item in interests))
        if not normalized or any(item not in allowed for item in normalized):
            raise ValueError("Choose one or more supported interests: architecture, art, food, history or outdoors.")
        changes["interests"] = normalized
    if step_free_access is not None:
        if not isinstance(step_free_access, bool):
            raise ValueError("Step-free access preference must be true or false.")
        changes["stepFreeAccess"] = step_free_access
    return changes


@mcp.tool(title="Save travel preferences", annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=False))
async def set_travel_profile(ctx: Context, home_airport: str | None = None, currency: str | None = None, adults: int | None = None,
                             children: int | None = None, cabin_class: str | None = None, nonstop_only: bool | None = None,
                             min_hotel_rating: float | None = None, hotel_stars: list[int] | None = None,
                             trip_budget_eur: float | None = None, interests: list[str] | None = None,
                             step_free_access: bool | None = None) -> CallToolResult:
    """Remember the traveler's home airport and preferences so they never have to repeat them.
    cabin_class: economy | premium_economy | business | first. hotel_stars e.g. [4, 5]."""
    try:
        changes = _validated_profile_changes(
            home_airport, currency, adults, children, cabin_class, nonstop_only,
            min_hotel_rating, hotel_stars, trip_budget_eur, interests, step_free_access)
    except (TypeError, ValueError) as e:
        return _error(str(e))
    prof = store.update_profile(_user(ctx), **changes)
    home = places.label(prof["homeAirport"]) if prof["homeAirport"] else "not set"
    speech = f"Got it. Home airport {home}, {prof['adults']} adult{'s' if prof['adults'] > 1 else ''}, {prof['cabinClass'].replace('_', ' ')}" + \
             (", nonstop only" if prof["maxStops"] == 0 else "") + "."
    return _result(speech, {"kind": "profile", "title": "Travel preferences saved", "profile": prof})


@mcp.tool(title="Show travel preferences", annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_travel_profile(ctx: Context) -> CallToolResult:
    """Return the traveler's saved home airport and preferences."""
    prof = store.get_profile(_user(ctx))
    home = places.label(prof["homeAirport"]) if prof["homeAirport"] else "not set yet"
    return _result(f"Your home airport is {home}, and you travel {prof['cabinClass'].replace('_', ' ')}.", {"kind": "profile", "title": "Travel preferences", "profile": prof})


@mcp.tool(title="Forget saved travel memory", annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def forget_travel_memory(ctx: Context) -> CallToolResult:
    """Delete the current user's saved profile, trips and price watches. Use only when the user explicitly asks to forget/delete saved travel data."""
    store.delete_user_memory(_user(ctx))
    return _result("I deleted your saved travel profile, trips and price watches.", {"kind":"profile","title":"Travel memory deleted","profile":store.get_profile(_user(ctx))})


@mcp.tool(title="Review saved trips", annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def list_saved_trips(ctx: Context, limit: int = 10) -> CallToolResult:
    """Show the current user's saved trip summaries so they can inspect what travel memory is stored."""
    trips = store.list_trips(_user(ctx), max(1, min(int(limit), 25)))
    return _result(f"I found {len(trips)} saved trip{'s' if len(trips) != 1 else ''}.", {"kind":"memory","title":"Saved trips","trips":trips})


@mcp.tool(title="Save demo trip", annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False, openWorldHint=False))
async def save_demo_trip_tool(ctx: Context, trip: dict) -> CallToolResult:
    """Save a completed Barcelona demo estimate to the current user's SQLite travel memory."""
    if not isinstance(trip, dict) or trip.get("kind") != "demo-trip" or trip.get("destination") != "Barcelona":
        return _error("Only a completed Barcelona demo trip can be saved.")
    if not isinstance(trip.get("itinerary"), dict) or not isinstance(trip.get("costBreakdown"), dict):
        return _error("The demo trip is incomplete and could not be saved.")
    trip_id = store.save_trip(_user(ctx), "Barcelona · demo trip", trip)
    saved = next((item for item in store.list_trips(_user(ctx)) if item["id"] == trip_id), None)
    return _result("Saved the Barcelona demo estimate to your travel memory.",
                   {"kind":"saved-trip","title":"Trip saved","trip":saved})


@mcp.tool(title="Delete one saved trip", annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def delete_saved_trip_tool(ctx: Context, trip_id: str) -> CallToolResult:
    """Delete one saved trip by its identifier, leaving the profile and other trips unchanged."""
    if not store.delete_trip(_user(ctx), trip_id):
        return _error("That saved trip was not found. Refresh the list and try again.")
    return _result("Deleted the selected saved trip.", {"kind":"memory","deletedTripId":trip_id})


# ------------------------------------------------------------------ search
@mcp.tool(title="Search flights", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def search_flights(ctx: Context, destination: str, departure_date: str, return_date: str | None = None,
                         origin: str | None = None, nonstop_only: bool | None = None, sort_by: str = "price") -> CallToolResult:
    """Search Google Flights for one date (one-way, or round trip when return_date is given).
    Dates accept 2026-11-12, 'next friday', 'november 12'. sort_by: price | duration."""
    try:
        o, d = _origin(ctx, origin), _place(destination, "destination")
    except ValueError as e:
        return _error(str(e))
    dep, ret = parse_date(departure_date), parse_date(return_date) if return_date else None
    if not dep:
        return _error(f"I didn't understand the date {departure_date}.")
    prof = dict(store.get_profile(_user(ctx)))
    if nonstop_only is not None:
        prof["maxStops"] = 0 if nonstop_only else None
    await ctx.report_progress(0.2, 1.0, f"Searching flights {o['label']} to {d['label']}")
    try:
        r = await _run(planner.search_flights, o["code"], d["code"], dep, ret, prof, None, 6, sort_by)
    except Exception as e:
        return _error(f"Google Flights didn't respond right now ({e}). Please try again in a moment.")
    fl = [_short_flight(f) for f in r["flights"]]
    cur = prof["currency"]
    if not fl:
        return _error(f"I found no flights from {o['label']} to {d['label']} on {_spoken_date(dep)}.")
    f = fl[0]
    stops = "nonstop" if f["stops"] == 0 else f"with {f['stops']} stop{'s' if f['stops'] > 1 else ''}"
    lvl = r["insights"].get("priceLevel")
    speech = (f"The best fare to {d['label'].split(' (')[0]} on {_spoken_date(dep)} is {_money(f['price'], cur)} "
              f"{'round trip ' if ret else ''}with {', '.join(f['airlines'])}, {stops}." + (f" That's {lvl} for this route." if lvl else ""))
    return _result(speech, {"kind": "flights", "title": f"{o['label']} → {d['label']}", "subtitle": _spoken_date(dep) + (f" – {_spoken_date(ret)}" if ret else ""),
                            "currency": cur, "origin": o["code"], "destination": d["code"], "departureDate": dep.isoformat(),
                            "returnDate": ret.isoformat() if ret else None, "flights": fl, "insights": r["insights"], "url": r["url"]})


@mcp.tool(title="Find the cheapest days to fly", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def find_cheapest_dates(ctx: Context, destination: str, when: str, trip_length_nights: int | None = None,
                              origin: str | None = None) -> CallToolResult:
    """Compare fares for every departure day in a window ('november', 'next month', '2026-11-01 to 2026-11-20')
    and return the cheapest days. trip_length_nights makes it a round trip of that length."""
    try:
        o, d = _origin(ctx, origin), _place(destination, "destination")
    except ValueError as e:
        return _error(str(e))
    win = parse_window(when)
    if not win:
        return _error(f"I didn't understand when you want to travel: {when}.")
    prof = store.get_profile(_user(ctx))
    await ctx.report_progress(0.1, 1.0, f"Comparing up to 14 departure days to {d['label']}")
    r = await _run(planner.cheapest_dates, o["code"], d["code"], win[0], win[1], trip_length_nights, prof)
    if not r["cheapest"]:
        return _error("I couldn't get any fares for that window. Try different dates.")
    c, cur = r["cheapest"], prof["currency"]
    speech = (f"The cheapest day to fly to {d['label'].split(' (')[0]} is {_spoken_date(c['departureDate'])} at {_money(c['price'], cur)}"
              + (f", returning {_spoken_date(c['returnDate'])}" if c.get("returnDate") else "") + "."
              + (f" That saves {_money(r['savingsVsMostExpensive'], cur)} compared to the most expensive day." if r["savingsVsMostExpensive"] else ""))
    return _result(speech, {"kind": "dates", "title": f"Cheapest days: {o['label']} → {d['label']}",
                            "subtitle": f"{r['searchedDates']} departure dates compared", "currency": cur,
                            "origin": o["code"], "destination": d["code"], "results": r["results"], "cheapest": c})


@mcp.tool(title="Search hotels", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def search_hotels(ctx: Context, city: str, check_in: str, nights: int = 2, max_price_per_night: float | None = None,
                        min_rating: float | None = None) -> CallToolResult:
    """Search Google Hotels with real prices for the given check-in date and number of nights."""
    ci = parse_date(check_in)
    if not ci:
        return _error(f"I didn't understand the check-in date {check_in}.")
    prof = dict(store.get_profile(_user(ctx)))
    if min_rating is not None:
        prof["minHotelRating"] = min_rating
    await ctx.report_progress(0.2, 1.0, f"Searching hotels in {city}")
    try:
        hs = await _run(planner.search_hotels, city, ci, nights, prof, None, 60)
    except Exception as e:
        return _error(f"I couldn't search hotels in {city}: {e}")
    if max_price_per_night:
        hs = [h for h in hs if (h["pricePerNight"] or 1e12) <= max_price_per_night]
    hs = [_short_hotel(h) for h in hs[:8]]
    cur = prof["currency"]
    if not hs:
        return _error(f"I found no hotels in {city} matching your standards for those dates.")
    h = hs[0]
    speech = (f"My top pick in {city} is {h['name']}, rated {h['rating']}, at {_money(h['pricePerNight'], cur)} a night, "
              f"{_money(h['priceTotal'], cur)} for {nights} nights.")
    return _result(speech, {"kind": "hotels", "title": f"Hotels in {city}", "subtitle": f"{_spoken_date(ci)}, {nights} nights",
                            "currency": cur, "hotels": hs})


# ------------------------------------------------------------------ the agentic workflow
@mcp.tool(title="Plan a whole trip", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def plan_trip(ctx: Context, destination: str, when: str, nights: int = 3, budget: float | None = None,
                    origin: str | None = None) -> CallToolResult:
    """Plan a complete trip: compares round-trip fares across the travel window, finds well-rated hotels for the
    cheapest dates and returns the best flight + hotel packages within the budget (total for all travelers).
    when: 'november', 'next month', 'this weekend', or 'YYYY-MM-DD to YYYY-MM-DD'."""
    try:
        o, d = _origin(ctx, origin), _place(destination, "destination")
    except ValueError as e:
        return _error(str(e))
    win = parse_window(when)
    if not win:
        return _error(f"I didn't understand when you want to travel: {when}.")
    start, end = win
    if start == end:  # a single date means "around then"
        start, end = start - dt.timedelta(days=3), start + dt.timedelta(days=3)
    uid = _user(ctx)
    prof = store.get_profile(uid)
    city = d["label"].split(" (")[0]
    await ctx.report_progress(0.1, 1.0, f"Comparing round-trip fares to {city}")
    try:
        r = await _run(planner.plan_trip, o["code"], d["code"], city, start, end, nights, budget, prof)
    except Exception:
        return _error("The live flight or hotel provider failed. No live prices are available; try again later or use the clearly labeled offline demo plan.")
    await ctx.report_progress(1.0, 1.0, "Done")
    if not r["packages"]:
        return _error(r.get("message") or f"I couldn't put together a trip to {city} for those dates.")
    cur, p = prof["currency"], r["packages"][0]
    speech = (f"Best value: fly {_spoken_date(p['departureDate'])}, back {_spoken_date(p['returnDate'])}, and stay at {p['hotel']['name']}, "
              f"rated {p['hotel']['rating']}. {_money(p['total'], cur)} in total, flight {_money(p['flightPrice'], cur)} and hotel {_money(p['hotelPrice'], cur)}.")
    if r.get("message"):
        speech = r["message"] + " " + speech
    elif budget:
        speech += f" That's {_money(budget - p['total'], cur)} under your budget."
    speech += " Want me to watch this price?"
    store.save_trip(uid, f"{o['code']}-{d['code']} {p['departureDate']}", {"request": {"destination": d["code"], "when": when, "nights": nights, "budget": budget}, "best": p})
    return _result(speech, {"kind": "packages", "title": f"Trip to {city}", "subtitle": f"{nights} nights" + (f" · budget {_money(budget, cur)}" if budget else ""),
                            "currency": cur, "origin": o["code"], "destination": d["code"], "packages": r["packages"], "steps": r["steps"]})


# ------------------------------------------------------------------ price watches (state across sessions)
@mcp.tool(title="Watch a flight price", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
async def watch_price(ctx: Context, destination: str, departure_date: str, return_date: str | None = None,
                      origin: str | None = None, target_price: float | None = None) -> CallToolResult:
    """Start tracking the best fare for a route and dates. Later, check_price_watches reports any drop."""
    try:
        o, d = _origin(ctx, origin), _place(destination, "destination")
    except ValueError as e:
        return _error(str(e))
    dep, ret = parse_date(departure_date), parse_date(return_date) if return_date else None
    if not dep:
        return _error(f"I didn't understand the date {departure_date}.")
    uid = _user(ctx)
    prof = store.get_profile(uid)
    r = await _run(planner.search_flights, o["code"], d["code"], dep, ret, prof, None, 1)
    price = r["flights"][0]["price"] if r["flights"] else None
    label = f"{o['code']} → {d['code']}, {dep.strftime('%b %d')}" + (f" – {ret.strftime('%b %d')}" if ret else "")
    params = {"origin": o["code"], "destination": d["code"], "departure": dep.isoformat(), "return": ret.isoformat() if ret else None}
    store.add_watch(uid, "flight", label, params, price, prof["currency"], target_price)
    cur = prof["currency"]
    speech = f"I'm watching {label}. It's {_money(price, cur)} right now" + (f", and I'll tell you when it drops below {_money(target_price, cur)}." if target_price else ". Ask me any time if the price dropped.")
    return _watches_result(ctx, speech)


@mcp.tool(title="Check watched prices", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
async def check_price_watches(ctx: Context) -> CallToolResult:
    """Re-check every watched fare now and report price drops since the user started watching."""
    uid = _user(ctx)
    prof = store.get_profile(uid)
    ws = store.list_watches(uid)
    if not ws:
        return _result("You're not watching any prices yet. Say: watch this flight.", {"kind": "watches", "title": "Price watches", "watches": []})

    def recheck(w):
        p = w["params"]
        try:
            r = planner.search_flights(p["origin"], p["destination"], p["departure"], p["return"], prof, None, 1)
            return w["id"], (r["flights"][0]["price"] if r["flights"] else None)
        except Exception:
            return w["id"], None
    results = await _run(lambda: list(planner.pool.map(recheck, ws)))
    news = []
    for wid, price in results:
        w = store.record_price(uid, wid, price)
        if w and price is not None and w["first_price"] is not None:
            diff = price - w["first_price"]
            if diff < 0:
                news.append(f"{w['label']} dropped {_money(-diff, w['currency'])} to {_money(price, w['currency'])}")
            if w["target_price"] and price <= w["target_price"]:
                news.append(f"{w['label']} is now below your target of {_money(w['target_price'], w['currency'])}")
    speech = ("Good news: " + "; ".join(news) + ".") if news else f"I checked {len(ws)} watched fare{'s' if len(ws) > 1 else ''}. No price drops yet."
    return _watches_result(ctx, speech)


@mcp.tool(title="List watched prices", meta=UI_META, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def list_price_watches(ctx: Context) -> CallToolResult:
    """List all fares the user is watching, with the price history since each watch started."""
    return _watches_result(ctx)


def _watches_result(ctx, speech=None):
    ws = store.list_watches(_user(ctx))
    out = [{"id": w["id"], "label": w["label"], "firstPrice": w["first_price"], "lastPrice": w["last_price"], "bestPrice": w["best_price"],
            "targetPrice": w["target_price"], "currency": w["currency"], "history": w["history"], "params": w["params"]} for w in ws]
    speech = speech or (f"You're watching {len(out)} fare{'s' if len(out) != 1 else ''}." if out else "You're not watching any prices yet.")
    return _result(speech, {"kind": "watches", "title": "Price watches", "subtitle": f"{len(out)} active", "watches": out})


@mcp.tool(title="Stop watching a price", meta={"ui": {"resourceUri": VIEW_URI, "visibility": ["model", "app"]}},
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def stop_watching(ctx: Context, watch_id: str) -> CallToolResult:
    """Stop tracking a watched fare (watch_id from list_price_watches)."""
    ok = store.stop_watch(_user(ctx), watch_id)
    return _watches_result(ctx, "Okay, I stopped watching that fare." if ok else "I couldn't find that watch.")


# ------------------------------------------------------------------ app
def build_app():
    app = mcp.streamable_http_app()
    token = os.environ.get("TRIP_SCOUT_TOKEN")
    if not token:
        return app

    async def auth(scope, receive, send):  # optional bearer auth for deployments
        if scope["type"] == "http":
            hdr = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if hdr != f"Bearer {token}":
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await app(scope, receive, send)
    return auth


def main():
    import uvicorn
    uvicorn.run(build_app(), host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
