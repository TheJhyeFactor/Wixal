# Wixal 0.7.10 Alpha 4 — Recovery and evidence

Alpha 4 brings the merged native-app fixes completed after Alpha 3 into one current Wixal installation. It is an Apple Silicon macOS alpha, ad-hoc signed and **not Developer ID signed or notarised**. No model weights are bundled.

## What changed

- **Run controls:** accepted guidance receives a model step even during final-answer streaming; Stop remains available while result verification settles.
- **Queue and drafts:** active queued jobs retain their task identity; owner/run guidance drafts survive navigation and relaunch.
- **Long conversations and recovery:** retained tool evidence and context summaries survive helper restarts; disconnect and uncertain-effect recovery preserve evidence without replaying actions.
- **Background scheduling:** the oldest due routine runs first, preventing overdue jobs from starving behind newer ones. Actual sleep/wake/reboot qualification remains open.
- **Model and source evidence:** unfinished inspection stages, owned discovery/inspection reader handles and controller correction feedback remain available in model context. Source reads support bounded chunks and exact search offsets. Verification rejects more unsupported scanner claims, altered known references and nonliteral saved XML.
- **Acceptance tools:** reusable specialist TLS/capture/readiness and native WebKit cookie/expiry/logout/disconnect checks retain exact build identities and independent observations.
- **Installation hygiene:** keep one canonical `/Applications/Wixal.app`; the release checklist now requires retiring obsolete preview/test installs after verification. A dry-run-first cleanup command moves recognised obsolete apps to Trash while retaining user data.

## Validation and evidence boundaries

Fresh checks for this release:

| Check | Result |
| --- | --- |
| Python engine regression | 397 passed |
| Swift interaction / activity / Markdown | 24 / 29 / 5 passed |
| Website assessment | 7 passed |
| Installed startup, including slow/failed database | 5/5 passed |
| Packaged source provenance | All 127 source entries matched |
| Existing workspace launch and relaunch | Passed; existing project/history visible |
| Installed real-model agent checks (`gpt-oss:20b`) | 2/3 passed; source reading and background run passed, artifact verification required attention |
| Installation cleanup | 40 obsolete installs moved to Trash; one canonical app remains |

The artifact case saved the requested JSON but the model supplied invalid `verify_json` calls. Independent verification rejected its completion claim and retained `needs_attention`. This is an unresolved model qualification result, not a passing artifact acceptance.

Exact Alpha 4 package, archive, installed-app and source checks are recorded in the accompanying `release-info.json` and `release-verification.json`. Dated development results remain bound to their own helper/source/model identities. The earlier 54-handshake TLS assessment and six-case WebKit recovery results are development evidence; they are not silently transferred to the Alpha 4 package.

## Known limits

Cybersecurity model qualification remains **failed/incomplete**. The latest development model answer inferred an examined portion of a stopped scan despite absent probe-completion evidence; independent review rejected it. Stronger controller checks do not certify every model interpretation. Inspect retained evidence and configure independent success criteria for important tasks.

Public managed-tool downloads still require a qualified production signed catalogue and independent signing custody. Contributor GitHub Device Flow still needs its registered client ID. Live provider/account lifecycle, full spoken VoiceOver/layout, actual sleep/reboot, real two-Mac sync, broader hardware/OS qualification and automatic updates remain open. The macOS14 minimum is a deployment target, not full OS-matrix acceptance. Remote execution, messaging/voice gateways and additional platforms remain proposal-first expansion work.

Download and replace Wixal manually. Preserve your existing workspace and models; older app bundles can be moved to Trash after the new version passes launch and data-retention checks.
