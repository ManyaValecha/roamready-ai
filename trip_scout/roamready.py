"""Deterministic destination itinerary optimizer and disruption rescue demo.

The small Barcelona catalog is explicitly illustrative: estimates are not live
prices, opening hours, weather, or venue status. Replace it with licensed feeds
before using for a real trip.
"""
from __future__ import annotations

ATTRACTIONS = [
    {"name":"Sagrada Família","area":"Eixample","interest":"architecture","cost":26,"minutes":100,"open":"09:00–18:00","stepFree":True},
    {"name":"Park Güell","area":"Gràcia","interest":"architecture","cost":18,"minutes":90,"open":"09:30–19:30","stepFree":False},
    {"name":"Picasso Museum","area":"El Born","interest":"art","cost":14,"minutes":90,"open":"10:00–19:00","stepFree":True},
    {"name":"Gothic Quarter walk","area":"Gothic Quarter","interest":"history","cost":0,"minutes":75,"open":"All day","stepFree":False},
    {"name":"La Boqueria market","area":"El Raval","interest":"food","cost":0,"minutes":60,"open":"08:00–20:30","stepFree":True},
    {"name":"Barceloneta waterfront","area":"Barceloneta","interest":"outdoors","cost":0,"minutes":90,"open":"All day","stepFree":True},
    {"name":"Montjuïc gardens","area":"Montjuïc","interest":"outdoors","cost":0,"minutes":90,"open":"10:00–20:00","stepFree":True},
    {"name":"Casa Batlló","area":"Eixample","interest":"architecture","cost":35,"minutes":75,"open":"09:00–20:00","stepFree":True},
    {"name":"Hospital de Sant Pau","area":"Eixample","interest":"architecture","cost":18,"minutes":75,"open":"09:30–18:30","stepFree":True},
    {"name":"Fundació Joan Miró","area":"Montjuïc","interest":"art","cost":15,"minutes":75,"open":"10:00–19:00","stepFree":True},
    {"name":"Eixample gallery walk","area":"Eixample","interest":"art","cost":0,"minutes":60,"open":"All day","stepFree":True},
    {"name":"Sant Antoni market tasting","area":"El Raval","interest":"food","cost":22,"minutes":75,"open":"10:00–18:00","stepFree":True},
    {"name":"Gràcia café stroll","area":"Gràcia","interest":"food","cost":0,"minutes":60,"open":"All day","stepFree":True},
]
AREAS = {"Eixample": {"Eixample":8,"Gràcia":24,"El Born":22,"Gothic Quarter":20,"El Raval":18,"Barceloneta":28,"Montjuïc":30},
         "Gràcia": {"Eixample":24,"Gràcia":8,"El Born":30,"Gothic Quarter":28,"El Raval":27,"Barceloneta":35,"Montjuïc":35},
         "El Born": {"Eixample":22,"Gràcia":30,"El Born":8,"Gothic Quarter":12,"El Raval":14,"Barceloneta":18,"Montjuïc":28},
         "Gothic Quarter": {"Eixample":20,"Gràcia":28,"El Born":12,"Gothic Quarter":8,"El Raval":12,"Barceloneta":18,"Montjuïc":25},
         "El Raval": {"Eixample":18,"Gràcia":27,"El Born":14,"Gothic Quarter":12,"El Raval":8,"Barceloneta":22,"Montjuïc":20},
         "Barceloneta": {"Eixample":28,"Gràcia":35,"El Born":18,"Gothic Quarter":18,"El Raval":22,"Barceloneta":8,"Montjuïc":30},
         "Montjuïc": {"Eixample":30,"Gràcia":35,"El Born":28,"Gothic Quarter":25,"El Raval":20,"Barceloneta":30,"Montjuïc":8}}

