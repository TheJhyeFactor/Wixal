# Website analytics verification — 6 October 2026

Published website commit: afe14c4. Pages deployment 37413188674 succeeded. App CI 37413188686 succeeded. Daily metrics workflow on main commit f9258f8 completed successfully in run 37413217735 and saved README.md, latest.json and snapshots/2026-10-06.json on wixal-metrics.

The dedicated GA4 property Wixal (557599207), stream Wixal website (16050367110), measurement ID G-C6ZMWP9EX9 was created in the signed-in account with Australia/Sydney reporting time and AUD. Enhanced measurement is off because the site explicitly emits page_view and file_download. The user behaviour report snapshot was selected.

Local checks pass for nine HTML documents and 377 local page/asset/fragment links, source image dimensions, JavaScript syntax, and git diff whitespace. Analytics VM checks verify no Google tag before consent or after decline; returning opt-in; one initial page view; one matching release download event per click; no event after revocation; cross-tab revocation; and removal of query/fragment data from page/referrer URLs.

Live /stats/ shows eight DMG/ZIP release asset downloads (two on latest v0.7.3). These are GitHub asset counts, not unique users. The narrow in-app browser has no horizontal page overflow; its stacked metric cards and release table were visually inspected. Footer analytics preferences remain reachable. The download page still targets verified release assets. The production Google tag is present after opt-in. No warning or error was recorded in the in-app browser.

GA4 Realtime visibly received a real verification visit: Download for Mac and Download stats page views, first_visit, session_start, user_engagement, and one file_download. The download event contains file_name and file_extension. These verification visits/clicks are real test traffic and should not be described as acquired customers or installations.

Chrome's real download navigation reached its ERR_BLOCKED_BY_CLIENT page at the GitHub release asset host; no bypass was attempted. The in-app browser exercised the same site download link and the file_download event was received in GA4. Transfer completion and installed-app usage are outside this change.

The default GitHub Actions token successfully retrieves public release counts but cannot retrieve repository views/clones. Those fields are marked unavailable in the archived workflow report. The local owner-authorized GitHub CLI snapshot returned repository traffic; native GitHub Insights remains available. Daily traffic archiving requires the documented scoped METRICS_TRAFFIC_TOKEN, which has not been configured. The desktop app checkout's ongoing local changes were not included in the website or metrics commits.

The live footer preferences were reopened, analytics was declined, and navigation to /privacy/ was verified to have no googletagmanager.com script. The privacy page also has no narrow-screen overflow. A key-event registration for file_download was submitted with no monetary value; the processed Events table still showed its first-event delay notice, so that registration is not yet confirmed in the table. Realtime receipt of file_download is confirmed independently.
