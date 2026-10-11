# Agent checklists, evidence and skills

Available in Wixal 0.7.10 Alpha 5. These tools use Wixal’s native engine, workspace storage and existing authority and action-review rules.

## Durable task progress

Ask an agent to create a checklist with `todo_list`, work through it and update each item after the corresponding action. The live-run view displays pending, in-progress and completed items. The saved plan has a revision and survives context compaction and helper restarts. Only one item may be in progress at a time.

Unfinished items prevent an ordinary successful conclusion. A completed checklist is the model’s progress record; configure independent success criteria to verify artifacts, tool output or commands. A fully checked plan can still be unverified or require attention.

Example request:

> Create a checklist to inspect evidence.txt and retrieve its saved result. Read the file, list the retained checkpoints, read that checkpoint’s full result, then mark the steps complete. Report the exact marker from the evidence.

## Recover saved tool evidence

`tool_result_read` reads settled checkpoints from the current task. Omit `checkpoint_id` to list references, then pass an exact returned ID to retrieve its saved result. Use `next_offset` while `more` is true. Results include the saved text’s digest. Retrieval reads retained evidence without repeating the original action.

This is useful after context compaction, which removes older complete tool rounds from the model’s immediate context while preserving the task brief, controller feedback and recent call/result chains. Saved evidence remains in workspace storage. Reading an old result does not establish that the external source is still current.

## Import skills with supporting text

Import a package through its `SKILL.md`. Wixal snapshots eligible text resources under references, examples, templates, assets and scripts. The importer bounds the package to 32 supporting files and 192 KB of UTF-8 text; symlinks, credential paths and unsupported files are rejected or excluded. Inspect the returned resource list to see what was retained.

`load_skill` loads the main instructions by name. To read supporting text, pass its exact returned `resource` path, such as `references/evidence.md`. Use `offset`, `max_chars`, `next_offset` and `more` for pagination. Script snapshots are text; loading them does not execute them. Later edits to the external package do not silently change the imported snapshot.

Skills retain workspace identity. Supporting snapshots participate in evaluation digests, transfer checks and rollback versions. Evaluate candidate versions against explicit cases before promotion.

## Child handoffs and discovery

`delegate_task` accepts explicit handoff context. Include the relevant filenames, facts, scope and expected output. Children remain read-only with a restricted tool set, bounded calls and execution time. They do not inherit parent private instructions, notes or memory, and cannot recursively delegate. Parent authority still bounds the work.

`workspace_info` accepts a keyword `query`, searches enabled tool names and descriptions, and loads up to eight matching schemas. Discovery does not grant permission or install a missing provider. Named-file repair requests retain eligible edit and command tools when the task also explicitly requests changes or execution.

## Verify numeric results against their source

Use `verify_json` to compare a saved JSON field against a separate source. `identity` compares a JSON value, `length` checks its length and `sum` independently adds a numeric JSON array. CSV sums use `sourcePointer` `/column_name` and `transform` `sum`.

For a project containing `numbers.csv` with a numeric `value` column and `totals.json` containing `{"total":21}`:

```json
{
  "path": "totals.json",
  "pointer": "/total",
  "sourcePath": "numbers.csv",
  "sourcePointer": "/value",
  "transform": "sum"
}
```

The verifier rereads actual source bytes and reports source hashes. It rejects self-comparison, invalid sources, malformed numbers and nonfinite or out-of-bound values before registering an unusable durable check. A valid comparison proves the configured relationship; it does not prove that the input dataset is complete or correct.

## Recovery and limits

Malformed tool-call batches are rejected before any member executes. Nested arguments are validated, and correction attempts are bounded. Successful use of the exact tool requested in an earlier failed discovery resolves that discovery error; an explicit success criterion requiring discovery itself still requires successful discovery.

Alpha 5 acceptance covers five local `gpt-oss:20b` scenarios: four passed on the fresh package, while the model selected the wrong saved checkpoint in the checklist/evidence case and independent verification rejected completion. Other models and providers need separate qualification. Remote execution, messaging gateways and voice/media integrations remain incomplete. See the [release notes](release-0.7.10-alpha.5.md) and [source comparison](hermes-agent-improvements-2026-10-12.md).