def build_itinerary(days=3, budget=120, interests=None, accessible=False, unavailable=None, party_size=1):
    days=max(1,min(int(days),7)); budget=max(0,float(budget)); interests=[x.lower() for x in (interests or ["architecture","history","food","art","outdoors"])]
    blocked={x.lower() for x in (unavailable or [])}; chosen=set(); plan=[]; spent=0; previous="Eixample"
    candidates=[a for a in ATTRACTIONS if a["name"].lower() not in blocked and a["interest"] not in blocked and a["interest"] in interests and (not accessible or a["stepFree"])]
    for day in range(1,days+1):
        stops=[]
        available=[a for a in candidates if a["name"] not in chosen and a["cost"]*party_size+spent<=budget]
        available.sort(key=lambda a:(interests.index(a["interest"]) if a["interest"] in interests else len(interests), AREAS[previous][a["area"]], a["cost"]))
        clock=9*60; last_area=previous
        for a in available:
            if len(stops) >= 2: break
            if a["cost"] * party_size + spent > budget: continue
            transit=AREAS[last_area][a["area"]]
            start=clock+transit; end=start+a["minutes"]
            if end>18*60: continue
            if a["open"] != "All day":
                opens, closes = [int(x.split(":")[0])*60+int(x.split(":")[1]) for x in a["open"].split("–")]
                if start < opens or end > closes: continue
            stops.append({**a,"costPerPerson":a["cost"],"cost":a["cost"]*party_size,"travelMinutes":transit,"start":f"{start//60:02}:{start%60:02}","end":f"{end//60:02}:{end%60:02}","reason":f"Matches {a['interest']} interest; {transit} min from previous stop."})
            chosen.add(a["name"]); spent+=a["cost"]*party_size; clock=end+15; last_area=a["area"]
        if stops: previous=stops[-1]["area"]
        plan.append({"day":day,"stops":stops})
    return {"destination":"Barcelona","days":plan,"estimatedActivityCost":spent,"budget":budget,"remainingBudget":round(budget-spent,2),"estimatedTravelMinutes":sum(s["travelMinutes"] for d in plan for s in d["stops"]),"dataLabel":"Illustrative demo estimates; verify venue hours, prices and access before travel.","accessibilityFilter":accessible,"partySize":party_size}

def rescue_itinerary(days=3,budget=120,interests=None,accessible=False,disruption="Sagrada Família closed"):
    # Deterministic scenario allows a reproducible before/after demonstration.
    blocked=["Sagrada Família"] if "sagrada" in disruption.lower() else (["outdoors","Park Güell","Barceloneta waterfront","Montjuïc gardens"] if any(x in disruption.lower() for x in ("rain","weather")) else [disruption])
    new=build_itinerary(days,budget,interests,accessible,blocked)
    return {"disruption":disruption,"removedStops":blocked,"itinerary":new,"changes":[f"Removed unavailable stops: {', '.join(blocked)}.",f"Rebuilt remaining days within the ${budget:g} activity budget.","All replacement stop costs and travel estimates are shown as illustrative demo data."],"confirmationRequired":False}


DEMO_BASE_COSTS = {"airfare": 620, "lodging": 480, "meals": 280, "localTransport": 80}


def build_demo_trip(days=4, total_budget=1800, travelers=2, interests=None, unavailable=None):
    """Offline, fully labeled illustrative trip estimate for the repeatable judging demo."""
    days = max(1, min(int(days), 7))
    travelers = max(1, min(int(travelers), 8))
    budget = max(0.0, float(total_budget))
    fixed = dict(DEMO_BASE_COSTS)
    activity_cap = max(0.0, budget - sum(fixed.values()))
    itinerary = build_itinerary(days, activity_cap, interests, unavailable=unavailable, party_size=travelers)
    breakdown = {**fixed, "activities": itinerary["estimatedActivityCost"]}
    total = sum(breakdown.values())
    return {"kind":"demo-trip", "destination":"Barcelona", "days":days, "travelers":travelers,
            "currency":"EUR", "budget":budget, "costBreakdown":breakdown, "estimatedTotal":total,
            "remainingBudget":round(budget-total, 2), "itinerary":itinerary,
            "estimatedTravelMinutes":itinerary["estimatedTravelMinutes"],
            "costAssumptions":{"airfare":"€620 round-trip estimate for two travelers","lodging":"€160/night × 3 nights","meals":"€70/day × 4 days for two","localTransport":"€40 per traveler for the trip","activities":"Illustrative admission estimates multiplied by traveler count"},
            "dataLabel":"SIMULATED ESTIMATES — airfare, lodging, meals, local transport, ticket costs, hours and routing are illustrative, not live prices or availability."}


def rescue_demo_trip(days=4, total_budget=1800, travelers=2, interests=None, disruption="Sagrada Família closure"):
    before = build_demo_trip(days, total_budget, travelers, interests)
    blocked = ["Sagrada Família"] if "sagrada" in disruption.lower() else ["outdoors", "Park Güell", "Barceloneta waterfront", "Montjuïc gardens"]
    after = build_demo_trip(days, total_budget, travelers, interests, blocked)
    return {"kind":"demo-rescue", "disruption":disruption, "simulated":True, "before":before, "after":after,
            "removedStops":blocked, "changes":{"estimatedCostDelta":after["estimatedTotal"]-before["estimatedTotal"],
            "remainingBudgetDelta":after["remainingBudget"]-before["remainingBudget"],
            "travelMinutesDelta":after["estimatedTravelMinutes"]-before["estimatedTravelMinutes"]},
            "dataLabel":"SIMULATED DISRUPTION — no live venue or weather feed is connected."}
