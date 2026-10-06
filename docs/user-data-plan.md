# Wixal user data decisions

Prepared 6 October 2026. This is a design discussion, not a claim that analytics has been enabled.

## Confirmed direction

The user selected minimal account information plus optional anonymous usage analytics, and specified `omeleyjhye@gmail.com` for privacy and account requests. Optional product analytics is not implemented or active. No analytics SDK, collector, persistent analytics identifier or extra Firebase collection was added by this change.

Current online data is Firebase email/password authentication, display name (which may be an alias), Firebase UID, verification status, authentication metadata and explicitly saved cloud presets and a global preference profile of up to 1,200 characters. Passwords go to Firebase and are not saved by Wixal. Firebase processes technical authentication information such as IP addresses and user agents independently of any optional Wixal analytics choice.

## Proposed analytics

Use a separate, off-by-default setting. Declining it must leave guest and account features available. Avoid collecting a persistent installation identifier or using a Firebase account token to authenticate event uploads: that would create a possible account link. Aggregate feature counts on-device and report through a collector designed to avoid retaining identifiers, account context, request bodies containing content, or unnecessary request logs. Confirm the collector's infrastructure logging and abuse controls before calling its output anonymous.

Candidate event categories:

| Category | Candidate data | Purpose |
|---|---|---|
| App starts | Daily aggregate count | Understand overall usage |
| Feature use | Counts for models, terminal, files, memory, tools and settings | Prioritise product work |
| Model downloads | Success/failure/cancel counts; broad size bands | Improve download experience |
| Presets | Save/apply/delete counts | Measure account feature usefulness |
| Environment | App version; macOS major version; coarse hardware architecture | Identify compatibility patterns |

Do not include emails, UID, display name, persistent device ID, model prompt/response, exact model names or custom endpoints, project name, root path, filenames, file content, URLs, scan targets, command text, stdout/stderr, saved memory, clipboard, screenshots, ages, birth dates, location or credentials. Usage linked to an account or a persistent device should be described as pseudonymous, not anonymous.

Retention is not agreed yet. One proposal is to discard raw reports after 30 days and retain aggregated counts for 90 days. This is a proposal only. Avoid small cohort breakdowns that make an individual recognisable. Revocation should discard unsent local counts and stop future reports; already anonymous aggregate counts may not be attributable for deletion, which must be explained accurately.

## Open decisions before final policies

- Legal operator name. The supplied contact email is confirmed, but the legal identity has not been supplied.
- Eligibility age and whether any parental permission is required. Avoid collecting birth dates merely to support a broad eligibility rule.
- Analytics event list, aggregation, collector, abuse controls, infrastructure logs, retention and opt-in wording.
- Account deletion handling, target response times and provider backup limitations.
- Applicable overseas-processing countries and subprocessors. Sydney Firestore does not imply Australian-only authentication processing.
- Whether versioned acceptance of final terms should be recorded and where. Opening the current drafts does not record final contractual acceptance.

## Draft artifacts

`resources/legal/terms.md` and `resources/legal/privacy.md` are the canonical bundled drafts. The app loads them through a restricted main-process IPC handler. They remain readable offline without sign-in. No final policy acceptance requirement or cloud acceptance record is created while these documents are drafts.

Reference guidance: [OAIC APP 1](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-1-app-1-open-and-transparent-management-of-personal-information), [ACCC consumer rights](https://www.accc.gov.au/business/selling-products-and-services/consumer-rights-and-guarantees), and [Firebase data processing](https://firebase.google.com/support/privacy).
