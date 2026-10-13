# Native cyber adaptation from Decepticon

13 October 2026. Local implementation on the existing 0.7.x native app line.

A subsequent completion pass adds PDF/Word exports, verified ZIP import, real offline Ghidra, sensor lifecycle controls and actual LAN checks. See [the completion evidence and remaining gaps](decepticon-cyber-completion-2026-10-13.md). The implementation limits and test counts below describe the earlier pass.
Upstream reviewed: BitterSecurity/Decepticon at
`00fc3b594c40f6e48e22341669cf7048c117781f`.

## Implemented behavior

Wixal retains its SwiftUI interface, Python service, SQLite workspace,
JSON-line IPC, existing operation controller and action reviews. The new
modules implement compatible Decepticon reporting, methodology, planning,
defensive observation and static-analysis patterns behind those boundaries.
The existing attributed CVSS arithmetic remains the only directly adapted
Decepticon source utility. No additional upstream runtime modules are copied.

- `cyber_read` discovers exact project engagement IDs, reads redacted/paged
  retained evidence, examines report quality and duplicate suggestions,
  ranks candidate paths, checks planning, inspects operation recovery,
  reads local sensor health/leads and discovers configured analysis tools.
- `cyber_manage` saves revisioned finding drafts, computes severity, checks
  report completeness, records capability-specific retests, saves planning,
  exports deliverables, installs reviewed procedures, manages explicitly
  enrolled local log sources and retains source-bound static analysis.
- Finding drafts require description, impact, assumptions, counterevidence,
  confidence rationale, severity-change conditions, remediation, retest plan
  and retained evidence. Edits retain bounded history and invalidate old
  disposition/verification metadata. Report completion never confirms a
  vulnerability. Duplicate candidates are never silently merged.
- Retests bind finding revision, target, objective, scope and independently
  retained validation records. Only declared checks may be described as
  passing; model prose and generic scalar comparisons cannot close a finding.
- The existing graph now ranks candidate paths transparently by unresolved
  inferred relationships and path length. Recommendations include missing
  prerequisites and stop conditions. No path executes an action.
- Nine planning fields create one versioned dossier: threat profile,
  acceptance criteria, deconfliction, contacts, data handling, abort conditions,
  deliverables, retention and retest criteria. Scope changes mark it stale.
- Deliverables include technical and executive Markdown reports, planning,
  SARIF, event timeline, engagement JSON and a portable ZIP/hash manifest.
  Evidence copies are explicitly selected, redacted derivatives. Private
  originals and exported derivatives have separate hashes. Exports use
  fixed members and never walk/bundle the project directory. Automatic
  redaction is limited; client content still needs operator review.
- Thirteen additional original Wixal assessment procedures complement the
  five existing role packs. Each new procedure records the upstream review
  revision and adaptation provenance; none grants execution authority.
- Three additional read-only analysis roles (defensive analyst, binary
  analyst and remediation reviewer) complement the five existing specialists.
  Sensor/binary specialists receive only role-appropriate target- and
  scope-bound evidence with original hashes, not arbitrary workspace context.
- Local log collection requires explicit source enrollment and start review.
  It collects complete file records into retained batches, creates unverified
  incident leads and reports malformed records, rotation, truncation and
  coverage limits. Starts last at most ten minutes; collection is capped at
  sixteen MB per source, sixteen enrolled sources per engagement and eight
  concurrent monitors. Scope/project changes revoke collection. Restart
  leaves monitoring paused. It neither blocks traffic nor changes services.
- Existing reviewed PTY command sessions gain unchanged-output detection.
  Quiet output is ambiguous; the controller neither sends input nor kills or
  replays a command automatically. Existing ownership, input review and
  process-group cleanup remain in force.
- Static binary triage hashes a selected bounded file and records headers and
  strings without execution. External analysis imports must identify their
  provider and match the selected binary SHA-256. REA/Ghidra tools remain
  explicitly configured external MCP providers with their own review.
- Cyber toolkit native controls are available under Cybersecurity →
  Engagements → Cyber toolkit. Existing attack paths and specialist controls
  expose the enhanced ranking and roles.

## Intentional integration limits

This implementation adapts compatible product behavior; it does not install
Decepticon's complete framework. It adds no Neo4j, LangGraph, Caddy/Fluent Bit
stack, payload corpus, Sliver/C2, BloodHound, cloud credentials or new arbitrary
shell capability. Live monitoring covers enrolled project files, not all
machine/network traffic. Reverse engineering beyond native triage requires a
separately configured engine. The existing isolated Linux worker remains
bounded to its supported typed scan profiles.

Model tools, prompts and skills are integrated; model weights are not trained
or modified. Upstream benchmarks do not qualify Wixal or a local model.
Production tool-catalogue signing, general model qualification, cloud/AD/C2
execution and distribution/notarisation remain separate work.

## Reproduction and evidence

Meaningful regressions live in `native/tests/test_cyber.py` and the existing
interactive-session, engagement and assurance suites. The full native engine
suite is run with:

```sh
PYTHONPATH=native/engine native/.venv/bin/python -m unittest discover -s native/tests
```

`native/scripts/cyber-acceptance.py` exercises actual local-model tool calls,
actual local log collection, source-bound specialist analysis, portable report
hashes and helper restart through production JSON-line IPC. It requires an
explicit existing local model and loopback endpoint; it downloads no weights.
Source, packaged and installed results remain separate evidence classes.

Actual packaged-model validation exposed a reasoning-only response being marked
completed by the existing analysis queue. Evidence-only analysis now uses bounded
optional thinking, retains a failed first attempt, permits one conclusion request,
and fails visibly if the final answer remains empty or contains unsupported tool
calls. Regression cases cover empty responses, successful bounded continuation
and non-executing rejection of analysis tool calls.

Validation artifacts for this change are under
`artifacts/native/cyber-adaptation-2026-10-13/`. Failed/intermediate attempts are
retained separately from frozen final results. See the machine validation
summary in that directory for exact counts, hashes and runtime limitations.

Attribution: `native/third_party/decepticon/NOTICE.md`; licence and provenance
are also embedded in the helper resources.

## Final local validation

- 555 engine tests passed on the final source, including the new cyber and
  analysis-completion regressions.
- Native release build, packaged and installed strict signature checks passed.
  The installed source manifest matches all 159 recorded source entries.
- The installed helper passed seven actual Qwen3.5-9B local-model cases:
  discovery, planning, finding draft, report export, defensive lead review,
  defensive specialist analysis and binary specialist analysis.
- Helper restart preserved finding, incident and evidence counts and left
  scope and monitors paused.
- Native UI checks exercised finding validation, report export, planning
  validation and analysis-provider readiness in isolated synthetic state.
- Temporary model serving and the disposable GUI session were stopped.

The final evidence summary is
`artifacts/native/cyber-adaptation-2026-10-13/validation.json`.
The canonical installation is `/Applications/Wixal.app`. Existing app backups
are retained by the native installer. This local build remains
`0.7.10-alpha.6`; no public release was published by this task.
