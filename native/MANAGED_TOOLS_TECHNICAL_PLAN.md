# Wixal Native managed tools and add-ons: technical implementation plan

Implementation update (9 October 2026): [native preview implementation and measured acceptance status](MANAGED_TOOLS_IMPLEMENTATION_STATUS.md). The original planning status below describes the earlier document-only request.

Date: 8 October 2026

Status: design for review before integration. This request produces planning documents only. No tool source is forked, package downloaded, executable installed, release published, application packaged, or integration implemented.

Companion documents:

- [Acceptance and model utilisation matrix](MANAGED_TOOLS_ACCEPTANCE_MATRIX.md)
- [RustScan integration design](RUSTSCAN_INTEGRATION_PLAN.md)

## 1. Objective and boundaries

Keep the native application compact while offering separately downloadable tools whose packages, adapters, workflows and model utilisation have been tested as specific combinations. Make installation, execution, evidence, updates and recovery predictable in the actual Finder/Dock application.

The application ships the interface, permission enforcement, package manager, trust bootstrap and executable adapters. The catalogue supplies authenticated package descriptions and versioned declarative workflow content. Tool binaries, compatible runtimes and assessment content download when needed. Downloaded packages cannot register arbitrary Python/Swift adapter code in the engine.

Initial managed scope: RustScan on Apple Silicon, with an existing independently verified Nmap installation for linked inspection. Wider tool migration follows measured pilot acceptance. Native currently declares macOS 14 as its minimum; that declaration is not evidence that every tool works on every later OS. Intel support requires its own package and installed-app evidence before advertisement.

No universal compatibility guarantee is possible. The deliverable is bounded compatibility evidence, explicit unsupported states and safe recovery. Installation does not grant execution permission, expand target authority or establish model competence.

## 2. Inspected source baseline

Reviewed checkout HEAD: `af866b68b100dad005c1d44de4a908c35028dff7`, with existing uncommitted native work. Engine version at review: `0.7.10-alpha.2`. These identify the review context, not a clean release artifact.

| Existing area | Current behaviour | Required development |
|---|---|---|
| `engine/wixal/addons.py` | Curated catalogue, Homebrew recipes, install/manage jobs, version-command verification | Managed providers, authenticated catalogue, exact package identities and compatibility selection |
| `engine/wixal/addon_execution.py` | Fixed adapters, direct argv, target/project checks | Shared invocation contract, package selection and execution leases |
| `engine/wixal/tools.py` | Session-owned processes, bounded output, read/stop and approval | Typed executable handles, environment isolation, complete evidence capture and lifecycle events |
| `engine/wixal/agent_authority.py` | Target and effect authority | Consistent typed enforcement across named tools, add-ons and chained work |
| `engine/wixal/context_policy.py` | Progressive schemas and bounded inference evidence | Readiness-aware schema selection and evaluated tool lifecycle exposure |
| `engine/wixal/security_workspace.py` | Persistent investigations, dependencies, queue and interruption | Discovery-result bindings and package provenance in runs |
| `engine/wixal/security_records.py` | Observations, findings, contracts and model planner | Source-preserving projections and capability-specific compatibility |
| `Sources/AddonLibraryView.swift` | Shared Tools UI, install/verify/update/repair/remove | Separate installation/readiness/model states and managed-version recovery |
| `engine/wixal/storage.py` | Single-owner workspace SQLite state serialized as JSON | Workspace references to a separate per-user package registry |
| `scripts/addon-library-acceptance.py` | Actual tool cases plus a real model catalogue-discovery case | Full install/update/failure and model task-utilisation suites |
| `scripts/package.py` | Distinct development, alpha and distribution packaging modes | Include updater dependencies/trust bootstrap and verify managed tools outside the app bundle |

Existing tests are useful starting points; their previous success does not certify this proposed architecture. All new acceptance must identify exact source/package/installed helper hashes. Leave unrelated working-tree changes untouched.

## 3. Compatibility is a tuple, not an installed flag

Track independently:

1. **Package installed:** files are present.
2. **Package verified:** identity, integrity, platform and local readiness match the signed description.
3. **Capability ready:** the application's adapter supports that exact package and its prerequisites.
4. **Model evaluated:** a specific model/runtime/prompt configuration passed the capability's utilisation evaluation.
5. **Permission available:** the current project/task enables the capability and permits its effects.

Execution eligibility depends on 2, 3 and 5. Advertised verified AI utilisation additionally requires 4. Untested models remain visibly unevaluated; policy enforcement applies regardless. A model evaluation failure never disables the underlying manually usable capability by implication.

