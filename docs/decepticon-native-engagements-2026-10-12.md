# Native red-team engagements: implementation and validation

12 October 2026 · Development preview · Native SwiftUI/Python

## Implemented

Wixal now has a persistent engagement layer over the existing investigation queue. Cybersecurity opens an Engagements view, with Investigations and Agents still available. The engagement owns an objective, target set, versioned scope, approval receipt, objectives/hypotheses, evidence-linked relationships, restricted specialist assignments, operation receipts, observation checks, cleanup and report exports.

Scope includes directly supported capabilities, destination exclusions, a bounded testing window, a run budget and per-run deadline. Contacts/deconfliction, threat profile, evidence handling and abort conditions are retained descriptive fields; prose is not interpreted as an automatic policy. Scope approval always requests explicit operator review, independently of project bypass. Every actual action still follows the project's action-review setting. Scope revisions revoke approval and stop owned queued/running work. Approval checks are repeated after asynchronous review and at queue commit/dispatch. A complete plan exceeding the remaining run budget is rejected before any member is queued.

Existing unbound investigations preserve their historical behaviour and evidence; migration does not invent approved engagement scope for them. A target belongs to at most one open engagement. Generic shell commands, arbitrary custom contracts, external autonomous controllers and automatic research-provider calls are not allowed inside the new engagement envelope. The current scoped capabilities are native website/network observations, local simulations, project software inventory, evidence analysis/planning and the optional typed Linux scan adapter. Tool readiness and scope permission are separate catalogue states.

HTTP assessment connections resolve and check destination exclusions, pin the selected address and preserve the original TLS hostname. Redirects remain unfollowed. Nmap and discovery use checked resolved destinations. Local simulations have a separate context bound to the exact disposable loopback fixture; they do not become evidence about the selected live target.

## Evidence, planning and specialists

Successful engagement runs retain bounded exact JSON snapshots in private content-addressed files. Records carry SHA-256, size, source run and ownership. Reads and verification recheck the digest; results are paged without repeating the original operation. JSON artifact import retains inert external-untrusted evidence inside the selected project, with no archive extraction or controller invocation.

Objectives carry hypotheses, expected observable signals, prerequisites and scope revisions. Explicit replacement retains the earlier objective as superseded. Superseded objectives cannot be resurrected, and a new scope cannot close successfully using completed objectives from an earlier scope. Relationships link actual engagement targets, observations, findings and objectives with evidence IDs, rationale and inferred/observed/disproved states. Candidate-path search is bounded to six hops, twenty returned paths and five hundred expansions. It does not execute a path or establish access.

Five specialist roles run through the existing serial model queue: planner, recon analyst, researcher, verifier and reporter. Each receives selected retained target evidence and an explicit question. It has no tool execution, network, credential or parent private-context channel. Its response remains analysis, not independent verification. Five optional text-only skill snapshots provide corresponding procedures and assignment templates; loading them grants no authority.

The observation evaluator requires two distinct collected Wixal run records from comparable target/capability/profile/environment/scope identities. It evaluates an explicit type-sensitive scalar signal and rejects simulated/external/model-analysis inputs. A discriminated observation can satisfy its associated observation objective. It cannot automatically mark a finding confirmed or demonstrate exploit truth. Capability-specific exploitation validators remain separate work.

The CVSS 3.1 utility computes base/environmental scores from a validated vector. Findings retain the vector, version, score and rationale together. Scoring marks the finding for review and does not confer verification. This arithmetic is selectively adapted from Decepticon under Apache-2.0, with stricter version/duplicate/empty metric parsing and no LangChain dependency.

## Operations, recovery, cleanup and reporting

Runs retain engagement/scope/environment identity, their existing session, outputs and effect state. A restart pauses running engagements, revokes scope approval and never replays uncertain operations. Interrupted effects remain unknown. Ordinary completion requires completed current objectives and reviewed cleanup; unknown runs require explicit linked reconciliation. An operator can close incomplete with a reason while preserving unmet work.

