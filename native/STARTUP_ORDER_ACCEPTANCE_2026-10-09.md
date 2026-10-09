# Native splash startup order acceptance

Verified on 2026-10-09 against the development app installed at `/Applications/Wixal.app`.

The splash is now the initial window content. An AppKit drawing marker starts the engine after the first visible splash frame. The workspace is constructed only after the launch reveal finishes and the engine becomes ready, or after startup fails so that recovery controls remain accessible. Animation disabled and reduced motion display the static wordmark briefly. Escape finishes the reveal while retaining the splash if the engine is still loading. Theme and launch preferences are cached per native data scope for use before the engine handshake.

The integration script uses the installed native executable, its actual bundled Python helper, and isolated real SQLite storage. The delayed case holds an exclusive SQLite lock for three seconds. The failure case supplies an invalid database path. No engine responses or accepted legal setup state are fabricated.

| Installed app case | Result | Splash to workspace |
| --- | --- | --- |
| Animated launch | Passed | 2.217 seconds |
| Animation disabled | Passed | 0.403 seconds |
| Reduced motion | Passed | 0.423 seconds |
| Three-second database delay | Passed | 3.169 seconds |
| Database startup failure | Passed | 2.302 seconds, recovery workspace |

The normal launch with the user's existing saved workspace was also observed visually: the splash appeared alone first, then the connected workspace opened. Production OSLog observations recorded first splash presentation at 18:09:16.165, reveal completion at 18:09:18.369, engine ready at 18:09:26.331 and workspace mount at 18:09:26.449. The splash remained visible during the roughly ten-second engine startup.

Evidence is stored under `artifacts/native/startup-order/`: `installed-final/report.json`, `normal-installed-launch.log`, `install-final.json`, and `final-verification.json`. The source manifest matches the working source and every packaged file matches the installed bundle. `codesign --verify --deep --strict /Applications/Wixal.app` passed. This is a local development build; these checks do not establish notarization or a public release.

Installed UI executable SHA-256: `57d3c7fd755884958da57894ddea826693558543cad617511f3c5ea41c97c67a`.

Installed engine helper SHA-256: `9fb7cda52f0bc86ea90f8a11625b5ba2e9b7d53c99c948bed1d5c5ed83871595`.

The previous installed app is retained at `/Users/jhye/Library/Application Support/Wixal Release Backups/20261009-180817/Wixal.zip`.

To repeat the integration checks, use a new output directory:

```sh
native/.venv/bin/python native/scripts/startup-order-acceptance.py --output artifacts/native/startup-order/new-run
```
