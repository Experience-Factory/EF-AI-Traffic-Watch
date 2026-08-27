# -*- coding: utf-8 -*-
"""Turn the daily CSVs into the buckets the report draws: one point per week for
the two detailed months, one weekly-average point per month for the six before."""
import csv
import datetime as dt
import os

import window as W

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

SESSION_FIELDS = ["sessions", "purchaseRevenue", "transactions", "keyEvents", "engagedSessions"]
PAGE_FIELDS = ["screenPageViews", "sessions", "entrances"]


def read(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def weekly(rows, key_fields, keys, value_fields, weeks):
    """Sum daily rows into ISO weeks. Returns {week_monday: {key: {field: value}}}."""
    index = {w: {} for w in weeks}
    span = {w: (w, w + dt.timedelta(days=6)) for w in weeks}
    starts = sorted(weeks)
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        monday = d - dt.timedelta(days=d.weekday())
        if monday not in index:
            continue
        key = tuple(r[k] for k in key_fields)
        if keys is not None and key not in keys:
            continue
        bucket = index[monday].setdefault(key, {f: 0.0 for f in value_fields})
        for f in value_fields:
            bucket[f] += float(r.get(f, 0) or 0)
    return index


def buckets(win):
    """Ordered list of report points, each already expressed as a weekly figure."""
    out = []
    for ym in win["averaged_months"]:
        weeks = [w for w in win["weeks"] if W.month_of_week(w) == ym]
        if weeks:
            out.append(
                {
                    "kind": "avg",
                    "label": dt.date(ym[0], ym[1], 1).strftime("%b"),
                    "sub": f"{len(weeks)}-week avg",
                    "weeks": weeks,
                    "start": weeks[0],
                    "end": weeks[-1] + dt.timedelta(days=6),
                }
            )
    for ym in win["detailed_months"]:
        for w in [w for w in win["weeks"] if W.month_of_week(w) == ym]:
            out.append(
                {
                    "kind": "week",
                    "label": f"W{w.isocalendar().week:02d}",
                    "sub": w.strftime("%d %b"),
                    "weeks": [w],
                    "start": w,
                    "end": w + dt.timedelta(days=6),
                }
            )
    return out


def fill(bucket_list, index, key, value_fields):
    """Average the per-week values of a bucket for one key (venue or page)."""
    for b in bucket_list:
        acc = {f: 0.0 for f in value_fields}
        for w in b["weeks"]:
            row = index.get(w, {}).get(key)
            if row:
                for f in value_fields:
                    acc[f] += row[f]
        n = len(b["weeks"])
        b.setdefault("data", {})[key] = {f: acc[f] / n for f in value_fields}
        b["data"][key]["_total"] = dict(acc)
    return bucket_list
