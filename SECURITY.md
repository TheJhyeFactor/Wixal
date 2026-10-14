# Security policy

## Supported versions

Wixal is a public alpha. Security fixes target the latest published native alpha and `main`. Older alpha releases and the retained Electron implementation do not receive a separate security maintenance stream. Upgrade to the latest release before checking whether a problem persists.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/TheJhyeFactor/Wixal/security/advisories/new). Do not post vulnerabilities, credentials, private conversations, or exploitable details in public issues or discussions.

Include the affected version or commit, macOS and architecture, reproduction steps, expected and actual behaviour, impact, and a minimal redacted example. For tool or agent issues, identify the selected project, tool, approval state, and relevant evidence. Use a disposable test workspace and avoid sending real personal data or model credentials.

The maintainer will assess reports and coordinate fixes and disclosure through GitHub security advisories. This project has no guaranteed response time or paid bug bounty. Please coordinate public disclosure through the private report so a fix and advisory can be prepared.

## Security boundaries

Reports involving project scope escapes, credential exposure, symlink traversal, approval bypasses, command execution, IPC validation, untrusted model/tool output, model downloads, and managed-tool provenance are especially relevant. Model output is untrusted; prose claiming an action completed does not establish that it ran.

Only test systems and data you own or have permission to assess. Ordinary bugs and feature requests belong in [public issues](https://github.com/TheJhyeFactor/Wixal/issues), after removing private information.
