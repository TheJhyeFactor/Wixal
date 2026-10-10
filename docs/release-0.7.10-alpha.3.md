# Wixal 0.7.10 Alpha 3 — Keep the work moving

Alpha 3 makes active agent work easier to manage and recovery more dependable. Queue another task without interrupting the current run, resume in the original conversation and project, and keep your draft when a save needs correction. It also strengthens command cleanup, activity history and retained tool evidence.

**Download [Wixal-0.7.10-alpha.3-macOS-arm64.zip](https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.10-alpha.3/Wixal-0.7.10-alpha.3-macOS-arm64.zip)** for **Apple Silicon, macOS 14 or newer**. Python and the local Ollama runner are included. Model weights download separately.

## What’s improved

- **Manage work while an agent runs.** Queue and cancel pending tasks during active work. Queued tasks retain their saved agent profile and project. Cancelled jobs remain cancelled across restarts.
- **Resume where the task belongs.** Recovery requires the original conversation and available project. Personal tasks remain personal. Stop and guidance apply to the actual selected run, so an old control cannot affect a newer task.
- **Keep drafts on failed saves.** Agent, workflow, schedule and queue editors wait for acknowledgement before closing. Rejected submissions show the error and retain your text. Guidance clears after success and preserves edits made while the request was pending.
- **Read the actual outcome.** Activity preserves queued, paused, interrupted and attention-required states. Command output paging advances over complete Unicode characters, including emoji. Reads wait until output collection and evidence finalization finish.
- **Trust evidence over acknowledgements.** Agent success checks inspect resolved command output and independent criteria. Pending or failed tool responses cannot satisfy a success check. Complete Nmap results retain structured port/service evidence; malformed and incomplete scans remain visible failures.
- **Clean up owned processes.** Failed or paused runs stop their own command collectors. Cancellation and timeouts terminate owned process groups, including descendants left after a command leader exits. Project boundaries are checked again after action review.
- **Start with the splash.** The splash appears before the engine starts and workspace loads. Startup respects animation-off and reduced-motion settings and handles delayed or failed database startup.
- **Upgrade without losing tool history.** Retained managed transactions no longer block startup after an app version change. Older packages remain in history, with execution and rollback gated by qualification for the current build.
- **Inspect the tool library and prepare bug reports.** The shared library exposes installed providers, readiness and lifecycle state. Settings can prepare sanitized local diagnostic bundles for review.

## Install or upgrade

1. Quit Wixal, extract the ZIP and replace **Wixal.app** in **Applications**.
2. Existing native data stays at `~/Library/Application Support/Wixal Native`. Replacing the app retains the workspace and model library. Back up important work before testing an alpha.
3. Open Wixal and choose a tool-capable model for agent tasks. Updates remain manual GitHub downloads.

This prerelease is **ad-hoc signed, not Developer ID signed or notarised**. If macOS blocks first launch, review the release and source, then use **System Settings → Privacy & Security → Open Anyway**.

The release includes `SHA256SUMS.txt` and `release-info.json` with asset hashes, source commit, package identities and validation results. Download the ZIP and checksum file into the same folder, then check:

```sh
shasum -a 256 -c SHA256SUMS.txt
```

## Verification and limits

The implementation passed **300 Python regression tests**, **29 production activity checks**, **16 submission/guidance checks** and **5 Markdown checks** before release packaging. Installed UI acceptance exercised rejected/corrected saves in all three editors, guidance, queue/cancel during active work and selected stop/resume. The development build also passed five startup scenarios and three real-model agent cases with **gpt-oss:20b**. [The completion record](https://github.com/TheJhyeFactor/Wixal/blob/main/native/AGENT_CONTROLS_COMPLETION_2026-10-10.md) retains those build-specific identities and evidence.

The public Alpha 3 package was rebuilt separately and checked against its exact installed identity:

| Check | Result |
| --- | --- |
| Python regression suite | 302 passed, including two new app-upgrade cases |
| Production Swift acceptance | 29 activity, 16 submission/guidance and 5 Markdown checks passed |
| Installed startup | 5/5 passed: animated, animation off, reduced motion, delayed database and failed-database recovery |
| Installed real-model agents | 3/3 passed with gpt-oss:20b: source review, reviewed artifact/readback and a closed-helper background task |
| Package provenance | 124 source files match; installed helper, executable, metadata and source-manifest hashes match the package; deep strict signature verified |
| Website | Link/analytics checks and 20 browser cases passed at exact desktop/mobile widths in light/dark appearance with reduced motion |

The release provenance records exact hashes and results. Controlled-response UI tests establish application behaviour; real-model tests provide bounded evidence for the cases exercised. Neither establishes reliability for every model or task. Earlier scanner interpretation failures remain documented rather than treated as passing evidence.

## What remains gated

- **Public managed-tool downloads:** Alpha 3 includes the library and managed profiles for RustScan, ffuf, Nuclei, Trivy and OSV-Scanner. It bundles no managed tool executables or production repository. Public catalogue promotion remains gated on qualified signed metadata and independent key custody. Supported external installations remain available. [Managed development evidence](https://github.com/TheJhyeFactor/Wixal/blob/main/native/MANAGED_TOOLS_CONTINUATION_2026-10-10.md) is separate from public distribution qualification.
- **Contributor GitHub sign-in:** Device Flow and reviewed submission are implemented, but the registered client ID is not configured. Export and review a local report, then submit it through [GitHub Issues](https://github.com/TheJhyeFactor/Wixal/issues). Live contributor authorization is not claimed.
- **Broader release qualification:** Developer ID signing, notarisation, automatic updates, wider hardware/OS acceptance, full accessibility coverage, actual sleep/wake/reboot acceptance and real two-Mac sync remain outstanding. The macOS 14 minimum is a deployment target, not a claim of testing every supported OS.
- Remote/off-Mac execution, messaging/voice gateways and broader model/service certification remain incomplete. Background routines require an awake Mac, and desktop-only browser actions need the app open. Commands run with your Mac account’s access. Security findings and model interpretations still require review.

[Getting started](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/native-alpha.md) · [Changelog](https://github.com/TheJhyeFactor/Wixal/blob/main/CHANGELOG.md) · [Source and build guide](https://github.com/TheJhyeFactor/Wixal/blob/main/native/README.md)
