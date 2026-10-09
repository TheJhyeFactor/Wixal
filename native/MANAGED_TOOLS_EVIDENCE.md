# Managed acceptance evidence

The 104-family contract is retained in `tools-distribution/acceptance-suite.json`.
`scripts/managed-acceptance-matrix.py` checks normalized envelopes against every
family. Missing classes, absent cases, failed outcomes and another configuration
remain explicit. Release gates can be deferred with `--exclude-gate release`;
this always leaves `releaseQualified` false.

An envelope contains an exact `identity` and a `cases` list. Each case supplies
its family `id`, terminal `status`, `evidenceClasses`, and retained evidence files
with paths relative to the evidence root and SHA-256 hashes. Hashes are checked
against actual files. Combining evidence from another package revision, helper,
adapter, source manifest, platform or model configuration is rejected.

`MOD-15` requires both `naturalDiscovery` and `sourceInspection`, each with
exactly attempts 1 through 30 and at least 29 successful outcomes. Failed
attempts must stay in the report with their evidence. Critical fabricated
success or unauthorized effects block qualification regardless of the count.
Other mandatory families require all submitted outcomes to pass and every
specified evidence class to be present.

For the completion harness, `scripts/managed-completion-evidence.py` exports
measured RustScan claims from completed core/lifecycle reports and optional
prerequisite reports. It verifies that the reports refer to the supplied app's
actual helper. It deliberately keeps partial families partial: a backend
cancellation does not supply installed UI evidence, and one source-file read
does not establish all context-pressure cases. Other tools and installed GUI
runs require their own reviewed envelopes.

Example, after the runs have completed:

```sh
native/.venv/bin/python native/scripts/managed-completion-evidence.py \
  --evidence-root artifacts/native/managed-tools-completion \
  --app release/native/completion/Wixal.app \
  --core artifacts/native/managed-tools-completion/packaged-handles-final/report.json \
  --lifecycle artifacts/native/managed-tools-completion/lifecycle-final/report.json \
  --prerequisites artifacts/native/managed-tools-completion/model-prerequisites-final/report.json

native/.venv/bin/python native/scripts/managed-acceptance-matrix.py \
  --identity artifacts/native/managed-tools-completion/normalized-completion/identity.json \
  --claims artifacts/native/managed-tools-completion/normalized-completion/claims.json \
  --evidence-root artifacts/native/managed-tools-completion \
  --exclude-gate release \
  --output artifacts/native/managed-tools-completion/normalized-completion/matrix.json
```

The example intentionally references the preserved build used by the long model
run. A subsequently installed helper cannot inherit that build's model results.
The report is an acceptance inventory and does not publish a release or grant a
model badge.
