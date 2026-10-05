# Developing Wixal

Use Node.js 22 or newer, the Xcode command line tools, and an Apple Silicon Mac. Install dependencies with `npm ci`, then run `npm run rebuild` to rebuild node-pty for Electron.

## Check a change

```sh
npm test
npm run check
npm run test:app
```

The app test launches Electron with temporary state and a small test project. It exercises model selection, file previews, tool settings, image attachments, project memory, the real PTY, persistence, offline recovery, and compact window layout. Screenshots are saved in `artifacts/`.

The full test uses an installed tool-capable vision model to create a fixture file after approval, recall a saved preference, and describe an image. The current fixture expects Qwen and Gemma models in the local Ollama library.

To check the interface and terminal without running inference:

```sh
WIXAL_SKIP_MODEL_TEST=1 npm run test:app
```

This still needs Ollama running and the model metadata expected by the fixture.

## Package a Mac app

```sh
npm run package
WIXAL_APP_PATH="$PWD/release/Wixal-darwin-arm64/Wixal.app/Contents/MacOS/Wixal" npm run test:app
```

Packaging creates `release/Wixal-darwin-arm64/Wixal.app`. The native node-pty module is unpacked from asar so its spawn helper can run. The app is not Developer ID signed or notarised.

## Update the graphics

```sh
npm run assets
npm run media
npm run assets
npm run motion
```

Build the assets, record fresh app media, then rebuild the header with the new workspace screenshot and export its motion. The recording uses a real app session with disposable demo data. See [the visual guide](visuals.md) for source files and motion behaviour.
