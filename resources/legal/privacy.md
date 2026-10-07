# Wixal Privacy Policy

**Draft for review · Version 2026-10-06-draft · Prepared 6 October 2026**

This draft describes the current Wixal preview and separates current collection from proposed optional analytics. The operator's legal name, retention procedures and overseas-processing details require confirmation before publication. It is not a claim that the application has been certified as compliant with any privacy law.

## 1. Who to contact

The Wixal project operator maintains the application and its account service. **Operator legal name: to be confirmed.** For privacy questions, access, correction, account deletion or complaints, contact [omeleyjhye@gmail.com](mailto:omeleyjhye@gmail.com). Avoid including passwords, sign-in tokens or private project content.

## 2. Account information

If you create an account, Firebase Authentication receives your email address and password. Your display name is also stored with your account. Firebase assigns an account identifier and maintains information such as email-verification state and authentication timestamps. Wixal uses this information to sign you in, display your profile and limit cloud preset and global-profile access to the verified account owner.

Wixal does not save your account password in its local workspace or include it in cloud presets. Saved session tokens are held in the app's encrypted credential file through the Mac's credential encryption service. They are used to restore and refresh your sign-in and are cleared from this installation when you sign out.

Firebase also processes technical information, including IP addresses and user-agent information, for authentication security and abuse prevention. This is separate from optional Wixal product analytics.

## 3. Cloud workspace presets

When you explicitly save a preset, Wixal uploads its name, theme, text size, motion preference, sidebar layout, conversation mode, summary preference and context-window setting. Presets are stored under your Firebase account identifier so you can retrieve, apply and delete them. Preset names are user-provided text, so avoid including sensitive information in a name.

Preset syncing does not upload chat history, project files, project names or paths, terminal output, saved project memory, approval rules or enabled-tool lists.

## 3a. Optional global preferences

When a verified account user explicitly saves Global preferences, Wixal uploads that short text profile (up to 1,200 characters) to an owner-only Firestore document. The profile refreshes when you sign in or restore an account, and can be refreshed manually. Only include information you want reused. Clear the text and save to remove it. Guest profiles stay on this Mac and are not uploaded on sign-in. Project-only chats exclude the global profile. Project notes and chat history remain local.

## 4. Local workspace information

Wixal stores conversations, project references, saved memory, preferences, model usage and performance measurements locally to provide its workspace features. Files and terminal commands are processed using your Mac user's permissions. Users sharing the same macOS login may be able to access the same local workspace. A Wixal account is not a separate encrypted vault for local projects.

Guest mode does not create a Firebase account or upload cloud presets. Local information remains until you remove it using available app controls or remove the app's saved data. Uninstalling the application alone may leave saved data on the Mac.

## 5. External tools and connections

Local model inference runs on the Mac. Downloading models contacts the selected model source. Web searches, browser inspection, API requests, network assessments and commands may send queries, requested URLs, request bodies, network traffic or other user-selected information to external destinations. Destination services can receive your IP address and their own request logs.

If you enable the companion or an external connection, the context you choose to share can be disclosed to that connection. This is separate from account preset syncing. Review each destination and the information being shared. An account does not automatically enable workspace sharing.

## 6. Optional usage analytics: proposed, not active

The selected direction is minimal account data plus optional anonymous usage counts. Product analytics are **not active in this release**, and this draft does not opt you into them.

The proposed categories are coarse feature-use counts, app starts, model download outcomes, preset actions, app version and a coarse macOS version. The reporting mechanism, retention period and consent controls must be agreed and implemented before collection begins.

The proposal excludes emails, account identifiers, persistent device identifiers, exact locations, ages or dates of birth, project names, file paths, prompts, responses, file contents, terminal commands and command output. Any future analytics option should be off by default, separate from account registration, and revocable. Data should only be described as anonymous after the reporting design has been checked for account linkage and identifying details. Technical service logs may still contain IP addresses.

## 7. Providers and locations

Google Firebase provides authentication and the cloud preset database. The current Cloud Firestore database is configured in Sydney, Australia. That database location does not mean every Firebase service, authentication record or provider support process operates only in Australia. Firebase or its subprocessors may process data overseas, including in the United States. The complete applicable country and subprocessor details should be confirmed for the final policy.

See Google's [Firebase privacy and security information](https://firebase.google.com/support/privacy) for its service processing and retention practices. Wixal currently does not integrate an advertising SDK, Google Analytics or Firebase Crashlytics.

## 8. Retention and deletion

Global preferences remain until you clear and save the profile or the account is deleted. Cloud presets remain until you delete them or the operator removes them as part of an account deletion request. Authentication records remain until the online account is deleted. Firebase may retain provider logs and backup copies for its published retention periods; live deletion is not a promise of immediate removal from every backup.

No automatic inactivity-deletion schedule or analytics-retention schedule has been set in this preview. The operator must confirm its deletion process and any legal retention requirements before the final policy is published. Signing out does not delete the online account. Online account deletion does not remove local copies from your Mac.

## 9. Access, correction and complaints

You can view your email and display name in Account, manage cloud presets in the app, and use Firebase's password-reset flow. Contact [omeleyjhye@gmail.com](mailto:omeleyjhye@gmail.com) for account-data access, profile corrections or account deletion. The operator may need to verify that a request comes from the account owner.

If you have a privacy complaint, describe it and the outcome you are seeking using that contact address. The operator's response timeframe and escalation process should be confirmed in the final policy. Where applicable, Australian privacy complaints may be raised with the Office of the Australian Information Commissioner after contacting the organisation and allowing it a reasonable opportunity to respond.

## 10. Policy changes

Material changes should be explained before new collection begins. Agreeing to future Terms & Conditions should not substitute for a separate choice about optional analytics. This draft will be updated after the remaining data and operator decisions are confirmed.
