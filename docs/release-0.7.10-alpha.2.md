Wixal 0.7.10 Alpha 2 fixes tool discovery in native Chat. Chat now uses the same automatic tool-selection path as Agents, including when older workspace tool switches are empty or disabled.

Download **Wixal-0.7.10-alpha.2-macOS-arm64.zip**. It contains one **Wixal.app** for **Apple Silicon, macOS 14 or newer**. Replace the existing app in Applications; existing native workspace data is retained. Python and the local Ollama runner are included. Model weights download separately.

## What changed

- Chat discovers available project, command, web, memory and connected MCP tools automatically. The model chooses the tools needed for the request.
- Chat's tools drawer is an inspectable catalogue without per-tool switches. Tool suggestions use the discovered catalogue, and `@` mentions remain optional.
- The Chat composer exposes its action-review setting. Existing review preferences, project boundaries and saved-agent Read only policies still apply.
- Chat can progressively load schemas within small context budgets and receives bounded correction feedback for recoverable tool failures. Declined and uncertain actions are not retried automatically.
- Chat's instructions require executable calculations for derived project counts when available and independent comparisons before claiming a saved result is verified.
- Chat receives the tool-name inventory alongside progressive schemas. The `run_command` schema now exposes its already supported bounded timeout, preventing a valid timeout from being rejected as an unknown field.
- MCP connection and tool settings copy now describes automatic discovery.

## Validation

- 215 engine regression tests pass, including eleven new Chat cases: empty legacy preferences, optional mentions, cross-category discovery, real file/command effects, review rejection, attachment reads, model/project prerequisites, connected MCP, error correction, context fitting, cancellation and bounded command timeouts.
- Native Swift release compilation and all five production Markdown acceptance checks pass.
- Real-model acceptance uses gpt-oss:20b through the installed packaged helper's production JSON IPC. It covers actual source inspection, a report derived from the real project manifest, independent command verification and a declined write with no side effect.
- Native Chat's catalogue, review controls and optional tool suggestions were inspected in the installed app.
- Package and installed helper/source hashes match; all 105 packaged source files match the release source. Deep strict ad-hoc signature verification passes.

Earlier real-model attempts are retained: one produced malformed tool-call JSON on a large catalogue, and another miscounted manifest scripts. Independent checks rejected the incorrect report. These failures motivated the calculation guidance and do not establish reliability for every model or task.

## Alpha limits

This alpha is ad-hoc signed and is **not Developer ID signed or notarised**. Updates are manual downloads from GitHub. If macOS blocks first launch, review the source and release notes and use System Settings → Privacy & Security → Open Anyway.

Native data remains at `~/Library/Application Support/Wixal Native`. Back up important work. Commands run with your Mac account's access. Tool-capable models are required for actions; browser work requires the native desktop, and background routines require an awake Mac. Existing limits around remote/off-Mac execution, messaging/voice, broader model and connected-service acceptance, production security evaluation, sleep/wake/reboot acceptance and automatic updates remain.
