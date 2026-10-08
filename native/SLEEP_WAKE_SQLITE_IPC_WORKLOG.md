# Sleep, SQLite startup, and IPC work log — 2026-10-07

## Scope

This pass investigated the reported sleeping-Mac wake gap, the isolated SQLite startup stall, and Unix-domain socket failures for long workspace paths. It changed the IPC path, made SQLite lock waiting explicit and bounded, and added an app-side startup watchdog with OSLog diagnostics. It did not add a privileged power-management service.

## What changed

- `native/engine/wixal/service.py` now hashes the resolved workspace path to a per-user endpoint under the system temporary directory (`wxipc-<uid>`). The directory is created with mode `0700` and rejected if its owner, type, or permissions are unsafe. The socket itself is mode `0600`. The existing `<workspace>/engine.sock` name remains a symlink for compatibility with ordinary short-path clients.
- `native/engine/wixal/cli.py` connects directly to the short endpoint. This is needed because passing an overlong symlink pathname to `connect(2)` can still exceed `sockaddr_un.sun_path`.
- `native/engine/wixal/storage.py` sets a 3-second SQLite busy timeout for cold-start database lock acquisition and closes the database and workspace lock if initialization fails. This gives actual SQLite lock contention a bounded, clean retry path.
- `native/Sources/EngineClient.swift` now times out a child engine that has not completed its startup handshake after 30 seconds, stops that child, shows a recovery message, and records launch/success/timeout/failure events in the `EngineStartup` OSLog category. This prevents a file-open stall from leaving the UI indefinitely at “Starting Python engine”; it does not repair an unavailable or blocked filesystem. The watchdog is present in current installed app `34996b6c3f3a2c5f62fe70453c549c63b505da5b567c7914952f8e46e267343c`. SwiftPM native build and package/install succeeded with `--build-system native`; using the default build system fails because the selected Command Line Tools do not provide Apple's `metal` compiler.
- `native/tests/test_ipc.py` now starts the real engine and terminal client with a workspace whose socket pathname exceeds 100 bytes, checks the private short endpoint and mode, and verifies cleanup.
- `native/tests/test_startup_recovery.py` exercises bounded SQLite exclusive-lock contention followed by a successful reopen, long-path mapping, and schedule catch-up/restart persistence.

## Verification

Command run from `native/`:

```text
PYTHONPATH=engine:tests .venv/bin/python -m unittest test_startup_recovery test_ipc -v
Ran 5 tests in 3.897s — OK
```

The IPC test used the production engine subprocess, real AF_UNIX connection, terminal client, and a fixture model HTTP server. The SQLite test held a real exclusive database transaction: startup failed after the configured bounded wait, then reopened persisted state after releasing the lock. The scheduling test reopened actual SQLite state and confirmed a previously claimed run is marked interrupted and not replayed.

## Findings and limits

### Sleeping Mac

The existing opt-in per-user LaunchAgent uses `RunAtLoad` and `StartInterval=60`. It can check for due work after login and after the machine wakes; it cannot wake sleeping hardware. Apple's [`IOPMSchedulePowerEvent` documentation](https://developer.apple.com/documentation/iokit/1557076-iopmschedulepowerevent?language=objc) explicitly requires root. The per-user LaunchAgent cannot obtain that authority. `pmset schedule` also changes machine-wide power settings and requires administrator authority. This local host has zero valid code-signing identities; the installed app is ad-hoc signed. No privileged helper, system schedule, or global power configuration was installed or changed.

Therefore sleeping-Mac wake remains unsupported in this local-preview build. The safe supported behavior is catch-up after a normal wake/login while the user session is active. To offer scheduled wake later, Wixal needs an explicitly approved, signed and notarized privileged helper with a narrow one-shot wake API and clear setup/removal UX, or it must rely on the user configuring system power schedules themselves. The current evidence supports not claiming that feature.

### SQLite startup stall

`artifacts/native/workflow-engine-startup-sample.txt` shows the blocked thread in `sqlite3.connect -> openDatabase -> sqlite3BtreeOpen -> unixOpen -> robust_open -> posixOpen`. It contains no database pathname, errno, or filesystem-provider information. That locates the wait inside the OS file-open path before SQLite schema, WAL, or database lock setup; it does not establish corruption or lock contention as the original cause.

A bounded SQLite busy timeout addresses lock acquisition after open, and the new test proves that path. The earlier kernel-level open stall did not reproduce in this pass, so it is **not claimed fixed**. If it recurs, capture the database path and filesystem type plus a fresh sample and `fs_usage`/`opensnoop` evidence for the affected PID before changing data or SQLite recovery behavior. Keep the original database untouched until the open target is known.

The app-side watchdog bounds the visible wait and gives a recovery action for a nonresponsive startup child. It also terminates that child instead of allowing overlapping retries. This is a user-facing recovery mitigation, not a root-cause repair for the original `posixOpen` stall; the missing path/provider evidence prevents a safe targeted fix. The current watchdog source is built and installed. SwiftPM's native build system succeeded; the earlier default build path failed because the selected Command Line Tools lack `metal`.

### Socket paths

The long socket path issue is fixed and covered by an actual engine/client integration test. The compatibility symlink supports older short-path consumers; new code should use `ipc_socket_path()` so long paths do not reach the kernel socket call.


## Startup diagnostics, 8 October 2026

The helper emits startup phase, exact SQLite path and PID before opening the database; the native client records these through local EngineStartup OSLog. A regression verifies pre-open reporting and successful completion. This improves evidence for a recurrence of the original posixOpen stall; it does not establish its filesystem cause or replace the 30-second startup watchdog and bounded SQLite lock timeout. Full supporting suite now passes 114 tests.
