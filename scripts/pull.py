# -*- coding: utf-8 -*-
"""Pull the daily GA4 numbers this report is built on.

Writes three append-and-merge CSVs in data/ (keyed rows are overwritten, older
rows outside the current window are kept, so history accumulates):
  sessions_daily.csv   per day and venue, AI vs all traffic and revenue
  b2b_daily.csv        per day and B2B page, AI vs all views/sessions/entrances
  ai_sources_daily.csv per day and assistant, sessions
  ai_sources_venue_daily.csv per day, venue and assistant, sessions and revenue
  matomo_daily.csv     per day and venue, Matomo visits and AI-assistant visits

Usage:  python scripts/pull.py [--asof YYYY-MM-DD] [--start YYYY-MM-DD]
"""
import argparse
import csv
import datetime as dt
import json
import os
import urllib.parse
import urllib.request

import ga4_client as ga
import window as W

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

VENUES = ["antwerp", "eupen", "all"]
SESSION_METRICS = ["sessions", "purchaseRevenue", "transactions", "keyEvents", "engagedSessions"]
PAGE_METRICS = ["screenPageViews", "sessions"]
SOURCE_METRICS = ["sessions", "purchaseRevenue", "transactions"]
# GA4 Data API has no "entrances" metric: landings are counted with a second query
# on landingPagePlusQueryString, whose session count is exactly the entrance count.
LANDING_METRICS = ["sessions"]

# Matomo (hosted by Pixelbar) counts every visitor without cookies, so unlike GA4 it is
# not cut down by the consent banner. Token: MATOMO_TOKEN in Actions, a local file here.
MATOMO_URL = "https://matomo.pixelbar.be/index.php"
MATOMO_SITES = {"antwerp": 234, "eupen": 235}
MATOMO_TOKEN_FILE = r"C:\Users\Laptop - Regis\.claude\matomo-token.txt"

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


def pull_sources_venue(cl, start, end):
    """Per day, venue and AI source: sessions and the revenue booked in them."""
    out = []
    for venue in ("antwerp", "eupen"):
        filt = ga.and_all(ga.venue_filter(venue), ga.ai_filter())
        for dims, mets in ga.run(
            cl, ["date", "sessionSource"], SOURCE_METRICS, start, end, filt
        ):
            row = {
                "date": dt.datetime.strptime(dims[0], "%Y%m%d").date().isoformat(),
                "venue": venue,
                "source": dims[1],
            }
            for m, v in zip(SOURCE_METRICS, mets):
                row[m] = num(v)
            out.append(row)
    return out


def matomo_token():
    token = os.environ.get("MATOMO_TOKEN", "").strip()
    if not token and os.path.exists(MATOMO_TOKEN_FILE):
        with open(MATOMO_TOKEN_FILE, encoding="utf-8-sig") as f:
            token = f.read().strip()
    return token


def matomo_api(token, **params):
    # POST keeps the token out of URLs and works with "secure only" tokens
    body = urllib.parse.urlencode({"module": "API", "format": "json", "token_auth": token, **params})
    req = urllib.request.Request(MATOMO_URL, data=body.encode("utf-8"))
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    if isinstance(out, dict) and out.get("result") == "error":
        raise RuntimeError("Matomo: " + str(out.get("message")))
    return out


def pull_matomo(token, start, end):
    rows = []
    for venue, site in MATOMO_SITES.items():
        dates = f"{start},{end}"
        visits = matomo_api(token, method="VisitsSummary.getVisits", idSite=site, period="day", date=dates)
        ai = matomo_api(
            token, method="Referrers.getAIAssistants", idSite=site, period="day", date=dates, filter_limit=-1
        )
        for d, n in visits.items():
            day_ai = ai.get(d) if isinstance(ai.get(d), list) else []
            rows.append({
                "date": d,
                "venue": venue,
                "visits": num(n),
                "ai_visits": sum(int(r.get("nb_visits", 0) or 0) for r in day_ai),
            })
    return rows


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

    rows = pull_sources_venue(cl, start, end)
    n = merge_csv(
        os.path.join(DATA, "ai_sources_venue_daily.csv"),
        ["date", "venue", "source"] + SOURCE_METRICS,
        rows,
        ["date", "venue", "source"],
    )
    print(f"[pull] ai_sources_venue_daily.csv {len(rows):5d} rows pulled, {n} total")

    # Matomo is a second source: if it fails, keep the GA4 data and the last Matomo pull
    token = matomo_token()
    if not token:
        print("[pull] matomo_daily.csv  skipped, no MATOMO_TOKEN")
        return
    try:
        rows = pull_matomo(token, start, end)
    except Exception as e:
        print(f"[pull] matomo_daily.csv  FAILED, kept previous data: {e}")
        return
    n = merge_csv(
        os.path.join(DATA, "matomo_daily.csv"),
        ["date", "venue", "visits", "ai_visits"],
        rows,
        ["date", "venue"],
    )
    print(f"[pull] matomo_daily.csv     {len(rows):5d} rows pulled, {n} total")


if __name__ == "__main__":
    main()