A compatibility tuple contains package digest, package revision, dependency/content digests, OS/architecture, adapter/schema/parser versions, app build and helper hash. Model evaluation extends it with model weight digest or an explicit unavailable-digest marker, quantization, runtime version, context size, generation settings, schema-selection policy and instruction-pack hash.

Signed release metadata may declare an app/adapter version range only after the supported range is justified. Otherwise list tested builds and label other combinations unevaluated. A backend-only result is not installed-UI coverage.

## 4. Distribution strategy and repository ownership

Proposed repository: `wixal-tools`, containing definitions, build recipes, compatibility contracts, test scenarios and release descriptors. The name is a proposal; no repository is created by this plan.

```text
wixal-tools/
  definitions/<tool-id>/package.json
  recipes/<tool-id>/
  patches/<tool-id>/
  contracts/<capability-id>/
  scenarios/<capability-id>/
  workflows/<workflow-id>/
  release-descriptors/<package-id>/
  ci/
  docs/
```

Three distribution strategies are permitted per package: tested upstream artifact, Wixal build from pinned upstream source, or a Wixal fork with a small maintained patch set. Record the strategy and source commit. Do not fork every project by default.

Build recipes pin source, dependencies, compiler/runtime versions, CI action revisions and build environment. Fork maintenance includes an upstream-difference report, patch rationale, security-update tracking and rebase tests. Reproducibility is measured where achievable; a pinned recipe alone is not proof of bit-for-bit reproducibility.

Use versioned GitHub release artifacts initially; catalogue metadata may be hosted separately on a stable endpoint. Use immutable releases for promoted payloads and exact artifact URLs rather than `latest`. GitHub documents locked release tags/assets and release attestations [S1]. Never place upstream security-tool build execution and production release signing in the same untrusted job.

Per-tool packaging review covers redistribution permissions, notices, corresponding source requirements where applicable, runtime dependencies and operating-system privileges. Do not assume all tools share a licence. Nmap has its own published source licence [S5]; retain the external Nmap provider until its proposed distribution arrangement is explicitly reviewed. A source fork does not remove upstream obligations.

## 5. Package, capability, content and workflow contracts

Use four separate identities:

- **Package:** immutable downloadable executable/runtime artifact.
- **Capability:** application-owned typed input/output and effect contract.
- **Content pack:** templates, script data, advisories or other data consumed by a capability.
- **Workflow:** versioned instructions referring to known capability contracts.

One package may implement several capabilities. One capability may support a finite set of package versions. Workflow installation must not enable tools or confer permission.

Proposed descriptor fields, all validated with an application-owned strict schema:

| Group | Required information |
|---|---|
| Identity | Tool ID, upstream version/commit, package revision, artifact ID and digest |
| Source | Upstream URL, distribution strategy, recipe hash, patch-set hash and source archive |
| Platform | OS/architecture, minimum OS, explicit tested OS/build matrix |
| Artifact | URL, compressed/unpacked sizes, format, SHA-256, inventory digest and entrypoint |
| Dependencies | Exact runtime/library IDs and hashes; no unconstrained dependency selection |
| Compatibility | Adapter/schema/parser IDs and allowed revisions, tested app builds |
| Effects | Filesystem/network/privilege requirements described by known capability contracts |
| Readiness | Identifier of an app-owned bounded verification procedure |
| Evidence | Acceptance report digest, build provenance, signing/notarization identity where applicable |
| Content | Required/optional content-pack versions and freshness policy |
| Distribution | Licence metadata, notices, source and distribution-review status |
| Lifecycle | Channel, supersedes, withdrawal/revocation state and approved recovery targets |

Artifact ID is content-addressed. Upstream version and Wixal package revision are separate. Rebuilding, changing packaged dependencies, signing, or modifying payloads creates a new artifact identity and acceptance record. Hash the final distributed bytes after all signing/notarization/package steps.

Entrypoints must be relative paths inside the verified package. The descriptor cannot specify a shell installer, arbitrary verification command, adapter import or unrestricted environment injection. Size and dependency limits are enforced before download/extraction.

Content updates are independently versioned. Nuclei templates, Nmap data/scripts and vulnerability databases are not assumed stable just because a scanner binary is pinned. Tool-specific data-refresh behaviour is documented and tested. Advisory freshness and deterministic parser compatibility are separate claims.

## 6. Catalogue authentication and update trust

Recommended implementation: evaluate and pin the Python TUF client, including its packaged cryptographic dependencies, for authenticated target discovery/download. Ship the trusted bootstrap root in the signed application; never learn initial trust from the download endpoint. TUF's documented client loads the local trusted root [S3]. Do not implement a bespoke signature verifier as a shortcut.

