# Website and GitHub metrics

The website uses the dedicated Wixal GA4 property (557599207), web stream Wixal website (16050367110), measurement ID G-C6ZMWP9EX9. Reporting uses Australia/Sydney and AUD. The public measurement ID is configuration, not a secret.

- Website visitors, page views and referrals: https://analytics.google.com/analytics/web/#/a378375598p557599207/reports/intelligenthome
- Download button clicks: GA4 event `file_download`, with `file_name`, `file_extension`, and `release_version`. Enhanced measurement is off to prevent duplicate download events. Mark file_download as a key event if desired once it appears.
- Current public release counts: https://thejhyefactor.github.io/Wixal/stats/
- Daily GitHub report and snapshots: https://github.com/TheJhyeFactor/Wixal/tree/wixal-metrics
- GitHub workflow: https://github.com/TheJhyeFactor/Wixal/actions/workflows/metrics.yml
- Owner-only native repository traffic: https://github.com/TheJhyeFactor/Wixal/graphs/traffic

Analytics loads only after visitor opt-in. Analytics preferences remain in the footer; declining disables collection and removes cookies created by this integration. Query strings and fragments are omitted from page URLs and referrers. Ads and Google Signals are disabled. Downloads work without JavaScript or analytics consent. No desktop app telemetry was added.

GitHub counts DMG/ZIP asset requests across all published releases, including repeat and direct downloads. Website download clicks do not prove transfer completion. Neither metric establishes installs or active app users. Repository visitors and clones do not measure website visitors.

The metrics workflow runs daily at 19:23 UTC (06:23 Sydney during daylight saving, 05:23 otherwise), on release publication, and manually. It preserves one daily snapshot plus the latest report on `wixal-metrics`; workflow artifacts last 90 days. GitHub traffic APIs expose a rolling 14-day window. Do not sum overlapping window totals or daily unique counts to infer lifetime unique people.

The default Actions token reads public release counts. Archiving repository views/clones needs a fine-grained PAT scoped only to Wixal with **Administration: read**, saved as repository Actions secret `METRICS_TRAFFIC_TOKEN`. Missing access is reported as unavailable, never zero. Do not copy a broad personal login token into Actions. Native GitHub Insights remains available to the owner without this secret.

For a local owner-authorized snapshot, use `node scripts/github-metrics.mjs --local`. This calls the signed-in GitHub CLI and writes to ignored `artifacts/github-metrics/`. No credentials appear in the report.

Build override: `GA_MEASUREMENT_ID` and GitHub Actions repository variable `GA_MEASUREMENT_ID` can replace the default public ID. Use only a dedicated Wixal stream. Verify consent, page views and file_download events before changing the property.
