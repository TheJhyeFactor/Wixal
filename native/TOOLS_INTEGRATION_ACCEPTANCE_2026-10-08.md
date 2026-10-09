# Native Tools integration acceptance — 8 October 2026

Implemented and installed in `/Applications/Wixal.app`, retaining version `0.7.10-alpha.2`. Native-only changes; no public release was made.

## Delivered

- Tools in the main sidebar, with Browse and Installed views.
- Categories, search, program/workflow filtering, package details and readiness.
- Installed management: executable verification, update, repair, removal, job output, cancellation and installation history.
- Global program installation across projects on this Mac; workflow packs retain account ownership while spanning projects.
- One automatic-install preference in Settings → Tools & permissions. AI requests require installation review when disabled, including when task execution otherwise bypasses individual review. Direct user installation clicks do not require a second approval.
- Cybersecurity Manage tools and the tools drawer navigate to the shared workspace. Cybersecurity remains mounted while navigating away, preserving its investigation view state.

## Verification

- 31 focused tests passed across `test_addons`, `test_settings`, `test_security_workspace` and `test_security_records`.
- Native release build and `script/build_and_run.sh --package-only` succeeded.
- Installed bundle passed `codesign --verify --deep --strict`.
- `git diff --check` passed.
- Nine packaged acceptance cases passed: catalogue, actual Homebrew registry, workflow, real ffuf execution against a local authorised test server, investigation adapter execution, real TShark processing of an explicitly labelled synthetic capture, installed OSV readiness, real OSV project scanning, and catalogue discovery by a real local Qwen3:1.7b model.
- Update, repair and removal were verified with actual fixture processes and pinned argv. Existing user programs were not uninstalled to test removal.
- OSV was already present during the final acceptance runs; those runs verified readiness rather than performing another download.

Live checks in the final installed app confirmed:

1. Browse → Manage Nmap opens its expanded Installed row.
2. Verify returns the actual Nmap 7.991 executable output.
3. Installation settings opens Tools & permissions with the single global automatic-install switch.
4. Open Tools returns to the same workspace.
5. Cybersecurity → Manage tools opens Tools.
6. Web security category filters the programme and workflow cards correctly.

The app was left open at Tools → Browse → Web security. Screenshot: `../artifacts/native/tools-browse-installed-app.png`.

## Bundle identity and evidence

Final executable SHA-256: `e93fe1ca6bd66b31d817cdc2f195cf0be9df34816a0402f3d85f7432ef84441f`.

Final bundled helper SHA-256: `eb242b5bb1a7fcebd67c63309ddbfd9fb4da7e9fe55d61183237c1c7a8a8b852`.

The helper hash matches the successful packaged acceptance report. Final UI refinements changed the Swift executable only.

- `../artifacts/native/install-current.json`
- `../artifacts/native/addon-library/packaged.json`
- `../artifacts/native/tools-package.log`
- `../artifacts/native/tools-install.log`
- `../artifacts/native/tools-real-acceptance.log`

Previous installed app retained at `/Users/jhye/Library/Application Support/Wixal Release Backups/20261008-185212/Wixal.zip`.

## Remaining capability work

ZAP, mitmproxy and Metasploit are catalogue/install entries that require specialist setup and complete AI execution adapters. Installation must not be described as autonomous attack readiness. Wireshark/TShark currently supports saved capture analysis; live capture permissions and the desktop application are separate setup. Workflow packs provide instructions, not a guarantee of exploitability or successful execution of every possible assessment.
