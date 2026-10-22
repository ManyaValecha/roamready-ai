"""Google Hotels engine: builds the `ts` search state (protobuf), pages with `qs` tokens and parses ds:0."""
import base64
import datetime as dt
import json
import random
import re
import threading
import time

try:
    from curl_cffi import requests as creq
except (ImportError, OSError):  # offline tests and platforms without the native curl wheel
    import requests as _requests
    class _RequestsFallback:
        @staticmethod
        def get(url, **kwargs):
            kwargs.pop("impersonate", None)
            return _requests.get(url, **kwargs)
    creq = _RequestsFallback()

CONSENT = {"CONSENT": "YES+cb", "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"}
DS0 = re.compile(r"AF_initDataCallback\(\{key: 'ds:0', hash: '\d+', data:(.*?), sideChannel: \{\}\}\);</script>", re.S)
K_HOTEL, K_PAGE, K_TOTAL = "397419284", "410579159", "416343588"
NEARBY = {1: "attraction", 2: "transit", 3: "airport", 6: "restaurant"}
MODE = {0: "driving", 2: "walking", 3: "public_transport"}


class SearchError(Exception):
    pass


class Blocked(Exception):
    pass


def _v(n):
    o = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            o.append(b | 0x80)
        else:
            o.append(b)
            return bytes(o)


def _b(f, d):
    return _v((f << 3) | 2) + _v(len(d)) + d


def _i(f, n):
    return _v(f << 3) + _v(n)


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def build_ts(location, check_in, check_out, currency, adults=2):
    loc = _b(7, location.encode("utf-8"))
    d = lambda x: _i(1, x.year) + _i(2, x.month) + _i(3, x.day)
    dates = _b(2, _b(1, d(check_in)) + _b(2, d(check_out)) + _i(3, (check_out - check_in).days)) + _b(6, _i(1, adults))
    return _b64(_i(1, 1) + _b(3, _b(1, _b(2, loc)) + _b(2, dates)) + _b(5, _b(1, _b(7, currency.encode()))))


def build_qs(token):
    return _b64(_b(2, token.encode()) + _i(7, 13))


def _g(a, *idx):
    for i in idx:
        if isinstance(a, dict):
            a = a.get(i)
        elif isinstance(a, list) and isinstance(i, int) and i < len(a):
            a = a[i]
        else:
            return None
    return a


def _num(s):
    if isinstance(s, (int, float)):
        return s
    if isinstance(s, str):
        m = re.sub(r"[^\d.]", "", s.replace(",", ""))
        try:
            return float(m) if "." in m else int(m)
        except ValueError:
            return None
    return None


def parse_hotel(h):
    name = _g(h, 1)
    if not isinstance(name, str):
        return None
    info = _g(h, 2) or []
    fid = _g(h, 9)
    cid = None
    if isinstance(fid, str) and ":" in fid:
        try:
            cid = str(int(fid.split(":")[1], 16))
        except ValueError:
            pass
    offer = _g(h, 6, 2) or []
    rating = _g(h, 7) or []
    stars = {}
    for s in _g(rating, 1, 0) or []:
        if isinstance(s, list) and len(s) > 2:
            stars[str(s[0])] = s[2]
    aspects = []
    for a in _g(rating, 9) or []:
        if isinstance(a, list) and len(a) > 4 and isinstance(a[4], str) and a[4]:
            aspects.append({"aspect": a[4], "positiveShare": round(a[1] * 100) if isinstance(a[1], (int, float)) else None, "mentions": a[2]})
    near = []
    for n in _g(info, 19) or []:
        for p in (_g(n, 1, 2) or []):
            if isinstance(p, list) and p and isinstance(p[0], str):
                near.append({"name": p[0], "type": NEARBY.get(_g(n, 0), "other"),
                             "travelTimes": {MODE.get(t[0], str(t[0])): t[1] for t in (p[2] or []) if isinstance(t, list) and len(t) > 1}})
    photos = []
    for ph in _g(h, 5, 1) or []:
        u = _g(ph, 1, 0)
        if isinstance(u, str):
            photos.append(re.sub(r"=s\d+-w\d+-h\d+.*$", "=s1000", u))
    cls = _g(h, 3)
    token = _g(h, 20)
    total = _num(_g(offer, 9, 0))
    return {
        "name": name,
        "hotelClass": _g(cls, 1) if isinstance(_g(cls, 1), int) else None,
        "hotelClassText": _g(cls, 0) if isinstance(_g(cls, 0), str) else None,
        "pricePerNight": _num(_g(offer, 1, 4)),
        "priceTotal": total,
        "priceText": _g(offer, 1, 0),
        "rating": _g(rating, 0, 0),
        "reviewCount": _g(rating, 0, 1),
        "ratingDistribution": stars or None,
        "ratingAspects": aspects,
        "description": _g(h, 11, 0),
        "latitude": _g(info, 0, 0), "longitude": _g(info, 0, 1),
        "checkInTime": (_g(info, 17, 0) or "").replace("\u202f", " ") or None,
        "checkOutTime": (_g(info, 17, 1) or "").replace("\u202f", " ") or None,
        "website": _g(info, 29, 2),
        "countryCode": _g(info, 36) if isinstance(_g(info, 36), str) else None,
        "nearbyPlaces": near,
        "photos": photos[:10],
        "googleHotelsUrl": f"https://www.google.com/travel/hotels/entity/{token}" if isinstance(token, str) else None,
        "googleMapsUrl": f"https://maps.google.com/?cid={cid}" if cid else None,
        "placeId": fid,
    }


