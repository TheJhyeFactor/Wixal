# RustScan integration plan for Wixal Native

Implementation update (9 October 2026): [native preview implementation and measured acceptance status](MANAGED_TOOLS_IMPLEMENTATION_STATUS.md). The original planning status below describes the earlier document-only request.

Date: 8 October 2026

Status: proposed design only. This document authorises no implementation, installation, update, packaging or deployment. The only deliverable for this request is this plan.

Distribution and qualification are governed by the later [managed tools technical plan](MANAGED_TOOLS_TECHNICAL_PLAN.md) and its [acceptance matrix](MANAGED_TOOLS_ACCEPTANCE_MATRIX.md). This document remains the RustScan capability design; Homebrew is an external-provider option rather than the sole planned distribution path.

## Product decision

Add RustScan as a first-class TCP port discovery capability. Keep Nmap for host discovery, service identification and the existing web, TLS, SSH and selected-check profiles. Use Wixal's existing Tools library, investigation records, execution queue and project approval policy.

The useful addition is broader port coverage followed by focused inspection, with clear evidence and controllable workload. Do not promise a fixed scan speed or treat a successful process exit as complete network coverage.

Recommended initial experience:

1. Open an investigation and choose **Discover TCP ports** under Recon.
2. Select **Selected ports** or **All TCP ports**, with a visible target and workload estimate. Selected ports is the default. A website URL initially selects its explicit/default port; a broader host scan is an explicit choice.
3. Optionally select **Inspect discovered ports** and a Nmap profile. Services is the default follow-up; web, TLS, SSH and other existing profiles remain explicit choices.
4. Review the resulting one- or two-step plan using the project's existing review setting.
5. Watch discovery and inspection as separate linked runs; inspect raw evidence and structured results from either step.

Standalone discovery works when only RustScan is installed. The linked inspection option requires Nmap and both tools enabled. A missing dependency is displayed before queuing.

## Current integration points

| Area | Current implementation | Planned responsibility |
|---|---|---|
| Shared Tools library | `engine/wixal/addons.py`, `Sources/AddonLibraryView.swift` | Curated RustScan package, executable/version verification, readiness and existing install/update/repair actions |
| Tool execution | `engine/wixal/tools.py`, `engine/wixal/resources/tools.json` | Typed discovery tool and common target validation; existing command ownership/read/stop machinery |
| Agent authority | `engine/wixal/agent_authority.py`, agent tool/context policies | Target and project checks for discovery and evidence-derived inspection |
| Investigations | `engine/wixal/security_workspace.py` | Prepare and execute discovery runs, retain output, dependency lifecycle and time budgets |
| Evidence and plans | `engine/wixal/security_records.py` | Structured ports, provenance, per-run handoff, discovery history and planner contracts |
| Chat evidence | `engine/wixal/security_evidence.py` | Structured RustScan evidence using the same parser as investigations |
| Native UI | `Sources/SecurityWorkspaceView.swift`, tool drawer/catalog consumers | Discovery form, linked inspection, readiness, progress and evidence views |

Current source already has a shared add-on library and investigation plans. The Nmap runner assumes XML; the investigation ingest path currently overwrites a service's latest values with a new observation. Both assumptions must be addressed explicitly. Current approval metadata also identifies Nmap by executable basename and final argv position; that shortcut must not become the authority mechanism for the new tool.

## Proposed architecture and tool contract

Create a focused `engine/wixal/network_discovery.py` module for planning, strict parsing and normalization. Share it between chat execution and investigation execution. Keep process lifetime in the existing Tools job infrastructure rather than inventing a second scanner job system.

Introduce `network_discover`, a distinct built-in capability and tool. Reuse `network_read` and `network_stop` for its command session. Add readiness for RustScan and Nmap separately to `security_tools`, preserving existing response fields for current consumers.

Proposed inputs:

