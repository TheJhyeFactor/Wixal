# Tool workflows and limits

Wixal runs enabled tools through the app controller, returns their actual evidence to the same conversation, and asks the local model to continue from it. Choose a model marked **Tools**. Chat can use tools on request; Agent works through a task with them. Built-in tools need no MCP connection.

## Working with a website

Try: “Open https://jhye.dev/, follow Work, and tell me which projects are on that page.”

1. `browser_open` reviews the destination and opens an isolated Chromium session. It returns a session ID, rendered text, links and control refs.
2. `browser_read` refreshes those refs and can wait for expected text or read another text chunk. Use `filter` to find controls by label.
3. `browser_action` reviews clicking a button/link, filling ordinary text or selecting a listed option. A link opens its destination through the navigation review. Every snapshot replaces old refs. Controls that change during review must be read again.
4. `browser_close` releases the session. If you explicitly ask to close the browser and the model omits its last close call, Wixal executes and records that cleanup before the final answer. Stop closes this conversation's browser sessions; quitting closes all of them. Sessions are ephemeral and do not survive restart.

`browser_inspect` is a convenient one-shot alternative. It waits for rendered content, returns paginated text metadata, and closes its browser automatically.

| Limit | Behaviour |
| --- | --- |
| Active browser sessions | Four across the app; close one before opening another. |
| Idle lifetime | Fifteen minutes. Sessions belong to one conversation and selected project. |
| Page operation | Thirty-second ceiling; explicit waits up to ten seconds, default 1.2 seconds. Expected text that does not appear is reported. |
| Rendered text | Default 12,000 characters per snapshot, maximum 24,000; use `next_offset` for the rest. |
| Controls | Up to 120 visible controls from the first 3,000 candidates; filter labels to narrow them. |
| Inputs | Up to 2,000 characters, ordinary text fields only. Passwords, credentials, payment and verification fields, file controls and submissions are unsupported. |

Browsers use separate temporary storage and do not share the user's existing login. Permissions, downloads and popups are denied. Non-web destinations and page network methods other than GET, HEAD and OPTIONS are blocked. Redirects and scripted main-page navigation need an explicit reviewed destination. A rendered page can still contain untrusted scripts and data. GET requests can have server-side effects on badly designed sites, and filling a text field can trigger page scripts. Review the site and control before approving. This is a browsing tool for reading and ordinary controls, not full authenticated computer use.

## Search and HTTP

`web_search` returns real source titles, URLs and available snippets, deduplicated by URL, with one to ten results (default eight). DuckDuckGo challenges, rate limits and unsupported responses report an error; a genuinely empty result is labelled **No results**. Wixal never substitutes invented sources.

`http_request` supports GET, HEAD and reviewed JSON writes. Redirect destinations require another reviewed request. A request has a 20-second timeout and retains at most 1 MB; its response explicitly reports truncation. Text chunks are at most 24,000 characters and include `next_offset`, total characters and `more`. GET pagination performs another request, so a changing page may differ. Write pagination is rejected to avoid accidentally repeating a mutation. Request bodies are JSON up to 16,000 characters; no stored provider credentials or arbitrary authentication headers are attached.

## Project files and tools

File tools stay inside the selected project and reject protected credential paths and escaping symlinks. `read_file` and `search_files` support text files up to 1 MB. Listing/search traversal skips dependencies, credential files and symlinks, and covers at most 1,200 files and six directory levels. Search reports files skipped for size and supports match offsets; narrow the project to improve coverage.

`edit_file` replaces one exact unique text match after a before/after review. Ambiguous or missing matches fail. Both edits and full writes reject a file changed during review. `make_directory` creates one reviewed project directory with an existing parent. Enabled shell commands run with the Mac user's access; they are not confined by these file-tool path checks.

Task-relevant tool schemas load first to leave more context for conversation and evidence. `workspace_info` can load files, commands, web, security, memory or external schemas. Large external catalogs initially load the first eight external schemas; use workspace_info with a specific enabled tool name for another. The tool kit remains the permission boundary: discovery never enables a disabled tool. New browser controls inherit a previously enabled browser tool once; new file tools inherit write access once. Later changes in the tool kit remain respected.

A declined action ends tool execution for that turn and requests a visible conclusion. Three identical failed calls also request a conclusion rather than repeatedly retrying the same failure. Running command/scan polling remains available. Tool results are saved in full on disk; model input uses bounded, parseable excerpts with whole URLs and refs where they fit. Missing evidence can be obtained through another chunk or control filter.

Local MCP tools validate basic advertised argument constraints before review. Servers can expose paginated catalogs up to 80 tools; duplicates and repeated cursors are rejected. Calls respect Stop and a 60-second timeout. Text evidence enters chat; image/audio results are labelled as omitted and should be saved by the server as project artifacts.

The live regression target is **jhye.dev**. Controlled local fixtures cover failures that cannot reliably be reproduced on a production site. Passing fixtures validates those tested behaviours; it does not guarantee every website, MCP server or local model behaves the same way.
