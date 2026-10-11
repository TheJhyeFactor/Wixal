# Schedule ordering and power qualification, 11 October 2026

Issue [#10](https://github.com/TheJhyeFactor/Wixal/issues/10) remains open. This record separates a reproduced scheduler defect from unfinished real-device power acceptance.

## Reproduced defect and correction

With the native app closed, a LaunchAgent invokes the installed helper every 60 seconds and each invocation claims one due routine. The former scheduler inspected persistent list order. A 60-second routine at the front of that list repeatedly ran while older overdue routines waited. This was observed with actual local-model runs and independently recorded effects in disposable projects. Distinct short-interval runs were legitimate claims; the defect was starvation of the waiting routines.

The scheduler now examines routines by oldest `nextRun`, keeping the persistent presentation order unchanged. It retains owner checks, the exclusive workspace lease, claim-before-execution storage and action review. Older work therefore receives a claim before a recently due short interval.

Two regression cases use actual tool execution and files: an older due routine runs before a recently due 60-second routine, and an older routine gets the next background claim after a missed short interval is skipped. Both assertions fail against the previous source and pass with this correction. These controlled-model regressions are not real-model or power acceptance.

## Retained real-device evidence

The first attempt confirmed a real 21-second sleep in the macOS power log. HID activity woke the Mac before the seeded routines became due. This does not qualify missed-run recovery through sleep. Awake observations from this attempt reproduced the ordering defect above. Its original apps, data, task identities and effect ledgers were retained, then the two owned LaunchAgents were unregistered and schedules disabled.

A separate replacement app was built from the corrected source. Its installed helper SHA-256 is `148a7a238ed08364d1f22ec2e6c8774f47cf41ae5a1213f2bc4e8099891ee0b9`; source manifest SHA-256 is `40ac75ddaf9eea01398f588806b1cd4fa6c1bb4706a4868fa4633bfdd47edc56`. All 127 manifest entries match source. Both foreground and closed-app disposable workspaces passed manual scheduled preflight with the real `gpt-oss:20b` model, actual inference counters, independent single-effect ledgers and successful verification. These preflights establish readiness, not sleep or reboot acceptance.

Local evidence is retained under `artifacts/native/priority-20261011`: `schedule-fairness-before-final.log`, `schedule-fairness-after.log`, `power-qualification/`, and the separate `power-fairness/` protocol. Raw local macOS logs and workspace data are not published.

## Subsequent validation and owner test window

The full Python suite passed: **381 tests in 143.771 seconds**. The first invocation omitted the engine import path and failed to load four modules; the corrected run supplied `PYTHONPATH=native/engine` and passed all tests. The installed schedule API also prepared Sydney and UTC calendar routines, independently checking their different wall times against the same UTC instant. Those disabled routines have not executed through a power transition.

The owner subsequently asked to defer sleep/wake/reboot focus while using the laptop. No second power transition was started. Both replacement LaunchAgents were unregistered and all replacement schedules disabled; preparation and retained evidence remain available for the later window.

## Remaining acceptance

A sleep lasting across due times, foreground and closed-app catch-up, configured timezone and missed-run policy, competing workspace claims, review and desktop-only pause/resume, notification/history persistence, and actual reboot/sign-in still require their recorded real-device observations. The owner authorised this Mac for these tests and will handle reboot/sign-in. Keyboard Navigation and VoiceOver are authorised temporarily for issue #11 and have not yet been changed.

This is development-app evidence. No public release or notarisation claim is made. Model qualification remains tracked by issue #6.
