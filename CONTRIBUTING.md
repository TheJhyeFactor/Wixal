# Working on Wixal

Keep it focused. Fix a real problem, show what changed and include how you checked it.

## Before opening a PR

Run `npm test` and `npm run check`. If you touch the interface, terminal or agent loop, run the app smoke check too. Changes to native modules need a packaged app check; a successful build alone won’t tell you whether the terminal works.

Add a test when behaviour or permissions change. Small wording and styling changes just need a real visual check.

## Interface and copy

Use plain wording. Say what the control does. Keep the dark workspace, restrained pink accents and W identity consistent. Screens should help someone do the next thing, without slogans or pretend features.

Screenshots should come from the running app with a test project. Keep personal files, credentials and private conversations out of them.

## Boundaries to keep

- Privileged work stays in the main process, behind validated IPC.
- Read and write tools stay inside the selected project and keep credential and symlink checks.
- Writes and agent commands need review every time.
- Tool preferences are enforced in the controller, not just in the UI.
- Don’t claim a command ran or a file changed unless its result proves it.
- Keep saved memories explicit and visible.

## Bug reports

Include your macOS version, machine architecture, Wixal version, Ollama version and model name. Tell us what you did, what you expected and what actually happened. A small reproduction is useful. Remove private paths and content before sharing logs.
