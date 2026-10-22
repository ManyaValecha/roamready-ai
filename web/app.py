"""Alexa+ simulator host for Trip Scout.

A web app that plays the role of Alexa+: it loads the Trip Scout Agent Skill as its instructions, connects to the
Trip Scout MCP server over Streamable HTTP, lets an LLM choose and call MCP tools, speaks the answer and renders the
MCP Apps view (ui://roamready-ai/view.html) like an Echo Show screen.

LLM: any OpenAI-compatible chat endpoint with tool calling.
  LLM_BASE_URL (default https://text.pollinations.ai/openai - free, no key), LLM_API_KEY, LLM_MODEL (default "openai").
  Amazon Bedrock works through its OpenAI-compatible endpoint, e.g.
  LLM_BASE_URL=https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1  LLM_MODEL=openai.gpt-oss-120b-1:0
If the LLM is unreachable, a small rule-based intent router keeps the demo working.

Run:  python -m web.app   ->  http://127.0.0.1:8770
"""
import asyncio
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import time
import uuid

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MCP_URL = os.environ.get("TRIP_SCOUT_MCP_URL", "http://127.0.0.1:8765/mcp")
LLM_BASE = os.environ.get("LLM_BASE_URL", "https://text.pollinations.ai/openai").rstrip("/")
DEMO_MODE = os.environ.get("ROAMREADY_DEMO_MODE", "1") == "1"
LLM_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "openai")
MCP_TOKEN = os.environ.get("TRIP_SCOUT_TOKEN", "")
PORT = int(os.environ.get("SIM_PORT", os.environ.get("PORT", "8770")))
VERCEL_DEMO = os.environ.get("ROAMREADY_DEPLOYMENT_MODE") == "vercel"
DEMO_SAFE_TOOLS = {
    "plan_demo_trip", "rescue_demo_trip_tool", "simulate_provider_failure",
    "plan_local_itinerary", "rescue_itinerary_tool", "set_travel_profile",
    "get_travel_profile", "forget_travel_memory", "list_saved_trips",
    "save_demo_trip_tool", "delete_saved_trip_tool",
}

with open(os.path.join(ROOT, "skills", "trip-scout", "SKILL.md"), encoding="utf-8") as f:
    SKILL = f.read().split("---", 2)[-1].strip()   # body of the Agent Skill (frontmatter stripped)

SESSIONS = {}   # session_id -> list of chat messages
LAST = {}       # session_id -> arguments for watch_price derived from the last result
DEMO_TRIPS = {} # session_id -> deterministic demo request used for the before/after rescue


def system_prompt():
    today = dt.date.today()
    return (f"You are Alexa+. Today is {today.strftime('%A, %B %d, %Y')}. You have the RoamReady AI skill:\n\n{SKILL}\n\n"
            "Always use the tools for travel questions; never invent prices. Reply in plain spoken English, no markdown.")


# ------------------------------------------------------------------ MCP host side
async def mcp_call(user_id, fn):
    async with streamablehttp_client(MCP_URL, headers={"x-user-id": user_id, **({"Authorization": f"Bearer {MCP_TOKEN}"} if MCP_TOKEN else {})}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


async def list_tools(user_id):
    async def go(s):
        tools = (await s.list_tools()).tools
        view = (await s.read_resource("ui://roamready-ai/view.html")).contents[0].text
        return tools, view
    return await mcp_call(user_id, go)


def to_openai_tools(tools):
    out = []
    for t in tools:
        vis = ((t.meta or {}).get("ui") or {}).get("visibility", ["model", "app"])
        if "model" not in vis:
            continue
        schema = dict(t.inputSchema or {"type": "object", "properties": {}})
        schema["properties"] = {k: v for k, v in (schema.get("properties") or {}).items() if k != "ctx"}
        out.append({"type": "function", "function": {"name": t.name, "description": (t.description or "")[:1000], "parameters": schema}})
    return out


# ------------------------------------------------------------------ LLM
async def llm(messages, tools):
    headers = {"Content-Type": "application/json"}
    if LLM_KEY:
        headers["Authorization"] = f"Bearer {LLM_KEY}"
    body = {"model": LLM_MODEL, "messages": messages, "tools": tools, "tool_choice": "auto", "temperature": 0.2}
    url = LLM_BASE if LLM_BASE.endswith("/openai") or LLM_BASE.endswith("/completions") else LLM_BASE + "/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as c:
        for attempt in range(2):
            r = await c.post(url, headers=headers, json=body)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]
            if r.status_code < 500 or attempt:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:120]}")
            await asyncio.sleep(1.5)   # transient 5xx from a free endpoint: retry once


