# EF AI Traffic Watch

Daily report on how much of Experience Factory's traffic and online revenue arrives
through AI assistants (ChatGPT, Copilot, Gemini, Perplexity and friends), split
between **Antwerp** and **Eupen**, with a focus on the **teambuilding / bedrijfsevent**
pages of both sites.

The report is rebuilt every morning at 09:00 Brussels time and published to
GitHub Pages from `docs/`.

## What it shows

| Block | Content |
|:---|:---|
| Last complete week | AI sessions, share of traffic, AI revenue, B2B page views, each against the previous week and against the Jan-Jun weekly average |
| Traffic | AI sessions per week and AI share of each venue's sessions |
| Money | AI-attributed online revenue by venue, and its share of all online revenue |
| B2B focus | Views of the teambuilding / bedrijfsevent pages inside an AI session, per page |
| Full data | Every point behind the charts |
| Method | What counts as AI, how venues are split, and where the numbers under-report |

## The rolling window

The current calendar month and the one before it are shown **week by week**. The six
months before that are shown as **one weekly average per month**. Anything older drops
off. So a run in September shows Feb-Jul as monthly averages and Aug-Sep as weeks,
while January disappears and July collapses into an average.

Weeks are ISO weeks, Monday to Sunday, and a week belongs to the month of its Thursday.
**Only finished weeks are ever shown**: the week in progress is excluded, so the last
point is always the last full Monday-to-Sunday week.

## Layout

```
scripts/ga4_client.py       GA4 auth + the AI / venue filter definitions
scripts/pull.py             daily GA4 pull  -> data/*.csv
scripts/window.py           the rolling-window rule
scripts/series.py           daily rows -> weekly buckets
scripts/build_report.py     buckets -> docs/index.html
scripts/report_template.html the page itself (CSS + inline SVG charts)
data/*.csv                  append-and-merge history, one row per day
docs/index.html             the published report, self-contained
docs/assets/                EF brand source files (IDigital, Raleway, logo),
                            base64-embedded into the page at build time so the
                            report keeps the charter wherever it is opened
```

## Running it by hand

```bash
pip install -r requirements.txt
python scripts/pull.py --asof 2026-08-24
python scripts/build_report.py --asof 2026-08-24
```

`--asof` makes the run behave as if it happened that morning, which is how the
first report was produced for Monday 24 August 2026. Without it, today is used.

On the developer machine the scripts fall back to the local claude-seo OAuth token.
In GitHub Actions they use the `GA4_SA_JSON` secret, a service-account key with
Viewer access on GA4 property `355017554`.

## Setup

See [SETUP.md](SETUP.md) for the service account, the repo secret and the Pages
configuration.

## Known measurement limits

- The native GA4 "AI Assistant" channel group only exists from about June 2026, so
  history is measured on `sessionSource` as well. Both rules are OR-ed together.
- Assistants that send a visitor without a referrer land in **Direct**, which carries
  most of the site's revenue. AI money is therefore under-reported, not over-reported.
- Venue-level revenue is empty before May 2026: until the cross-domain tracking
  changed, bookings were recorded on sessions with no `/antwerp/` or `/eupen/`
  landing page.
- Site-wide session volume roughly doubled in week 20 for a measurement reason.
  Absolute AI counts stay comparable, percentages only from May onwards.
- The `/antwerp/` pages only exist in this GA4 property from 8 December 2025.
