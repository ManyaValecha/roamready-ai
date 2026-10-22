"""Offline unit tests (no network): dates, places, protobuf encoding, persistence, fallback intents."""
import base64
import datetime as dt
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trip_scout.dates import parse_date, parse_window
from trip_scout.engines.flights import build_tfs
from trip_scout.engines.hotels import build_qs, build_ts
from trip_scout.places import Places
from trip_scout.planner import _trusted_rating
from trip_scout.store import Store

TODAY = dt.date(2026, 9, 24)   # a Thursday


def test_parse_date_forms():
    assert parse_date("2026-11-12", TODAY) == dt.date(2026, 11, 12)
    assert parse_date("tomorrow", TODAY) == dt.date(2026, 9, 25)
    assert parse_date("next friday", TODAY) == dt.date(2026, 9, 25)
    assert parse_date("November 12th", TODAY) == dt.date(2026, 11, 12)
    assert parse_date("12 march", TODAY) == dt.date(2027, 3, 12)          # past month rolls to next year
    assert parse_date("in 2 weeks", TODAY) == dt.date(2026, 10, 8)
    assert parse_date("gibberish", TODAY) is None


def test_parse_window():
    assert parse_window("november", TODAY) == (dt.date(2026, 11, 1), dt.date(2026, 11, 30))
    assert parse_window("next month", TODAY) == (dt.date(2026, 10, 1), dt.date(2026, 10, 31))
    assert parse_window("2026-11-01 to 2026-11-20", TODAY) == (dt.date(2026, 11, 1), dt.date(2026, 11, 20))
    assert parse_window("this weekend", TODAY) == (dt.date(2026, 9, 25), dt.date(2026, 9, 27))


def test_places():
    p = Places()
    assert p.resolve("JFK")["code"] == "JFK"
    assert p.resolve("New York")["code"] == "NYC"
    assert p.resolve("barcelona")["code"] == "BCN"
    assert p.resolve("Heathrow")["code"] == "LHR"
    assert p.resolve("Lisbon")["code"] == "LIS"
    assert p.resolve("Atlantis Nowhere") is None


def test_flights_tfs_protobuf():
    tfs = build_tfs([("2026-11-12", "JFK", "LHR")], "business", {"adults": 2}, "one_way", 0)
    raw = base64.urlsafe_b64decode(tfs + "=" * (-len(tfs) % 4))
    assert b"2026-11-12" in raw and b"JFK" in raw and b"LHR" in raw
    assert raw.endswith(bytes([0x98, 0x01, 0x02]))           # field 19 (trip) = one way
    assert bytes([0x48, 0x03]) in raw                        # field 9 (seat) = business
    assert bytes([0x42, 0x02, 0x01, 0x01]) in raw            # field 8 packed passengers = 2 adults


def test_hotels_ts_matches_browser():
    # captured from a real Google Hotels browser session
    browser = "CAEaMgoUEhIKCC9tLzA1eXdnOgZQcmFndWUSGhIUCgcI6g8QCxgMEgcI6g8QCxgOGAIyAggBKgcKBToDQ1pL"
    ours = build_ts("Prague", dt.date(2026, 11, 12), dt.date(2026, 11, 14), "CZK", adults=1)
    decode = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    b, o = decode(browser), decode(ours)
    assert o.endswith(b[-9:])                                # same currency block
    assert b"Prague" in o and b[b.index(b"\x12\x1a"):b.index(b"*")] == o[o.index(b"\x12\x1a"):o.index(b"*")]  # same dates/guests block
    assert build_qs("CBI=").startswith("Eg")


def test_trusted_rating_prefers_many_reviews():
    few = {"rating": 5.0, "reviewCount": 12}
    many = {"rating": 4.7, "reviewCount": 3000}
    assert _trusted_rating(many) > _trusted_rating(few)


def test_store_profile_and_watches():
    with tempfile.TemporaryDirectory() as d:
        s = Store(os.path.join(d, "t.db"))
        assert s.get_profile("u")["homeAirport"] is None
        s.update_profile("u", homeAirport="JFK", adults=2, maxStops=0)
        s.update_profile("u", maxStops=None)                  # explicit "any stops" must persist
        prof = s.get_profile("u")
        assert prof["homeAirport"] == "JFK" and prof["adults"] == 2 and prof["maxStops"] is None
        w = s.add_watch("u", "flight", "JFK-BCN", {"origin": "JFK"}, 500, "USD")
        s.record_price("u", w["id"], 450)
        w2 = s.record_price("u", w["id"], 470)
        assert w2["best_price"] == 450 and w2["last_price"] == 470 and len(w2["history"]) == 3
        assert s.list_watches("other") == []                  # users are isolated
        assert s.stop_watch("u", w["id"]) and s.list_watches("u") == []
        s.close()


