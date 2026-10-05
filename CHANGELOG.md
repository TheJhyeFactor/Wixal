# Changelog

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