def parse_page(html):
    m = DS0.search(html)
    if not m:
        return None, None, None, None
    d = json.loads(m.group(1))
    entries = _g(d, 0, 0, 0, 1) or []
    hotels, nxt, total, resolved = [], None, None, None
    for e in entries:
        blk = _g(e, 1)
        if not isinstance(blk, dict):
            continue
        if K_TOTAL in blk:
            t = _g(blk, K_TOTAL)
            resolved = (_g(t, 2), _g(t, 3))
            if total is None and isinstance(_g(t, 0), int):
                total = _g(t, 0)
        if K_HOTEL in blk:
            try:
                r = parse_hotel(_g(blk, K_HOTEL, 0))
            except Exception:
                r = None
            if r:
                hotels.append(r)
        elif K_PAGE in blk:
            p = blk[K_PAGE]
            nxt = p[0] if isinstance(p, list) and p and isinstance(p[0], str) and p[0] else None
            total = p[2] if isinstance(p, list) and len(p) > 2 and isinstance(p[2], int) else total
    return hotels, nxt, total, resolved


class Hotels:
    def __init__(self, proxy_fn=None, max_retries=5):
        self.proxy_fn = proxy_fn
        self.max_retries = max_retries
        self.lock = threading.Lock()
        self.stats = {"requests": 0, "retries": 0, "proxied": 0}

    def fetch(self, params):
        last, use_proxy = None, False
        for attempt in range(self.max_retries):
            with self.lock:
                self.stats["requests"] += 1
                self.stats["proxied"] += int(use_proxy)
            kw = {}
            if use_proxy and self.proxy_fn:
                p = self.proxy_fn(f"gh{random.randint(1, 10 ** 9)}")
                kw["proxies"] = {"http": p, "https": p}
            try:
                r = creq.get("https://www.google.com/travel/search", params=params, impersonate="chrome",
                             headers={"Accept-Language": "en-US,en;q=0.9"}, cookies=CONSENT, timeout=45, **kw)
                if r.status_code in (429, 503) or "/sorry/" in str(r.url):
                    raise Blocked(f"HTTP {r.status_code}")
                if r.status_code != 200:
                    raise SearchError(f"HTTP {r.status_code}")
                return r.text
            except SearchError:
                raise
            except Exception as e:
                last = e
                with self.lock:
                    self.stats["retries"] += 1
                if attempt >= 1 and self.proxy_fn:
                    use_proxy = True
                time.sleep(min(2 * (attempt + 1), 8) + random.random())
        raise Blocked(f"Google Hotels did not respond ({last})")

    def search(self, location, check_in, check_out, adults=2, currency="USD", language="en", country="us", limit=100, on_page=None):
        base = {"q": f"hotels in {location}", "hl": language, "gl": country,
                "ts": build_ts(location, check_in, check_out, currency, adults)}
        token, got, total, pages, seen, place = None, 0, None, 0, set(), None
        while got < limit and pages < 80:
            params = dict(base)
            if token:
                params.update({"qs": build_qs(token), "ap": "MAE"})
            hotels, nxt, t, res = parse_page(self.fetch(params))
            pages += 1
            if pages == 1:
                if hotels is None:
                    raise SearchError("no hotel results for this location")
                if res and res[1] == 0:
                    raise SearchError(f"location not recognized by Google (it suggested '{res[0]}')")
                place = res[0] if res else None
            if hotels is None:
                break
            total = t or total
            fresh = []
            for h in hotels:
                k = h.get("placeId") or h["name"]
                if k not in seen:
                    seen.add(k)
                    h["resolvedLocation"] = place
                    fresh.append(h)
            fresh = fresh[: limit - got]
            got += len(fresh)
            if fresh and on_page:
                if on_page(fresh, total) is False:
                    break
            if not nxt or not hotels or nxt == token:
                break
            token = nxt
        return got, total