Use standard root, targets, snapshot and timestamp metadata; record a repository protocol/operations document. TUF handles authenticated metadata versions, expiry and target hashes/lengths [S2]. Wixal remains responsible for package policy, extraction, activation and compatibility.

Operational proposal: offline root/release authority, protected release promotion, separate short-lived online metadata signing, and tested root rotation. A 2-of-3 root threshold is recommended for public production but requires real independent custody and a recovery drill. A single-operator preview must describe its weaker custody honestly; do not fabricate quorum by keeping all keys together.

Signed catalogue data is a target file bound to exact package descriptors. Separate stable and preview channels. The updater accepts only app-known provider types and capability IDs. Unknown fields/contracts fail closed for installation but must not prevent the rest of Tools from loading.

Reject stale/replayed catalogue updates and mismatched target metadata. Keep a persisted trusted metadata floor. Explicit package rollback is allowed only to a locally verified, compatible, non-revoked digest authorised by policy; it does not roll back TUF metadata versions.

Expiry or catalogue outage blocks new unverified installations and activation decisions that require fresh metadata. Existing locally verified packages remain available under their recorded policy. Show last verification/revocation-check times. An offline machine cannot learn a new remote revocation, and the interface/report must not imply otherwise.

Build attestations help establish provenance, but do not prove safe behaviour, correct source or compatibility. Release promotion still requires the acceptance tuple and final-payload checks [S6].

## 7. Local storage, ownership and concurrency

Proposed per-OS-user root:

```text
~/Library/Application Support/Wixal/ManagedTools/
  registry.sqlite3
  metadata/<channel>/
  downloads/<digest>.part
  staging/<transaction-id>/
  packages/<tool-id>/<artifact-digest>/
  content/<content-id>/<artifact-digest>/
  journals/<transaction-id>.json
  locks/
```

Use a dedicated package registry rather than placing device-global install state inside a project's workspace JSON. Multiple isolated workspaces can otherwise race against the same files. Package manager mutations use a cross-process transaction lock; activation uses per-tool locking. Keep hashing/extraction off the UI/engine request loop.

Binary storage is local to the macOS user and shared across their projects. Installation jobs keep requester/session/project ownership; task authority remains project scoped. Account-specific workflow content keeps its existing owner boundary. No installation automatically transfers guest notes, workflow ownership or evidence to a cloud account.

Persist package records, installations/activation pointers, install jobs, content versions, run leases, provider records and verification status. Additive schema migrations record a registry version and retain a backup before structural changes. Workspace records contain package references and provenance, not package payloads.

Each execution acquires a lease on an immutable artifact before spawning. Updates cannot mutate it. Registry recovery reconciles leases with verified process identity; never kill an arbitrary PID merely because an old record exists. Removal/garbage collection cannot delete an artifact while any live run or rollback policy retains it.

Evidence references survive package removal. A user may delete an old payload when no lease needs it while retaining the hash/version record needed to explain historical findings.

## 8. Installation and activation transaction

State progression:

```text
requested -> checking_policy -> resolving -> downloading -> verifying
  -> extracting -> checking_readiness -> activation_pending -> ready
```

Distinct terminal/attention states: declined, cancelled, failed, interrupted, unsupported and setup_required. Update keeps the previously active package ready until the replacement transaction commits.

Algorithm:

1. Validate requested ID/channel and current installation policy, requester ownership and task boundary.
2. Resolve a compatible signed descriptor and exact dependency closure. Detect cycles/conflicts and compute total download/unpacked size.
3. Check free space and existing staged downloads; do not infer readiness from an external binary with the same name.
4. Download with bounded retries, timeout, size and redirects. Allowed redirect hosts come from app/provider policy; credentials and arbitrary local/file URLs are rejected.
5. Verify authenticated length/hash before opening the archive. Partial download resume requires revalidation of the final complete artifact.
6. Extract into a private same-volume staging directory. Reject traversal, absolute paths, duplicate/case-colliding entries, unexpected hardlinks, escaping symlinks, device files, privileged modes and excessive expansion/file counts. Initial single-binary RustScan packages need no symlinks; later formats require an explicit safe profile.
7. Verify inventory, executable architecture, dependencies and distribution signature policy. Audit library load paths; no hidden dependency on the publisher's Homebrew installation.
8. Run a bounded app-owned readiness check with controlled cwd/environment. Installation verification makes no unsolicited live target scan.
9. Publish the immutable package directory and atomically commit its activation pointer with a durable transaction journal. Dependency closure is active before the parent becomes ready.
10. Emit final readiness and retain the previous compatible version. Cleanup only files owned by this transaction.

Filesystem publication and SQLite commit are not one transaction. Journal states must distinguish directory published, pointer committed and cleanup pending; startup recovery completes or unwinds these idempotently. Kill the process at each boundary in tests.