class LLMError(Exception):
    pass


# ------------------------------------------------------------------ rule-based fallback (keeps the demo alive offline)
def fallback_intent(text):
    t = text.lower()
    m_budget = re.search(r"(?:under|budget(?: of)?|have|for|total)\s*[€$]?\s?([\d,]{3,6})", t)
    budget = float(m_budget.group(1).replace(",", "")) if m_budget else None
    m_nights = re.search(r"(\d+)\s*(?:night|day)", t)
    nights = int(m_nights.group(1)) if m_nights else (3 if "weekend" in t else None)
    TIMEWORDS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|next month|this weekend|next weekend|the \w+|\d+ \w+)"
    m_dest = None
    for m in re.finditer(r"\b(?:to|in|visit|at)\s+([a-z][a-z .'-]+?)(?=\s+(?:in|on|for|next|this|from|under|with|around|between|we|and|,|\.)|[,.?!]|$)", t):
        if not re.fullmatch(TIMEWORDS, m.group(1).strip()):
            m_dest = m   # keep the last non-time match: "cheapest to fly to Lisbon" -> Lisbon
    dest = m_dest.group(1).strip() if m_dest else None
    if dest:
        dest = re.split(r"\b(?:to|in|visit|at)\s+", dest)[-1]           # "fly to lisbon" -> "lisbon"
        dest = None if re.fullmatch(r"(?i)(fly|go|travel|get|me|us)", dest) else dest.title()
    m_when = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|next month|this weekend|next weekend)\b", t)
    when = m_when.group(1) if m_when else None
    m_home = re.search(r"(?:i live in|i'm in|i am in|fly(?:ing)? from|home airport is)\s+([a-z][a-z .'-]+?)(?=\s+(?:and|we|,|\.)|[,.?!]|$)", t)
    if m_home and (not dest or dest.lower() == m_home.group(1).strip()):
        return "set_travel_profile", {"home_airport": m_home.group(1).strip().title()}
    interest_values = [v for v in ("architecture", "art", "food", "history", "outdoors") if v in t]
    travelers_match = re.search(r"\b(\d+)\s+(?:people|travelers|travellers|adults)\b", t)
    demo_args = {"days": nights or 4, "travelers": int(travelers_match.group(1)) if travelers_match else 2,
                 "trip_budget_eur": budget or 1800, "interests": interest_values or ["architecture", "art", "food", "history", "outdoors"]}
    if re.search(r"\b(step[- ]free|wheelchair|accessible)\b", t):
        demo_args["step_free_access"] = True
    if re.search(r"\b(simulate|provider|outage|offline fallback)\b", t) and re.search(r"\b(fail|failure|outage|unavailable)\b", t):
        return "simulate_provider_failure", demo_args
    if "barcelona" in t and re.search(r"\b(plan|build|create)\b", t) and ("€" in text or "budget" in t or "trip" in t):
        return "plan_demo_trip", demo_args
    if re.search(r"\b(rescue|replan|re-plan|closed|closure|rain|disruption)\b", t) and ("barcelona" in t or "trip" in t or "itinerary" in t):
        return "rescue_demo_trip_tool", {**demo_args, "disruption": "rain disruption" if "rain" in t or "weather" in t else "Sagrada Família closure"}
    if re.search(r"\b(rescue|replan|re-plan|closed|closure|rain|disruption|delayed)\b", t):
        return "rescue_itinerary_tool", {"days": nights or 3, "activity_budget": budget or 120, "disruption": "rain disruption" if "rain" in t else "Sagrada Família closed"}
    if re.search(r"\b(day plan|itinerary|attractions|things to do)\b", t):
        return "plan_local_itinerary", {"days": nights or 3, "activity_budget": budget or 120}
    if re.search(r"\b(show|list|review)\b.*\b(saved )?trips\b", t):
        return "list_saved_trips", {}
    if re.search(r"\b(drop|dropped|cheaper yet|my prices|price watch|any news)\b", t):
        return "check_price_watches", {}
    if re.search(r"\bwatch\b", t):
        return "__watch_last__", {}
    if "hotel" in t and dest:
        return "search_hotels", {"city": dest, "check_in": when or "in 3 weeks", "nights": nights or 2}
    if re.search(r"cheapest (day|time|date)|when .*cheap", t) and dest:
        return "find_cheapest_dates", {"destination": dest, "when": when or "next month", "trip_length_nights": nights}
    if dest:
        return "plan_trip", {"destination": dest, "when": when or "next month", "nights": nights or 3, "budget": budget}
    return None, {}


