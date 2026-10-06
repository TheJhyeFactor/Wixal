# Changelog

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