Cancellation during download/extraction leaves the previous active package usable. Cancellation after the activation commit cannot claim the new package was never installed; return the actual committed state and offer removal/recovery as a separate action.

No model-authored install commands, post-install scripts, Homebrew upgrades of unrelated packages or automatic system permission changes in managed mode. Specialist installers remain an explicit provider with specialist readiness.

## 9. Execution contract and failure isolation

Proposed engine services, implemented later:

| Interface | Responsibility |
|---|---|
| `CatalogueClient.refresh(channel)` | Authenticate catalogue metadata and return validated descriptors |
| `PackageRegistry.resolve(capability, platform, app)` | Select a compatible active package or structured unavailable reason |
| `Installer.prepare/commit/cancel` | Durable package lifecycle transaction |
| `Adapter.plan(inputs, authority, package)` | Validate typed inputs and produce immutable invocation plan |
| `Runner.start/read/stop` | Existing asynchronous process ownership plus artifact lease |
| `Parser.normalize(raw, invocation)` | Produce versioned structured observations and warnings |
| `EvidenceStore.retain(record)` | Retain full provenance/raw output and bounded inference views |

An invocation includes capability ID, adapter revision, package/content digests, absolute executable path, argv, controlled environment, cwd, target scope, effect summary, deadline, output/resource limits and owner/session/project IDs. Approval applies to this concrete plan; changed plans require the existing policy to be applied again.

Use direct subprocess argv. Scrub unneeded secret/proxy/loader variables, supply tool-specific config/temp paths and explicitly allow necessary runtime values. Models cannot supply arbitrary environment variables. Package correctness is not an OS sandbox: filesystem/network effects must also be bounded by adapter and authority, with OS isolation adopted where supported and proven.

Exit-code meaning is capability specific. For example, a tool's findings exit code must not be confused with process failure. Distinguish tool exit, signal, deadline, cancellation, parser failure and evidence truncation.

Retain complete bounded raw evidence separately from display/model excerpts. Stream incrementally into files with a digest; on evidence cap exhaustion terminate or mark capture incomplete according to the contract. Never parse a UI excerpt as a complete document. Separate stdout/stderr where formats require it.

Stop terminates process groups with graceful then forced deadlines and releases leases after child reaping. Background tasks, chat and investigations share the same lifecycle. A tool crash produces a structured result; it must not crash the engine or freeze native rendering.

## 10. Tool API and existing UI migration

Preserve existing `addon_catalog`, `addon_install`, `addon_job`, `addon_run` and `addon_workflow` callers where practical. Add optional provider/channel fields with validated defaults and version the response contract. Maintain compatible `installed` fields temporarily; new consumers use explicit readiness dimensions.

`addon_catalog` reports source/provider, active artifact/version, compatible alternatives, adapter availability, local verification time, compatible update and model evaluation status. Return bounded model-facing summaries; full catalogue descriptions remain available on demand.

`addon_install` selects only a compatible approved descriptor. Preserve the current manual-install versus AI-install distinction and the user's automatic-install preference. Execution bypass must not override an installation-review requirement. A successful install cannot enable disabled execution tools.

`addon_job` reports stage, bytes, dependency readiness, error code and cancellation outcome. Download percentage derives from known bytes; build/readiness stages are named phases rather than invented overall progress percentages.

`addon_run` resolves a known capability to an absolute leased executable. Generic discovered external tools do not silently acquire a managed adapter or a verified AI badge.

UI states: Not installed, Downloading, Verifying, Ready, Setup required, Unsupported, Update available, Update failed, and Unavailable. Model details add Evaluated, Unevaluated or Limited for the selected capability/configuration. Precise reason/action is visible without opening a raw log.

Keep Browse/Installed navigation, filters, detail expansion, existing job history and investigation selection. Verification is read-only except updating its recorded result. Repair re-downloads the selected approved artifact; Update chooses a tested compatible newer package; Remove distinguishes managed payload removal from external provider instructions. Rollback selects a recorded allowed digest, never an arbitrary URL.

## 11. Existing external tools and migration

Providers are `managed`, `external_homebrew` and `specialist_installer`. Tool IDs do not imply ownership of user-installed programs.

Inventory existing executables without uninstalling/upgrading them. Record external path/version/architecture and an integrity fingerprint where feasible. Mark externally managed packages separately, and reverify on detected changes before another execution. A previously passed external version string does not authenticate subsequently replaced bytes.

Managed install is explicit; choosing it changes only Wixal's selected provider. External binaries remain untouched. A managed version is never selected merely because its name sorts before a Homebrew path. Existing investigations retain their original executable provenance.

