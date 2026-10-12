# Hugging Face model library and local security assurance

12 October 2026 · Native SwiftUI/Python implementation

## Model library

New downloads use the public Hugging Face Hub, replacing the Ollama registry catalogue and pull path. Fourteen curated, revision-pinned single-file GGUF choices are included. Operators can browse another public repository and select a supported GGUF file. The file listing shows its licence, size and repository revision. Downloads retain repository, commit, filename, SHA-256 and size. The cache is keyed by file hash, range resume validates the returned range, and import occurs only after size, GGUF magic and checksum verification. A failed checksum discards the invalid partial file. Redirects are restricted to Hugging Face HTTPS hosts; no repository scripts, Python packages, remote model code or hosted inference run.

Hugging Face is the model source. Wixal's existing bundled Ollama runtime remains the local inference backend, using an exact local GGUF import rather than a registry pull. Installed models, existing selections, conversation history, benchmarks and legacy model import remain available. Old registry download jobs are retained as history and paused at restart, but cannot resume through the new provider; select their replacement in the Hugging Face catalogue. Download provenance persists independently of queue dismissal.

Current compatibility is public, single-file text GGUF with published LFS SHA-256 and size. Split GGUF, vision projectors, gated/private repository authentication, raw Safetensors and MLX packages are not silently treated as compatible. The UI explains incompatible repositories. Local import and successful inference are distinct from suitability for agents. An actual Qwen3-0.6B Q8 download/import/inference passed, but this small model misread a status in one specialist case; that failure is preserved. It is not advertised as a qualified specialist model.

Primary source documentation: [Hub downloads](https://huggingface.co/docs/huggingface_hub/package_reference/file_download), [GGUF support](https://huggingface.co/docs/hub/gguf), [local Ollama imports](https://docs.ollama.com/import).

## Completed local security additions

The engagement workspace has a **Validation & identities** view with native API, identity, deterministic validation, defensive evidence and structured import controls.

- Bearer-token identity leases use macOS Keychain. State, model contexts and exports retain references and metadata, not token values. Leases bind target, project, scope revision and expiry; saving and using an identity request explicit review. Revocation removes its Keychain value. Scope/project races after review and after a Keychain write reject the lease and clean its secret. Authenticated observations require HTTPS except for explicit loopback labs.
- A typed `api_observe` capability collects at most six same-origin GET paths with optional identity reference. It has no arbitrary headers, inline secrets, queries, redirects, cookie session, mutation or external provider call. DNS and destination exclusions use the existing pinned connection boundary. Responses retain body hashes and bounded structured JSON; raw bodies are omitted and known token echoes are redacted.
- Deterministic contracts evaluate **API access boundaries**, **network port states**, and **response-header values**. They require two distinct completed collected records, comparable target/capability/environment/current scope, and the declared signal. An API access contract requires the declared distinct identities, identical paths, the allowed 200/private signal and denied 401/403 control. An inconclusive result cannot complete an objective. A validated requirement does not automatically mark a finding confirmed or demonstrate broader compromise.
- `recon_operator` and `inventory_operator` assignments queue one exact supported typed operation through the existing coordinator. Their role allowlist intersects approved scope, target and readiness. No shell, arbitrary tool loop, secret value or independent dispatcher is introduced. Model analysis roles remain evidence-only.
- Specialist analysis reads only the explicitly selected, hash-verified immutable evidence snapshots. It no longer appends derived inventory or uses a subsequently mutated run result. General selected-evidence inventory also selects the matching historical observation rather than unrelated newer values.
- Candidate path search excludes older-scope edges and rechecks referenced evidence hashes.
- Linux reconciliation inspects exact owned container/network identities and records liveness or absence. It never replays work, removes another owner's object or equates environment cleanup with target-side cleanup. Operations expose an inspect control. The services profile now has actual Linux runtime acceptance alongside cancellation and reconciliation.
- Structured external JSON import validates a bounded findings list and maps external statuses to unverified claims. It does not import scope, authority, commands or confirmed native findings. It is a structural importer, not a claim of complete version-specific Decepticon format compatibility.
- Defensive sensor JSON retains sensor identity, time coverage, timestamped run references and original evidence. Correlation uses the exact operation and event type. Matching evidence is `observed`; complete declared coverage without a match is `not_observed`; incomplete coverage is `unknown`. This is evidence correlation, not automatic sensor deployment or an automatic offensive/defensive loop.

## Qualification and remaining boundaries

The repeatable packaged acceptance is `native/scripts/hf-security-acceptance.py`. It performs a real public Hub transfer, exact file verification, local import/inference, real macOS Keychain storage/revocation, owned HTTP access/control observations, deterministic evaluation, all five specialist analysis roles, server-event correlation, untrusted import, exports and restart. The role checks use installed `gpt-oss:20b`; each has one held-out anonymous-observation case. This does not qualify every model, domain or workload.

Worker acceptance is `native/scripts/worker-acceptance.py --profile services`, against the dedicated no-host-mount Colima validation VM and recorded worker image. The VM is stopped after tests and owned objects are removed. Results and original failed attempts remain under `artifacts/native/hf-security-completion/`.

The user selected **continue with the local lab; leave remote and AD/cloud qualification pending**. No remote destination, cloud credential or AD environment was used. Remaining platform work includes authenticated cookie/OAuth/API mutation workflows, capability-specific exploitation validators, persistent interactive terminal environments, remote workers, dedicated AD/cloud adapters and qualification, live external-controller approval bridging, vendor sensor adapters, broader held-out model matrices and distributable release packaging. Contacts, threat descriptions and prose abort conditions remain descriptive fields; no model interprets them into implicit permission. Existing explicit exclusions, run budgets, testing windows, deadlines and stop controls remain enforced.

This implementation does not add C2, phishing, persistence, arbitrary payload execution or full autonomous attack chains. GitHub/website publication and Apple notarisation are separate delivery claims.

## Evidence

- `artifacts/native/hf-security-completion/validation.json`: consolidated identities, tests, deployment and boundaries.
- `artifacts/native/hf-security-completion/packaged-acceptance-final/results.json`: final packaged Hub/API/model acceptance.
- `artifacts/native/hf-security-completion/packaged-acceptance/results.json`: retained earlier small-model failure.
- `artifacts/native/hf-security-completion/linux-services-final/results.json`: actual services, egress, cancellation and reconciliation.
