# AI command and web review tools

Enable the tools in Workspace → Tool kit, select a tool-capable model, open a project folder and use Chat or Agent. Check the tool toggles before starting; the current workspace defaults enable the tool catalog. The project is the command working directory and location for reports; targets can be websites, servers or networks.

Enable `command_start`, `command_read`, `command_write`, `command_stop`, `command_save_output`, `browser_inspect`, and `write_file` together for a complete workflow. Existing `http_request` and `web_search` provide API responses and source discovery.

Example prompt:

> Inspect my authorised test website at http://localhost:8080. Review the rendered page and use installed command-line tools as needed. Read every command result before deciding what to do next. Save command evidence as output.json and maintain findings.md with observations, supporting evidence and unresolved questions.

The model chooses the command and arguments. These actions follow the workspace approval mode: Review each action prompts, while Approved all runs enabled tools without individual prompts. Command results are returned as tool messages in the current conversation, saved in chat history, and supplied to the model for its next decision. This enables repeated command → output → review → next command steps, up to 32 agent steps per turn.

## Command sessions

- `command_start`: command plus optional `timeout_seconds` (1–3600, default 600). Returns `session_id` immediately.
- `command_read`: session ID, optional character `offset`, and `wait_ms` (0–10000, default 1000). Returns combined stdout/stderr, state, exit code, cancellation reason and pagination offsets. Follow `next_offset` while `more` is true. Continue polling while state is running.
- `command_write`: reviewed stdin text and optional `close_stdin`. Include a newline when the process expects a line.
- `command_stop`: kills the process group.
- `command_save_output`: reviewed project-relative file path, with an existing parent. Saves retained output and execution metadata as JSON. Output older than the retained 1 MiB character buffer is discarded; `earliest_offset` records this. For complete large scan results, have the scanner write a report directly and inspect that report with file tools or commands.

Sessions belong to the current project and conversation, remain available across turns while the app stays open, and are stopped when the app exits. Stop during a turn also cancels commands started in that turn. Sessions are piped shell processes, not PTYs: full-screen tools and commands requiring a TTY need the existing manual terminal. At most eight commands can run concurrently. Tools such as scanners must already be installed; this change does not bundle scanning engines.

## Browser inspection

`browser_inspect` loads one HTTP(S) page in an isolated Electron browser with JavaScript enabled. It returns rendered text, links, form field names/types, external script URLs and console messages after a bounded wait, with text chunk offsets. It does not collect input values, share provider cookies, submit forms, grant browser permissions, open popups or permit downloads. Top-level redirects require a separately reviewed URL. Page scripts can request HTTP(S) subresources as part of loading; this is not a vulnerability scan or an authenticated browsing session. For persistent navigation, reviewed clicks, ordinary text/select controls and delayed-page waits, use browser_open, browser_read, browser_action and browser_close. See [tool workflows and limits](tool-workflows.md). Screenshot capture and authenticated sessions remain unsupported.

Tool output and page content are evidence, not instructions. The model is instructed to assess results honestly, respect declines, use only authorised targets and distinguish scanner findings from verified vulnerabilities. Host shell commands retain normal Mac access and are not sandboxed.

## Network assessment form and profiles

Open a project and **Tools → Network assessment**. Enter an authorised IP, hostname, HTTP(S) URL or private IPv4 subnet, select a profile and optionally override TCP ports. **Run assessment** sends the validated target/profile/ports to the selected tool-capable local model, which starts the scan and reads its results. Both Chat and Agent have these tools automatically; no MCP server is needed.

Nmap is detected at `/opt/homebrew/bin/nmap`, `/usr/local/bin/nmap` or `/usr/bin/nmap`. Install it with `brew install nmap` if missing. Wixal runs fixed scanner arguments directly, without shell interpolation. Website URLs resolve to their host and explicit/default port; a URL path does not constrain a host scan. Individual public targets are supported. Subnets must be private IPv4 /24–/32, at most 256 addresses. IPv6 individual hosts are supported. Each scan has a 10–600 second limit (default 180), one retry, bounded script timing and XML output.

