"""Rebuild trip_scout/data/airports.json from OurAirports (public domain): medium/large airports with scheduled service."""
import csv, io, json, os
from curl_cffi import requests as r

raw = r.get("https://davidmegginson.github.io/ourairports-data/airports.csv", timeout=90).text
out = []
for a in csv.DictReader(io.StringIO(raw)):
    if a["type"] not in ("large_airport", "medium_airport") or a["scheduled_service"] != "yes" or len(a["iata_code"] or "") != 3:
        continue
    out.append({"iata": a["iata_code"], "name": a["name"], "city": a["municipality"], "country": a["iso_country"],
                "large": a["type"] == "large_airport", "lat": round(float(a["latitude_deg"]), 3), "lon": round(float(a["longitude_deg"]), 3)})
path = os.path.join(os.path.dirname(__file__), "..", "trip_scout", "data", "airports.json")
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "airports")