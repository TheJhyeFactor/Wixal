# Installed browser session recovery

Issue#18 now has independently reviewed owned-fixture cookie/session recovery evidence from the actual installed native WebKit browser. This is local fixture acceptance, not qualification of a third-party authentication provider. No model response is generated or inserted.

The frozen **Wixal Recovery Verified** app has helper SHA256 `37e845ca1b70b275a86b9e0bf23d3ef8890e4411c4db48a3bb3ae32cf0256ed9` and source-manifest SHA256 `b94db7a4b4978c83979493c5d7eb1f76cea8b28f2918fe3acaf8440f1ef27fb0`. Strict signature verification passes. Its recorded earlier source/package identity remains separate from the newer Model Probe helper and current main.

| Case | Installed result and independent server observation |
| --- | --- |
| Cookie-authenticated navigation | A disposable session POST sets an HttpOnly cookie; subsequent private-page GET is authorised and native page evidence displays its authenticated state. |
| Server-side expiry | The fixture invalidates the session; the next real private GET is unauthorised and native page evidence displays authentication required. |
| Logout | A single logout POST clears usable session state; subsequent private GET is unauthorised. |
| Network loss | The listener is stopped and previously accepted fixture connections refuse responses; native browser_open reports a connection error rather than successful page evidence. |
| Reconnect | Restarting the same endpoint allows navigation again and displays the current unauthorised state. |
| Closed-page isolation | After signing in, closing the ephemeral page and opening a new page does not carry its cookie; the server and returned native evidence both show unauthorised state. |

All six cases pass with eleven scoped browser reviews. The retained server ledger records exactly three disposable-session POSTs and one logout POST. Every native tool result is retained alongside the independent request ledger. Original workspace/conversation selection is restored in finally, the validation conversation is archived, and native accessibility inspection confirms the original unsent keyboard-test draft including its tab. No global settings, credentials or original history are changed.

The first exploratory run passed all six cases. Preparing the reusable runner exposed a fixture issue: stopping a ThreadingHTTPServer listener can leave an already accepted connection able to answer one more request. That attempted disconnect did not actually disconnect the endpoint, so its result remains failed rather than being counted as browser acceptance. The fixture now explicitly refuses responses on existing connections while offline. The corrected reusable runner passes all six cases without a product change. Earlier pre-browser harness setup errors are also retained locally; none establish a product failure.

The runner requires an already running installed app and an existing disposable guest workspace. It does not insert welcome/setup state, accept legal terms, enter provider credentials, disable review or fabricate page responses. The fixture is a declared owned HTTP service which generates real cookie-bearing requests and native WebKit navigation. Reports bind the executed script, helper and source manifest by hash.

Issue#18 remains open for advertised live third-party HTTP/API/MCP and authenticated-provider combinations, including their actual expiry/revocation/outage policies. The fixture results do not certify those external accounts or providers. Raw fixture observations stay local under artifacts/native/priority-20261011/browser-session-recovery-offline/. Public release and failed cybersecurity model qualification are unchanged.
