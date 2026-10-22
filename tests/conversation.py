"""Conversation test against the Alexa+ simulator host (web/app.py): the full demo script, end to end."""
import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8770"
SCRIPT = [
    "I live in New York, we are two adults",
    "Plan a long weekend in Barcelona in November, we have 2500 dollars",
    "Watch that price",
    "When is it cheapest to fly to Lisbon next month for 4 nights?",
    "Did any of my prices drop?",
]
sid = None
with httpx.Client(timeout=180) as c:
    for line in SCRIPT:
        t = time.time()
        r = c.post(BASE + "/api/chat", json={"session_id": sid, "user_id": "conversation-test", "text": line}).json()
        sid = r["session_id"]
        print(f"\nUSER: {line}\nALEXA ({r['mode']}, {round(time.time() - t, 1)}s): {r['speech']}")
        for tr in r["trace"]:
            print("   ", json.dumps(tr)[:260])
        if r.get("ui"):
            sc = r["ui"]["toolResult"].get("structuredContent", {})
            print("    [screen]", sc.get("kind"), "-", sc.get("title"))
