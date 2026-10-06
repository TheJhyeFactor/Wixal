# Changelog

## 0.7.8 — 6 October 2026

- Added isolated Chromium browser sessions with reviewed navigation, fresh control refs, ordinary clicks/text/select actions, delayed-content waits, pagination and cleanup.
- Added distinct empty/blocked search outcomes, deduplicated source URLs and snippets, paginated HTTP GET evidence, HEAD support and explicit response limits.
- Load task-relevant tool schemas with category and specific-tool discovery while preserving the enabled-tool permission boundary.
- End tool execution for the turn after a declined action or three identical failures; request a visible evidence-based conclusion.
- Added exact unique file edits and directory creation with review and concurrent-change checks; file search now covers supported 1 MB text files and later matches.
- Added readable browser/search/HTTP activity and bounded valid JSON model excerpts with whole refs/URLs and session metadata.
- Added argument validation, real MCP process regressions and actual Chromium CI coverage; live browser, search and model tests use jhye.dev.

## 0.7.7 — 6 October 2026

- Added a 1,200-character explicit global preference profile, local for guests and owner-only Firebase syncing for verified accounts.
- Added project memory scope choices, editable notes, 8k/24k/48k saved-character budgets, capacity indicators and explanations of recall tradeoffs.
- Automatically retrieves bounded relevant excerpts from earlier active chats in the same project; project-only excludes global preferences.
- Added a context meter, reply reserve, model/RAM-aware 32k ceiling and recommendations to continue in a new chat.
- Added fresh-chat and model-summary handoff choices with visible injected context, retained source history and labelled failure excerpts.
- Fixed local model switching by recording the generating model and converting older foreign tool exchanges into portable text evidence.
- Included the local tool, assessment and interface improvements developed in 0.7.4–0.7.6, plus account setup, optional presets, launch controls and app icon choices.


## 0.7.6 — 6 October 2026 (local build)

- Added restrained surface depth across all four themes, softer floating-panel shadows and a warmer Paper palette with clearer card separation.
- Kept the newest tool evidence readable during long assessments; empty local-model conclusions retry once without repeating tools, then surface an error if still blank.
- Added native website assessments with bounded same-origin GET probes, protected-path checks and saved JSON/Markdown evidence.
- Added portable vulnerable/hardened attack fixtures with browser script execution, cross-origin writes, throttling and logout replay.
- Added website/attack buttons and embedded evidence-focused assessment response guidance for every local tool-capable model.
- Verified website/source assessments and local Qwen tool workflows in development.

## 0.7.5 — 6 October 2026 (local build)

- Restricted inference to the included Wixal local engine and combined ready models with importable Ollama models in one picker.
- Automatically embedded live workspace, tool and approval context in model requests; added workspace_info.
- Used supported thinking metadata for GPT-OSS and retained reasoning across tool steps; migrated the default context to 8k.
- Added persistent workspace-scoped Approved all, immediate policy switching during runs and local action records.
- Added eight Nmap assessment profiles, validated targets/ports, owned scan sessions, cancellation, readable port/service evidence and JSON report metadata.
- Preserved valid command-result JSON when shortening long output for model context.
- Added real HTTP/TLS scan fixtures and model/tool/approval UI tests.

## 0.7.4 — 6 October 2026 (local build)

- Enabled native tools automatically in Chat and Agent for tool-capable models.
- Kept enabled follow-up tools available after @mentions and allowed visible clarification for missing arguments.


## 0.7.3 — 6 October 2026

- Coordinated sidebar width, brand, toggle, new-chat and footer motion, with fixed-width navigation and a short label fade.
- Made collapse and expand respond immediately, reverse smoothly and save the final layout in order during rapid toggles.
- Removed collapsed navigation from keyboard focus, restored focus to the toggle when needed, and respected both macOS and in-app reduced-motion preferences.
- Fixed repeated Workspace-button clicks to close its menu, kept the menu anchored throughout motion and preserved equal, centered bottom-left controls at desktop and compact sizes.
- Applied saved layout without a startup animation and refreshed real app screenshots and a recorded sidebar animation.

## 0.7.2 — 6 October 2026