Cleanup items record pending, accepted or operator-evidence-reviewed dispositions. The review method is explicit; manually reviewed cleanup is not a deterministic target-state validator. Stopping an operation does not imply target cleanup. JSON/Markdown exports use unique filenames and include scope history, objectives, findings, verification records, evidence identities, relationships and limitations.

## Optional Linux worker

See [worker setup and boundaries](../native/worker/README.md).

The adapter supports a locally built `wixal-security-worker:v1` image on a local Docker Linux daemon. The native app neither installs a runtime nor pulls/builds an image during a run. Readiness is inspected explicitly. Each operation additionally reviews the immutable image ID and exact resolved address/port contract, then creates a dedicated labelled network/container with resource limits, no host mounts and no Docker socket mount. A trusted bootstrap applies a default-drop nftables policy before unprivileged Nmap starts. A failed policy application starts no scan. Only typed ports/services scans are supported; there is no arbitrary command or exploit execution surface.

Saved ownership labels protect cancellation/cleanup. Unacknowledged environment cleanup becomes a retained cleanup requirement. The adapter rejects host loopback/link-local targets rather than silently changing their meaning inside a container. Container teardown establishes environment cleanup only, not removal of target-side effects.

**Qualified boundary:** a dedicated Colima Linux VM was created to complete validation. Both source and packaged helpers passed actual nftables allow/deny checks, a typed scan against an owned lab service, cancellation and labelled container/network cleanup. The worker entrypoint bytes in the image match the reviewed source. The VM has no host-directory mounts and did not become the default Docker context. It is stopped after acceptance. This qualifies the tested ports profile and image/runtime identity, not arbitrary images, service-probe coverage, exploitation or a multi-tenant platform. The capability remains unavailable until an operator explicitly configures/inspects the runtime and approves its scope. The optional image is not bundled or published.

## Upstream provenance

Reference revision: [BitterSecurity/Decepticon d6bfd87ad9f910cfff715da04c804638990a8538](https://github.com/BitterSecurity/Decepticon/tree/d6bfd87ad9f910cfff715da04c804638990a8538).

Copied utility: `packages/decepticon/decepticon/tools/reporting/cvss.py` → `native/engine/wixal/security_cvss.py`. Changes and full licence are retained under `native/third_party/decepticon/`, embedded engine resources and application notices. Engagement code and skill text are Wixal implementations informed by the review. The Decepticon framework, payload corpora, provider fallback and research telemetry are not dependencies of this implementation. CVSS is owned by FIRST.Org, Inc. and used by permission; [specification](https://www.first.org/cvss/v3.1/specification-document).

## Validation artifacts

The separate development app is `artifacts/native/decepticon-engagements/Wixal Engagement Preview.app`. It uses isolated preview data and the configured local Ollama endpoint. It is ad-hoc signed development software, not a new public release or a notarised distribution.

- Focused regressions: `native/tests/test_engagements.py` and `test_security_worker.py`.
- Packaged real-model acceptance: `native/scripts/engagement-acceptance.py`.
- Actual acceptance output: `artifacts/native/decepticon-engagements/packaged-real-model-final-local/results.json`.
- Actual Linux source and packaged acceptance: `artifacts/native/decepticon-engagements/linux-source/results.json` and `linux-packaged-final-local/results.json`.
- Aggregate validation: `artifacts/native/decepticon-engagements/validation.json`.

Acceptance uses an owned loopback HTTP service with independent server records, the packaged helper and actual installed local weights. It evaluates approval gating, positive/baseline observations, path provenance, specialist inference, skill snapshots, external-untrusted import, report export and restart recovery. Linux execution qualification is reported separately. See the final validation JSON for actual results rather than inferring success from this procedure description.

Final validation: 453 engine tests passed (36 new regressions), release-mode Swift build passed, five packaged `gpt-oss:20b` acceptance groups passed, and three Linux runtime acceptance groups passed through both source and packaged helpers. The native UI was inspected at its 920 × 640 minimum content size, including saved evidence and draft creation. Final source/signature identities are recorded in the aggregate validation JSON.