Use a feature flag for managed catalogue/provider rollout, retaining the current provider during pilot. The flag cannot bypass security checks. Preserve settings and historical jobs through additive migration; do not reclassify old version checks as new compatibility certification.

## 12. Evidence and investigation semantics

Every result records invocation ID, actual arguments/effect scope, package and content identities, adapter/parser revisions, run/session/project ownership, timing, termination, raw evidence digests and parse/coverage limitations. Model interpretation links to these records but cannot overwrite their facts.

Derived observations keep source-run IDs and timestamps. Later lower-information results cannot erase previously identified service details. Latest reachability and historical identity remain distinguishable. Partial scans cannot establish service removal; comparisons require comparable coverage.

Chained steps use a typed immutable evidence reference with source result hash and matching target/project ownership. RustScan-to-Nmap retains per-host port mappings. Condition evaluation must inspect the selected source observations, not any historical result from the target.

All stages follow project permission policy, including automatically prepared follow-up steps. A completed installer does not approve the scan. A successful scan process does not establish exploitability, and an advisory match does not prove affected runtime exposure.

## 13. Model utilisation evaluation design

Evaluate the real model through the actual Wixal tool router and engine, without substituting a protocol fixture for utilisation evidence. Record exact model/runtime/settings and package tuple. Serialise local model inference as current investigation execution does; tool work may run in parallel under resource budgets.

Each capability has task scenarios across these behaviours:

- Discovery from a natural-language task, including when no tool is explicitly named.
- Correct selection versus a smaller or more suitable capability.
- Valid typed arguments and required-input clarification.
- Installation readiness/policy, asynchronous job polling, read offsets and stop handling.
- Appropriate use of source-bound follow-up evidence.
- Recovery from one recoverable failure without repeated identical calls or unbounded retries.
- Accurate interpretation of empty/partial/failed output and conflicting observations.
- Correct abstention for disabled tools, missing prerequisites and out-of-scope effects.
- Resistance to tool-output instructions that ask the model to alter authority or fetch/run unrelated code.
- Context pressure, schema discovery and model switching without losing source identifiers or permission state.

Scenario oracle is independent of the model: actual listener inventory, server request log, source file hashes, registry transaction events and invocation traces. A prose claim or model-graded verdict alone cannot pass a scenario. Automated factual checks cover known results; human review handles nuanced explanation, with explicit rubric and recorded rationale.

Persist selected schemas, prompts, calls/arguments, validated plans, approvals, tool outcomes and final answer. Retain visible operational evidence, not hidden reasoning. Redact credentials and unnecessary private content before any public artifact upload; publish only designated lab evidence. Keep local complete evaluation records when required.

Run ordinary, adversarial and held-out variants. Development scenarios may guide adapter improvements; held-out cases remain excluded from tuning, with any contamination recorded and replacements introduced. Do not hard-code scenario markers into prompts or adapters. Repeat stochastic cases and report every attempt, first-attempt success, assisted recovery, retries, token usage and elapsed time.

Provisional promotion policy per model/configuration: pilot repeats 5 times per critical end-to-end scenario; stable repeats 30 times for each core task scenario. Require at least 29/30 successful end-to-end runs for each core scenario, plus all prerequisite cases. Require 100% backend policy enforcement in every negative case. Any executed unauthorised effect or critical fabricated-success result blocks model qualification pending diagnosis. Finite passing samples do not prove zero future failures. Record counts and uncertainty rather than an invented universal reliability score.

Evaluate at a supported low-context configuration and the normal default; specify actual values after discovering installed models. Advertise only measured model configurations. New model weights, quantization, runtime, router, schema or system instructions can invalidate qualification. Limited models may retain manual tools and simpler capabilities; show the limitation and permit explicit task-level use under enforced authority rather than silently swapping models.

## 14. Test architecture and acceptance evidence

The companion matrix defines stable scenario IDs, failure oracles, evidence class and release gate. Every capability adds a suite manifest mapping supported features to scenarios, with mandatory/optional/platform-specific status.

Evidence classes:

- **R:** deterministic regression/fixture tests for boundaries and rare failures.
- **P:** final package/build and dependency verification.
- **L:** real local service/file execution using the actual tool.
- **M:** real model utilisation via Wixal.
- **I:** installed native app, UI and helper verification.
- **D:** authenticated distribution/install/update/recovery against actual artifacts.

Fixtures are appropriate for adversarial archives, malformed output and interrupted transaction simulation. They cannot stand in for actual package installation, service scanning, model utilisation or Finder/Dock checks. Missing required hardware, executable or service is skipped/blocked with an explanation, never passed.

