# Decepticon attribution

Wixal adapts the CVSS arithmetic from BitterSecurity/Decepticon at revision
`d6bfd87ad9f910cfff715da04c804638990a8538`, Apache License 2.0.
Source: https://github.com/BitterSecurity/Decepticon/blob/d6bfd87ad9f910cfff715da04c804638990a8538/packages/decepticon/decepticon/tools/reporting/cvss.py

Copied path: `native/engine/wixal/security_cvss.py`.
Changes: remove LangChain tool dependency; require the exact CVSS 3.1 prefix;
reject duplicate and empty metrics. Other engagement code and skill text are
Wixal implementations informed by the architecture review, not a bundled
Decepticon runtime or payload collection.

Full licence: `LICENSE` in this directory and packaged
`wixal/resources/DECEPTICON-LICENSE.md`.

CVSS is owned by FIRST.Org, Inc. and used by permission.
Specification: https://www.first.org/cvss/v3.1/specification-document
Scores are retained with their vector and version; scoring is separate from verification.

## Native cyber adaptation, 13 October 2026

Reference revision: `00fc3b594c40f6e48e22341669cf7048c117781f`.
Reviewed reporting/finding_quality.py, finding_epistemics.py, finding_dedupe.py,
SARIF/report/export/timeline utilities, research/chain.py, engagement planning,
selected assessment and methodology skills, the bash session wrapper,
Blue Cell collection/coverage documentation and REA/Ghidra evidence contracts.

The cyber.py, cyber_findings.py, cyber_reports.py, cyber_planning.py,
cyber_sensors.py and cyber_tools.py modules, native Cyber toolkit view and
thirteen additional cyber procedures are original Wixal implementations
informed by this review. They use Wixal storage, controller, approvals,
model-tool discovery and evidence identities. No additional Decepticon
runtime modules, LangGraph, Neo4j, payload corpus or specialist container
images are bundled. Static triage never executes the binary; imported
analysis remains an external assertion bound to selected source bytes.

The original CVSS adaptation and its source revision above are unchanged.
Decepticon's own Apache-2.0 licence is retained. External corpora and analysis
engines retain their separate licences and are not redistributed here.
