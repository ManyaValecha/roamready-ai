"""Tolerant date parsing for spoken requests: '2026-11-12', 'tomorrow', 'next friday', 'november 12', 'in 3 weeks', 'november'."""
import calendar
import datetime as dt
import re

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}


def _future(d, today):
    return d if d >= today else d.replace(year=d.year + 1)


def parse_date(text, today=None):
    """Return a single date or None."""
    today = today or dt.date.today()
    if text is None:
        return None
    if isinstance(text, dt.date):
        return text
    s = str(text).strip().lower().replace(",", " ")
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return dt.date.fromisoformat(s)
    if s in ("today", "tonight"):
        return today
    if s == "tomorrow":
        return today + dt.timedelta(days=1)
    m = re.fullmatch(r"in (\d+) (day|days|week|weeks|month|months)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        days = n if unit.startswith("day") else n * 7 if unit.startswith("week") else n * 30
        return today + dt.timedelta(days=days)
    m = re.fullmatch(r"(next |this )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", s)
    if m:
        delta = (WEEKDAYS[m.group(2)] - today.weekday()) % 7 or 7
        return today + dt.timedelta(days=delta)
    m = re.fullmatch(r"([a-z]+) (\d{1,2})( \d{4})?", s) or re.fullmatch(r"(\d{1,2}) ([a-z]+)( \d{4})?", s)
    if m:
        a, b, y = m.group(1), m.group(2), m.group(3)
        mon, day = (a, b) if a.isalpha() else (b, a)
        if mon in MONTHS:
            year = int(y) if y else today.year
            d = dt.date(year, MONTHS[mon], int(day))
            return d if y else _future(d, today)
    return None


def parse_window(text, today=None):
    """Return (start, end) for 'november', 'next month', 'this weekend', a single date, or 'a to b'."""
    today = today or dt.date.today()
    if text is None:
        return None
    s = str(text).strip().lower()
    if " to " in s or " - " in s or " until " in s:
        a, b = re.split(r" to | - | until ", s, maxsplit=1)
        da, db = parse_date(a, today), parse_date(b, today)
        if da and db:
            return da, db
    if s in MONTHS:
        mon = MONTHS[s]
        year = today.year if mon >= today.month else today.year + 1
        start = dt.date(year, mon, 1)
        return max(start, today + dt.timedelta(days=1)), dt.date(year, mon, calendar.monthrange(year, mon)[1])
    if s == "next month":
        y, m = (today.year + (today.month // 12), today.month % 12 + 1)
        return dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])
    if s in ("this weekend", "next weekend"):
        fri = today + dt.timedelta(days=(4 - today.weekday()) % 7 or (7 if s == "next weekend" else 0))
        return fri, fri + dt.timedelta(days=2)
    d = parse_date(s, today)
    if d:
        return d, d
    return None
