"""Trip Scout planner: orchestrates Google Flights + Google Hotels into budget-aware trip packages.

This is the agentic core that goes beyond "a wrapper around an API": one request fans out into many
flight searches across a date window, picks the cheapest days, pulls hotels for those exact dates,
filters them by the traveler's standards and ranks complete packages against the budget.
"""
import datetime as dt
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .engines.flights import Blocked as FBlocked, Flights, SearchError as FSearchError
from .engines.hotels import Blocked as HBlocked, Hotels, SearchError as HSearchError

MAX_DATES = 14
CACHE_TTL = 600   # seconds; fares move, but not within a conversation


class _TTLCache:
    def __init__(self, ttl=CACHE_TTL, size=512):
        self.ttl, self.size, self.d, self.lock = ttl, size, {}, threading.Lock()

    def get_or(self, key, fn):
        now = time.time()
        with self.lock:
            hit = self.d.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        val = fn()
        with self.lock:
            if len(self.d) >= self.size:
                self.d.pop(min(self.d, key=lambda k: self.d[k][0]))
            self.d[key] = (now, val)
        return val


def _d(x):
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


def _pax(profile, adults=None):
    return {"adults": adults or profile.get("adults") or 1, "children": profile.get("children") or 0}


def _short_flight(f):
    if not f:
        return None
    return {"price": f["price"], "airlines": f["airlines"], "departure": f["departure"], "arrival": f["arrival"],
            "durationMinutes": f["durationMinutes"], "stops": f["stops"],
            "flightNumbers": [l["flightNumber"] for l in f["legs"] if l.get("flightNumber")],
            "layovers": [l["airport"] for l in f["layovers"]], "co2Kg": f["co2Kg"]}


def _trusted_rating(h, prior=4.0, weight=150):
    """Bayesian average: a 5.0 from 12 reviews should not beat a 4.7 from 3,000."""
    n = h.get("reviewCount") or 0
    r = h.get("rating") or prior
    return (r * n + prior * weight) / (n + weight)


def _short_hotel(h):
    return {"name": h["name"], "pricePerNight": h["pricePerNight"], "priceTotal": h["priceTotal"], "rating": h["rating"],
            "reviewCount": h["reviewCount"], "hotelClass": h["hotelClass"], "latitude": h["latitude"], "longitude": h["longitude"],
            "photo": (h.get("photos") or [None])[0], "googleHotelsUrl": h.get("googleHotelsUrl"),
            "highlights": [a["aspect"] for a in sorted(h.get("ratingAspects") or [], key=lambda a: -(a["positiveShare"] or 0))[:2]]}