# ------------------------------------------------------------------ agent loop
async def run_turn(session_id, user_id, text):
    trace, ui = [], None
    t0 = time.time()
    tools, view_html = await list_tools(user_id)
    oa_tools = to_openai_tools(tools)
    msgs = SESSIONS.setdefault(session_id, [])
    msgs.append({"role": "user", "content": text})
    convo = [{"role": "system", "content": system_prompt()}] + msgs[-12:]
    speech, mode = None, "llm"

    async def execute(name, args):
        nonlocal ui
        res = await mcp_call(user_id, lambda s: s.call_tool(name, args))
        sc = res.structuredContent or {}
        trace.append({"tool": name, "arguments": args, "isError": res.isError, "kind": sc.get("kind"), "speech": sc.get("speech")})
        if sc.get("kind") in ("flights", "dates", "hotels", "packages", "watches", "itinerary", "rescue", "demo-trip", "demo-rescue", "provider-fallback"):
            ui = {"html": view_html, "toolInput": {"arguments": args}, "toolResult": res.model_dump(mode="json", exclude_none=True)}
        pick = (sc.get("packages") or [None])[0] if sc.get("kind") == "packages" else sc.get("cheapest") if sc.get("kind") == "dates" else sc if sc.get("kind") == "flights" else None
        if pick and sc.get("destination"):
            LAST[session_id] = {"origin": sc.get("origin"), "destination": sc["destination"],
                                "departure_date": pick.get("departureDate"), "return_date": pick.get("returnDate")}
        return res, sc

    try:
        if DEMO_MODE:
            raise LLMError("deterministic local demo routing enabled")
        for _ in range(4):   # up to 4 tool rounds per user turn
            msg = await llm(convo, oa_tools)
            calls = msg.get("tool_calls") or []
            if not calls:
                speech = (msg.get("content") or "").strip()
                break
            convo.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            round_results = []
            for c in calls:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                res, sc = await execute(c["function"]["name"], args)
                round_results.append((res, sc))
                convo.append({"role": "tool", "tool_call_id": c.get("id") or uuid.uuid4().hex, "content": json.dumps({"speech": sc.get("speech"), "isError": res.isError, **{k: v for k, v in sc.items() if k in ("origin", "destination", "cheapest", "packages")}})[:6000]})
            if all(not r.isError and s.get("speech") for r, s in round_results):
                # tools answer in voice-ready sentences: speak them now instead of paying for another LLM round trip
                speech = " ".join(s["speech"] for _, s in round_results)
                break
        if not speech and trace:
            speech = trace[-1]["speech"]
    except (httpx.HTTPError, LLMError, KeyError, ValueError) as e:
        if trace and trace[-1].get("speech"):
            # the LLM already chose and ran the tool - just speak the tool's answer
            trace.append({"note": f"LLM follow-up failed ({str(e)[:120]}); spoke the tool result directly"})
            speech = trace[-2]["speech"] if "note" in trace[-1] else trace[-1]["speech"]
            msgs.append({"role": "assistant", "content": speech})
            return {"speech": speech, "ui": ui, "trace": trace, "mode": "llm+tool", "ms": int((time.time() - t0) * 1000)}
        mode = "fallback"
        reason = "Deterministic demo mode is on; no external LLM request was made." if DEMO_MODE else f"LLM unavailable ({str(e)[:120]}); rule-based intent router used"
        trace.append({"note": reason})
        name, args = fallback_intent(text)
        if name == "rescue_itinerary_tool" and session_id in DEMO_TRIPS:
            name = "rescue_demo_trip_tool"
            args = {**DEMO_TRIPS[session_id], "disruption": "rain disruption" if "rain" in text.lower() or "weather" in text.lower() else "Sagrada Família closure"}
        if name == "__watch_last__":
            name, args = ("watch_price", LAST[session_id]) if session_id in LAST else ("check_price_watches", {})
        if name == "rescue_demo_trip_tool":
            previous = DEMO_TRIPS.get(session_id)
            args = ({**previous, "disruption": args.get("disruption", "Sagrada Família closure")}
                    if previous else args)
        if name:
            call_args = {k: v for k, v in args.items() if v is not None}
            if name == "plan_demo_trip": DEMO_TRIPS[session_id] = dict(call_args)
            res, sc = await execute(name, call_args)
            speech = sc.get("speech")
        else:
            speech = "I can plan trips, find the cheapest days to fly, search hotels and watch prices. Where would you like to go?"
    speech = speech or "Sorry, I didn't catch that."
    msgs.append({"role": "assistant", "content": speech})
    return {"speech": speech, "ui": ui, "trace": trace, "mode": mode, "ms": int((time.time() - t0) * 1000)}


