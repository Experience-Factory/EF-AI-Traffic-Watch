# Setup

One-off steps, about ten minutes. Everything after this is automatic.

## 1. Create the service account (Google Cloud)

Project: **innate-gizmo-431111-f8** (the one that already holds the claude-seo OAuth
client and has the Analytics Data API enabled).

1. https://console.cloud.google.com/iam-admin/serviceaccounts?project=innate-gizmo-431111-f8
2. **Create service account** → name `ef-ai-traffic-watch` → Create and continue →
   **skip** the role step (it needs no GCP role, only GA4 access) → Done.
3. Open the new account → **Keys** → Add key → Create new key → **JSON** → it downloads
   a `.json` file. Keep it, it cannot be downloaded twice.
4. Copy the account's email, it looks like
   `ef-ai-traffic-watch@innate-gizmo-431111-f8.iam.gserviceaccount.com`.

## 2. Give it read access to GA4

1. https://analytics.google.com → Admin → the property **355017554** (the one that
   covers Antwerp and Eupen, EN and NL).
2. Property access management → **+** → Add users → paste the service-account email.
3. Role: **Viewer**. Uncheck "Notify by email" (a service account has no inbox).
4. Save.

## 3. Store the key in GitHub

Repo → Settings → Secrets and variables → **Actions** → New repository secret.

| Name | Value |
|:---|:---|
| `GA4_SA_JSON` | the **entire content** of the downloaded JSON file, pasted as-is |

Optionally add a repository **variable** `GA4_PROPERTY_ID` if the property ever changes;
without it the scripts use `355017554`.

## 4. Turn on Pages

Repo → Settings → **Pages** → Source: *Deploy from a branch* → Branch: `main`,
folder: **/docs** → Save. The report is then served at the URL GitHub shows on that
screen.

> This repository is **public**, a decision taken deliberately on 27 August 2026 so
> that Pages works without a paid plan. Anyone can read the report and the daily CSVs,
> revenue figures included, without needing the link: a public repo is listed on the
> organisation profile and returned by GitHub code search. Do not add anything here
> that should stay internal.

## 5. First run

Actions → **Daily AI traffic report** → Run workflow. It pulls GA4, rebuilds
`docs/index.html` and commits both. After that it runs by itself every morning at
07:00 UTC.

## Maintenance

- **Delivery time**: GitHub does not guarantee when a scheduled workflow starts. On
  free runners this one was delayed by 5 to 12 hours during its first week. The
  workflow therefore asks five times (05:00, 05:30, 06:00, 06:30 and 07:00 UTC) and
  the first attempt that actually fires builds the report; the later ones see today's
  commit already there and stop at the guard step, costing a few seconds. If the
  report is regularly late, add more early crons rather than moving the existing ones.
- **DST**: the crons run from `0 5 * * *`, which is 07:00 Brussels while summer time
  is in force. Shift every line one hour later after 26 October 2026, and back at the
  end of March. Same nudge as the EF-Social-Media-Trendy workflow.
- **Service-account keys do not expire**, unlike the OAuth token on the developer
  machine. If the workflow starts failing with a permission error, check that the
  service account is still listed in GA4 property access management.