class Planner:
    def __init__(self, flights=None, hotels=None, workers=6):
        self.flights = flights or Flights()
        self.hotels = hotels or Hotels()
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.cache = _TTLCache()

    # ------------------------------------------------------------------ primitives
    def search_flights(self, origin, dest, date, return_date=None, profile=None, adults=None, limit=5, sort="price"):
        p = profile or {}
        key = ("f", origin, dest, str(date), str(return_date), p.get("cabinClass"), adults or p.get("adults"), p.get("children"),
               p.get("maxStops"), p.get("currency"), p.get("language"), p.get("country"))
        fl, ins, url = self.cache.get_or(key, lambda: self.flights.search(
            origin, dest, str(date), str(return_date) if return_date else None, p.get("cabinClass") or "economy", _pax(p, adults),
            p.get("maxStops"), None, p.get("currency") or "USD", p.get("language") or "en", p.get("country") or "us"))
        fl = [dict(f) for f in fl if f["price"] is not None]
        if sort == "price":
            fl.sort(key=lambda f: f["price"])
        elif sort == "duration":
            fl.sort(key=lambda f: (f["durationMinutes"] or 1e9, f["price"]))
        return {"flights": fl[:limit], "insights": ins or {}, "url": url, "count": len(fl)}

    def search_hotels(self, city, check_in, nights, profile=None, adults=None, limit=40):
        p = profile or {}
        ci = _d(check_in)
        guests_n = adults or max(p.get("adults") or 1, 1)
        key = ("h", city.lower(), ci, nights, guests_n, p.get("currency"), p.get("language"), p.get("country"), limit)

        def fetch():
            acc = []
            self.hotels.search(city, ci, ci + dt.timedelta(days=nights), guests_n, p.get("currency") or "USD", p.get("language") or "en",
                               p.get("country") or "us", limit=limit, on_page=lambda hs, total: acc.extend(hs))
            return acc
        got = self.cache.get_or(key, fetch)
        min_r = p.get("minHotelRating")
        classes = set(p.get("hotelClasses") or [])
        guests = (adults or max(p.get("adults") or 1, 1)) + (p.get("children") or 0)
        bad = ["hostel", "dorm", "capsule", "bed in"] + (["single room", "single bed"] if guests > 1 else [])
        ok = [dict(h) for h in got if h["priceTotal"] is not None
              and (h["reviewCount"] or 0) >= 40
              and not any(b in h["name"].lower() for b in bad)
              and (min_r is None or (h["rating"] or 0) >= min_r)
              and (not classes or h["hotelClass"] in classes)]
        ok.sort(key=lambda h: h["priceTotal"] / max(_trusted_rating(h) - 2.5, 0.3))
        return ok

    # ------------------------------------------------------------------ date intelligence
    def _dates(self, start, end, max_n=MAX_DATES):
        start, end = _d(start), _d(end)
        today = dt.date.today()
        start = max(start, today + dt.timedelta(days=1))
        days = (end - start).days + 1
        if days <= 0:
            return []
        step = max(1, -(-days // max_n))
        return [start + dt.timedelta(days=i) for i in range(0, days, step)][:max_n]

    def cheapest_dates(self, origin, dest, start, end, nights=None, profile=None, adults=None):
        """Search every departure date in the window (round trip if nights given) and rank them."""
        dates = self._dates(start, end)

        def one(d):
            ret = d + dt.timedelta(days=nights) if nights else None
            try:
                r = self.search_flights(origin, dest, d, ret, profile, adults, limit=1)
                best = r["flights"][0] if r["flights"] else None
                return {"departureDate": d.isoformat(), "returnDate": ret.isoformat() if ret else None,
                        "price": best["price"] if best else None, "flight": _short_flight(best), "url": r["url"],
                        "priceLevel": r["insights"].get("priceLevel"),
                        "typicalRange": [r["insights"].get("typicalPriceLow"), r["insights"].get("typicalPriceHigh")]}
            except (FSearchError, FBlocked) as e:
                return {"departureDate": d.isoformat(), "returnDate": ret.isoformat() if ret else None, "price": None, "error": str(e)}

        res = list(self.pool.map(one, dates))
        priced = sorted([r for r in res if r["price"] is not None], key=lambda r: r["price"])
        return {"searchedDates": len(dates), "results": priced, "failed": [r for r in res if r["price"] is None],
                "cheapest": priced[0] if priced else None,
                "savingsVsMostExpensive": (priced[-1]["price"] - priced[0]["price"]) if len(priced) > 1 else 0}

    # ------------------------------------------------------------------ the agentic workflow
    def plan_trip(self, origin, dest, dest_city, start, end, nights, budget=None, profile=None, adults=None, top=3):
        """Flights across a date window + hotels for the best dates -> ranked packages within budget."""
        steps = []
        cal = self.cheapest_dates(origin, dest, start, end, nights, profile, adults)
        steps.append(f"Compared round-trip fares for {cal['searchedDates']} departure dates")
        if not cal["results"]:
            return {"packages": [], "steps": steps, "message": "No flights found for those dates."}
        best_dates = cal["results"][:3]

        def hotels_for(c):
            try:
                return c, self.search_hotels(dest_city, c["departureDate"], nights, profile, adults, limit=40)
            except (HSearchError, HBlocked) as e:
                return c, []

        packages = []
        for c, hs in self.pool.map(hotels_for, best_dates):
            steps.append(f"Checked {len(hs)} well-rated hotels for {c['departureDate']}")
            for h in hs[:5]:
                total = round(c["price"] + h["priceTotal"], 2)
                packages.append({"departureDate": c["departureDate"], "returnDate": c["returnDate"], "nights": nights,
                                 "flight": c["flight"], "flightPrice": c["price"], "hotel": _short_hotel(h),
                                 "hotelPrice": h["priceTotal"], "total": total,
                                 "withinBudget": (budget is None or total <= budget),
                                 "flightsUrl": c["url"]})
        within = [p for p in packages if p["withinBudget"]]
        pool = within or packages
        pool.sort(key=lambda p: p["total"] / max(_trusted_rating(p["hotel"]) - 2.5, 0.3))
        chosen, seen_hotels = [], set()
        for p in pool:  # diversity: different hotels in the shortlist
            if p["hotel"]["name"] in seen_hotels:
                continue
            seen_hotels.add(p["hotel"]["name"])
            chosen.append(p)
            if len(chosen) >= top:
                break
        if len(chosen) < top:
            chosen += [p for p in pool if p not in chosen][: top - len(chosen)]
        steps.append(f"Built {len(packages)} flight + hotel combinations and ranked them by value")
        msg = None
        if budget is not None and not within:
            cheapest = min(packages, key=lambda p: p["total"])
            msg = f"Nothing fits the {budget:g} budget; the cheapest option is {cheapest['total']:g}."
        return {"packages": chosen, "steps": steps, "budget": budget, "message": msg,
                "cheapestFlightDate": cal["cheapest"]["departureDate"], "datesCompared": cal["searchedDates"]}
