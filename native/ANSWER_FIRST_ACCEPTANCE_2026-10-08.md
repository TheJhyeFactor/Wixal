# Answer first acceptance, 8 October 2026

The user approved Answer first, with subtle animation and task output kept out of the main response. Scope is Working and Response; the app shell is retained.

## Implemented

- Answer text streams directly into the conversation. The activity panel above the composer is replaced by one inline status with elapsed time, Stop and a Details disclosure. The current status updates in place.
- Intermediate assistant/tool messages are grouped into work evidence; completed work shows the last answer and collapsed Details. Historical work uses a quiet Details disclosure. Controller approval still uses the existing review flow.
- Details retains model thinking, tool actions/output/events, sources and usage. Raw thinking is forwarded only when emitted by the model, bounded separately from answer text, persisted, and excluded from subsequent chat request context. Optional thinking is enabled for capable models, low where supported, with output reserve for the final answer. Non-thinking models remain supported.
- Animation: a restrained working symbol pulse, 160 ms status/answer-block transitions, 220 ms Details expansion/chevron movement, and 60 ms streaming batches. Reduce Motion disables discretionary effects. No artificial typewriter delay or invented completion percentage.
- Markdown tables have quiet horizontal rules, real accessible cells, safe line-break handling and height measured from actual native row geometry. A clipped final-row defect found in the first installed screenshot was corrected and visibly retested.
- Model instructions now describe actual Chat/Agents/Cybersecurity sections and their purpose; Files/Terminal are project tools, and unsupported Remote/Debug/Preview modes must not be invented. Enabled tools remain discoverable under existing project, model and review requirements.

## Verification and exact package

Installed `/Users/jhye/Applications/Wixal Native.app`; prior bundle retained by installer.

Executable SHA-256: `130df02f3ada5d6cbe06dff9909294333a125269738f99e01091e7eebd35537a`.
Engine SHA-256: `74deae4e9b262b4e3cbce35a43f011d5bcd89d2e69d07e868fac5bbf44466c9b`.

Full supporting suite: **116 tests passed**. Production Markdown parser checks: **5 passed**. Release build, package, hash-verified install and packaged smoke passed. All logs and screenshots are in `artifacts/native/answer-first/`.

Visible UI tests used `/tmp/wixal-answer-first/state`, with a disposable project. A deterministic Ollama-shaped loopback fixture streamed separate thinking chunks, a real read_file action against a fixture README, and a table answer. Live thinking appeared in Details; interim narration/action output stayed out of the completed answer. Stop during thinking returned the UI to idle. Exact helper hash is the same for the initial live test and final package; later native changes fixed row geometry and moved sources under Details. Final installed completed response, full table and collapsed disclosure were checked again at 920 × 640 content points.

An actual local **gpt-oss:20b** request also completed: it named Chat, Agents and Cybersecurity correctly in three bullets, used no tools, and retained model thinking in Details. The final package visibly reopened this saved actual result and the fixture table without a separate memory-reference disclosure. Fixture tests are presentation/transport evidence, not model quality benchmarks.

Screenshots: `response.png` (final table and collapsed Details), `working.png` (initial live compact state), `details.png` (retained thinking/file evidence), `local-model.png` (final actual model response). `acceptance.json` retains exact hashes and transcript metadata.

Normal workspace restoration visibly passed on the final package: Wixal project and existing Recents were present, Chat remained selected, gpt-oss:20b was connected, and the app was left open.

## Boundaries

Reduce Motion handling was checked in source; OS preference switching and animation frame profiling were not performed. Exhaustive keyboard/VoiceOver/all-theme acceptance is still open. This pass does not add a chart/diagram renderer or revise every onboarding question. Native remains a local development preview; existing account/two-Mac/platform and original SQLite incident boundaries remain unchanged. No real project was deleted or user conversation sent during acceptance.
