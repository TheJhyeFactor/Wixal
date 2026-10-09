# Managed tools preview distribution

The controlled source/build repository is now [TheJhyeFactor/wixal-tools](https://github.com/TheJhyeFactor/wixal-tools). It records exact source pins and license-file hashes for the eleven existing tools, links their controlled forks, retains the 104-family release contract, and builds unsigned RustScan candidates from vendored pinned source. Inherited workflows on the forks are disabled. Immutable releases are enabled on the central repository for future qualified promotions. These source/build contracts do not configure an approved download catalogue in the application.

Executable profiles cover standalone RustScan, ffuf, Nuclei, Trivy and OSV-Scanner on Apple Silicon. The native engine owns adapters, readiness procedures and parsers. A catalogue cannot supply executable Python/Swift integration code, installer commands or environment settings. Controlled Go candidate recipes and workflows are configured in the source repository.

`managed-preview-repository.py` creates a signed local TUF repository with two package revisions of a real supplied binary. It requires an explicit source commit, licence and separate key directory. It records the original binary digest and optional Homebrew receipt. This is a local repack recipe, not proof of a reproducible source build. No production keys are generated or published by application packaging.

Run it with an output under `artifacts/`, and keep signing keys outside the served directory. Serve only the repository on loopback. `package.py --development --managed-repository <client.json>` embeds its configuration and public bootstrap root in the helper resources and records their hashes in `TOOL_TRUST_MANIFEST.json`. Preview endpoints are rejected for alpha/production builds.

Ordinary builds without that option retain external providers and explain that managed downloads are unconfigured. There is no default download endpoint that learns its own trust key.

The registry is per OS user under `~/Library/Application Support/Wixal/ManagedTools`. `WIXAL_MANAGED_TOOLS_ROOT` selects an isolated registry for tests. Project records retain invocation/evidence references; shared packages confer no scan authority. Updates retain immutable old payloads, leases block removal, and historical descriptor records survive removal. Explicit provider selection never removes Homebrew binaries.

The catalogue schema is validated by `wixal.managed_tools.descriptor`. This preview permits one dependency-free Mach-O binary and required licence/provenance files, authenticated exact artifact sizes/digests, known readiness/adapter identities, explicit tested OS versions and allowed app versions. Additional executable/runtime profiles are rejected until their contracts are implemented and tested. Existing Nmap, ffuf, Nuclei, TShark, Trivy, OSV, testssl and specialist providers retain their existing integrations; they are not newly certified managed distributions.

Publication is a separate promotion step. The controlled repository includes candidate recipes and offline catalogue signing, assembly, root rotation and gated promotion verification. The public trust and independent custody contract remains unconfigured at the user's request. Local preview roles use one operator and do not establish production custody. The fetcher permits at most four explicitly allowlisted redirects without forwarding credentials; GitHub's signed query parameters are permitted only on named HTTPS asset hosts after a reviewed redirect.

See [implementation and acceptance status](../MANAGED_TOOLS_IMPLEMENTATION_STATUS.md) for executed evidence and the uncompleted release gates.