Proposed evaluation report shape; placeholder values illustrate structure and are not acceptance evidence:

```json
{
  "schemaVersion": 1,
  "suiteId": "managed-rustscan",
  "status": "not_run",
  "identity": {
    "appBuild": "<build-id>",
    "installedHelperSha256": "<sha256>",
    "sourceManifestSha256": "<sha256>",
    "packageSha256": "<sha256>",
    "adapterRevision": "<revision>",
    "modelDigest": "<digest-or-unavailable>"
  },
  "environment": {"architecture": "arm64", "macOSBuild": "<build>"},
  "cases": [],
  "requiredCases": [],
  "skippedCases": [],
  "evidenceManifestSha256": "<sha256>"
}
```

The report validator requires every mandatory case to have passed, links raw evidence hashes, rejects identity mismatch and distinguishes source from packaged/installed mode. `status: passed` is derived from these checks; an authored summary cannot set it independently. Reports identify suite version and exclusions. Keep acceptance report manifests immutable with the corresponding promoted artifact.

Performance checks use equivalent workload and facts: same hosts, ports and timeout/retry assumptions. Separate discovery from service/scripts. Measure correct detections, missed known services, request/connection counts, resource peaks, duration and cancellation latency. Tune defaults using measured results on supported devices; initially record baselines rather than claim an unmeasured speed target.

## 15. CI, promotion and final-artifact testing

Pipeline stages:

1. Validate descriptor/contracts/licence review status and dependency locks.
2. Build/download candidate in an isolated environment; verify upstream identity and generate dependency inventory/SBOM.
3. Run regressions and real tool scenarios on eligible macOS runners.
4. Sign/notarize where the intended distribution channel requires it, then assemble final artifact.
5. Hash and test final payload on a clean eligible machine. Confirm no unrecorded Homebrew/runtime dependency.
6. Run model suites using actual local runtime/models and packaged helper; keep test models and private credentials out of distributed payloads.
7. Run installed UI and distribution lifecycle acceptance, including quarantined download behaviour.
8. Validate the full evidence tuple and produce provenance/acceptance manifests.
9. Publish immutable payload from a protected promotion job, then update authenticated catalogue metadata to reference it.

Source-build jobs have no production release keys. Signing jobs consume reviewed content-addressed artifacts, never execute an arbitrary fork's workflow with release secrets. PR tests cannot publish to stable. Package source changes may trigger appropriate checks but cannot themselves authorize a release.

A promoted tool combination passes package/adapter/real-use/distribution and installed-app gates. AI qualification is separately attached per measured model. At least one supported real model must qualify before advertising the new capability as verified AI use. An unevaluated model does not retroactively invalidate manual readiness.

Use source-level matrices for fast PR feedback and controlled macOS hardware for installed/model gates. CI runners lacking local model or hardware are not permitted to substitute mocks and label the gate passed. Do not cross-multiply all versions unnecessarily: test every advertised platform/model boundary and dependency combination, with explicit pairwise expansion and full tests on shared-runtime changes.

## 16. macOS distribution and privileges

The managed tools reside outside `Wixal.app`; app updates must not modify tool payloads and tool updates must not modify the application bundle. Verify the independently distributed executable/dependencies and the app's packaged engine on their own merits.

Production download acceptance must validate the chosen Developer ID/notarization process and real Gatekeeper/quarantine behaviour on a clean Mac. Apple's distribution guidance distinguishes Developer ID signing and notarization [S4]. A local ad-hoc signature is not public distribution evidence. Keep local development/explicit alpha channels visibly distinct until fresh distribution evidence exists.

No quarantine stripping, Gatekeeper bypass, automatic sudo, root service install or global permission change to make a package appear ready. Capture tools, proxies, GUI applications and specialist frameworks have prerequisite profiles for user configuration/permissions. A missing prerequisite is setup_required, with an explicit supported action.

## 17. Per-tool onboarding policy

| Tool/group | Planned treatment | Main acceptance concern |
|---|---|---|
| RustScan | First managed package and dedicated discovery contract | Coverage, strict result parsing, resource budget and Nmap handoff |
| Nmap | Existing external provider first; managed redistribution decision later | XML/NSE data dependencies, fixed profiles and distribution terms |
| ffuf | Candidate for next managed adapter | Request rate, wordlist scope, JSON output and cancellation |
| Nuclei | Package plus separately controlled selected templates | Template identity, update suppression, actual request effects and interpretation |
| OSV-Scanner/Trivy | Explicit dependency/advisory-data policy | Findings exit codes, database freshness, outbound fetches and local project ownership |
| testssl | Script/runtime package profile | Shell/runtime dependencies, output and TLS handshake workload |
| TShark/Wireshark | Saved-capture capability before live capture | Dependencies, input evidence and separately granted capture privileges |
| ZAP/mitmproxy/Metasploit | Specialist/setup providers until dedicated contracts pass | Runtime/daemon lifecycle, scope, authentication and explicit configuration |
| Workflow packs | Signed declarative content tied to contract revisions | Instructions, permissions, referenced capabilities and model behaviour |

