Wixal 0.6.0 adds real web and API tools, external MCP connections, saved conversation summaries and local model downloads to the Mac workspace.

## What’s new

![Wixal 0.6.0 feature overview](https://raw.githubusercontent.com/TheJhyeFactor/Wixal/v0.6.0/assets/features-0.6.svg)

- **Continue long conversations.** Older turns are summarized using your selected model and saved with the chat. Inspect or clear the summary in Project memory; the original messages remain saved. Failed summary requests fall back to labelled excerpts.
- **Recall project decisions.** Search earlier active chats, select relevant project notes, and review an agent's proposed memory before saving it.
- **Read complete project files.** Large text reads include a continuation offset. File edits and shell commands retain their review flow, streamed results and cancellation.
- **Search and read the web.** Enable DuckDuckGo search or reviewed HTTP requests. Review the exact query or URL, HTTP method and JSON body before sending. Source links and actual responses return to the agent.
- **Connect external tools.** Save a local MCP server's executable and arguments, click Connect, and enable individual discovered tools. Each invocation displays its server, tool and arguments for review.
- **Download local models in Wixal.** The Ollama picker accepts model tags and shows layer progress, cancellation and completion. Context preferences now include 64k and 128k when the model supports them.

Open **Workspace → Tool kit** for new tools, **Project memory** for summaries, and **⌘L** for models. Web and external tools start disabled. MCP servers reconnect only when you click Connect after restarting the app.

[Feature guide and examples](https://github.com/TheJhyeFactor/Wixal/blob/v0.6.0/docs/features.md) · [User guide](https://github.com/TheJhyeFactor/Wixal/blob/v0.6.0/docs/user-guide.md) · [Full changelog](https://github.com/TheJhyeFactor/Wixal/blob/v0.6.0/CHANGELOG.md)

## Install

Requires an Apple Silicon Mac running macOS 13 or newer. Open the DMG and drag **Wixal.app** into **Applications**, or extract the ZIP and move the app there. Existing local projects, chats, memories and provider preferences are preserved.

For local inference, install and start Ollama, then download or select a model in Wixal. Cloud providers are optional; [provider setup](https://github.com/TheJhyeFactor/Wixal/blob/v0.6.0/docs/connections.md) explains credentials and workspace consent. External MCP servers require their own installed runtimes and secure credential setup.

This preview is ad hoc signed, without Developer ID signing or notarisation. If macOS prevents it from opening, follow [Apple's instructions for apps that aren't notarised](https://support.apple.com/en-au/102445) if you trust the source.

SHA-256 hashes for the downloads are in **SHA256SUMS.txt**. **release-info.json** records the source commit, build platform, macOS minimum and signing status.

## Verification

The automated suite covers persistence, project isolation, review enforcement, file traversal protections, provider protocols, summaries, network requests, model pull streams and a real MCP server process. Electron checks exercise approved and declined HTTP requests against a real local service, reviewed memory saves, external tools, summary inspection, download progress/cancel, restart persistence and compact layout. A real local vision model also created a file through the review UI, recalled project memory and described an attached image. Cloud inference and downloads use protocol fixtures in the UI suite; live cloud account eligibility and downloading a new large model were not tested.

## Practical limits

- Network tools return bounded text/JSON and do not attach stored credentials or follow redirects. Authenticated services can use a trusted local proxy or an MCP server's credential configuration.
- MCP connections support local stdio servers. Non-text result blocks are labelled as omitted; artifact tools should save files into the project. Server startup runs with your user permissions and can perform actions before tool review.
- Context sizing uses estimates. Summaries can omit details; full history remains saved, with project history search available for recall.
- Large models and contexts need enough RAM and disk space. Web search can be rate limited by its upstream service.
