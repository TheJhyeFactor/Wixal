# Model library refresh — 12 October 2026

Models now has three tabs: Browse, Your models, and Models & engine. The third tab contains the current model, context window, Mac hardware and engine controls, Import models, and saved benchmarks. Browse and Your models retain their compact searchable rows and Hugging Face filters. Active and queued downloads remain inline in Your models.

## Selected library

The user explicitly selected these six local candidates from their supplied research. The saved catalog contains one pinned single-file GGUF for each. General Hugging Face search remains available.

| Model | Hugging Face publisher | Quantization | Download GB |
| --- | --- | --- | ---: |
| Qwen3.5 9B | unsloth | Q4_K_M | 5.68 |
| Gemma 4 E4B IT | unsloth | Q4_K_M | 4.98 |
| Gemma 4 12B IT | bartowski | Q4_K_M | 7.66 |
| Qwen3.8 27B | prithivMLmods | Q4_K_S | 15.83 |
| KAT-Coder 2.5 Dev | RemySkye | Q3_K_S | 15.18 |
| Qwen3.6 35B-A3B | unsloth | UD-Q3_K_S | 15.36 |

The six files total 64.69 GB. Q3 was chosen for the two roughly 35B models to reduce weight memory on the 24 GB Mac. RAM estimates remain visible and depend on context size. Qwen3.8 exceeds the estimated budget even at 4k context; a successful short generation does not establish comfortable sustained use.

Every download uses the installed desktop's production `model-pull` IPC and Wixal's existing pinned-revision, size-checked, SHA-256-checked Hugging Face downloader. Imported models carry source provenance. No Ollama registry pulls or manual weight downloads are used. The bundled Ollama 0.35.1 inference runtime remains in place; direct llama.cpp migration is deferred.

## Cleanup and evidence

The external Ollama model directory and the legacy Wixal model directory were moved into a dated folder in the user's Trash, and empty active directories recreated. The retired stores held about 82 GB combined. This is recoverable cleanup and does not reclaim their disk space until Trash is emptied. Credentials, application configuration, unrelated Hugging Face dataset caches, and test artifacts were preserved.

Local evidence is saved in `artifacts/native/model-library-refresh-2026-10-12/`: `selections.json` records exact repositories, revisions, files and hashes; `model-cleanup.json` records recoverable cleanup; `downloads.json` records production transfer/import outcomes and independent file hashes; `generation-checks.json` records bounded generation checks. These checks distinguish download/import success from usable model output. Provider and task labels are Hub metadata, not independent capability qualification.

The updated app was installed at `/Applications/Wixal.app`. The release Swift build, 34 model tests and full 491-test engine suite passed. All 143 installed source-manifest entries matched the working source, and strict signature verification passed. User message arrays and draft content were preserved through installation and relaunch. One null empty draft was normalized to an empty draft object.

Text generation checks do not qualify tools, agents, security workflows, vision, audio, long context or model quality. The initial two Gemma selections were pretrained variants and produced incorrect or repetitive chat responses despite successful imports. They were replaced with explicitly instruction-tuned (`-it`) variants from Unsloth and bartowski through the same Wixal downloader. Initial selections and failed evidence remain saved separately; final generation results determine qualification.

## Final installed result

All six selected instruction/chat models downloaded, passed independent size/SHA-256 checks, and imported through the installed Wixal downloader. Each returned `42` to the bounded `17 + 25` text-generation check at 4k context on the final installed helper. Your models shows six installed models and zero download jobs. Qwen3.5 9B remains selected at 4k context. These are smoke checks, not broad model-quality or agent-tool qualification.

A diagnostic IPC client disconnect exposed an uncaught `BrokenPipeError` during socket cleanup. Cleanup now treats an `OSError` from waiting for an already disconnected peer as an expected disconnect. Ten abrupt installed-client disconnects (200 ping requests) left the helper responsive without a UI warning. The final full engine suite passed all 491 tests again.

One earlier update required clearing an orphaned helper while external diagnostic clients were connected. The final quit left no helper or runtime processes behind; a fresh launch recovered all six models without replaying downloads. Messages and draft content were preserved. Final evidence and executable hashes are in the local `validation.json`, `generation-checks.json`, `downloads.json`, and `restart-check.json` reports.