- `target`: the investigation's pinned target or explicitly authorised chat target.
- `coverage`: `selected` or `all_tcp`.
- `ports`: validated TCP numbers/ranges for selected coverage; disallow contradictory coverage/ports arguments.
- `pace`: `careful` or `balanced`; translated into bounded settings rather than arbitrary CLI text.
- `timeout_seconds`: the overall run deadline, initially within the existing 10–600 second tool envelope.

Return the existing asynchronous `session_id` pattern, plus tool/version, requested coverage, resolved target count, planned connection attempts and read/stop instructions. No free-form RustScan arguments, user scripts or trailing commands.

For investigation handoff, extend `network_scan` with an optional `source_run_id`. Discovery remains a separate run. A source-bound scan derives its exact hosts and ports from the immutable source result at execution time, before review. It must reject a manually supplied conflicting target/port list and require the source run as an explicit dependency.

For chat, use an equivalent session-owned discovery reference that is bound to the originating project and retained result. Do not accept raw model-authored text as a discovery reference. Introduce the chat handoff only after the investigation path is proven.

## Deterministic command execution

Run RustScan directly with an argv list, using standalone mode:

```text
rustscan --config-path <Wixal-owned-empty-config> --no-config
  --scripts none --greppable --no-banner
  --addresses <validated-literal-address>
  --ports <validated-list>  OR  --range 1-65535
  --batch-size <bounded-value> --timeout <bounded-ms> --tries <bounded-value>
```

This is a command shape, not a runnable command or final tuned preset.

Use a private temporary directory and an empty config file for each run. Explicit config isolation matters: upstream reads the configuration before applying the no-config merge decision, so `--no-config` alone is not enough to prevent a malformed personal config from affecting startup. Delete temporary files after the process is stopped and evidence retained.

Do not invoke RustScan's scripting engine for the Nmap handoff. Wixal launches Nmap independently with its existing fixed profiles, XML output and deadline. Do not increase system limits or introduce elevated privileges. Treat file-descriptor headroom as a preflight limit and lower concurrency when necessary.

Resolve hostnames once per approved plan and record the resulting address set. Show the resolution and address count before execution; use literal addresses for both stages. If queued resolution becomes stale, re-plan and apply the existing review policy to the changed address set. Reject DNS answers that violate an explicit IP/CIDR boundary. Hostname authority must not silently grant a full-port host scan when the supplied authority only permits a website origin/port.

## Workload and scope controls

First delivery supports individual IPv4/IPv6 addresses and hostnames. Limit a hostname's resolved set, provisionally to four addresses, and expose that expansion in review. Keep current Nmap private-subnet host discovery available.

Provisional presets, to be tuned by measurements:

| Preset | Concurrent sockets | Per-attempt timeout | Attempts |
|---|---:|---:|---:|
| Careful | 32 | 2,000 ms | 2 |
| Balanced | 128 | 1,500 ms | 2 |

Concurrency limits are not requests-per-second limits. The UI must not claim these values establish a particular traffic rate. Account for concurrent investigations with a scanner-wide socket budget, provisionally 256 slots. Reserve/release budget across runs so four queue slots cannot each independently consume the entire budget. The queue slot limit remains a separate control.

Show unique ports × addresses and the retry allowance. Reject impossible or excessive requests before spawn; provisionally cap one discovery plan at 262,140 address/port pairs. All TCP ports is explicit and never the default for a subnet.

Later private IPv4 /24–/32 support reuses existing scope validation but adds total-work caps and per-host results. Permit selected ports across a bounded subnet; split larger full-port work into explicitly reviewed host batches. Never scan public CIDRs or expand to out-of-scope hosts through discovered evidence.

Extend target authority checks, disabled-tool policy, isolated-branch restrictions and project requirements for the new capability. Pass typed assessment metadata through the execution/review path. Revalidate source ownership, scope, enabled tools and executable readiness just before execution, including when project review is bypassed.

## Evidence model and parser

Normalize a discovery result into a versioned record containing:

- Scanner name, verified version and executable identity.
- Original target, pinned addresses, requested port coverage and scan parameters.
- Start/end times, process state, exit code and termination reason.
- Per-host observed open TCP ports; no guessed product or version.
- Raw evidence location/hash, capture truncation state and parser warnings.
- Coverage state: finished requested attempts, partial execution or indeterminate output.

