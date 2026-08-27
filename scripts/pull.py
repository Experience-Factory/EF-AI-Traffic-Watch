# -*- coding: utf-8 -*-
"""Pull the daily GA4 numbers this report is built on.

Writes three append-and-merge CSVs in data/ (keyed rows are overwritten, older
rows outside the current window are kept, so history accumulates):
  sessions_daily.csv   per day and venue, AI vs all traffic and revenue
  b2b_daily.csv        per day and B2B page, AI vs all views/sessions/entrances
  ai_sources_daily.csv per day and assistant, sessions

Usage:  python scripts/pull.py [--asof YYYY-MM-DD] [--start YYYY-MM-DD]
"""
import argparse
import csv
import datetime as dt
import os

import ga4_client as ga
import window as W

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

VENUES = ["antwerp", "eupen", "all"]
SESSION_METRICS = ["sessions", "purchaseRevenue", "transactions", "keyEvents", "engagedSessions"]
PAGE_METRICS = ["screenPageViews", "sessions"]
# GA4 Data API has no "entrances" metric: landings are counted with a second query
# on landingPagePlusQueryString, whose session count is exactly the entrance count.
LANDING_METRICS = ["sessions"]

B2B_REGEX = (
    r"^/(antwerp|eupen)/(nl/|fr/|de/)?(teambuilding|bedrijfsevent|business|business-events|"
    r"business-event-aftermovie|business-event-discovery-call|business-event-teambuilding|"
    r"evenement-entreprise-teambuilding|firmenveranstaltung)/?$"
)


def merge_csv(path, fieldnames, rows, key_fields):
    existing = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[tuple(r[k] for k in key_fields)] = r
    for r in rows:
        existing[tuple(str(r[k]) for k in key_fields)] = r
    ordered = sorted(existing.values(), key=lambda r: tuple(str(r[k]) for k in key_fields))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in ordered:
            w.writerow(r)
    return len(ordered)


def num(v):
    f = float(v or 0)
    return int(f) if f == int(f) else round(f, 2)


def pull_sessions(cl, start, end):
    out = {}
    for venue in VENUES:
        vf = ga.venue_filter(venue)
        for scope, filt in (
            ("all", vf),
            ("ai", ga.and_all(vf, ga.ai_filter())),
        ):
            for dims, mets in ga.run(cl, ["date"], SESSION_METRICS, start, end, filt):
                d = dt.datetime.strptime(dims[0], "%Y%m%d").date().isoformat()
                row = out.setdefault(
                    (d, venue),
                    {"date": d, "venue": venue, **{f"{s}_{m}": 0 for s in ("ai", "all") for m in SESSION_METRICS}},
                )
                for m, v in zip(SESSION_METRICS, mets):
                    row[f"{scope}_{m}"] = num(v)
    return list(out.values())


def pull_b2b(cl, start, end):
    page_filter = ga.regex_filter("pagePath", B2B_REGEX)
    out = {}
    for scope, filt in (
        ("all", page_filter),
        ("ai", ga.and_all(page_filter, ga.ai_filter())),
    ):
        for dims, mets in ga.run(cl, ["date", "pagePath"], PAGE_METRICS, start, end, filt):
            d = dt.datetime.strptime(dims[0], "%Y%m%d").date().isoformat()
            page = "/" + dims[1].strip("/") + "/"
            row = out.setdefault(
                (d, page),
                {"date": d, "page": page, **{f"{s}_{m}": 0 for s in ("ai", "all") for m in PAGE_METRICS + ["entrances"]}},
            )
            for m, v in zip(PAGE_METRICS, mets):
                row[f"{scope}_{m}"] += num(v)

    landing_filter = ga.regex_filter("landingPagePlusQueryString", B2B_REGEX)
    for scope, filt in (
        ("all", landing_filter),
        ("ai", ga.and_all(landing_filter, ga.ai_filter())),
    ):
        for dims, mets in ga.run(
            cl, ["date", "landingPagePlusQueryString"], LANDING_METRICS, start, end, filt
        ):
            d = dt.datetime.strptime(dims[0], "%Y%m%d").date().isoformat()
            page = "/" + dims[1].split("?")[0].strip("/") + "/"
            row = out.setdefault(
                (d, page),
                {"date": d, "page": page, **{f"{s}_{m}": 0 for s in ("ai", "all") for m in PAGE_METRICS + ["entrances"]}},
            )
            row[f"{scope}_entrances"] = row.get(f"{scope}_entrances", 0) + num(mets[0])
    for row in out.values():
        for s in ("ai", "all"):
            row.setdefault(f"{s}_entrances", 0)
    return list(out.values())


def pull_sources(cl, start, end):
    out = []
    for dims, mets in ga.run(
        cl, ["date", "sessionSource"], ["sessions"], start, end, ga.ai_filter()
    ):
        out.append(
            {
                "date": dt.datetime.strptime(dims[0], "%Y%m%d").date().isoformat(),
                "source": dims[1],
                "sessions": num(mets[0]),
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None, help="pretend the run happens on this date")
    ap.add_argument("--start", default=None, help="override the pull start date")
    args = ap.parse_args()

    asof = dt.date.fromisoformat(args.asof) if args.asof else dt.date.today()
    win = W.build(asof)
    start = args.start or win["data_start"].isoformat()
    end = win["data_end"].isoformat()
    print(f"[pull] as-of {asof} ({asof:%A}) · window {start} -> {end}")

    cl = ga.client()
    os.makedirs(DATA, exist_ok=True)

    rows = pull_sessions(cl, start, end)
    n = merge_csv(
        os.path.join(DATA, "sessions_daily.csv"),
        ["date", "venue"] + [f"{s}_{m}" for s in ("ai", "all") for m in SESSION_METRICS],
        rows,
        ["date", "venue"],
    )
    print(f"[pull] sessions_daily.csv   {len(rows):5d} rows pulled, {n} total")

    rows = pull_b2b(cl, start, end)
    n = merge_csv(
        os.path.join(DATA, "b2b_daily.csv"),
        ["date", "page"] + [f"{s}_{m}" for s in ("ai", "all") for m in PAGE_METRICS + ["entrances"]],
        rows,
        ["date", "page"],
    )
    print(f"[pull] b2b_daily.csv        {len(rows):5d} rows pulled, {n} total")

    rows = pull_sources(cl, start, end)
    n = merge_csv(
        os.path.join(DATA, "ai_sources_daily.csv"),
        ["date", "source", "sessions"],
        rows,
        ["date", "source"],
    )
    print(f"[pull] ai_sources_daily.csv {len(rows):5d} rows pulled, {n} total")


if __name__ == "__main__":
    main()