- Redesigned the main workspace with project/model readiness, practical starting prompts, a focused composer and direct Files, Tools, Memory and Terminal controls.
- Added explicit Chat/Agent selection with descriptions and keyboard navigation.
- Saved text drafts locally across chat changes and app restarts; kept temporary attachments scoped to the current conversation.
- Added individual code-block copying and jump-to-latest navigation.
- Updated only the pending text node during streaming, preserving saved message nodes and earlier reading position.
- Made selecting a chat return directly from the Models page and derived the title-bar version from the running app.
- Refreshed packaged-app screenshots, tours and concise product information while staying on the 0.7.x release line.

## 0.7.1 — 6 October 2026

- Reorganized the model chooser around Installed and Downloads tabs, with provider, current model, context and local-engine settings in a separate setup panel.
- Added download search and sorting, independent filters for each library view, clearer selected-model and memory-fit information, and a model menu for deletion.
- Added a dedicated Models page, direct catalog downloads, a persistent serial queue with pause/resume/cancel/retry, installation verification and selection after download.
- Added model-drive space and loaded-memory readings, explicit memory release and suggested context settings.
- Cached unchanged model metadata, bounded metadata requests, throttled progress updates and reused hardware identity. External-engine memory estimates now account for higher precision context caches.
- Kept the local provider branded as Wixal Local in both bundled-engine and external-server modes.
- Aligned the bottom-left Models, Settings and Workspace controls with equal hit areas and icon positions in expanded and collapsed sidebars; kept the menu anchored on resize.
- Added appearance and workspace preferences, sidebar resizing and an in-app project folder picker.
- Refreshed actual app screenshots, the model tour and product information.
- Kept development on the 0.7.x patch release line.

## 0.7.0 — 6 October 2026

- Included the managed Wixal Local engine and independent model imports, with upstream credits and pinned runtime provenance.
- Added reported usage, real local benchmarks and model fit filters.
- Added explicit @tools, rendered-page inspection and longer command sessions.
- See [the 0.7.0 release notes](docs/release-0.7.0.md) for the complete release and verification details.

## 0.6.0 — 6 October 2026

- Added reviewed DuckDuckGo web search and HTTP requests for web pages and JSON APIs, disabled until enabled in the tool kit.
- Added local MCP stdio server connections, discovered tool catalogs, individual tool controls, per-call review, timeout and disconnection.
- Added automatic model-generated conversation summaries with incremental persistence, bounded input chunks, labelled fallback excerpts and a summary inspector in Project memory.
- Added project-scoped conversation search and reviewed agent memory saves. Relevant project notes are selected by prompt instead of taking the oldest notes first.
- Added continuation offsets for large file reads. Large tool results remain saved in full while inference uses bounded excerpts.
- Added in-app Ollama downloads with layer progress, cancellation, completion checks, and 64k/128k context preferences.
- Fixed the packaged companion helper by unpacking package metadata alongside app source and dependencies, so external Node processes can read the release version.
- Updated the README, feature guide, architecture, release notes, real app screenshots and motion tour for the new capabilities.
- Added feature coverage through a real MCP child process, a real local HTTP service, Electron review dialogs, saved summaries and download fixtures. Updated existing UI tests for the Workspace menu.

## 0.5.1

- Added a collapsible sidebar with saved layout and a workspace menu for project tools and navigation.
- Added Ollama, OpenAI, ChatGPT, Claude, Gemini, Grok, DeepSeek, Groq, Mistral, OpenRouter, and custom endpoint connections.
- Added encrypted provider credentials, optional cloud context, and ChatGPT sign-in.
- Added a private ChatGPT companion with selected project sharing, a task inbox, and reviewed work in Wixal.
- Added conversation archives with search, reading, and restore; added confirmation for permanent deletion.
- Refined the new-chat screen, composer, project suggestions, logo, and motion.

## 0.2.0

- Reworked the desktop interface with a simpler layout, clearer controls and plain wording.
- Added a searchable Ollama model picker with tool and image support information.
- Added project file browsing, previews, tool controls, and a zsh terminal.
- Added image attachments, conversation search, saved project memory, and offline recovery.