Use strict address and port parsing, normalize order and duplicates, and reject results outside the pinned address/port set. Read from complete retained output, not the UI's 100,000-character excerpt. Keep stdout and stderr distinguishable where practical. Unknown lines remain inspectable diagnostics; an unexpected result format prevents automatic inspection.

A clean empty result means **No open ports detected in the requested coverage**. It does not establish host absence, confirmed closed ports, absence of filtering or service safety. Successful execution means the configured attempts finished, not that all reachable services were found.

Timed-out, cancelled or malformed runs retain raw output and any valid observations with explicit partial status. Partial evidence is reviewable but is not automatically eligible for handoff. Provide an explicit new plan to inspect selected partial observations if desired. Do not infer percent complete from elapsed time or open-port count; RustScan's greppable output can arrive only after discovery finishes.

The shared parser feeds both chat evidence and investigation results. Avoid two incompatible adapters producing different interpretations of the same output.

## Preserve service history

RustScan observations establish an open port, not a named service. Store port observations with source and time, keeping Nmap's service-identification observations separately attributable.

For the current host/service inventory, project the latest port observation alongside the latest identified service and its own timestamp/source. A later empty service object must not erase earlier identification. If a later Nmap run reports a closed port, show the historical service identity as historical rather than implying it is still present. Conflicting observations remain visible.

Derive scan changes only across comparable completed runs with matching target/coverage. Missing ports in a partial scan must not be marked removed. An open port remains an informational observation, not automatically a vulnerability finding.

## Nmap handoff and lifecycle

The **Discover and inspect** UI creates an explicit two-node investigation plan. Use the existing dependency mechanism, with a new typed discovery-result binding. Current scalar discovery bindings are insufficient for a host-to-port mapping.

The inspection step must:

1. Require a completed, valid discovery source from the same project and target.
2. Freeze the source run ID and result hash into its provenance.
3. Select ports separately for every host. Never apply the union of all discovered ports to every host.
4. Intersect with a selected protocol profile where appropriate: SSH uses observed port 22; TLS/web use the explicitly selected relevant ports. Preserve custom nonstandard-port selections.
5. Split large lists into bounded Nmap invocations, provisionally 256 ports per host per invocation, under a shared inspection deadline. Aggregate parsed results without concatenating XML documents.
6. Show exact derived targets/ports and profile before executing under the existing approval setting.

When discovery finds nothing, skip inspection with an explanatory reason. Cancellation, parser failure or interrupted discovery cannot trigger follow-up scanning. Nmap failure leaves discovery available and inspection failed or partial; it does not relabel the entire workflow as fully completed.

Stop terminates active scanner process groups, cancels outstanding work and prevents queued dependent steps from starting. Stopping a two-stage workflow stops both stages; stopping only the inspection stage keeps discovery. Restart retains current interrupted semantics and never silently replays either stage.

If RustScan is unavailable, retain direct Nmap assessment and show it as a selectable alternative. Do not silently replace a failed RustScan run with a different scan or expand coverage. Retrying or falling back creates a traceable new plan under the same approval policy.

## Native interface and AI behaviour

- Tools → Network shows RustScan with verified readiness, version, source and existing package-management actions. Reuse the shared library rather than creating investigation-specific installation settings.
- Recon offers **Discover TCP ports** and the optional inspection toggle. Display target, selected coverage, estimated workload, pace and deadline in ordinary product language.
- Run rows expose the current stage, elapsed time and discovered-port count when available. Show separate discovery and inspection outcomes and warnings about incomplete evidence.
- Results allow opening the exact source run and raw evidence, filtering by host and selecting observed ports for a new assessment.
- Advanced details expose effective arguments, version and provenance without putting them in the primary user flow.

