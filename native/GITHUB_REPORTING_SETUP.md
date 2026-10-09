# Contributor GitHub reporting

Wixal prepares a report locally, sanitizes the supplied description and selected diagnostic evidence before the model sees it, then shows the full report for review. Each public submission requires contributor sign-in and an unchecked, per-report confirmation. The destination is fixed to `TheJhyeFactor/Wixal`. Reporting does not expose a model tool or grant investigation, local editing, PR creation or merge authority.

Register a GitHub **OAuth App** for Wixal and enable **Device Flow** in its settings. Supply its public client ID when packaging:

```sh
native/.venv/bin/python native/scripts/package.py --development --github-client-id REGISTERED_PUBLIC_CLIENT_ID
```

The client ID is public application configuration. A client secret is neither requested nor bundled. Do not put an access token or maintainer credentials in this option. Existing managed repository configuration can be passed alongside it.

The report review screen opens GitHub's device verification page and displays the user code. The contributor authorizes through GitHub, then checks sign-in in Wixal. The backend enforces GitHub's polling interval, slow-down responses, expiry and cancellation. It verifies the contributor's `/user` identity before making submission available. Tokens and device codes remain in process memory and are cleared on sign-out or the next reporting interaction after an account switch. Quitting Wixal ends that reporting session.

GitHub OAuth's `public_repo` scope permits broader public repository writes than issue creation alone. The review screen discloses this scope. Wixal's reporting implementation uses only its fixed identity and issue endpoints. See GitHub's [OAuth Device Flow documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps) and [issue creation API](https://docs.github.com/en/rest/issues/issues#create-an-issue).

Publishing checks the reviewed draft digest and permits only one submission attempt for that draft. A network failure after submission can leave the outcome unknown; Wixal does not automatically repeat the POST. The contributor must check GitHub before preparing another issue.

Current configuration: the registered client ID is awaiting the application's owner. Builds without it display an actionable unavailable message. The protocol and policy tests use controlled responses; they do not prove live contributor authorization. No community issue has been uploaded during implementation acceptance.
