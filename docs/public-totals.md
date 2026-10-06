# Public Wixal totals

The home, download and stats pages show GitHub DMG/ZIP download totals across published releases and GA4 active website users over the last 30 calendar dates (29daysAgo through today in Australia/Sydney). Repeat downloads count again. The visitor count covers analytics participants and is not desktop-app usage.

The `website-users.yml` workflow on main reads GA4 property 557599207 with the analytics.readonly OAuth scope, then publishes only the count, reporting period, source and timestamp to `wixal-metrics/website-users.json`. No visitor dimensions or raw reports are published. A missing, invalid, thresholded or stale report displays unavailable; it is never replaced with a fabricated zero.

Authentication uses Google Workload Identity Federation and the Wixal Analytics Reader service account. No downloadable service-account key is required. The provider restricts repository ID 1405411559, owner ID 218314198, main, and `.github/workflows/website-users.yml`. The service account has Viewer access only to the Wixal GA property and no Cloud project roles.

The visitor snapshot refreshes daily at 19:43 UTC and can be refreshed through Actions. The website rejects snapshots older than 48 hours. GA processing can delay recent visits. The website loads Google Analytics only after consent; public totals remain visible without analytics consent.

Run `node website/scripts/test-users.mjs` to validate aggregate parsing. Website validation includes build, local links, syntax, consent behavior and aggregate parsing.
