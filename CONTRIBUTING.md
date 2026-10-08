# Working on Wixal

The current app is the native alpha in `native/` on `main`. Build and validate that app when changing the interface or engine. Earlier Electron source is retained for history and migration.

## Before opening a PR

Run the engine regression suite and the Markdown/activity acceptance commands in [the native guide](native/README.md). Native engine and UI changes need a packaged app check: a successful compile alone does not establish runtime behaviour. Real model acceptance needs an actual local model and isolated workspace; keep that evidence separate from fixtures.

For website changes run `BASE_PATH=/Wixal/ npm --prefix website run build` and `BASE_PATH=/Wixal/ npm --prefix website run check`. Keep optional analytics behind consent.

Add meaningful regression tests when behaviour or permissions change. Small wording and styling changes need an actual visual check.

## Interface and copy

Use plain wording. Describe what a control does. Preserve the workspace’s themes, restrained accents and W identity. Use screenshots from the running app with a safe project; exclude personal files, credentials and private conversations.

## Engine boundaries

Validate IPC and scope in the controller. File tools retain selected-project, credential and symlink checks. Agents choose eligible tools under their authority policy; review decisions are enforced in the engine. Do not claim a command ran or a file changed without returned evidence. Keep memories visible and editable. Do not automatically replay uncertain side effects.

## Reports

Include macOS, machine architecture, alpha version, model name, expected behaviour and a small reproduction. Remove private content and credentials from logs.