# ------------------------------------------------------------------ HTTP
async def index(request):
    return FileResponse(os.path.join(HERE, "static", "index.html"))


async def app_view(request: Request):
    uid = request_user_id(request)
    async def go(s):
        return (await s.read_resource("ui://roamready-ai/view.html")).contents[0].text
    return JSONResponse({"html": await mcp_call(uid, go)})


def request_user_id(request: Request, body=None):
    if VERCEL_DEMO:
        uid = request.session.get("user_id")
        if not uid:
            uid = uuid.uuid4().hex
            request.session["user_id"] = uid
        return uid
    return ((body or {}).get("user_id") or request.headers.get("x-user-id") or "demo-user")[:64]


async def config(request: Request):
    return JSONResponse({"hosted": VERCEL_DEMO, "temporaryStorage": VERCEL_DEMO})


async def chat(request: Request):
    body = await request.json()
    client_sid = body.get("session_id") or uuid.uuid4().hex
    uid = request_user_id(request, body)
    sid = f"{uid}:{client_sid}" if VERCEL_DEMO else client_sid
    out = await run_turn(sid, uid, (body.get("text") or "").strip()[:500])
    out["session_id"] = client_sid
    return JSONResponse(out)


async def reset(request: Request):
    body = await request.json()
    client_sid = body.get("session_id")
    uid = request_user_id(request, body)
    sid = f"{uid}:{client_sid}" if VERCEL_DEMO and client_sid else client_sid
    if sid:
        SESSIONS.pop(sid, None); LAST.pop(sid, None); DEMO_TRIPS.pop(sid, None)
    # Reset the conversation only. Persistent profile, saved trips and watches
    # have a separate explicit forget action and must not be deleted implicitly.
    return JSONResponse({"reset": True})


async def tool(request: Request):
    """MCP Apps: the view (iframe) asks the host to proxy tools/call to the MCP server."""
    body = await request.json()
    name = body.get("name")
    if DEMO_MODE and name not in DEMO_SAFE_TOOLS:
        return JSONResponse({"error": "That tool is disabled in the no-live-provider demo."}, status_code=403)
    uid = request_user_id(request, body)
    res = await mcp_call(uid, lambda s: s.call_tool(name, body.get("arguments") or {}))
    return JSONResponse(res.model_dump(mode="json", exclude_none=True))


app = Starlette(routes=[Route("/", index), Route("/api/config", config), Route("/api/view", app_view), Route("/api/chat", chat, methods=["POST"]), Route("/api/tool", tool, methods=["POST"]), Route("/api/reset", reset, methods=["POST"])])
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
if VERCEL_DEMO:
    session_secret = os.environ.get("ROAMREADY_SESSION_SECRET")
    if not session_secret:
        raise RuntimeError("ROAMREADY_SESSION_SECRET is required for the hosted demo.")

    class SignedDemoSessionMiddleware:
        """Give each hosted browser a tamper-resistant demo namespace without a third-party session store."""
        def __init__(self, inner, secret):
            self.inner = inner
            self.secret = secret.encode("utf-8")

        def _decode(self, cookie):
            try:
                encoded, supplied = cookie.rsplit(".", 1)
                expected = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(supplied, expected):
                    return {}
                raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
                uid, timestamp = raw.rsplit(".", 1)
                if time.time() - int(timestamp) > 60 * 60 * 24 * 30:
                    return {}
                return {"user_id": uid}
            except (ValueError, UnicodeError, TypeError):
                return {}

        def _encode(self, uid):
            raw = f"{uid}.{int(time.time())}".encode("utf-8")
            encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
            sig = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            return f"{encoded}.{sig}"

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.inner(scope, receive, send)
            from http.cookies import SimpleCookie
            jar = SimpleCookie()
            jar.load(dict(scope.get("headers", [])).get(b"cookie", b"").decode("latin-1"))
            morsel = jar.get("roamready_session")
            session = self._decode(morsel.value) if morsel else {}
            scope["session"] = session

            async def send_with_cookie(message):
                if message["type"] == "http.response.start" and session.get("user_id"):
                    headers = list(message.get("headers", []))
                    headers.append((b"set-cookie", f"roamready_session={self._encode(session['user_id'])}; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Lax".encode("ascii")))
                    message["headers"] = headers
                await send(message)

            await self.inner(scope, receive, send_with_cookie)

    app = SignedDemoSessionMiddleware(app, session_secret)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
