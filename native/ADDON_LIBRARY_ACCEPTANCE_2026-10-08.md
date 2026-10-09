# Native programs and workflow library — 8 October 2026

## Delivered

Cybersecurity → Tools & skills opens the native library with Catalogue, Workflows, Activity and Automation views. The regular Tools drawer links to the same library. There are ten curated program entries and four bundled instruction packs. Program detection, structured integration and specialist setup are shown separately.

Models discover `addon_catalog`, `addon_discover`, `addon_install`, `addon_job`, `addon_run` and `addon_workflow` through the existing progressive schema system. Workload selection remains a model decision. A pack installs loadable skill instructions; existing agent skill selection and workflow authoring remain available.

The controller installs exact Homebrew core/cask identifiers through argument arrays, records source, reason, process output, exit status and readiness, serialises installations, and supports cancellation. Restart marks uncertain jobs interrupted rather than replaying them. Job reads enforce owner and conversation identity. Read-only and isolated branches cannot install packages; read-only tasks cannot stop installations.

Automatic installation defaults on for this new library, following the request for self-sufficient tool setup. It is editable in Automation and applies to curated core formulae only. Casks and newly researched candidates use existing action review. Task target scope and execution review remain separate from installation policy.

Additional named Homebrew core formulae can be researched into candidates using actual registry metadata. Candidate installation stays pinned to the core registry; it cannot install an arbitrary tap, URL or model-authored shell recipe. Candidates use the existing command system until a dedicated adapter is provided. Unsupported official installers, privilege changes and specialist setup are not automated.

Structured execution adapters cover ffuf, selected signed Nuclei templates, saved-capture TShark analysis, Trivy filesystem assessments, OSV source scanning and testssl TLS review. Nmap retains its existing adapter. Program jobs use the existing owned command lifecycle and output retention. Installed adapters appear directly in investigation plans with pinned target/path and adapter identity. Investigation execution waits for actual process completion and retains an evidence excerpt for subsequent AI analysis. ffuf observations become route inventory.

ZAP, mitmproxy and Metasploit entries explicitly retain specialist setup status. No unrestricted exploit session or invisible certificate/capture privilege configuration was added. Nuclei requires a selected signed project template and disables external interaction callbacks; it does not run the entire template collection.

## Validation

Focused tests cover registry identifier rejection, workflow idempotency, declined installation, installer process lifecycle and pinned arguments, conversation isolation, read-only boundaries, target scope, project paths, automatic installation and cancellation. Existing chat/agent/security record tests were also run. The focused combined suite passed 28 tests.

Real acceptance checks actual Homebrew metadata, a real OSV-Scanner installation and executable verification, actual ffuf against two loopback routes, the investigation queue adapter, actual TShark against an explicitly synthetic capture, actual OSV scanning of Wixal's dependency files, loadable workflow persistence and real Qwen3 1.7B tool-based catalogue discovery. Fixture tests and synthetic packet content are distinct from real program execution. Model discovery does not establish autonomous reasoning quality across all workloads.

Reports: `artifacts/native/addon-library/source.json` and `packaged.json`. The initial real installation's durable audit record remains in the isolated acceptance workspace. Subsequent runs verify the existing installation. The source run passed all nine cases before the final output-parser refinement; final packaged status is recorded separately below.

## Installation

The final alpha bundle is installed at `/Applications/Wixal.app`; no public release was performed. Installation verified the code signature and matching packaged/installed executable, helper and Info.plist bytes. The previous bundle is retained at `/Users/jhye/Library/Application Support/Wixal Release Backups/20261008-175415/Wixal.zip`.

The final packaged acceptance passed all nine cases. Its helper SHA-256 matches the installed helper: `b803a32ae52d8b9fcadce5256c5e7c5054f29a47f6dc258d4e75d7694ca95e9e`. Installed executable SHA-256: `b3d0302747eaad79984057d0ee259e407be55f009e841f1dc3343f0aaeaae43a`.

Live native inspection verified catalogue layout and installed detection, actual Nmap version verification, automatic-install policy enabled, installation of the website workflow into the skill library, and additional `jq` discovery from registry metadata with an existing executable detected. `jq` was not installed by this check. OSV-Scanner was installed during isolated real acceptance; the other detected tools were already present. Final wording distinguishes dedicated adapters, generic command integration and official installers.

The combined suite passed 28 tests; after the final presentation changes, all six add-on unit tests passed again. Real-model acceptance verifies tool-based catalogue discovery. The actual installer and assessment adapters were exercised separately; this does not establish that every model can autonomously research, install and complete every security workload.
