# Agent workflow audit — 11 October 2026

Issue #6 remains open. Repeated failures across model families justified auditing the application and qualification harness before choosing another model. The audit found application defects and independent model-answer defects; changing the model alone does not resolve both.

## Source comparison

Reviewed pinned source, not just feature descriptions:

- Hermes Agent `c152ba5a82d7d39554489e8e8df47c3542a43c14`: [terminal lifecycle](https://github.com/NousResearch/hermes-agent/blob/c152ba5a82d7d39554489e8e8df47c3542a43c14/tools/terminal_tool.py), [tool executor](https://github.com/NousResearch/hermes-agent/blob/c152ba5a82d7d39554489e8e8df47c3542a43c14/agent/tool_executor.py), and [schema registry](https://github.com/NousResearch/hermes-agent/blob/c152ba5a82d7d39554489e8e8df47c3542a43c14/tools/registry.py). Foreground execution returns settled output; background execution is explicit. Tool responses are paired with their calls and persisted. Invalid arguments become actual tool errors rather than silently repaired inputs.
- OpenClaw `e7e3b949ae134060cc8c2a7cd8d224ad27edcd91`: [execution lifecycle](https://github.com/openclaw/openclaw/blob/e7e3b949ae134060cc8c2a7cd8d224ad27edcd91/src/agents/bash-tools.exec-run.ts), [request validation](https://github.com/openclaw/openclaw/blob/e7e3b949ae134060cc8c2a7cd8d224ad27edcd91/src/agents/bash-tools.exec-request-preparation.ts), and [background-process contract](https://github.com/openclaw/openclaw/blob/e7e3b949ae134060cc8c2a7cd8d224ad27edcd91/docs/gateway/background-process.md). `awaitResults=true` prevents detachment of a required result. Its ordinary execution can still yield to background; this audit adopts the explicit awaited-result mechanism for Wixal discovery.

These mechanisms were adapted within Wixal's existing tool registry, JSON-line service, approvals, owned jobs and evidence system. No framework migration or copied provider implementation was needed.

## Defects reproduced and corrected

1. **Incorrect tool selection.** MOD-10 asks to fetch an HTTP page and prohibits executing page instructions. The previous fixed category priority treated the prohibited word “execute” as a command request, omitted `http_request`, and supplied command schemas. Ministral attempted `http_request`; the inference server rejected it as absent. This old result is an application failure and is not valid evidence that the model followed an injection. Selection now uses the first positive task category; missing eligible schemas remain discoverable through `workspace_info`. Actual prepared-request regression checks cover HTTP requests with prohibited command instructions and ordinary website reading.
2. **Unnecessary asynchronous choreography.** Even a two-port discovery returned a running handle, forcing a model to poll before continuing. `network_discover` now awaits its owned process and evidence finalization by default. `await_results=false` explicitly retains background discovery and its read/stop lifecycle. The completed receipt is consumed directly by outcome, factual-claim and evidence checks; no synthetic model read is inserted.
3. **Polling delayed already available evidence.** Job reads previously slept for the entire requested interval even if execution settled earlier. Reads now wait on the shielded collector until settlement or their bounded deadline. A real short command requested with a ten-second poll must return within three seconds.
4. **Cancellation during resource binding.** A real-process cancellation test found a launched discovery could be interrupted while its socket reservation was being bound. This path now stops the owned process, awaits its collector and retains partial evidence before releasing resources. Foreground cancellation and explicit background Stop are checked using the actual managed scanner.

## Test realism and result attribution

Owned loopback listeners, an adversarial HTTP page, approval records, filesystem sentinel checks and real scanner processes are realistic controlled acceptance inputs. They test bounded behavior, not internet coverage or production repository trust. A fixture or an automatic grade cannot establish installed desktop or model qualification.

The earlier Ministral diagnostic had 13/14 automatic passes, including the alternate-model retained-history case. Reviewing every intermediate and final answer yielded 7/14 independent passes, six answer failures and the HTTP application failure. Failures included invented examined-port counts, claiming probes were checked before a terminal result, a nonexistent `full` inspection profile, and proposing a forbidden workaround. The original report is retained unchanged; attribution and independent review are separate files.

An observed open endpoint is evidence of that observation. Requested coverage is not a per-port completion ledger. Therefore `examinedPortCount=null` remains unknown even after successful scanner exit. A cancelled scan establishes cancellation and partial evidence, not an exact count of probes attempted. That qualification requirement remains intact.

The fresh candidate uses the same model prompts and port oracle. The partial/lifecycle setup now explicitly selects background discovery because those cases must manually Stop a running job. This is a declared tool-contract setup change, not a relaxed assertion. A frozen source manifest and helper hash identify the package before fresh inference. One attempt per diagnostic case is allowed; a failed mandatory independent gate prevents entry into the thirty-run qualification suite.

## Validation and remaining boundary

Evidence is retained under `artifacts/native/workflow-audit-20261011/`. The prior package results remain under `artifacts/native/ministral8-qualification-20261011/`. The full Python regression suite passed 414 tests, including actual scanner foreground/background cancellation and command settlement. The frozen development package matched all 130 source entries. The fresh retained-cancellation model check passed automatic and independent review; the prerequisite diagnostic is recorded separately when settled. Model success prose alone will not close #6. The canonical installed public application remains separate from the temporary development qualification package.

After qualification, retire the temporary app into Trash and stop only the owned local repository server. Keep one canonical `/Applications/Wixal.app`; preserve reports and manifests rather than accumulating active application versions. Never remove user workspaces, model downloads or unrelated apps as part of this cleanup.
