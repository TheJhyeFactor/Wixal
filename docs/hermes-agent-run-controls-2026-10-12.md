# Hermes-inspired run controls, 12 October 2026

Wixal now gives agents explicit per-attempt limits, an opportunity to conclude before a turn or call cap, and a durable reason when repeated evidence causes a pause. These changes build on the existing checklist, full evidence retrieval, skill snapshots and isolated delegation.

## Upstream review and native design

Reviewed Hermes at [8a7a5a905fc66ed82b922587a8e3c011e819dbb5](https://github.com/NousResearch/hermes-agent/tree/8a7a5a905fc66ed82b922587a8e3c011e819dbb5), specifically `agent/iteration_budget.py`, `agent/conversation_loop.py` and `agent/turn_loop_errors.py`. Its budget warnings and bounded error handling informed this implementation. No additional Hermes modules, dependencies or source code were imported. Attribution is retained in `native/third_party/hermes/NOTICE.md`.

`native/engine/wixal/run_control.py` owns accounting and exact settled batch fingerprints; `agent.py` continues to own the loop, checkpoint persistence, review and verification. Native SwiftUI shows used and configured step/call counts in the live-run view. Counters reset for an explicitly resumed attempt; prior checkpoints and the checklist remain retained evidence. Existing per-agent execution timeouts remain enforced by the agent service.

## Resulting behavior

- Every model request receives the current attempt's consumed and remaining turn/call limits. At 80 percent consumption, the controller asks it to prioritize verification, checklist updates and a factual conclusion. This notice is constructed from controller data and fitted into the request's context budget.
- For profiles with at least two turns, the last turn has no tool schemas and is reserved for a conclusion. Exhausting the call cap also removes tools on the next turn. One-turn profiles retain their opportunity to execute a tool. The configured limits still bound malformed-call and verification retries.
- Three consecutive tool batches with exactly the same tool names, arguments and settled results stop further tools and pause the run after a conclusion. Changing arguments, changing evidence and error batches reset this detector. `network_read`, `command_read` and `addon_job` polling are excluded because unchanged live-job output is expected. This detector does not claim to identify every possible semantic loop.
- A batch larger than the remaining call budget is rejected before any member executes. Every saved call gets a matching checkpoint and explicit nonexecution result, avoiding partially executed batches and dangling call IDs. This is a budget preflight, not transactional rollback of tool failures.
- A conclusion does not bypass independent outcome checks. Pending checklist entries and missing required evidence still prevent successful completion. A no-progress pause remains paused even when the model claims success.

## Scope

This pass improves local execution control. It does not add remote execution, AD/cloud qualification, messaging gateways, voice/media, new model providers or a different inference engine. The Hugging Face library and the six downloaded models remain in place. Qualification uses the installed helper and real Qwen3.5 9B, with disposable local files; it does not qualify every downloaded model or every red-team workflow.

Validation evidence is recorded under `artifacts/native/agent-run-control-2026-10-12/`. See `validation.json` for final results and identity. Earlier test-harness failures remain retained separately from final qualification.
