# Reviewed security workflows in Alpha 6

Use these features only within an engagement whose targets and capabilities are authorised. The native cybersecurity assurance view exposes API identities, OAuth, API mutations, mutation-state validation, telemetry imports and external controller proposals.

## API identities and mutations

Create a short-lived identity lease for a selected target. Choose bearer, cookie or OAuth access token; the secret belongs in the secure field and is stored in macOS Keychain. Lease metadata may be retained in the workspace, but credentials must not be embedded in task prompts, evidence files or imported plans. Cookie values use a bounded `name=value` header format.

Observe the exact API path before changing it. For a mutation, select POST, PUT, PATCH or DELETE, enter the path and a JSON object body, then queue the operation. Review the exact action. Mutations never inherit a blanket action bypass. Responses retain bounded, redacted observations and hashes; network operations stay within the approved origin and scope.

To validate a state change, retain an independent baseline observation, execute the reviewed mutation, and retain a new observation. Select the completed mutation and configure the read path, JSON pointer and expected scalar before/after values. The validator checks evidence identity, scope, timing and exact values. Independently restore and verify the original state when cleanup is required.

## OAuth PKCE

Configure a public-client ID, scopes and same-origin authorization/token paths. Start the reviewed flow and open its authorization link. Wixal uses an ephemeral loopback callback, state checking and S256 PKCE. A flow expires after five minutes; a successful access token becomes a bounded lease. No client secret or refresh-token lifecycle is implemented. Identity-provider compatibility outside the tested local fixture is pending.

## Interactive commands

`command_start` supports `interactive: true` for a reviewed, project-owned command. `command_write`, `command_read` and `command_stop` operate on that job under existing ownership and review rules. Input is bounded, cancellation stops the process group, and a running session can preserve shell/program state across tool calls. Engine restart does not restore a live PTY. Commands run with the user's account access and must be reviewed accordingly.

## External proposals

Import a project-local JSON file with `name`, `targetId` and `nodes`. The import creates an inert draft. Review the resulting plan before separately requesting execution; Wixal rechecks its source evidence, target, scope revision and bounded node plan. Editing or replacing the proposal cannot silently alter the reviewed plan. Live external-controller protocol and approval forwarding integrations remain future work.

## Vendor telemetry

Import a project-local Suricata EVE or Zeek JSONL file, select the operation and declare coverage start/end times. Wixal retains the source evidence and normalises matching observations. A match requires the literal destination IP, port and time window; a hostname is not automatically mapped to an IP. An absence of matching telemetry is not proof that an operation was undetected, particularly with incomplete sensor coverage. Real deployed-sensor qualification remains pending.

## Evidence boundaries

The Alpha 6 automated suite covers controlled local fixtures. Six-model tool/coding/long-task/red-team qualification and installed-app end-to-end acceptance of these new flows are pending. Remote-worker and AD/cloud tests remain deferred. Review [release notes](release-0.7.10-alpha.6.md) before treating any capability as operationally qualified.
