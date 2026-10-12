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
