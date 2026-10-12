# Native model browser design proposal

Status: compact layout approved and implemented on 2026-10-12. Provider filtering, RAM estimates/recommendations, model deletion and inline downloads added. Inference migration remains deferred.

## Current findings

`native/Sources/ModelsView.swift` places Hugging Face discovery inside Downloads, alongside queue controls and a manually entered repository. Search wording refers to installed models while browsing downloads. Filters are collapsed and mix capabilities, file sizes and benchmark state. The download catalog has 14 file entries for five Qwen model sizes rather than one row per model with nested file choices.

`native/engine/wixal/huggingface_models.py` already supports pinned public-repository inspection, single-file GGUF selection, published hashes, resumable downloads, size/hash verification and local runtime import. It does not yet implement general Hub search. Split models and vision projectors are explicitly excluded. Runtime compatibility must not be inferred solely from a GGUF tag.

## Proposed information architecture

- Browse: model search and discovery, visible filters, grouped results and details/file choice.
- Your models: installed models, selection, storage, import and measured performance.
- Downloads are integrated into Your models: active and retained jobs with inline progress, pause/resume/cancel/retry and explicit verification/import phases. Active jobs remain visible even when installed-model filters exclude their metadata.

Keep runtime controls and detailed benchmark history out of the main browsing hierarchy. Retain them in the appropriate installed-model/settings views. Use native SwiftUI components, existing theme tokens and neutral surfaces.

## Design options

Browse and inspect: readable model cards with publisher, model size, smallest matching download and file options. Details reveal quantization, exact file size, source, licence and compatibility state.

Compact library: denser rows with the same controls and detail flow. Useful for comparing many results with less scrolling.

Interactive review uses the current catalog as sample data. Downloads and installed-library state are illustrative; there are no network writes or live installs. Filters for additional model types produce an honest empty state until discovery supplies suitable metadata.

## Filter and metadata requirements

- Separate parameter count from download bytes. MoE active parameters, if supplied, are a separate labelled field rather than substituted for total parameters.
- Search readable names, publishers and repository IDs. Keep exact file names in model details.
- Model type choices and labels come from Hugging Face’s official task catalog (`pipeline_tag`), with unlisted metadata shown as unknown. Keep runtime capabilities such as tool calling separate.
- Quantization, publisher, licence and compatibility can live in an additional filter sheet when there are enough results to warrant them.
- Treat missing parameter count, type, size or licence as unknown. Never silently convert unknown metadata to zero or a positive capability claim.
- Label publisher claims, runtime-reported capabilities and Wixal-tested behavior separately. Security suitability is not implied by a model name, tag or successful import.
- Fit estimates depend on selected quantization, context and this Mac; download bytes are not a RAM estimate.

## Implementation

Implemented bounded, paginated Hub discovery in the Python service with request cancellation, metadata caching, rate-limit/error handling and stale-result suppression. Translate UI filters to supported Hub queries, then inspect exact files when a result is opened. Apply file-byte constraints to verified file metadata, not total repository storage. Group results without combining unrelated publishers or revisions. Keep a bounded saved catalog available offline and label its age.

Public single-file GGUFs remain the initial installation scope. Gated/private repositories, unsupported architectures, split weights, projectors and non-GGUF formats need truthful unavailable/unsupported states rather than an enabled Download button. Additional type filters must reflect real available results, with coding/reasoning treated as task descriptions rather than acceptance guarantees.

Keep the existing pinned revision/hash download path, job persistence and action constraints. Browsing should remain available while generation is busy; download/import/select actions should respect their real constraints and state a reason when unavailable. Do not mark a transfer complete until verification and runtime import finish.

## Acceptance

Verify combined filters, sorting, unknown metadata and pagination without losing selections; no duplicate family rows for quantization files. Verify rapid search changes, cancellation, offline cache, rate limits, no results and unavailable repository states. Verify pause/resume/retry plus hash/import failures and correct installed-state transitions. Verify keyboard/VoiceOver labels, narrow native window layout, light/dark themes and readable long repository names. Preserve model selection, conversation histories and drafts.

The interactive proposal passed browser checks for parameter/download filters, empty type results, detail selection, simulated queue pause/cancel, both layout variants and narrow-width overflow. These checks are design evidence, not installed native acceptance.

## Primary references

- https://huggingface.co/docs/huggingface_hub/en/guides/search — Hub search/filtering, including parameter ranges.
- https://huggingface.co/docs/hub/gguf — GGUF discovery and metadata.

## Installed validation

487 engine tests passed, including ten new browser/deletion regressions. Swift release build and strict development signature verification passed; all 143 installed source manifest entries matched. Packaged and installed helper acceptance used live public Hub metadata and a retained, verified real Qwen GGUF for import, selection and isolated deletion/cache reclamation. Native UI checks observed provider selection, live search, file expansion, RAM labels, deletion confirmation/cancel, a real transfer bar in Your models, pause, resume and transition into an installed model. Real transfer checks used a separate workspace with the canonical installed app; the user library was restored afterward.

RAM figures are estimates at the displayed context, not measured minimums. Hub task labels and model-name parameter fallbacks do not establish tool or security suitability. Only public single-file GGUFs with published hashes are offered for download; successful runtime import remains required.

## Filter simplification follow-up

Replaced the six exposed dropdowns with Model type, Provider, Filters and Sort. Type and provider popovers show five popular GGUF choices plus search. Types use `https://huggingface.co/api/tasks`; providers are public organizations/users returned by `https://huggingface.co/api/quicksearch`. Popular defaults are ranked by occurrence in the 100 most-downloaded GGUF repositories, not claimed as a global provider league table. Task search covers the full official catalog; provider search queries the Hub after a short debounce. Size and RAM controls are in the Filters popover, with a concise active-filter summary.

Hub task IDs pass directly to model search instead of guessed coding/reasoning classifications. Exact repository task metadata is retained in model provenance. Defaults are cached for 24 hours and persisted, with stale metadata labelled during offline fallback. Selecting a provider or type starts a new search; superseded searches are cancelled and stale results cannot replace the current selection.

Validation: 491 engine tests, 34 focused model tests, six live packaged/installed acceptance groups, native five-choice/search popovers and the additional-filter panel. Installed source/signature checks and workspace content-preservation checks are retained in `artifacts/native/model-browser-filters-2026-10-12/validation.json`.