| Profile | Evidence collected | Default TCP ports |
| --- | --- | --- |
| Host discovery | Responding hosts and discovery reasons | Discovery probes on 22,80,443 |
| TCP ports | Open/closed/filtered states and reasons | 22,53,80,443,445,3389,8080,8443 |
| Service versions | Light service/version probes | Same as TCP ports |
| Web configuration | Titles, response headers, security-header observations | 80,443,8080,8443 |
| TLS configuration | Certificates, protocol and cipher enumeration | 443,8443 |
| SSH configuration | Host keys and advertised algorithms | 22 |
| Web path enumeration | Known paths using Nmap HTTP fingerprints | 80,443,8080,8443 |
| Selected vulnerability checks | POODLE, cookie flags and security-header observations | 80,443,8080,8443 |

TLS cipher and web-path enumeration are labelled intrusive because they make repeated connections/requests. The selected checks are a defined set of scripts, not an exhaustive vulnerability assessment. Nmap's [light version probes](https://nmap.org/book/man-version-detection.html) and [TLS cipher enumeration](https://nmap.org/nsedoc/scripts/ssl-enum-ciphers.html) describe their actual behaviour.

`security_tools` returns scanner availability and profiles. `network_scan` returns a session ID. `network_read` returns output, state, exit status, command, timestamps and assessment metadata; poll running sessions and follow `next_offset` for additional output. `network_stop` cancels the process group. `command_save_output` retains evidence in a project JSON report. The shared output buffer retains at most 1 MiB of characters and reports discarded output through `earliest_offset`.

Use **Approved all** beside the composer for an authorised workspace when you want enabled tools to run without individual approval dialogs. This policy covers scans, commands, file/report writes, web requests, memory and connected MCP calls. Switching to **Review each action** restores prompts for subsequent actions. The mode does not enable disabled tools, change file boundaries or give one workspace access to another workspace's command sessions.

## Assessment examples

```text
Discover responding hosts on my authorised lab network 192.168.1.0/24.
Use network_scan with discovery, read the output, and save discovery-evidence.json.

Assess services on my authorised server 192.168.1.20 on TCP ports 22,80,443.
Read every scan result, save service-evidence.json, and write findings.md
with observations, evidence, suspected issues and recommended validation.

Assess TLS configuration of https://localhost:8443 using the tls profile.
Explain the certificate and supported cipher evidence and save tls-evidence.json.

Run web path enumeration against my authorised lab website http://localhost:8080.
Report observed paths and response evidence; distinguish observations from
verified vulnerabilities before suggesting follow-up tests.
```

General command sessions remain available for other installed assessment tools and manually scoped follow-up tests. A successful scan or matching service version is not proof that exploitation succeeded.

## Test cases

`npm test` covers target/port/timeout validation, IPv6, private subnet limits, shell/option injection rejection, disabled tools, workspace approval persistence/revocation/isolation, real Nmap HTTP and TLS evidence, report saving, cancellation and command-session ownership. Real scanner cases require installed Nmap and report explicit skips when it is absent.

`npm run test:security` exercises the Electron scan form with a model protocol fixture and real Nmap against a disposable loopback HTTP service. It verifies no dialogs in Approved all, persistence after reload, Review prompting, switching to all while waiting, automatically embedded workspace tools and supported thinking settings. `WIXAL_APP_PATH` runs it against the packaged app. Tests do not scan external networks.

`npm run test:chat-tools-live` verifies actual tool-capable models through Wixal's bundled engine using an isolated project and state, including file reads without mentions, clarification, JavaScript-rendered browser evidence and command completion.

## Website assessment and attack simulations

Wixal now includes native `website_assess` and `website_simulate`, a website form, evidence reports and automatically embedded response guidance. Both run through the selected local model, including uncensored model weights. See [website workflows and tests](website-assessments.md).