Each onboarding proposal includes representative real tasks, independent expected facts, harmful failure modes, package/dependency strategy, parser semantics, model cases and support matrix. A library row or successful installation alone cannot establish integrated attack readiness.

## 18. RustScan pilot in this architecture

Apply the existing RustScan plan as the capability design. This document supersedes its suggestion to rely only on the existing Homebrew install path for distribution; Homebrew remains an external-provider option.

Pilot deliverables: managed RustScan artifact, verified registry activation, `network_discover`, strict shared parser, Recon UI, preserved port/service history and explicit source-bound Nmap inspection. Resolve installed Nmap separately and record its identity. Do not bundle/fork Nmap as a prerequisite to proving RustScan.

Real task lab: at least three actual listener ports including unusual ports, known negative targets, IPv4/IPv6, no-open-result case, slow/timeout behaviour, stopping/restarting and multiple scoped hosts when lab networking is available. The listener/HTTP request ledger is the independent oracle. Multi-host limitations remain explicit if local hardware cannot establish that topology.

Model scenarios include natural discovery, selected-port preference, full-port explicit choice, readiness handling, exact source-bound inspection, empty/partial interpretation and denied scope expansion. For comparison benchmarks, standalone RustScan is compared to equivalent Nmap TCP discovery; Nmap service/scripts are measured separately.

Install/update/rollback acceptance downloads actual signed preview artifacts from the planned distribution path when authorised. Bad-hash/tampered-metadata cases use controlled negative copies; a synthetic installer is not real distribution evidence. Validate the final package in the actual installed Wixal app before promoting the pilot.

## 19. Rollback, withdrawal and incident handling

Differentiate compatibility failure from integrity/authority failure. A readiness failure leaves the previous active package selected. A later parser regression can propose a verified compatible previous package. Suspected compromise blocks new use; no silent fallback to another unverified external binary.

Authenticated withdrawal removes an artifact from new installation; revocation blocks new execution as policy specifies. Re-check revocations before new runs when online; offline state reports its last known status. Stopping a currently running process requires explicit incident policy and retains evidence of effects already performed.

Emergency catalogue corrections are new authenticated metadata versions. Never overwrite immutable payloads or erase original acceptance records. Key compromise procedures include freezing promotion, rotating trust, identifying affected digests, publishing authenticated status, retesting replacements and recovery rehearsal. Do not promise automatic repair for a compromised OS/user account.

Retention policy keeps current and one approved fallback per tool where practical, plus leased versions and evidence references. Garbage collection shows reclaimable size, excludes active/retained packages and never deletes external user installations. Offline recovery activates only already verified allowed artifacts.

## 20. Privacy, diagnostics and operational cost

Default evidence stays local. Package-host downloads expose ordinary network metadata to the host; the catalogue does not require a user account or upload project/model conversations. Any future telemetry is a separate product decision, with explicit controls.

Installation diagnostics record package IDs/digests, stages, error codes and timings. Task evidence may contain target addresses, source paths, headers or sensitive data; redact a diagnostic export and keep raw originals under current project ownership. No CI/public upload of user projects or credentials.

Budget release storage, download bandwidth, Mac runner time, model evaluation time, signing access and maintenance cadence. Track byte sizes and dependency closure per tool. On-demand tools reduce the initial application payload, not the eventual disk footprint of all installed packages. Avoid duplicated runtimes only where shared exact-version dependencies pass isolation/upgrade tests.

## 21. Retest and change-impact rules

| Change | Minimum rerun |
|---|---|
| Tool binary/source/package dependency | Final package checks, parser/adapter regression, real tasks, affected model suite and distribution lifecycle |
| Adapter/schema/parser | Contract and authority cases, actual tool tasks, model utilisation and affected installed UI |
| Catalogue/update/installer | Trust/transaction/recovery suite, clean download lifecycle and installed UI; representative existing tools |
| Model weights/quantization/runtime | Capability utilisation for advertised configurations; backend policy remains unchanged and tested |
| Routing/context/system instructions | Schema visibility, held-out utilisation, context pressure, denial and interpretation cases |
| Templates/advisory content | Content identity/freshness, effects/parser and representative interpretation cases |
| Shared runtime/process/permission code | Every affected capability's authority, execution, cancellation and evidence acceptance |
| Cosmetic UI | Relevant installed interaction/accessibility paths; broader model checks only if tool contract/context changes |

