# Native investigation workflow v2 — 8 October 2026

## Delivered implementation

The native cybersecurity section now opens Investigations by default. Its security agent entry point uses the same target, inventory, research and plan records.

- Target search, project-scoped objectives/notes, archive/restore, parent device promotion and persisted default/stage model preferences.
- Discovery inventory for hosts, services, observed website routes/form inputs and software dependency declarations. Each observation retains its source run and change history. Input values and query values are omitted from form inventory.
- Consolidated findings with independent review states, notes, source runs, simulation labels and retest review indicators.
- Research fetches up to three returned or supplied sources through the existing reviewed HTTP tool. Source excerpts, status, hashes, truncation, errors and applicability rationales are retained. Automatic research uses observed products/versions or existing references; missing identification remains a visible evidence gap.
- An investigation controller queues recon, research and a schema-constrained AI planner. Proposed plans are saved as editable drafts, not treated as verified exploit outcomes.
- Native chain studio with a dependency graph, structured step editor, multiple prerequisites, evidence conditions, per-step models, explicit discovery bindings, advanced JSON, reusable templates and plan stop/retry controls.
- All dependencies must complete; matching open-port/HTTP-status/finding evidence can unlock a branch. A mismatched condition skips it. Conditions use originating prerequisite observations rather than unrelated latest results.
- Capability registration connects installed tools, their actual schemas, target binding, defaults and instructions to investigation execution. Execution continues to enforce enabled tools and existing project review settings.
- Software inventory reads bounded package.json, requirements.txt, pyproject.toml, Cargo.toml and go.mod declarations. It does not equate declared ranges with installed versions.
- JSON and Markdown report export writes unique files with findings, evidence, research, plans and audit history.
- AI context uses compact structured evidence, source IDs, explicit evidence selection and a model context budget rather than recursively including prior source bundles.

## Validation

The broad native regression suite passed 189 tests in 69.917 seconds during implementation. After the final backend refinements, 24 focused security, record and website tests passed in 8.298 seconds. These include fixtures and should not be confused with the actual model/tool checks below.

Real acceptance covers actual loopback Nmap and HTTP assessments running concurrently; real Gemma 3 1B inference; retrieved source excerpts; a schema-constrained model proposal saved as a draft; the actual Wixal package.json dependency inventory; and a plan containing parallel steps, a dependency join and an unmatched branch. It also exports real report files. See artifacts/native/security-workspace/acceptance.json for execution mode, helper hash and individual cases.

An early real-model check failed because the small model copied repeated evidence into its arguments. That output was rejected and retained. Capability-specific output schemas resolved the tested malformed-plan case. A syntactically valid plan or nonempty model response does not establish reasoning quality.

Live native checks verified migration of the earlier loopback run into inventory, draft and template saving, actual plan execution against TCP port 1, a completed first step and correctly skipped dependent step, target note persistence, archiving the last active target and recovering/restoring it without losing results. The visual review identified and corrected graph card sizing; raw inventory JSON is now collapsed behind technical evidence.

## Practical limits

The connected workflow is a bounded first investigation pass followed by editable proposed checks. It is not an unrestricted autonomous exploit loop. It supports registered installed tools; no new specialist exploit, privilege escalation, authenticated browser or binary/runtime analysis tools were installed in this change.

Source retrieval does not automatically prove advisory applicability. Applicability remains an explicit evidence-backed review decision. Some scanners can return uncertain classifications such as tcpwrapped; these are not product identification or a vulnerability.

Local inference is serialized, tool execution has 1–4 slots, and some workspace execution changes remain blocked while security work is pending. Templates with target-specific bindings must be made generic before reuse. Reports are JSON/Markdown; PDF report layout and external issue tracking are not included. Context budgeting uses the existing token estimator. Further testing on representative authorised device/server/network labs and model reasoning evaluations remains necessary.

## Installation state

The final development bundle was installed at `/Users/jhye/Applications/Wixal Native.app` at 10:40 Sydney time. The previous bundle was retained at `/Users/jhye/Applications/Wixal Native previous 20261008-104026.app`. Installation verified the code signature and matching packaged/installed executable, helper and Info.plist bytes.

The final packaged acceptance run passed all six cases. Its helper SHA-256 matches the installed helper: `784a9ea1a11a5a2c64702cf87fb453200cd41aca6a6afa40ec92c6628efaf300`. The installed native executable SHA-256 is `301b094eb3be87f55a0bc6ae5679b1dbe9f6340911dbf876d26f10d2971aef04`.

After installation, live native inspection confirmed that the saved completed plan and template survived, the graph cards and dependency arrow display without stretching or clipping, and inventory opens with concise summaries and collapsed technical evidence/history. The app was left on Cybersecurity → Investigations → Recon → Inventory, with no active security runs. This is a local development preview, not a published release.
