# Wixal accounts and setup

Wixal uses Firebase Authentication for email/password accounts and Cloud Firestore for optional named workspace presets and a short global preference profile. Guest mode keeps local chat, projects, files, memory, local models, tools and the terminal available. Online sign-in does not change model execution or grant tool permissions.

## Setup

New workspaces show setup at first launch. Choose a theme, open a project folder, and choose or download a model. Continue as a guest or create an account. Existing workspaces retain their preferences and can run setup again from Settings.

The Account button in the sidebar and Settings → Manage Wixal account open registration and sign-in. New accounts receive a Firebase verification email. Open its link and choose **I've verified my email**. Password reset and verification resend use Firebase's hosted email action pages.

## Account benefits

Verified users can save named presets, refresh them from Firebase, apply them on another Wixal installation, and delete them. A preset contains theme, conversation text size, motion preference, sidebar layout, conversation mode, summary preference, and context window size. Presets are applied explicitly. They never include projects, paths, enabled tools, approvals, commands, chat history, files, memory, model downloads or API credentials.

The optional global profile contains only the text explicitly entered in Memory → Global preferences, up to 1,200 characters. It lives under `users/{uid}/profile/memory` and uses owner-only verified-email rules. Save, refresh or clear it explicitly; account restoration also refreshes it. It is excluded from project-only chats. Guest and account profiles remain separate. Signing in does not upload guest preferences or project notes. [Memory guide](memory.md).

Each user's presets live under `users/{uid}/presets/{presetId}`. Firestore rules require an authenticated, email-verified owner for all operations. Default access to other collections is denied. Remote preferences are validated before applying them locally. Signing out clears the saved Wixal session and cached presets; local workspace data remains accessible as a guest and is shared by users of the same macOS login.

Session tokens are kept in the existing encrypted credential file through Electron safeStorage. They are never exposed through renderer snapshots. Passwords are submitted to Firebase from the main process and are not persisted. Saved sessions are checked against Firebase at startup and refreshed as needed. An offline start can always use guest mode.

## Firebase project

Project: `wixal-desktop-2026`, app: **Wixal Desktop**. Firestore uses Sydney (`australia-southeast1`) and the free tier. Public client configuration is in `resources/firebase-config.json`; it contains no Admin SDK or service-account credentials. `firebase.json` points to `firebase/firestore.rules`.

Deploy rules with `firebase deploy --only firestore:rules --project wixal-desktop-2026`. Email/password authentication must be enabled in Firebase Authentication. Do not use Firestore test mode. Firebase handles password verification, verification links, reset links and email throttling. See [Firebase Auth REST API](https://firebase.google.com/docs/reference/rest/auth) and [Firestore REST authentication](https://firebase.google.com/docs/firestore/use-rest-api).

## Validation

`npm run test:accounts` exercises first-run setup, guest continuation, account forms, saved appearance, guest preset denial, compact layout and renderer errors. `node --test test/accounts.test.cjs` exercises token isolation, email verification gates, expired-session refresh, cloud preset boundaries, sign-out and malformed settings. Live project verification and packaged app verification are separate checks.
