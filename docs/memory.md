# Memory and conversation context

Wixal 0.7.7 keeps saved preferences, project recall and the active model context separate. Model inference runs locally. A Wixal account can optionally sync one small global preference profile through Firebase; project notes, files and conversations remain on this Mac.

## What changed

Before this release, each workspace had explicit notes of up to 4,000 characters per entry. Relevant note chunks entered the prompt, history could be searched using a tool, and older complete conversation turns were automatically summarized. There was no total saved-note budget, account profile, memory scope choice, context progress meter or new-chat handoff. The newest turn could exceed the estimated request budget. Local assistant records did not identify the generating model, so switching models could pass another model's tool-call format and reasoning into the next request.

Now projects choose **Memory off**, **Project only** (the default), **Global preferences only**, or **Project + global preferences** when first opened. Existing projects keep their settings. Change a project's scope and budget in its Memory drawer. Project-only excludes global preferences and all other projects. Memory off disables saved notes and prior-chat retrieval, while the current conversation still supplies context. Switching scope does not delete saved notes.

## Saved memory limits

| Setting | Stored capacity | Maximum retrieved per request | Benefit and tradeoff |
| --- | --- | --- | --- |
| Light project memory | 8,000 characters | 1,000 characters | Focused, easy to curate; fewer lasting details. |
| Balanced project memory (default) | 24,000 characters | 2,400 characters | Useful room for conventions and decisions; keep notes current. |
| Detailed project memory | 48,000 characters | 4,000 characters | Retains more details; more curation and a larger share of active context when relevant. |
| Global preferences | 1,200 characters total | Whole short profile when enabled and allowed | A few personal preferences across chats; deliberately too small for project history. |

Each project note still has a 4,000-character limit. Capacity checks happen in the main process, including agent saves and edits. A lower budget cannot silently discard notes: remove enough saved text before reducing it. Old notes are preserved during migration, even if they exceed a new cap. The usage bar explains capacity and permits cleanup.

Stored capacity is not the model's context window or RAM allocation. Project recall ranks overlapping text chunks using words from the current request. Relevant earlier user/assistant messages from active chats in the same project can be included automatically. Archived chats and other projects are excluded. These excerpts share the per-request memory budget with saved notes; they do not occupy saved-note capacity. **Recall project conversations** can search for further details when enabled. This is local keyword retrieval, not semantic embedding search, and it cannot promise every relevant fact will be found. Files enter through file tools or explicit attachments; the whole project folder is not indexed automatically.

Notes are visible, editable and removable. An AI-proposed note uses **Save project memory** and follows the workspace approval policy. Global profiles are saved explicitly through the UI; models cannot silently write an account profile. Current instructions and enabled tool permissions take precedence over historical excerpts.

## Global account preferences

Use **Memory → Global preferences** for a preferred name, language, tone, accessibility needs or a short coding preference. Guests store this profile locally. Signed-in users save explicitly to `users/{uid}/profile/memory`; verified email and owner-only access are required. Sign-in, account verification and restoration load that account's profile. **Refresh from account** retrieves changes made elsewhere. Saves replace the complete short profile; there is no background merge, so refresh before editing on multiple Macs.

Guest and account profiles are separate. Signing in does not upload guest preferences, project notes or conversations. Signing out clears the account profile from the in-memory cache and returns to the guest profile. An offline account restore excludes its profile until a successful lookup and refresh. Project-only chats never include global preferences. Turning off **Use global preferences where allowed** stops inclusion without deleting the saved profile. Clear its text and save to forget it.

Firestore independently enforces the 1,200-character ceiling and rejects anonymous, unverified or other-account access. The profile is user-provided text; only save information you want reused. Account memory is cloud data even though model inference runs locally.

## Context limits and meter

The default is 8,192 tokens. Choices are 4k, 8k, 16k and 32k. Small windows reduce context cache RAM and prompt processing, but carry fewer original messages and may summarize sooner. Large windows retain more original detail at the cost of RAM and slower prompt processing. **32,768 tokens is the app ceiling**, further limited by the model's reported window and a hardware estimate. Macs with less than 24 GiB total RAM have a 16k ceiling. Model weight size and cache dimensions can lower the effective window further. Model selection starts at up to 16k; larger supported windows require an explicit settings choice.

The estimator reserves 25% of total RAM for the host, 15% model weight overhead and 1 GiB of workspace when model size is available. It is not a guarantee that a model will fit or perform well with other apps running. An unusually large model can still fail to load; choose a smaller model if necessary.

The composer meter estimates input usage, including conversation text, memories, instructions and tools. Its label shows the input budget separately from the total window. Roughly 15% of the window is reserved for output, bounded between 512 and 2,048 tokens. Draft estimates use an instruction allowance; outgoing requests use the actual prepared text. Neither is an exact model-tokenizer count, and images have an estimated token allowance.

At 80% estimated input usage, or after older messages have been left outside context, Wixal recommends a new chat. Full history remains saved. Automatic summaries condense older complete turns using the selected model, without tools. Failures use labelled excerpts. Tool output can be shortened for inference while its original result remains in history. The request budget check removes older complete turns and bounds tool evidence. Long tool loops convert older completed exchanges into labelled text excerpts while preserving the most recent native calls and results. If the newest input still exceeds the estimate, it returns an actionable error rather than relying on silent engine truncation. With 4k or a small-model window, disable unused tools and keep prompts short.

## Continue in a new chat

Choose **Continue in new chat** or the warning's **Start a new chat** action. **Start fresh** creates an empty chat in the same project. **Summarize & continue** uses the currently selected model, preserves goals, decisions, evidence, constraints, failed/declined actions and remaining work, then inserts a visible first message in a new chat. It does not automatically generate the next answer. The old chat stays saved. If model summarization fails, the new chat clearly labels fallback excerpts. Stop cancels handoff; a cancelled operation does not create a partial new chat.

A summary may omit details or contain errors. Review its first message and keep the original chat for exact evidence. Starting fresh still uses whatever saved memory scope the project allows.

## Switch models within a chat

Finish or stop a running response, open the model picker and select another local model. The chat ID, full original history, project scope and saved notes are retained. New assistant/tool records identify the generating model. Older foreign or unlabelled tool calls become textual descriptions and evidence; their reasoning and model-specific metadata are excluded. Current-model native tool exchanges stay intact. Text-only models see a label for older images instead of image bytes. Switching to a model without Tools changes the mode to Chat. New attachments still require an image-capable model.

This implements familiar project isolation and recall patterns, with visible controls and local budgets. It is not feature parity with proprietary ChatGPT, Claude, Grok or DeepSeek memory services. References: [ChatGPT project memory](https://help.openai.com/en/articles/10169521-projects-in-chatgpt), [Claude chat search and project memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context).
