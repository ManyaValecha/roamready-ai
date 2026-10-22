"""Persistent state for Trip Scout: traveler profiles, price watches and saved trips (SQLite).

State survives across Alexa+ sessions: a user can say "watch this flight" today and
"any price drops?" next week, and Trip Scout remembers the route, the price it saw and the history.
"""
import json
import os
import sqlite3
import threading
import time
import uuid

DEFAULT_PROFILE = {
    "homeAirport": None,
    "currency": "USD",
    "adults": 1,
    "children": 0,
    "cabinClass": "economy",
    "maxStops": None,          # None = any, 0 = nonstop only, 1, 2
    "minHotelRating": 4.0,
    "hotelClasses": [],        # e.g. [4, 5]
    "language": "en",
    "country": "us",
}


def _db_path():
    p = os.environ.get("TRIP_SCOUT_DB")
    if p:
        p = os.path.expanduser(p)
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return p
    d = os.path.join(os.path.expanduser("~"), ".trip_scout")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "roamready.db")


class Store:
    def __init__(self, path=None):
        self.path = path or _db_path()
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
            CREATE TABLE IF NOT EXISTS watches (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, label TEXT, params TEXT NOT NULL,
                target_price REAL, first_price REAL, last_price REAL, best_price REAL, currency TEXT,
                history TEXT NOT NULL DEFAULT '[]', created REAL, last_checked REAL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, label TEXT, data TEXT NOT NULL, created REAL);
            """)
            self.db.commit()

    # ------------------------------------------------------------------ profiles
    def close(self):
        with self.lock:
            self.db.close()

    def get_profile(self, user_id):
        with self.lock:
            r = self.db.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        prof = dict(DEFAULT_PROFILE)
        if r:
            prof.update(json.loads(r["data"]))
        return prof

    def update_profile(self, user_id, **changes):
        prof = self.get_profile(user_id)
        for k, v in changes.items():
            if k in DEFAULT_PROFILE:
                prof[k] = v
        with self.lock:
            self.db.execute("INSERT INTO profiles(user_id, data, updated) VALUES(?,?,?) "
                            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
                            (user_id, json.dumps(prof), time.time()))
            self.db.commit()
        return prof

    def delete_user_memory(self, user_id):
        """Forget profile, saved trips and price watches for one user only."""
        with self.lock:
            for table in ("profiles", "trips", "watches"):
                self.db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
            self.db.commit()

    # ------------------------------------------------------------------ watches
    def add_watch(self, user_id, kind, label, params, price, currency, target_price=None):
        wid = uuid.uuid4().hex[:8]
        now = time.time()
        hist = [{"t": now, "price": price}] if price is not None else []
        with self.lock:
            self.db.execute("INSERT INTO watches(id,user_id,kind,label,params,target_price,first_price,last_price,best_price,currency,history,created,last_checked) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (wid, user_id, kind, label, json.dumps(params), target_price, price, price, price, currency, json.dumps(hist), now, now))
            self.db.commit()
        return self.get_watch(user_id, wid)

    def _row(self, r):
        d = dict(r)
        d["params"] = json.loads(d["params"])
        d["history"] = json.loads(d["history"])
        d["active"] = bool(d["active"])
        return d

    def get_watch(self, user_id, wid):
        with self.lock:
            r = self.db.execute("SELECT * FROM watches WHERE user_id=? AND id=?", (user_id, wid)).fetchone()
        return self._row(r) if r else None

    def list_watches(self, user_id, active_only=True):
        q = "SELECT * FROM watches WHERE user_id=?" + (" AND active=1" if active_only else "") + " ORDER BY created"
        with self.lock:
            rows = self.db.execute(q, (user_id,)).fetchall()
        return [self._row(r) for r in rows]

    def record_price(self, user_id, wid, price):
        w = self.get_watch(user_id, wid)
        if not w or price is None:
            return w
        hist = (w["history"] + [{"t": time.time(), "price": price}])[-200:]
        best = min([p for p in (w["best_price"], price) if p is not None])
        with self.lock:
            self.db.execute("UPDATE watches SET last_price=?, best_price=?, history=?, last_checked=? WHERE id=? AND user_id=?",
                            (price, best, json.dumps(hist), time.time(), wid, user_id))
            self.db.commit()
        return self.get_watch(user_id, wid)

    def stop_watch(self, user_id, wid):
        with self.lock:
            n = self.db.execute("UPDATE watches SET active=0 WHERE id=? AND user_id=?", (wid, user_id)).rowcount
            self.db.commit()
        return n > 0

    # ------------------------------------------------------------------ trips
    def save_trip(self, user_id, label, data):
        tid = uuid.uuid4().hex[:8]
        with self.lock:
            self.db.execute("INSERT INTO trips(id,user_id,label,data,created) VALUES(?,?,?,?,?)",
                            (tid, user_id, label, json.dumps(data), time.time()))
            self.db.commit()
        return tid

    def list_trips(self, user_id, limit=10):
        with self.lock:
            rows = self.db.execute("SELECT * FROM trips WHERE user_id=? ORDER BY created DESC LIMIT ?", (user_id, limit)).fetchall()
        return [{"id": r["id"], "label": r["label"], "created": r["created"], "data": json.loads(r["data"])} for r in rows]
