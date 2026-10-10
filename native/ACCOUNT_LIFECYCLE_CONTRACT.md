# Account and connection lifecycle acceptance contract

This contract describes the current production APIs. Source/protocol regressions and a real disposable-account run are separate evidence. No real account was created, changed or deleted while preparing this contract.

## Wixal account

The native account uses configured Firebase email/password APIs. Creation requires a display name and a password of at least ten characters. Email verification gates cloud preference/memory operations. Session tokens belong in the macOS Keychain; passwords do not belong in saved workspace state or acceptance reports.

Sign-out clears the saved sign-in and active cloud presets/global memory. Local projects and conversations remain on the Mac. Signing out is not a remote account deletion or a local-history erasure. Guest preferences resume separately from the signed-in account preferences.

Password change reauthenticates the current email/password and checks the returned identity before changing the online password. New session credentials are saved to Keychain. If the online change succeeds but Keychain saving fails, the current session and explicit repair message are retained. Acknowledging a password-reset API request does not prove mailbox delivery.

Online deletion requires a signed-in account, the current password, matching reauthenticated identity and the exact `DELETE` confirmation. Owned cloud presets and cloud global memory are deleted before the online identity. This is not an atomic transaction: confirmed cloud deletions can precede an error. Local projects and conversations remain on the Mac. Keychain cleanup failures after a confirmed online deletion are reported separately.

## Connection credentials

Remote MCP OAuth uses the provider's authorization-code/PKCE flow, an actual loopback callback and per-workspace/per-server Keychain storage. Client metadata and access/refresh credentials are distinct. Ordinary disconnect and reconnect can reuse an authorized session; deleting the MCP connection clears its OAuth vault. Live provider revocation/expiry must be tested with that provider, not inferred from a fixture callback.

Contributor GitHub reporting has a separate Device Flow session. Its tokens/device codes are process-local and are cleared by reporting sign-out, account transition checks or helper termination. It requires its registered public client ID and explicit report review; Firebase sign-in does not authorize GitHub submission.

## Disposable-account run

Use a disposable account and mailbox selected by the owner. Record the app/helper identity, provider configuration, test-device identity and a non-secret account alias. Retain statuses and independent outcomes without including passwords, device codes, tokens or Keychain contents.

1. Create/sign in, verify email, save cloud preferences and memory, quit/reopen and check the restored identity.
2. Cancel sign-in and revoke/expire a provider session. Confirm connection status agrees with actual permitted calls and stale credentials do not authorize new work.
3. Switch between two disposable identities and guest use. Check active preferences, scoped memories, conversation ownership, connection state and saved reports against the retention policy above.
4. Change the disposable password and confirm old/new authentication behavior and restart restoration. Exercise a controlled Keychain failure separately from the live online change.
5. Interrupt deletion between cloud records, before identity deletion and after the request is sent. Retain confirmed removals and distinguish unknown remote outcomes. Never automatically repeat a destructive request after a lost response.
6. Delete only the designated disposable account. Independently verify the remote outcome, local record retention, correct sign-out state and credential cleanup. Source fixture passes cannot replace these observations.

This run remains pending a supplied disposable account/provider and an agreed mailbox workflow. The existing account failure regressions cover controlled boundaries, including partial cloud deletion, wrong-password rejection and Keychain-save failure after online password change.
