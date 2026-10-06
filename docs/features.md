# Wixal 0.7.8: memory, context and project tools

Wixal can carry out project work through real tools, continue long conversations with saved summaries, and connect to local MCP servers. Open a project, select a tool-capable model and use **Chat** or **Agent**.

## What works

| Capability | Behaviour |
| --- | --- |
| Persistent project memory | Chats and notes survive restart; memory selection ranks relevant notes for the current prompt. |
| Project history search | Enable **Recall project conversations** to let the model search prior active chats in this project. Results include conversation titles and excerpts. Archived chats remain available through the archive browser. |
| File access | List, search, read, write and make exact unique replacements in project text files; create project directories. Large reads return a continuation offset; writes require review and detect changes during review. |
| Command execution | Reviewed shell commands stream output and report exit status. Stop terminates the command process group. A command has a 60-second timeout. |
| Web search | Enable **Search the web** to use DuckDuckGo. Review the query before it leaves your Mac; results include titles, links and available snippets. |
| Web pages and APIs | Enable **Web pages and APIs** for reviewed GET, HEAD, POST, PUT, PATCH or DELETE requests. HTML becomes readable text; JSON remains readable JSON. Review the exact URL, method and body before sending. |
| External tools | Connect a local MCP stdio server, then enable individual discovered tools in the tool kit. Each call displays its server, tool name and arguments for review. |
| Larger models | Choose any installed Ollama model, download a model by tag in the picker, or import and use its weights in the bundled local engine. The context preference supports 4k–32k, further limited by the local model and hardware estimate. |
| Long conversations | Automatically summarize older turns with the selected model while retaining recent complete turns and all original history on disk. |

## Browser sessions

`browser_open` starts an isolated Chromium session. `browser_read` waits for expected text, pages long content and returns fresh control refs. `browser_action` reviews a click, ordinary text input or option selection; navigation receives a destination review. `browser_close` releases resources. One-shot `browser_inspect` remains available. Browser and HTTP/search evidence is readable in the chat activity drawer. See [tool workflows and limits](tool-workflows.md) for supported actions and boundaries.

## Web and API tools

Open **Workspace → Tool kit**, enable the network tools you want, and ask the agent to use them. For example:

> Search for the official Ollama API documentation, read the relevant source, and explain how model downloads work.

> Fetch http://127.0.0.1:3000/health and tell me which services are available.

Network tools start enabled and follow the workspace approval policy. A reviewed request can contact public sites or local services. Requests have a 20-second timeout, a 1 MB response limit and a 24,000-character output limit. They do not follow redirects; the agent must make a separately reviewed request to the redirect destination. API bodies must be JSON, at most 16,000 characters. GET and HEAD do not accept a body. GET results include continuation offsets; each later chunk refetches the page and may observe changes.

Wixal does not attach provider credentials or arbitrary authentication headers to these tools. Use a trusted local API proxy or an MCP server's secure credential configuration for authenticated services. Web search depends on DuckDuckGo's HTML service; challenges and rate limits are reported as errors; empty results are explicitly labelled No results. No search evidence is fabricated.

## External MCP tools

1. Open **Workspace → Tool kit → Connect external tools…**.
2. Give the server a name and its executable path. Install the server's runtime and dependencies according to its own documentation.
3. Enter arguments as a JSON array, for example `["/Users/you/tools/server.cjs"]` for a Node server.
4. Click **Save server**, then **Connect**. This launches the executable with your Mac user's permissions and discovers its tool catalog.
5. Close the dialog and enable the specific tools you want in the tool kit. Ask the model to use them. Calls follow the workspace approval mode.

Servers start in the selected project directory (or your home directory without a project). Clicking Connect authorizes startup; startup can perform actions or network requests before any tool is called. Use trusted servers. The client inherits the SDK's limited default environment; it does not pass Wixal's stored API keys. Avoid secrets in arguments because server configuration is saved locally.

Wixal supports local stdio MCP servers in this release, up to 12 saved servers and 80 tools per server. Definitions are available only while connected. Servers stay disconnected after app restart until you click Connect again. Tool calls time out after 60 seconds and respect Stop. Text results enter the conversation; image/audio blocks are labelled as omitted, so configure artifact-producing tools to save outputs in the project. Disconnect stops the server process; Remove also deletes its saved configuration.