The AI sees a typed capability and compact structured observations. It chooses direct Nmap for small focused checks, and proposes RustScan when broader port coverage advances the investigation objective. It cannot invent service versions, assume a port number identifies a product, select full-port scanning implicitly, enable disabled tools, or expand authorised targets. Planner schemas and reusable workflow packs must include the new capability and explicit handoff contract.

## Delivery sequence

1. **Adapter foundation:** curated package readiness, shared target/port validation, typed standalone discovery, config isolation, authority metadata and strict parser. Gate on real loopback IPv4/IPv6 and policy tests.
2. **Investigation and evidence:** native Recon form, persistent structured output, observation-history handling and source-scoped evidence. Gate on cancellation, restart and project isolation.
3. **Linked inspection:** two-stage plan, immutable result binding, per-host port selection, bounded Nmap batching, approval and empty/partial-result handling. Gate on exact derived invocation checks and real service identification.
4. **AI and broader workflows:** chat handoff, planner/schema updates, workflow instructions, measured preset tuning and bounded private-subnet support. Gate on model use of actual evidence and refusal of scope expansion.
5. **Installed acceptance:** package/install only when implementation is authorised; verify the actual Finder/Dock app, bundled helper identity, UI flows and retained evidence. Keep the current 0.7.x version policy and classify maturity from fresh evidence.

Each gate produces an inspectable acceptance report. Do not enable incomplete paths merely because a binary is installed.

## Verification and acceptance criteria

Meaningful regression cases cover target/option injection, port bounds, contradictory coverage, config isolation, malformed and out-of-scope output, unsupported CLI versions, DNS expansion, disabled tools, source-run ownership, immutable handoff, history preservation, deadline exhaustion and process cleanup.

Real acceptance uses disposable local listeners and actual installed RustScan/Nmap, with known services on both standard and unusual ports where feasible. Test IPv4 and IPv6, multiple listeners, no observed open ports, stopping discovery, stopping inspection, restart and persisted results. A missing executable is an explicit skipped/unavailable case, not a passed integration case.

For multi-host handoff, establish hosts with different open ports and assert the exact host/port map submitted to Nmap. Use actual local interfaces or an authorised lab where available; clearly label a fixture-only mapping test and do not substitute it for real network acceptance. Verify that ordinary Nmap profiles still work independently.

Benchmark equivalent port discovery against Nmap TCP connect discovery: same hosts, port sets, retries and documented timeout settings. Measure precision against known listeners, missed ports, runtime, resource use and cancellation latency across repeated runs. Evaluate service inspection separately; do not compare standalone RustScan time with Nmap service/script time as a speed claim. Presets become final only after those measurements.

Packaged acceptance verifies Tools readiness, standalone discovery with Nmap unavailable, a complete linked assessment, review/bypass modes, disabled tools, saved/reopened evidence, partial status and the absence of surviving scanner processes after Stop. Keep installed-app proof separate from source tests and public release readiness.

Done means the installed native app can perform bounded discovery, explain its coverage, preserve evidence, inspect only the selected discovered ports under the same authority, and stop/restart predictably. No fixed performance target is asserted before benchmarking.

## Sources and evidence limits

- [RustScan repository](https://github.com/bee-san/RustScan): purpose and Nmap handoff.
- [Released CLI options](https://github.com/bee-san/RustScan/blob/2.4.1/src/input.rs): standalone/config/concurrency/timeout controls.
- [Released main loop](https://github.com/bee-san/RustScan/blob/2.4.1/src/main.rs): config loading and final per-host greppable output.
- [Released scripting engine](https://github.com/bee-san/RustScan/blob/2.4.1/src/scripts/mod.rs): default Nmap command and shell execution.
- [Homebrew formula](https://formulae.brew.sh/formula/rustscan): macOS package source to verify again at implementation time.
- Local review: installed RustScan 2.3.0 and Nmap 7.991; both detected the disposable HTTP listener. Nmap additionally identified the service and title. This is functional evidence only, not a comparative discovery benchmark or installed Wixal integration result.

The proposed module names, API additions, limits and presets are design decisions to implement and validate. No RustScan integration code has been added by this planning request.
