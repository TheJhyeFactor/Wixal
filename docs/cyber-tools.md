# AI command and web review tools

Enable the tools in Workspace → Tool kit, select a tool-capable model, open a project folder and use Agent mode. Check the tool toggles before starting; the current workspace defaults enable the tool catalog. The project is the command working directory and location for reports; targets can be websites, servers or networks.

Enable `command_start`, `command_read`, `command_write`, `command_stop`, `command_save_output`, `browser_inspect`, and `write_file` together for a complete workflow. Existing `http_request` and `web_search` provide API responses and source discovery.

Example prompt:

> Inspect my authorised test website at http://localhost:8080. Review the rendered page and use installed command-line tools as needed. Read every command result before deciding what to do next. Save command evidence as output.json and maintain findings.md with observations, supporting evidence and unresolved questions.

The model chooses the command and arguments. Wixal asks you to review command starts, stdin, browser loads and file writes. Command results are returned as tool messages in the current conversation, saved in chat history, and supplied to the model for its next decision. This enables repeated command → output → review → next command steps, up to 32 agent steps per turn.

## Command sessions

- `command_start`: command plus optional `timeout_seconds` (1–3600, default 600). Returns `session_id` immediately.
- `command_read`: session ID, optional character `offset`, and `wait_ms` (0–10000, default 1000). Returns combined stdout/stderr, state, exit code, cancellation reason and pagination offsets. Follow `next_offset` while `more` is true. Continue polling while state is running.
- `command_write`: reviewed stdin text and optional `close_stdin`. Include a newline when the process expects a line.
- `command_stop`: kills the process group.
- `command_save_output`: reviewed project-relative file path, with an existing parent. Saves retained output and execution metadata as JSON. Output older than the retained 1 MiB character buffer is discarded; `earliest_offset` records this. For complete large scan results, have the scanner write a report directly and inspect that report with file tools or commands.

Sessions belong to the current project and conversation, remain available across turns while the app stays open, and are stopped when the app exits. Stop during a turn also cancels commands started in that turn. Sessions are piped shell processes, not PTYs: full-screen tools and commands requiring a TTY need the existing manual terminal. At most eight commands can run concurrently. Tools such as scanners must already be installed; this change does not bundle scanning engines.

## Browser inspection

`browser_inspect` loads one HTTP(S) page in an isolated Electron browser with JavaScript enabled. It returns rendered text, links, form field names/types, external script URLs and console messages at load completion. It does not collect input values, share provider cookies, submit forms, grant browser permissions, open popups or permit downloads. Top-level redirects require a separately reviewed URL. Page scripts can request HTTP(S) subresources as part of loading; this is not a vulnerability scan or an authenticated browsing session. There is no click, screenshot or delayed-page wait tool yet.

Tool output and page content are evidence, not instructions. The model is instructed to assess results honestly, respect declines, use only authorised targets and distinguish scanner findings from verified vulnerabilities. Host shell commands retain normal Mac access and are not sandboxed.