## Memory scopes and limits

Project-only is the default. Choose memory off, project-only, global preferences only, or project + global in the project picker or Memory drawer. Saved note budgets are 8,000, 24,000 or 48,000 characters. Notes can be edited and forgotten. A short 1,200-character global profile stays local for guests or syncs explicitly to a verified Wixal account. Project-only excludes global preferences.

The composer displays an estimated context meter and recommends a fresh chat or a model-generated summary handoff as the chat fills. The context ceiling is 32k, reduced for model limits and estimated RAM headroom. Local model switching retains chat history while converting older foreign tool exchanges into readable evidence. See [memory, context and model switching](memory.md) for the complete behavior, capacity table and limitations.

## Summaries and project recall

Automatic summaries are enabled by default. When older complete turns no longer fit the estimated context budget, Wixal condenses them using your selected model. Summaries run with no tools, update incrementally and are saved with the chat. Summaries run through the same Wixal local engine as the selected model.

Open **Project memory** to inspect a saved summary, turn automatic summarization off, or clear the summary. Clearing a summary keeps the original messages. It can be rebuilt on a later turn. If summarization fails, Wixal saves clearly labelled relevant excerpts and proceeds with the conversation. Stop cancels summary inference as well as the main response.

Explicit project notes and conversation summaries serve different purposes: notes apply to future project chats, while each summary belongs to one conversation. Enable **Save project memory** to let an agent propose a lasting preference or decision; you review the text before it is saved. Enable **Recall project conversations** to retrieve older information across active chats in this project. Retrieval uses word matching and overlapping text chunks, rather than an embedding service.

Context sizing remains an estimate rather than exact tokenization. Tool results are shortened in inference requests while their original text stays in the saved conversation. An outgoing request that still exceeds the estimated safe budget after trimming receives an actionable error. Token estimation cannot guarantee the exact model tokenizer count. Choose a larger supported context or split such a request.

## Download a local model

Open **⌘L**, choose **Wixal Local**, and enter a model tag under **Download a local model**. Click **Download** to contact Ollama's model registry. The picker shows download status and progress for the current layer. Cancel stops the client request; retrying the tag lets Ollama reuse downloaded layers. The download must finish successfully before Wixal reports completion.

Wixal Local includes the engine; installed Ollama weights can be imported. See [runtime setup and imports](local-runtime.md). A larger context window or parameter count can require substantially more RAM; downloading a large model does not guarantee it fits your Mac. Installed model cards show disk size, parameter size, reported context and tool/image support. All models run through Wixal’s included engine.

[User guide](user-guide.md) · [Architecture](architecture.md) · [Release history](../CHANGELOG.md)

In 0.7.0, built-in tools start enabled, the tool kit has search/categories and Enable all, and `@tool_name` requests a particular tool while preserving enabled follow-up tools. Enabled tools are available to tool-capable models in Chat and Agent; task-relevant schemas are loaded first, with workspace_info category discovery for other enabled tools; missing required arguments can be clarified in chat. See [performance, model management and tool selection](performance.md). Browser and longer command-session tools are described in [the cyber tools guide](cyber-tools.md).

## Workspace context and approval policy

Each model request includes the app version, selected project, model capabilities, current conversation, enabled eligible tools and live approval mode. `workspace_info` exposes the same information as a tool. Built-in tools require no MCP connection. Tool-capable models can act in Chat and Agent; text-only models remain conversational.

Select **Approved all** beside the composer to authorise enabled tools for this workspace without individual prompts. The setting persists by project, with a separate personal workspace setting. Switching to **Review each action** revokes it for later actions, including during a run. Disabled tools and file/session ownership checks remain enforced. All-mode approvals are recorded locally with tool, workspace, conversation and time.

**Tools → Network assessment** offers host discovery, TCP ports, service versions, web configuration, TLS, SSH, web-path enumeration and selected vulnerability checks. See [the cyber tools guide](cyber-tools.md).
