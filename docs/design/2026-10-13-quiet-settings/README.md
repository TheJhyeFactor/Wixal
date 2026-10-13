# Quiet Models, performance, context and memory

Native implementation of the approved Quiet workspace direction. Related issue: #54.

Models opens directly in Settings with Library, Discover, Downloads and Performance. Installed models use compact rows with optional details; the selected model and context link stay above section navigation. Downloads have a dedicated view and remain signposted from other tabs. Performance separates benchmarks on this Mac from recorded conversation usage. Imports and local engine/hardware controls expand on demand.

Context uses Context, Instructions, Saved memory and Suggestions tabs. Context controls and an eligible-source summary sit alongside each other when there is room and stack in narrow panes. Personal/project scope is explicit. Eligibility does not mean a source was consumed by a model request; actual recalled evidence remains separately inspectable. Instructions retain the explicit save and account-verification rules. Saved note drafts are scoped by identity, project and note scope across settings navigation. Forgetting a note asks for confirmation and preserves its source conversation. Suggestion review keeps the original quotes and replace/combine/separate choices.

Existing engine methods and boundaries are retained: no new inference runtime, automatic memory saving, provider integration, public version bump or workspace migration.

## Reference research

These are official published documentation and screenshot references, not installed-app comparisons or benchmark claims.

- [LM Studio per-model defaults](https://lmstudio.ai/docs/app/advanced/per-model): row-level model settings and advanced configuration on demand.
- [Jan settings](https://www.jan.ai/docs/desktop/settings) and [model hub](https://www.jan.ai/docs/desktop/quickstart): model management separated from hardware and appearance; discoverable hardware-fit information.
- [Msty local models](https://docs.msty.ai/studio/managing-models/local-models): installed/search/import organization and persistent install progress.
- [Msty insights](https://docs.msty.ai/studio/managing-models/insights): separate usage breakdowns, throughput and latency. Its cost estimates are not adopted for local Wixal requests.
- [Claude memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context): explicit project separation, chat-reference controls and inspectable saved memory.
- [Open WebUI memory management](https://docs.openwebui.com/features/chat-conversations/memory/): directly add/edit/delete saved memories. Wixal retains user approval of suggestions.

## Verification

Validation results are recorded in the pull request after native build, engine regressions, packaged signature/source verification and installed-app flows complete. Request usage counters and saved benchmark identity rules remain distinct; this UI change does not establish general model quality or new security qualification.
