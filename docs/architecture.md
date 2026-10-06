# How Wixal fits together

Wixal is an Electron app with a local HTML/CSS/JavaScript interface. Wixal Local manages a bundled, pinned Ollama runner on a fresh loopback port with its own model store. All production inference uses this engine; installed Ollama weights are imported, and cloud/external model selection is rejected by IPC and the controller. An external loopback engine is allowed only with explicit isolated test state for protocol fixtures. The optional companion exposes explicitly shared projects through a separate MCP stdio process.

```text
Renderer → restricted preload API → Electron main process
                                      ├─ Store: local projects, conversations and memories
                                      ├─ Ollama / provider adapters: catalogs and streaming inference
                                      ├─ Credentials / ChatGPTAuth: encrypted keys and browser OAuth
                                      ├─ Companion: paired local bridge and persistent task inbox
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
| `app/openai.cjs` | Stateless Responses requests, SSE parsing and provider input conversion |
| `app/credentials.cjs` | Main-process macOS-encrypted API keys and account records |
| `app/chatgpt-auth.cjs` | Loopback OAuth, PKCE, JWKS identity verification, refresh and revocation |
| `app/companion.cjs` | Loopback bridge, project consent, bounded reads and task queue |
| `app/companion-stdio.cjs` | MCP server forwarding to the paired local bridge |
| `app/agent.cjs` | Context selection, saved summaries, streaming and the tool loop |
| `app/tools.cjs` | Project paths, file operations, tool permission checks and shell execution |
| `app/memory.cjs` | Scope/budget validation, context ceilings and token estimates |
| `app/accounts.cjs` | Firebase accounts, optional presets and bounded global profile |
| `app/context.cjs` | Incremental summaries, relevant memory selection and scoped history retrieval |
| `app/network.cjs` | Reviewed search/HTTP requests, bounded response text and redirect rejection |
| `app/extensions.cjs` | Local MCP client lifecycle, tool discovery, reviewed calls and cleanup |
| `app/store.cjs` | Atomic local state and preference migration |
| `ui/renderer.js` | Views, model selection, file previews, attachments and interaction |
| `ui/styles.css` | Desktop layout and compact window adjustments |
| `scripts/smoke.cjs` | Real Electron and packaged-app verification |

## A message through the app

The main process checks the current model and validates image attachment IDs. Agent mode requires tool support when a project is open. Images require vision support. Unsupported requests fail before a user turn is added.

The agent adds the user message, loads explicit project memories and selects recent complete turns. It sends the allowed tool definitions to the selected provider, streams the response, then stores the completed assistant message and generation stats.

When a model calls a tool, the controller checks that it is enabled. Reads return bounded results. Writes and commands use the live workspace policy: Review each action or Approved all. The result goes back into the conversation and the loop continues. Cancellation reaches both inference and command process groups. There is a 32 step limit.

## Files and the host shell

Project file tools resolve real paths, reject traversal and symlinks outside the root, and exclude common credential paths. Writes recheck the file after review so a change made during the dialog is not silently overwritten. These checks do not make the whole application a sandbox.

An approved shell command can access anything available to the user account. The interactive terminal has the same host access and accepts direct user input. The review dialog and README explain that distinction.

## Images

Only user-selected images are imported. The main process limits file size, decodes PNG/JPEG/WebP with sharp, applies photo orientation metadata, resizes it and converts it to PNG. The renderer receives a thumbnail and an opaque ID. Sending a message resolves IDs from the main process cache, rather than accepting arbitrary paths or image bytes from the renderer. Resized images are saved in the user turn and sent using Ollama’s base64 image field.

Images remain visible in saved conversations when a text-only model is selected. Their bytes are excluded from that model’s request.

## Persistence and context

State is written to a temporary JSON file with mode `0600` and renamed over the current file. Existing installations receive new preference defaults without replacing their history. This is not encrypted storage.

Model context is bounded using an estimate, not a tokenizer. Whole recent turns are retained, including tool exchanges. The newest turn is checked against the estimated request budget; large tool results are shortened only for inference. An oversized new prompt returns an actionable error before being saved. Runtime context has a model/RAM-aware ceiling of 32k, with output space reserved. Project notes and earlier active chats share a bounded retrieval budget. Project-only excludes global profiles and other projects. New-chat handoff inserts a visible summary and retains the source. Assistant records identify their generating model; foreign tool calls and results become portable text evidence. See [memory details](memory.md). Older complete turns are automatically condensed by the selected model in bounded chunks and saved per conversation. Summary requests have no tools; failed inference falls back to labelled relevant excerpts. A prefix hash prevents stale or redundant compaction. Explicit notes are ranked by prompt relevance; overlapping text chunks support project-scoped history search. Retrieval uses word matching rather than embeddings.

## Renderer boundaries

Node integration is off; context isolation and Electron sandboxing are on. IPC checks the calling web contents and frame URL. Navigation and new windows are denied. Markdown is sanitised, remote media is blocked and file/shell access uses only the named preload methods.

## Historical cloud credentials and consent

The renderer never receives stored API keys, access tokens, refresh tokens or ID tokens. Credentials are encrypted with Electron safeStorage and written atomically with owner-only permissions. No plaintext fallback is used. A credential-loading failure preserves the existing file and leaves local models available.

Each project and the personal workspace require explicit cloud context consent before inference. OpenAI requests use the public Responses endpoint with store:false and stream:true. ChatGPT plan requests use namespaced local function tools, omit unsupported preview fields and send the required history explicitly. Encrypted reasoning output and matching tool call IDs are retained for stateless continuation. A provider switch converts earlier tool evidence to text instead of reusing foreign call IDs. Streams must reach response.completed before their assistant turn is committed.

The browser OAuth transaction has fresh state, nonce and PKCE, expires after five minutes and is consumed once. The listener binds to 127.0.0.1, validates its Host and state, and verifies ID-token signature, issuer, audience, expiry and nonce against OpenAI JWKS. Separate account registrations retain their issued client IDs and stable host ID. Refresh is serialized per account. Sign-out attempts revocation before removing local tokens and reports unconfirmed remote revocation.

## Private companion

Only the six declared companion tools are exposed through MCP. They list shared projects, read/search bounded project text, queue tasks and return task state. Shared project checks apply before and after disk reads; file tools still respect the enabled tool kit. Memory sharing is a separate preference. No shell or file-write tool is exposed remotely.

The bridge listens on a random loopback port. A rotating pairing token is stored in wixal-connection.json with mode 0600; the main process and MCP stdio helper use it locally. The bridge rejects browser-origin traffic and unexpected Host values, requires pairing, bounds requests and limits request rate. The pairing file and encrypted credentials are blocked by the project file tools. Pausing removes pairing and stops the bridge. The Secure MCP Tunnel process authenticates separately to OpenAI and forwards MCP over stdio. Tunnel transport keeps the server private; data returned to ChatGPT still reaches the cloud.

Tasks remain queued until started through trusted UI IPC. Each run uses its own conversation and captures its provider/account. Commands and writes use the existing review path. Task status distinguishes queued, running, waiting_review, completed, failed, cancelled and interrupted; a restart marks unfinished runs interrupted. Completed means the agent response finished, while tool outcomes separately report errors, declined actions and command exit status.

## Provider adapters

`app/providers.cjs` declares fixed service endpoints and validates explicit custom URLs. `app/cloud.cjs` selects Responses for OpenAI/ChatGPT/xAI, native Messages for Claude, and Chat Completions for the remaining services. `app/sse.cjs` decodes UTF-8 and split CRLF event boundaries. Each adapter waits for protocol completion before handing tools to the shared reviewed runtime. Claude requires both stopped content blocks and message completion. Chat Completions requires a finish reason and DONE; length/content filtering stops are errors.

Credentials migrate the original OpenAI key into the encrypted per-provider key map. No key reaches renderer snapshots. Catalog invalidation has a revision counter so late requests cannot replace a newly changed connection's models. Runs capture their connection credentials and custom endpoint; settings cannot change during a response. Custom endpoints reject redirects and require HTTPS except on loopback. Their model ID and capability choices are explicit user configuration.

### Conversation lifecycle

Sessions retain their project scope and messages when archived (`archivedAt`). Project selection skips archived sessions. Archives can be opened read-only; both the main-process chat handler and agent reject inference until restoration. Session mutations require an idle agent. Deletion removes linked task output copies, while leaving files and project memory intact. If the active chat is removed from the active list, Wixal selects another active chat or creates an empty one. Lifecycle state uses the existing atomic workspace save.

## Network tools and MCP clients

Network tools are opt-in and run in the main process. Review displays the URL, method, body or search terms before a request. Requests have a 20-second timeout, a 1 MB response cap, no automatically attached stored credentials and no automatic redirects. Search uses DuckDuckGo HTML results; HTML page responses become text. A blocked search service is an error, not a completed result.

External tools use the installed MCP SDK's Client and StdioClientTransport. Saved executable/argument configurations do not auto-launch on restart. A user's Connect click starts the process; tool discovery follows catalog pagination with bounds and generates stable hashed tool names to avoid collisions. Connected definitions join the enabled tool catalog in local inference. Every invocation follows the workspace approval policy and supports a 60-second timeout and abort signal. Disconnection and app shutdown close client transports. External server processes have the user's host permissions and may perform actions during startup.

Model downloads stream Ollama's pull endpoint to the renderer through named events. Progress is per layer; the runtime requires a success record, forwards errors, and aborts the HTTP request on Cancel or app shutdown. Context preferences now include 64k and 128k, with local inference clamped to reported model limits. Neither a larger preference nor a downloaded model guarantees enough host RAM.

## Managed local runtime

`app/runtime.cjs` owns payload verification, startup coalescing, loopback port allocation, a filtered child environment, readiness checks, process-group cleanup and independent model imports. `app/models.cjs` and the local agent resolve the active endpoint dynamically. Named IPC handlers expose only supported mode/lifecycle/import operations. Store migration defaults to managed mode without replacing conversation or project data. Generated native payloads are outside ASAR; source pins and build metadata are in `resources/runtime.json`. See [the runtime guide](local-runtime.md) for provenance and limits.

## Current local controller additions

`model-options.cjs` chooses supported thinking values and conservative model-selection context limits. `workspace-context.cjs` builds live workspace/capability/tool/policy context for every inference step and `workspace_info`. `approvals.cjs` centralises workspace-scoped all-mode decisions and their local records. `security-tools.cjs` validates explicit targets and ports, then launches fixed Nmap profiles as argument arrays through owned command sessions. Scan results retain command, timestamps, target/profile and bounded raw evidence. Model text never changes approval policy.
