# -*- coding: utf-8 -*-
"""GA4 Data API client + the shared filter definitions for EF AI Traffic Watch.

Auth resolution order:
  1. GA4_SA_JSON            service-account key, as raw JSON in an env var (GitHub Actions)
  2. GOOGLE_APPLICATION_CREDENTIALS  path to a service-account key file
  3. local OAuth token from the claude-seo config (developer machine fallback)
"""
import json
import os
import sys

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    RunReportRequest,
)

PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "355017554")
PROPERTY = f"properties/{PROPERTY_ID}"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# Assistants that show up as a referrer. The native "AI Assistant" channel group is
# NOT retroactive (sessions before ~June 2026 fall into "Unassigned"), so history has
# to be measured on sessionSource. PARTIAL_REGEXP is mandatory: FULL_REGEXP would
# require the pattern to cover the whole value, and "chatgpt" does not match
# "chatgpt.com".
AI_SOURCE_REGEX = (
    r"chatgpt|openai|gemini\.|bard\.|copilot|perplexity|claude\.ai|mistral|"
    r"deepseek|grok|meta\.ai|kagi|you\.com|phind"
)

VENUES = {
    "antwerp": r"^/antwerp(/|\?|$)",
    "eupen": r"^/eupen(/|\?|$)",
}


def credentials():
    raw = os.environ.get("GA4_SA_JSON", "").strip()
    if raw:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=SCOPES
        )
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if key_path and os.path.exists(key_path):
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    # developer fallback: the local claude-seo OAuth token
    sys.path.insert(
        0,
        r"C:\Users\Laptop - Regis\.claude\plugins\marketplaces\AgriciDaniel-claude-seo\scripts",
    )
    from google_auth import get_oauth_credentials

    return get_oauth_credentials(SCOPES)


def client():
    return BetaAnalyticsDataClient(credentials=credentials())


# ---------- filter helpers ----------
def regex_filter(field, pattern):
    return FilterExpression(
        filter=Filter(
            field_name=field,
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.PARTIAL_REGEXP,
                case_sensitive=False,
                value=pattern,
            ),
        )
    )


def ai_filter():
    return FilterExpression(
        or_group=FilterExpressionList(
            expressions=[
                FilterExpression(
                    filter=Filter(
                        field_name="sessionDefaultChannelGroup",
                        string_filter=Filter.StringFilter(value="AI Assistant"),
                    )
                ),
                regex_filter("sessionSource", AI_SOURCE_REGEX),
            ]
        )
    )


def venue_filter(venue):
    if venue == "all":
        return None
    return regex_filter("landingPagePlusQueryString", VENUES[venue])


def and_all(*expressions):
    kept = [e for e in expressions if e is not None]
    if not kept:
        return None
    if len(kept) == 1:
        return kept[0]
    return FilterExpression(and_group=FilterExpressionList(expressions=kept))


def run(cl, dimensions, metrics, start, end, dim_filter=None, limit=100000):
    """Run one report and return a list of (dim values tuple, metric values tuple)."""
    rows, offset = [], 0
    while True:
        resp = cl.run_report(
            RunReportRequest(
                property=PROPERTY,
                date_ranges=[DateRange(start_date=start, end_date=end)],
                dimensions=[Dimension(name=d) for d in dimensions],
                metrics=[Metric(name=m) for m in metrics],
                dimension_filter=dim_filter,
                limit=limit,
                offset=offset,
            )
        )
        for r in resp.rows:
            rows.append(
                (
                    tuple(d.value for d in r.dimension_values),
                    tuple(m.value for m in r.metric_values),
                )
            )
        offset += len(resp.rows)
        if len(resp.rows) == 0 or offset >= resp.row_count:
            break
    return rows
