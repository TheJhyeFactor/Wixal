# Wixal native alpha

**0.7.10 Alpha 2** is the current Wixal app. The canonical build is `release/native/Wixal.app`, installed locally as `/Applications/Wixal.app`. The public alpha download is on [GitHub](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.10-alpha.2); [the alpha guide](../docs/native-alpha.md) covers installation, workflows and limitations.

SwiftUI provides workspace screens, AppKit provides desktop integration and SwiftTerm, WebKit renders reviewed browser sessions, and a persistent Python engine owns the agent loop and SQLite storage. Bundled Ollama handles inference. The app runs without Node, Electron or a separately installed Python. No model weights are bundled.

The current source includes the [prioritized application gap audit and fixes](APPLICATION_GAP_AUDIT_2026-10-10.md), covering chat scanner evidence, command cleanup, agent outcome checks and queue controls, resume safety, editor acknowledgements and activity history. Its validation record distinguishes source tests, packaged/model evidence, installed checks and remaining external prerequisites. The [controls, editor and activity completion record](AGENT_CONTROLS_COMPLETION_2026-10-10.md) adds explicit execution identity checks, context restoration, acknowledged queue drafts and production submission/guidance acceptance. These changes do not update the already published alpha download.

## Build and run

Requires Apple Silicon macOS 14+, Swift 6.4 command-line tools, a build-time Python and the staged runtime payload. The public alpha and native CI use the Xcode 27 toolchain. Older Swift compilers can time out while checking the current SwiftUI views; this build-time requirement does not change the app's macOS 14 deployment target.

```sh
python3 -m venv native/.venv
native/.venv/bin/python -m pip install -r native/requirements-build.txt
# Stage the pinned Ollama payload if runtime/ollama is absent:
node scripts/runtime-stage.cjs
./script/build_and_run.sh --package-only
native/.venv/bin/python native/scripts/install.py --alpha
open /Applications/Wixal.app
```

`./script/build_and_run.sh` builds and opens the same native alpha. `--verify`, `--debug` and `--logs` are available. `native/scripts/wixal-packaged` runs the terminal client against the canonical packaged helper. If the desktop is open it connects over an owner-only Unix socket; otherwise it owns the workspace until it exits. The workspace lock prevents concurrent engines from overwriting state. Use `--data PATH` for isolated acceptance.

SwiftPM uses `--build-system native` so the AppKit terminal can build with Command Line Tools without a separate Metal compiler. Dependencies are pinned in `Package.resolved` and `requirements-build.txt`.

## Packaging

```sh
native/.venv/bin/python native/scripts/package.py --alpha
```

`--alpha` requires an alpha engine version and creates an explicitly labelled ad-hoc signed bundle. It cannot be combined with development or Developer ID options. Public release metadata states that it is not notarised. `--development` is for isolated local validation and allows `--preview-data` and a loopback `--preview-endpoint`; these overrides are not allowed in public alpha packaging.

For a notarised release, omit alpha/development flags and supply `--identity 'Developer ID Application: …' --notary-profile PROFILE`. The packager signs nested binaries, submits to notarytool, staples and checks Gatekeeper. This machine currently has no valid Developer ID identity. Packaging verifies the vendor payload and records source hashes before atomically replacing the staged build.

The native bundle identifier and workspace location retain compatibility with earlier native previews. The display name is Wixal. Installed background schedule commands are repointed to the canonical app by `install.py`.

## Validation

```sh
PYTHONPATH=native/engine:native/tests native/.venv/bin/python -m unittest discover -s native/tests -v
swift run --package-path native --build-system native -c release MarkdownAcceptance
swift build --package-path native --build-system native -c release --product ActivityAcceptance
native/.venv/bin/python native/scripts/agents-packaged-acceptance.py \
  --app release/native/Wixal.app --output artifacts/native/alpha-acceptance --management \
  --model gpt-oss:20b --endpoint http://127.0.0.1:11434
```

For the activity projection, run `native/.venv/bin/python native/scripts/activity-acceptance.py --workspace artifacts/native/alpha-acceptance/data/workspace.sqlite3` after the packaged suite. It compares actual persisted tool messages with the earlier production projection and verifies stable identities; Node is a development dependency for this comparison.

The packaged suite uses real source files, a real external local model, scratch writes, calendar routines, saved skills and a closed-helper background run. It writes evidence to an isolated workspace. It does not establish every model’s reliability or full UI coverage. Fixture/regression tests and real packaged model acceptance are separate evidence.

Earlier detailed reports remain available: [agent workflows](AGENTS_COMPLETION_ACCEPTANCE_2026-10-08.md), [security workspace](SECURITY_WORKSPACE_ACCEPTANCE_2026-10-08.md), [UI/UX](UI_UX_REDESIGN_ACCEPTANCE_2026-10-08.md) and [migration](MIGRATION_POPULATED_ACCEPTANCE.md). Their bundle names and hashes describe the builds tested at that time.

## Data and memory

State is stored in `~/Library/Application Support/Wixal Native/workspace.sqlite3`. The model library is in the same workspace’s `local-runtime/models`. Projects point to real folders. Approved edits and commands can change those files. Earlier Electron storage is imported explicitly and retained; encrypted credentials and account sessions are excluded.

Saved notes are editable. Local lexical/optional semantic recall, visible summaries, correction/forgetting and reviewed lasting-decision suggestions support context. Small global memory is separate from project notes. Optional encrypted folder sync excludes credentials, local project paths, tool authority and schedules. A real two-Mac run remains outstanding.

## Tools and authority

Agents discover eligible tool schemas and choose tools under their authority policy. Scope and review policy control execution. File writes recheck paths and current contents after approval. Commands have bounded output, ownership, timeouts and process-group cancellation; they run with the user’s Mac access, not an OS sandbox.

Trusted MCP connections support local stdio and remote HTTP, with optional SDK OAuth/Keychain storage. Connecting starts or contacts the configured server. Service-specific OAuth requires separate live acceptance. Bounded read-only child agents cannot recursively delegate.

Native WebKit tools support bounded public browsing and reviewed ephemeral interactive sessions. Credentials are entered manually and protected input remains unavailable to the model. Browser work requires the desktop. Optional awake closed-app schedules pause if review or the desktop is required. Sleep/wake/reboot acceptance is outstanding.

## Architecture and alpha boundaries

Swift communicates through JSON-line IPC; the owner-only Unix socket supports shared terminal access. Python persists tasks and checkpoints before work. Restarting the engine fails pending requests rather than replaying uncertain actions. The rewrite alone is not evidence of faster model generation.

Agents include reusable profiles, workflows, queue/history, schedules, artifact checks, skills and explicit skill evaluation. Cybersecurity includes scope, investigations, evidence and findings. Local tests do not establish production security quality. Remote execution, messaging/voice gateways, autonomous skill promotion, broader model/service acceptance, full accessibility, notarisation and automatic updates remain incomplete.

An adapted Hermes duration parser is included under MIT with [its notice](third_party/hermes/NOTICE.md). The main engine is Wixal’s implementation; this alpha does not claim full Hermes parity.