def test_fallback_intents():
    from web.app import fallback_intent
    assert fallback_intent("When is it cheapest to fly to Lisbon next month for 4 nights?") == \
        ("find_cheapest_dates", {"destination": "Lisbon", "when": "next month", "trip_length_nights": 4})
    name, args = fallback_intent("Plan a long weekend in Barcelona in November, we have 2500 dollars")
    assert name == "plan_trip" and args["destination"] == "Barcelona" and args["budget"] == 2500 and args["when"] == "november"
    assert fallback_intent("I live in Chicago")[0] == "set_travel_profile"
    assert fallback_intent("did any of my prices drop?")[0] == "check_price_watches"


def test_bedrock_provider_config_is_explicit_and_requires_credentials(monkeypatch):
    from web.app import LLMError, llm_config

    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="AWS_REGION"):
        llm_config()

    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    with pytest.raises(LLMError, match="AWS_BEARER_TOKEN_BEDROCK"):
        llm_config()

    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-only-token")
    assert llm_config() == (
        "bedrock",
        "https://bedrock-runtime.eu-west-1.amazonaws.com/openai/v1",
        "test-only-token",
        "openai.gpt-oss-120b-1:0",
    )


def test_bedrock_chat_request_uses_openai_compatible_endpoint_without_network(monkeypatch):
    import asyncio
    import httpx
    from web.app import llm

    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "tool selected", "tool_calls": []}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            captured["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, body=json)
            return FakeResponse()

    monkeypatch.setattr("web.app.httpx.AsyncClient", FakeClient)
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-only-token")
    monkeypatch.setenv("LLM_MODEL", "openai.gpt-oss-120b-1:0")
    result = asyncio.run(llm([{"role": "user", "content": "plan"}], [{"type": "function"}]))

    assert result["content"] == "tool selected"
    assert captured["url"] == "https://bedrock-runtime.eu-west-1.amazonaws.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-only-token"
    assert captured["body"]["model"] == "openai.gpt-oss-120b-1:0"
    assert captured["body"]["tools"] == [{"type": "function"}]


def test_mobile_provider_failure_notice_is_in_flow_and_announced():
    view = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trip_scout", "ui", "view.html")
    with open(view, encoding="utf-8") as f:
        source = f.read()
    assert 'class="eyebrow" role="status" aria-live="polite">Simulated provider failure' in source


def test_roamready_itinerary_constraints_and_budget():
    from trip_scout.roamready import build_itinerary
    plan = build_itinerary(days=3, budget=30, interests=["art", "food"], accessible=True)
    stops = [s for day in plan["days"] for s in day["stops"]]
    assert plan["estimatedActivityCost"] <= 30
    assert all(s["stepFree"] for s in stops)
    assert all(s["interest"] in ("art", "food") for s in stops)
    assert all(s["start"] >= "09:00" and s["end"] <= "18:00" for s in stops)
    assert plan["dataLabel"].startswith("Illustrative")


def test_disruption_rescue_removes_closure_and_explains_change():
    from trip_scout.roamready import rescue_itinerary
    result = rescue_itinerary(days=2, budget=60, disruption="Sagrada Família closed")
    stops = [s["name"] for d in result["itinerary"]["days"] for s in d["stops"]]
    assert "Sagrada Família" not in stops
    assert result["itinerary"]["estimatedActivityCost"] <= 60
    assert result["confirmationRequired"] is False
    assert result["changes"]


def test_memory_delete_clears_only_selected_user():
    with tempfile.TemporaryDirectory() as d:
        s = Store(os.path.join(d, "memory.db"))
        s.update_profile("u1", homeAirport="JFK")
        s.add_watch("u1", "flight", "JFK-BCN", {"origin":"JFK"}, 500, "USD")
        s.save_trip("u1", "Barcelona", {"best": {"total": 500}})
        s.update_profile("u2", homeAirport="LHR")
        s.delete_user_memory("u1")
        assert s.get_profile("u1")["homeAirport"] is None
        assert s.list_watches("u1") == [] and s.list_trips("u1") == []
        assert s.get_profile("u2")["homeAirport"] == "LHR"
        s.close()


def test_simulator_routes_disruption_to_rescue_tool():
    from web.app import fallback_intent
    name, args = fallback_intent("Sagrada Familia is closed, rescue my itinerary for 3 days under 120 dollars")
    assert name == "rescue_demo_trip_tool"
    assert args["days"] == 3 and args["trip_budget_eur"] == 120


def test_simulator_parses_four_day_eur_party_and_interests():
    from web.app import fallback_intent
    name, args = fallback_intent("Plan a four-day Barcelona trip for 2 people under €1,800; we love architecture, art and food")
    assert name == "plan_demo_trip"
    assert args == {"days":4,"travelers":2,"trip_budget_eur":1800,"interests":["architecture","art","food"]}


def test_four_day_eur_demo_and_rescue_comparison():
    from trip_scout.roamready import build_demo_trip, rescue_demo_trip
    trip = build_demo_trip(4, 1800, 2, ["architecture", "art", "food"])
    assert trip["days"] == 4 and trip["travelers"] == 2 and trip["currency"] == "EUR"
    assert trip["estimatedTotal"] <= 1800
    assert sum(trip["costBreakdown"].values()) == trip["estimatedTotal"]
    assert len(trip["itinerary"]["days"]) == 4
    rescue = rescue_demo_trip(4, 1800, 2, ["architecture", "art", "food"])
    before_names = [s["name"] for d in rescue["before"]["itinerary"]["days"] for s in d["stops"]]
    after_names = [s["name"] for d in rescue["after"]["itinerary"]["days"] for s in d["stops"]]
    assert "Sagrada Família" in before_names and "Sagrada Família" not in after_names
    assert rescue["after"]["estimatedTotal"] <= 1800
    assert rescue["changes"]["estimatedCostDelta"] == rescue["after"]["estimatedTotal"] - rescue["before"]["estimatedTotal"]


def test_demo_accessibility_preference_filters_original_and_rescue():
    from trip_scout.roamready import build_demo_trip, rescue_demo_trip
    trip = build_demo_trip(4, 1800, 2, ["architecture", "art", "food"], accessible=True)
    stops = [stop for day in trip["itinerary"]["days"] for stop in day["stops"]]
    assert trip["accessibilityFilter"] is True
    assert all(stop["stepFree"] for stop in stops)
    rescued = rescue_demo_trip(4, 1800, 2, ["architecture", "art", "food"], accessible=True)
    rescued_stops = [stop for day in rescued["after"]["itinerary"]["days"] for stop in day["stops"]]
    assert all(stop["stepFree"] for stop in rescued_stops)


def test_store_deletes_one_trip_without_touching_profile_or_other_trips():
    with tempfile.TemporaryDirectory() as d:
        s = Store(os.path.join(d, "saved-trips.db"))
        s.update_profile("u", homeAirport="JFK")
        first = s.save_trip("u", "Trip one", {"value": 1})
        second = s.save_trip("u", "Trip two", {"value": 2})
        assert s.delete_trip("u", first) is True
        assert [trip["id"] for trip in s.list_trips("u")] == [second]
        assert s.get_profile("u")["homeAirport"] == "JFK"
        assert s.delete_trip("someone-else", second) is False
        s.close()


def test_live_flight_and_hotel_provider_503_handled_without_network(monkeypatch):
    from trip_scout.engines import flights, hotels
    class Response:
        def __init__(self, status_code, text=""):
            self.status_code, self.text, self.url = status_code, text, "https://provider.invalid/"
    calls = []
    def ok(*a, **k):
        calls.append((a, k))
        return Response(200, "fixture response")
    monkeypatch.setattr(flights.creq, "get", ok)
    monkeypatch.setattr(hotels.creq, "get", ok)
    assert flights.Flights(max_retries=1).fetch({}) == "fixture response"
    assert hotels.Hotels(max_retries=1).fetch({}) == "fixture response"
    assert len(calls) == 2 and all(c[1]["timeout"] > 0 for c in calls)
    def unavailable(*a, **k): return Response(503)
    monkeypatch.setattr(flights.creq, "get", unavailable)
    monkeypatch.setattr(hotels.creq, "get", unavailable)
    monkeypatch.setattr(flights.time, "sleep", lambda *_: None)
    monkeypatch.setattr(hotels.time, "sleep", lambda *_: None)
    with pytest.raises(flights.Blocked): flights.Flights(max_retries=1).fetch({})
    with pytest.raises(hotels.Blocked): hotels.Hotels(max_retries=1).fetch({})
