# Agents UI preview · 8 October 2026

**Historical design-stage record.** Runtime execution has since been implemented; see [Agents runtime acceptance](AGENTS_RUNTIME_ACCEPTANCE_2026-10-08.md). The design-only boundaries and simulated-state checks below describe the earlier phase.

The Agents tab now contains an interactive native SwiftUI design preview. This phase covers the interface, transitions and local design drafts. New agent execution, workflow execution and scheduler activation remain the next integration phase.

User-directed tool design: the model discovers tools and chooses their use from the task. Agent creation must not ask the user to enable individual tools or tool groups. Existing backend allowlist behavior is unchanged until the runtime phase; the inspection catalog reports its current exposure honestly.

## Included

- First use: empty state, Project reviewer / Code assistant / Researcher templates, custom agent creation and access to the existing live conversation.
- Repeat use: searchable agent roster, edit, duplicate, archive and restore; individual agent workspace with Work, Configuration, Skills & tools, Memory and Schedules.
- Agent builder: purpose and instructions, model selection, project scope, action review policy, automatic model tool selection, memory scope and imported skill selection, followed by a review summary.
- Workflows: named stages, agent assignment, goals, expected outputs, review gates, failure behavior and reordering. Preview progress follows the saved stages and gates.
- Runs: queued, working, needs review, needs input, completed, failed, cancelled and interrupted interface states; task context, guidance, expandable activity and result summary.
- Schedules: agent and brief, repeat pattern, time, missed-run preference, notification preference, pause/enable preview and run-now preview.
- Tools: a read-only live tool inventory with purpose, input schema and current runtime exposure, tool usage placeholders and imported skills. The model chooses tools; no tool enable/disable switches appear in the Agents UI.
- Motion: navigation fades, run-state and context transitions, and hover/press feedback. Motion respects the system and Wixal reduced-motion preferences.
- Narrow windows: scrollable forms and content, adaptive navigation, and responsive run headings.

## Data and execution boundary

Design profiles, workflows and schedules use a separate versioned JSON store. They do not create engine tasks, change live permissions, write new memory or enable real schedules. Preview runs are transient and disappear when the app closes. Existing live execution remains accessible through the Live workspace menu.

The normal app stores drafts in `~/Library/Application Support/Wixal Agents Design/drafts.json`. The isolated review launcher uses `artifacts/native/agents-ui/drafts/drafts.json` and a separate scratch engine workspace. An unreadable existing draft file is preserved rather than overwritten.

## Validation performed

- Release Swift build passed using `swift build --package-path native --build-system native -c release`.
- Isolated store acceptance passed: initial empty state, persistence round trip, schedule pause, cancellation, custom workflow stages/review gates/completion, transient runs and corrupt-file preservation.
- `git diff --check` passed.
- A development package was built during the UI pass; the final review bundle was refreshed with the final release binary and passed `codesign --verify --deep --strict` after ad-hoc signing.
- Visible app checks covered first-use template creation, all builder steps, saved profile, workflow stage editing/reordering, schedule save/pause, and persistence after reopening.
- After the tool-selection correction, visible checks confirmed the builder has no tool switches, the catalog searches live tools, and a read_file disclosure shows its real description, input schema and runtime exposure.
- Final isolated review checks covered saved workflow stages, review gate, completed result, interrupted/restart, queued guidance and cancellation; profile memory and linked schedule views were inspected.
- Layout was inspected in dark and forest themes, including the review window at the configured 920 × 640 content size. This is not an exhaustive accessibility or every-theme audit.

The final review app is `artifacts/native/agents-ui/Wixal Agents UI Review.app`. The corrected automatic tool selection UI was rebuilt for the review bundle. The installed main app was not replaced with this final review build. Its version, existing chats and ongoing activity remain separate from this deliverable.

To reopen with the isolated data paths, use `artifacts/native/agents-ui/Open Agents UI Review.command`. To rebuild and stage a review bundle after source changes, close the review app and run `python3 native/scripts/agents-ui-review.py` after a release build. The staging script does not stop the main Wixal process.

## Next implementation phase

1. Resolve saved profiles into effective instructions, model, project, tools, imported skills and bounded memory context; validate runtime capability compatibility. Replace legacy manual tool enablement for Agents with automatic tool discovery and selection, while retaining task boundaries and action review enforcement.
2. Replace manual preview transitions with engine events and persistent run identity/history. Connect real review requests, guidance, cancellation and recovery evidence.
3. Execute workflow stages with their assigned agents, output handoff, gates and failure behavior.
4. Connect schedules to the existing scheduler with explicit activation, fresh run creation, missed-run handling, awake-state behavior and notifications.
5. Present real files, evidence, verification and errors in the result view; verify the integrated packaged app before installing it.

No live execution outcome is established by these UI previews.
