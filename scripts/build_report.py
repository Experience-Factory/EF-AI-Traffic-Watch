# -*- coding: utf-8 -*-
"""Build docs/index.html, the EF-branded AI Traffic Watch report.

Usage:  python scripts/build_report.py [--asof YYYY-MM-DD]
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import series as S
import window as W

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, "docs")

SESSION_FIELDS = [
    "ai_sessions", "all_sessions",
    "ai_purchaseRevenue", "all_purchaseRevenue",
    "ai_transactions", "all_transactions",
    "ai_keyEvents", "all_keyEvents",
    "ai_engagedSessions", "all_engagedSessions",
]
PAGE_FIELDS = ["ai_screenPageViews", "all_screenPageViews", "ai_sessions", "all_sessions",
               "ai_entrances", "all_entrances"]

B2B_GROUPS = [
    ("Antwerp - Teambuilding hub", "antwerp", [
        ("/antwerp/teambuilding/", "EN"),
        ("/antwerp/nl/teambuilding/", "NL"),
    ]),
    ("Antwerp - Bedrijfsevent / business events", "antwerp", [
        ("/antwerp/business-events/", "EN"),
        ("/antwerp/nl/bedrijfsevent/", "NL"),
        ("/antwerp/nl/business-events/", "NL legacy"),
    ]),
    ("Antwerp - Menu entry & legacy B2B pages", "antwerp", [
        ("/antwerp/business/", "EN menu"),
        ("/antwerp/nl/business/", "NL menu"),
        ("/antwerp/business-event-aftermovie/", "EN"),
        ("/antwerp/business-event-discovery-call/", "EN"),
        ("/antwerp/nl/business-event-discovery-call/", "NL"),
    ]),
    ("Eupen - Business event & teambuilding", "eupen", [
        ("/eupen/business-event-teambuilding/", "EN"),
        ("/eupen/fr/evenement-entreprise-teambuilding/", "FR"),
        ("/eupen/de/firmenveranstaltung/", "DE"),
    ]),
]
B2B_PAGES = [p for _, _, pages in B2B_GROUPS for p, _ in pages]


def safe_div(a, b):
    return (a / b) if b else 0.0


def build_payload(asof):
    win = W.build(asof)
    weeks = win["weeks"]

    sess_rows = S.read("sessions_daily.csv")
    sess_idx = S.weekly(sess_rows, ["venue"], None, SESSION_FIELDS, weeks)
    b2b_rows = S.read("b2b_daily.csv")
    b2b_idx = S.weekly(b2b_rows, ["page"], None, PAGE_FIELDS, weeks)

    bl = S.buckets(win)
    for venue in ("antwerp", "eupen", "all"):
        S.fill(bl, sess_idx, (venue,), SESSION_FIELDS)
    for page in B2B_PAGES:
        S.fill(bl, b2b_idx, (page,), PAGE_FIELDS)

    buckets = []
    for b in bl:
        entry = {
            "label": b["label"],
            "sub": b["sub"],
            "kind": b["kind"],
            "start": b["start"].isoformat(),
            "end": b["end"].isoformat(),
            "nweeks": len(b["weeks"]),
        }
        for venue in ("antwerp", "eupen", "all"):
            d = b["data"][(venue,)]
            entry[venue] = {
                "ai_sessions": round(d["ai_sessions"], 1),
                "sessions": round(d["all_sessions"], 1),
                "share": round(safe_div(d["ai_sessions"], d["all_sessions"]) * 100, 2),
                "ai_revenue": round(d["ai_purchaseRevenue"], 2),
                "revenue": round(d["all_purchaseRevenue"], 2),
                "ai_transactions": round(d["ai_transactions"], 2),
                "ai_key_events": round(d["ai_keyEvents"], 2),
                "ai_engagement": round(safe_div(d["ai_engagedSessions"], d["ai_sessions"]) * 100, 1),
                "engagement": round(safe_div(d["all_engagedSessions"], d["all_sessions"]) * 100, 1),
            }
        # AI money share is measured against ALL online revenue, both hosts
        entry["money"] = {
            "ai_revenue_venues": round(entry["antwerp"]["ai_revenue"] + entry["eupen"]["ai_revenue"], 2),
            "ai_revenue": entry["all"]["ai_revenue"],
            "online_revenue": entry["all"]["revenue"],
            "share": round(safe_div(entry["all"]["ai_revenue"], entry["all"]["revenue"]) * 100, 2),
            "ai_transactions": entry["all"]["ai_transactions"],
        }
        b2b = {"ai_views": 0.0, "ai_sessions": 0.0, "ai_entrances": 0.0, "views": 0.0}
        for page in B2B_PAGES:
            d = b["data"][(page,)]
            b2b["ai_views"] += d["ai_screenPageViews"]
            b2b["ai_sessions"] += d["ai_sessions"]
            b2b["ai_entrances"] += d["ai_entrances"]
            b2b["views"] += d["all_screenPageViews"]
        entry["b2b"] = {k: round(v, 1) for k, v in b2b.items()}
        buckets.append(entry)

    # per-page B2B detail: window total (not weekly average) + last complete week
    detail = []
    for group, venue, pages in B2B_GROUPS:
        for page, lang in pages:
            tot = {f: 0.0 for f in PAGE_FIELDS}
            for w in weeks:
                row = b2b_idx.get(w, {}).get((page,))
                if row:
                    for f in PAGE_FIELDS:
                        tot[f] += row[f]
            last = b2b_idx.get(weeks[-1], {}).get((page,), {f: 0.0 for f in PAGE_FIELDS})
            detail.append({
                "group": group, "venue": venue, "page": page, "lang": lang,
                "ai_views": round(tot["ai_screenPageViews"]),
                "ai_sessions": round(tot["ai_sessions"]),
                "ai_entrances": round(tot["ai_entrances"]),
                "views": round(tot["all_screenPageViews"]),
                "share": round(safe_div(tot["ai_screenPageViews"], tot["all_screenPageViews"]) * 100, 2),
                "last_week_ai_views": round(last["ai_screenPageViews"]),
                "last_week_views": round(last["all_screenPageViews"]),
            })

    # assistant split over the detailed months
    src_rows = S.read("ai_sources_daily.csv")
    first_detailed = min(b["start"] for b in bl if b["kind"] == "week")
    src = {}
    for r in src_rows:
        if r["date"] >= first_detailed.isoformat():
            src[r["source"]] = src.get(r["source"], 0) + float(r["sessions"] or 0)
    sources = sorted(
        ({"source": k, "sessions": int(v)} for k, v in src.items()),
        key=lambda x: -x["sessions"],
    )

    last, prev = buckets[-1], buckets[-2]
    baseline_buckets = [b for b in buckets if b["kind"] == "avg"]
    base = {
        v: sum(b[v]["ai_sessions"] for b in baseline_buckets) / len(baseline_buckets)
        for v in ("antwerp", "eupen", "all")
    }
    return {
        "generated": dt.datetime.now().strftime("%d %b %Y, %H:%M"),
        "asof": asof.isoformat(),
        "asof_label": asof.strftime("%A %d %B %Y"),
        "week_label": f"{win['week_start']:%d %b} - {win['week_end']:%d %b %Y}",
        "week_number": win["week_start"].isocalendar().week,
        "detailed_months": [W.month_label(m) for m in win["detailed_months"]],
        "averaged_months": [W.month_label(m) for m in win["averaged_months"]],
        "buckets": buckets,
        "b2b_detail": detail,
        "b2b_groups": [g[0] for g in B2B_GROUPS],
        "sources": sources,
        "last": last,
        "prev": prev,
        "baseline": {k: round(v, 1) for k, v in base.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None)
    args = ap.parse_args()
    asof = dt.date.fromisoformat(args.asof) if args.asof else dt.date.today()

    payload = build_payload(asof)
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(ROOT, "data", "report_data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)

    template = open(os.path.join(HERE, "report_template.html"), encoding="utf-8").read()
    html = template.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False))
    out = os.path.join(DOCS, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("[build] %s (%.0f KB) - week %s" % (out, len(html) / 1024, payload["week_label"]))


if __name__ == "__main__":
    main()
