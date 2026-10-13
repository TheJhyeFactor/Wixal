# Native theme collection

Implemented and checked locally on 13 October 2026. Sakura remains the default.

| Group | Themes, in picker order |
| --- | --- |
| Light | Pearl, Cloud, Paper, Dune |
| Dark | Graphite, Sakura, Forest, Midnight, Aurora, Obsidian |

`Sources/ThemePalette.swift` defines stable identifiers, light/dark behaviour and independent background, sidebar, panel, raised, inset, divider, text, muted, accent and secondary colours. `WixalTheme` supplies these colours to the existing native views. Terminal foreground, background and caret follow the chosen theme. System controls use the corresponding light/dark appearance.

Appearance settings show miniature workspace previews grouped by light/dark, with a checkmark and outline for the selected theme. Onboarding offers the same catalogue in an adaptive grid. Settings search includes all names. Startup appearance caching, engine validation, legacy imports and existing account-preset validation recognise all ten identifiers. This change does not enable an account or any sync service.

Each theme maps to the icon with the same identifier. Paper and Forest now have dedicated icons; manually saved Pearl or Copper choices remain valid. Match icon to theme can be turned off by selecting any of the eleven icons, and turning it back on immediately uses the current theme's icon. This changes the running Dock icon, not the Finder/bundle icon. The original four icon assets are retained; seven additional vector colourways and 1024px PNGs reuse the established Wixal W and cursor.

## Verification

- `swift build --build-system native --package-path native --product WixalNative`: passed using Swift 6.4.
- `PYTHONPATH=native/engine:native/tests native/.venv/bin/python -m unittest test_theme_catalogue test_settings test_engine test_startup_recovery -q`: 32 tests passed.
- Contrast regression checks cover primary and muted text against all five content surfaces, and accent text against background/sidebar/panel, at a minimum 4.5:1 ratio. Pearl and Dune accents were darkened slightly from the original concept to meet that target.
- All ten themes persist when committed SQLite state is reopened through the production Store, preserving exact saved messages and an unsent multiline draft. All themes also work during a held task without unlocking model context or tool permissions. Invalid combined theme/icon updates leave state unchanged.
- Native UI check in an isolated debug app at the production 920 × 640 minimum: selected all ten themes, rendered and selected all eleven icon choices, verified manual Copper survives a switch to Aurora, and restored matching to Aurora.
- Quit/relaunch of the final debug executable retained Aurora and theme matching. Its executable hash matched the final SwiftPM debug build.
- Native preview storage contains no copied conversations or credentials. Only already-completed setup state was copied from the existing workspace. Preview data and test logs are under `artifacts/native/theme-preview/`.
- Built the self-contained development bundle `artifacts/native/theme-package/Wixal Themes.app` with the existing native packager. Deep/strict ad-hoc signature validation passed, all 147 source-manifest entries matched, and all 22 shipped SVG/PNG icon files matched their source hashes.
- The frozen packaged helper accepted all ten theme/icon pairs and retained Aurora with theme matching after helper restart. The packaged native UI launched normally and selected all ten themes successfully, finishing on Aurora. Machine-readable package evidence is in `artifacts/native/theme-package/verification.json`.

## Evidence boundaries

These checks cover source, the debug build, engine persistence, an actual native preview, a self-contained local development package and the installed application. The package is ad-hoc signed and is not a notarised public release. This is not a full-screen regression pass across every product screen and theme. Public releases and version numbers were not changed. The Workbench layout shown in the earlier design concepts is outside this theme implementation.

## Local deployment

Installed the canonical alpha build at `/Applications/Wixal.app`, retaining version `0.7.10-alpha.6`. Installed-file verification, source provenance and deep/strict signature validation passed. All 147 packaged source entries matched, and shipped icon files matched their source hashes. The installed Appearance screen exposed all ten themes; switching to Aurora and back to the original Midnight succeeded.

The pre-install workspace snapshot and post-install state matched for all nine conversations, 40 messages, drafts, projects, selected model, active conversation and appearance settings. After relaunch and theme switching, saved history and draft payloads still matched; one draft's update timestamp was refreshed by the running app. SQLite integrity passed. The original Midnight theme and independent Midnight icon remain selected.

The two isolated preview bundles and the duplicate release output were moved to Trash and unregistered. Final inventory found one Wixal application outside Trash, `/Applications/Wixal.app`, with one running native app process. A ZIP of the previous installed version is retained under `~/Library/Application Support/Wixal Release Backups/` for rollback. Historical preview bundle paths above are no longer active installations. Deployment evidence is recorded in `artifacts/native/theme-preview/installed-verification.json`, `deploy-cleanup.json` and `deployment-final.json`.

Regenerate the seven new vector/PNG icon pairs with `node native/scripts/generate-theme-icons.cjs`. The existing native packager copies the entire `assets/icon-variants` directory into the bundle.
