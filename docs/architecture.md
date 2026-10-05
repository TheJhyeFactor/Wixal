# How Wixal fits together

Wixal is an Electron app with a local HTML/CSS/JavaScript interface. Ollama handles inference on `127.0.0.1:11434`. There is no hosted service in the current build.

```text
Renderer → restricted preload API → Electron main process
                                      ├─ Store: local projects, conversations and memories
                                      ├─ Ollama: model metadata and streaming chat
                                      ├─ Tools: project files and reviewed commands
                                      └─ node-pty: interactive zsh terminal
```

## Files to start with

| File | Responsibility |
| --- | --- |
| `app/main.cjs` | App lifecycle, validated IPC, dialogs, image import, approvals and PTY |
| `app/preload.cjs` | Named API calls and events exposed to the renderer |
| `app/images.cjs` | Validated PNG/JPEG/WebP import, photo orientation and resizing |
| `app/models.cjs` | Installed-model listing and capability/context discovery |
| `app/agent.cjs` | Context selection, streaming, saved turns and the tool loop |
| `app/tools.cjs` | Project paths, file operations, tool permission checks and shell execution |
| `app/store.cjs` | Atomic local state and preference migration |
| `ui/renderer.js` | Views, model selection, file previews, attachments and interaction |
| `ui/styles.css` | Desktop layout and compact window adjustments |
| `scripts/smoke.cjs` | Real Electron and packaged-app verification |

## A message through the app

The main process checks the current model and validates image attachment IDs. Agent mode requires tool support when a project is open. Images require vision support. Unsupported requests fail before a user turn is added.

The agent adds the user message, loads explicit project memories and selects recent complete turns. It sends the allowed tool definitions to Ollama, streams the response, then stores the completed assistant message and generation stats.

When a model calls a tool, the controller checks that it is enabled. Reads return bounded results. Writes and commands wait for review. The result goes back into the conversation and the loop continues. Cancellation reaches both inference and command process groups. There is a 12 step limit.

## Files and the host shell

Project file tools resolve real paths, reject traversal and symlinks outside the root, and exclude common credential paths. Writes recheck the file after review so a change made during the dialog is not silently overwritten. These checks do not make the whole application a sandbox.

An approved shell command can access anything available to the user account. The interactive terminal has the same host access and accepts direct user input. The review dialog and README explain that distinction.

## Images

Only user-selected images are imported. The main process limits file size, decodes PNG/JPEG/WebP with sharp, applies photo orientation metadata, resizes it and converts it to PNG. The renderer receives a thumbnail and an opaque ID. Sending a message resolves IDs from the main process cache, rather than accepting arbitrary paths or image bytes from the renderer. Resized images are saved in the user turn and sent using Ollama’s base64 image field.

Images remain visible in saved conversations when a text-only model is selected. Their bytes are excluded from that model’s request.

## Persistence and context

State is written to a temporary JSON file with mode `0600` and renamed over the current file. Existing installations receive new preference defaults without replacing their history. This is not encrypted storage.

Model context is bounded using an estimate, not a tokenizer. Whole recent turns are retained, including tool exchanges. The newest turn is always kept, so a very large turn can exceed that estimate. Runtime context is clamped to the model’s reported maximum. There is no automatic summary or semantic memory search.

## Renderer boundaries

Node integration is off; context isolation and Electron sandboxing are on. IPC checks the calling web contents and frame URL. Navigation and new windows are denied. Markdown is sanitised, remote media is blocked and file/shell access uses only the named preload methods.