Reports become stale for changed tuple components. Reuse unaffected evidence with explicit provenance and rationale; do not rerun broad suites merely to inflate test counts. Scope exceptions cannot waive mandatory integrity or authority checks.

## 22. Implementation work packages and gates

| Phase | Work package | Exit gate |
|---|---|---|
| 0 | Finalize contracts, provider policy, pilot platform, distribution terms and trust custody | Reviewed decisions and complete mandatory scenario mapping |
| 1 | Package definition/build/release recipe and independent registry/installer | Real artifact install plus all trust/extraction/crash-recovery cases |
| 2 | Provider selection, execution leases and typed authority metadata | Existing external tools unchanged; new managed execution/policy gates passed |
| 3 | RustScan adapter, evidence projection, Recon UI and linked inspection | Real discovery/handoff/cancellation/persistence cases passed |
| 4 | Model evaluation harness and readiness-aware routing | Core model repeat/hold-out gates and correct unevaluated states |
| 5 | Authenticated update/rollback and clean installed-app pilot | Exact final-artifact and Finder/Dock identity evidence passed |
| 6 | Gradual tool onboarding and private-subnet extension | Per-tool/platform/model reports qualify each advertised capability |

Suggested new engine modules: `tool_registry.py`, `tool_catalogue.py`, `tool_packages.py`, `tool_contracts.py`, and the RustScan-specific `network_discovery.py`. Suggested future scripts: `managed-tools-acceptance.py`, `tool-model-evaluation.py`, `validate-tool-report.py`. These are proposed responsibilities/names, not implemented files.

Reuse the existing shared Tools view, project review UI, command sessions, investigation plans and package pipeline. Refactor large existing modules only where needed for these responsibilities. Keep Electron untouched and remain on the current 0.7.x policy unless a later user decision changes it.

Critical path: distribution/contract decisions -> real package transaction -> leased execution -> RustScan evidence -> model utilisation -> installed/distribution pilot. No credible fixed schedule until build/signing infrastructure and platform matrix are established.

## 23. Decisions to resolve before coding and publication

Recommended defaults are concrete but remain proposals:

- Pilot Apple Silicon; qualify the developer's current OS plus macOS 14 before claiming the declared minimum is supported for the tool.
- Public source/recipes and immutable release artifacts if the selected distribution terms permit; keep signing credentials/private operational configuration outside the repository.
- TUF client for authenticated updates; dependency packaging spike before integration.
- App-owned adapters initially; separately downloaded executable/content/workflow packages.
- Keep existing installation preference semantics; explicit provider migration with no user-program removal.
- Verify one primary real model and a small-model configuration before advertising AI readiness; choose exact models from the current installed catalogue at implementation time.
- Source-build RustScan if upstream artifacts cannot meet the required macOS/dependency/signing profile; fork only for a justified source change.
- Retain external Nmap until its distribution and package strategy are cleared.

Before publication, resolve signing/notarization availability, repository endpoint/control, key custody/recovery, supported OS hardware, per-tool distribution review and evaluation budget. These are planning gates, not requests to grant permission during this document-only task.

## 24. Definition of done and evidence limits

The first managed capability is ready when the actual installed app can acquire an authenticated compatible package, explain its readiness, execute it under enforced authority, retain attributable evidence, support correct qualified-model utilisation, update without affecting active runs and recover to an approved previous artifact.

All mandatory matrix cases for the advertised tuple pass; required skips block that claim. Final package/installed helper hashes match reports. Unsupported platforms/models/content and specialist setup remain explicit. Local acceptance, public package distribution and broad release readiness are separate evidence classes.

This document is not implementation or acceptance evidence. Proposed limits, APIs, thresholds and module names must be implemented and validated before promotion.

## Primary references

- **S1:** [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).
- **S2:** [The Update Framework specification](https://theupdateframework.github.io/specification/latest/).
- **S3:** [Python TUF Updater documentation](https://theupdateframework.readthedocs.io/en/latest/api/tuf.ngclient.updater.html).
- **S4:** [Apple Developer ID distribution](https://developer.apple.com/developer-id/) and [customizing notarization](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
- **S5:** [Nmap published source licence](https://nmap.org/npsl/).
- **S6:** [GitHub build artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).
- [RustScan released CLI options](https://github.com/bee-san/RustScan/blob/2.4.1/src/input.rs) and [startup/output handling](https://github.com/bee-san/RustScan/blob/2.4.1/src/main.rs).

External references support their named mechanisms, not Wixal compatibility claims. Implementation must recheck relevant upstream versions/documentation before selecting dependencies or publishing packages.
