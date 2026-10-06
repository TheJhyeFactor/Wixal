# Using Wixal

## Start a conversation

Open a project with **⌘O**, choose a model with **⌘L**, and type a message. Wixal runs all models through its included local engine. The model picker combines ready models with installed Ollama models you can import and use.

Choose Chat or Agent from the mode menu in the composer. Agent mode can use the project tools you enable. Both modes receive enabled tools automatically on tool-capable models. Use the approval menu beside the composer to choose Review each action or Approved all for this workspace.

## Work with a project

Browse and search project files, preview their contents, and attach images to a conversation. Add notes in **Project memory** when you want Wixal to include them in later conversations for that project. Files, Tools, Memory and Terminal are directly available in the workspace header. Use the terminal for interactive commands.

Chats, text drafts and project notes are saved on this Mac. Draft text returns when you switch chats or reopen the app. Image attachments are temporary and clear when changing chats. All model inference stays local. Downloads contact the model registry after your click. Web tools and optional MCP connections contact the services you configure.

## Tools, recall and long chats

Each request has a quiet **Work history** timeline. It opens while tools are working and folds after the response finishes. Expand it and select a step to inspect its command, output and status in the activity dock above the composer. Repeated reads from the same command session share one step, with every original result still available under **Raw events**. **Approach & updates** contains the assistant's visible progress messages. The dock shows the current phase, including waiting for your review, and retains stopped or failed request status after restarting Wixal. Motion follows your Reduce motion setting and the Mac's motion preference.

Open **Tools** in the workspace header to enable web search, web pages and JSON APIs, conversation recall, reviewed memory saves, or tools from a connected MCP server. These actions show a review dialog in Review each action mode; Approved all runs enabled tools without individual dialogs. Built-in tools start enabled; external tools become available after explicitly connecting their server.

Project memory includes a switch for automatic long-conversation summaries and an inspector for the current chat's saved summary. Full messages remain saved. Use **Copy code** on a code block to copy just that code, and **Latest message** to return to the end of a long conversation. Streaming respects your position when reading earlier messages. Open **Models** in the sidebar to manage your library, or use **⌘L** for the selector. On **Downloads**, choose **Download** beside a catalog model or enter a tag in **Download by model tag**. Downloads run one at a time. You can pause, resume, cancel or retry each transfer. Closing Wixal leaves unfinished transfers paused until you resume them. After installation is verified, choose **Use model** to select it. Downloads stay in the engine library that started them; pause queued transfers before changing engines or providers.

Read the [feature guide](features.md) for setup, examples, MCP servers, context behaviour and service limits.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| ⌘O | Open a project |
| ⌘N | Start a conversation |
| ⌘K | Find a command |
| ⌘L | Choose a model |
| ⌘J | Show or hide the terminal |
| ⌘⇧F | Browse project files |
| ⌘⇧T | Open the tool kit |
| ⌘⇧M | Open project memory |
| Enter / Shift+Enter | Send / add a new line |

[Download Wixal](https://github.com/TheJhyeFactor/Wixal/releases/latest) · [Back to the project](../README.md)

Wixal Local starts automatically for local model requests. Expand **Local engine** in the setup panel to stop/start it, open its model folder, or import installed models. See [the local runtime guide](local-runtime.md).

Click the token/speed status below the composer for Usage & performance. The model manager supports real benchmarks, capability/size/fit filters, discovery and deletion. Type `@` in chat to select a tool explicitly. Built-in tools begin enabled and can be managed with search and categories in the redesigned tool kit. See [the performance and tool-selection guide](performance.md).

The Models setup panel shows a suggested context for the selected model, free space on the model drive and reported loaded-model memory. **Use suggested context** applies an explicit change. **Free model memory** unloads models from the active engine without deleting their installed files. Benchmark results are measurements of speed; memory fit remains an estimate.

Open **Tools → Network assessment** to select an authorised IP, hostname, website URL or local subnet, choose a scan profile and start the assessment. Results return to chat through the selected local model. [Profiles and examples](cyber-tools.md).

### Launch animation and sound

Wixal opens with a short animated lettermark and an original shimmering bell chord. The intro finishes automatically; Escape also dismisses it. Settings → Launch has separate animation and sound switches; both save on this Mac. Reduce Motion (in Wixal or macOS) skips the animation. The sound can stay enabled independently and follows your Mac’s output volume.

### App icon choices

Settings → App icon offers Sakura, Midnight, Pearl, and Copper. Select an icon to use it independently of the appearance theme, or enable Match icon to theme. Matching uses Sakura for Sakura, Midnight for Midnight, Pearl for Paper, and Copper for Forest. This choice saves locally and applies again when Wixal starts. It changes the compact sidebar icon and the running Mac Dock icon; Finder keeps the bundled application icon.

## Memory, context and continuing a chat

Choose project memory scope and size when opening a new folder. In Memory, edit or forget project notes, check saved capacity, and optionally save a short global preference profile. The context meter estimates input usage and reserves room for the reply. At 80%, consider **Continue in new chat**: start fresh or carry an AI summary as the first message. The original chat remains saved. Finish or stop a response before selecting another local model in the same chat. See the [memory guide](memory.md) for limits and tradeoffs.
