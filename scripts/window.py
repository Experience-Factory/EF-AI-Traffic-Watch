# -*- coding: utf-8 -*-
"""Rolling-window logic.

Rule agreed with the user: the current calendar month and the one before it are
shown week by week; the six months before that are shown as one weekly average
each; anything older drops off. So a run in September shows Feb-Jul as averages
and Aug-Sep as weeks, while January disappears and July collapses into an average.

Weeks are ISO weeks (Monday to Sunday). A week belongs to the month of its
Thursday, the ISO convention, so a week straddling two months lands in exactly
one bucket. Only complete weeks are ever used: the week in progress is excluded,
so the most recent point is always the last full Monday-to-Sunday week.
"""
import datetime as dt

DETAILED_MONTHS = 2
AVERAGED_MONTHS = 6


def last_complete_week(asof):
    """(monday, sunday) of the last week that had already finished on `asof`."""
    monday_of_asof_week = asof - dt.timedelta(days=asof.weekday())
    sunday = monday_of_asof_week - dt.timedelta(days=1)
    return sunday - dt.timedelta(days=6), sunday


def month_of_week(monday):
    thursday = monday + dt.timedelta(days=3)
    return (thursday.year, thursday.month)


def shift_month(ym, delta):
    y, m = ym
    idx = y * 12 + (m - 1) + delta
    return (idx // 12, idx % 12 + 1)


def month_label(ym):
    return dt.date(ym[0], ym[1], 1).strftime("%b %Y")


def build(asof):
    """Everything the pull and the report need for a given as-of date."""
    week_start, week_end = last_complete_week(asof)
    current_month = (asof.year, asof.month)
    detailed = [shift_month(current_month, -d) for d in range(DETAILED_MONTHS - 1, -1, -1)]
    averaged = [
        shift_month(current_month, -d)
        for d in range(DETAILED_MONTHS + AVERAGED_MONTHS - 1, DETAILED_MONTHS - 1, -1)
    ]
    # walk back week by week from the last complete week until we leave the window
    oldest = averaged[0]
    weeks, cursor = [], week_start
    while month_of_week(cursor) >= oldest:
        weeks.append(cursor)
        cursor -= dt.timedelta(days=7)
    weeks.reverse()
    return {
        "asof": asof,
        "week_start": week_start,
        "week_end": week_end,
        "detailed_months": detailed,
        "averaged_months": averaged,
        "weeks": weeks,
        "data_start": weeks[0],
        "data_end": week_end,
    }


if __name__ == "__main__":
    import sys

    d = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    w = build(d)
    print("as-of        ", w["asof"], w["asof"].strftime("%A"))
    print("last week    ", w["week_start"], "->", w["week_end"])
    print("detailed     ", [month_label(m) for m in w["detailed_months"]])
    print("averaged     ", [month_label(m) for m in w["averaged_months"]])
    print("weeks        ", len(w["weeks"]), w["weeks"][0], "->", w["weeks"][-1])
