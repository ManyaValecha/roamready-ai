"""Resolve spoken places ("Barcelona", "New York", "Heathrow", "LHR") to IATA airport / metro codes."""
import difflib
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))

# IATA metropolitan area codes (search all airports of a city at once)
METRO = {
    "NYC": "New York", "LON": "London", "PAR": "Paris", "TYO": "Tokyo", "CHI": "Chicago", "WAS": "Washington",
    "MIL": "Milan", "ROM": "Rome", "STO": "Stockholm", "MOW": "Moscow", "BJS": "Beijing", "SEL": "Seoul",
    "OSA": "Osaka", "BUE": "Buenos Aires", "RIO": "Rio de Janeiro", "SAO": "Sao Paulo", "YTO": "Toronto",
    "YMQ": "Montreal", "BER": "Berlin", "REK": "Reykjavik", "JKT": "Jakarta", "BKK": "Bangkok", "DXB": "Dubai",
}
ALIASES = {"nyc": "NYC", "new york": "NYC", "new york city": "NYC", "big apple": "NYC", "la": "LAX", "los angeles": "LAX", "sf": "SFO",
           "san francisco": "SFO", "vegas": "LAS", "las vegas": "LAS", "dc": "WAS", "washington dc": "WAS",
           "prague": "PRG", "praha": "PRG", "vienna": "VIE", "wien": "VIE", "munich": "MUC", "munchen": "MUC",
           "rome": "ROM", "milan": "MIL", "london": "LON", "paris": "PAR", "tokyo": "TYO", "berlin": "BER",
           "hawaii": "HNL", "honolulu": "HNL", "bali": "DPS", "cancun": "CUN", "lisbon": "LIS", "barcelona": "BCN",
           "madrid": "MAD", "amsterdam": "AMS", "dublin": "DUB", "athens": "ATH", "istanbul": "IST", "seoul": "SEL",
           "chicago": "CHI", "toronto": "YTO", "sydney": "SYD", "singapore": "SIN", "bangkok": "BKK", "dubai": "DXB"}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(airport|international|intl|city|the|to|from|in)\b", " ", s)
    return re.sub(r"[^a-z ]+", " ", s).strip()


class Places:
    def __init__(self):
        with open(os.path.join(HERE, "data", "airports.json"), encoding="utf-8") as f:
            self.airports = json.load(f)
        self.by_iata = {a["iata"]: a for a in self.airports}
        self.by_city = {}
        for a in self.airports:
            self.by_city.setdefault(_norm(a["city"]), []).append(a)

    def label(self, code):
        if code in METRO:
            return f"{METRO[code]} (all airports)"
        a = self.by_iata.get(code)
        return f"{a['city']} ({code})" if a else code

    def resolve(self, text):
        """Return {'code', 'label'} or None."""
        if not text:
            return None
        raw = text.strip()
        up = raw.upper()
        if re.fullmatch(r"[A-Z]{3}", up) and (up in self.by_iata or up in METRO):
            return {"code": up, "label": self.label(up)}
        n = _norm(raw)
        if n in ALIASES:
            c = ALIASES[n]
            return {"code": c, "label": self.label(c)}
        if n in self.by_city:
            cands = sorted(self.by_city[n], key=lambda a: (not a["large"], a["name"]))
            return {"code": cands[0]["iata"], "label": self.label(cands[0]["iata"])}
        # airport name contains the words ("heathrow", "charles de gaulle")
        hits = [a for a in self.airports if n and n in _norm(a["name"])]
        if hits:
            a = sorted(hits, key=lambda a: not a["large"])[0]
            return {"code": a["iata"], "label": self.label(a["iata"])}
        close = difflib.get_close_matches(n, list(self.by_city) + list(ALIASES), n=1, cutoff=0.82)
        if close:
            return self.resolve(close[0])
        return None
