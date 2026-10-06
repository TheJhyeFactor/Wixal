# Website assessments in Wixal

Wixal's selected tool-capable local model can assess an authorised website and run reproducible attack simulations. The controller executes native tools and returns actual results; no extra MCP connection is required. Open a project, choose a model marked Tools and open **Tools → Website assessment**. Select **Approved all** to avoid individual tool/report approval dialogs for that workspace.

## Live website tool

`website_assess` takes `url`, `profile` (`baseline` or `probes`), `max_pages` (1–12), optional `protected_paths` (up to eight known API paths) and a project-relative `report_prefix`. It saves JSON evidence and a Markdown assessment. A parent report folder must already exist.

Baseline checks HTML response headers, framing policy, CSP, MIME protection, referrer policy, HTTPS/HSTS, cookie attributes, same-origin links, and anonymous access/CORS on explicitly named protected paths. Probes add a benign script-reflection canary, `.env` and `.git/HEAD` signature checks and an external `next` redirect canary. Bodies are bounded and hashed; cookies are reduced to names/attributes. The tool omits cookie values and response bodies from reports.

Each run uses at most 36 GET requests, a two-minute deadline, ten-second request timeouts and a 512 KiB response limit. Redirects are manual and only same-origin crawl redirects are followed. Failed requests count toward the request limit. GET checks make no login attempts, submit no forms and write no website data. A reflected marker is a candidate to validate, not proof of browser execution. A protected path returning JSON requires semantic review before declaring access-control failure. Missing headers are configuration findings.

## Attack simulation tool

`website_simulate` starts disposable loopback-only fixtures and tests deliberately vulnerable and hardened implementations. It checks reflected script execution in an isolated Electron browser, framing configuration, synthetic sensitive files, redirects, anonymous access, cross-origin writes, forwarding-header throttling and logout replay. It saves JSON and Markdown reports with expected versus unexpected results. It accepts no external target. Fixture results demonstrate test behaviour; they are not evidence that a live site has the same defect.

Use the **Run local attack simulations** button or ask the selected model to run the tool. Native command sessions remain available for additional installed tools and source-specific test harnesses.

## Response contract

Every model request includes the app's assessment response guidance: target/scope/tool coverage, grouped findings, confidence and reproduction status, evidence/report paths, successful controls, errors/limits, prioritised remediation and concrete next tests. Live observations, local source reproductions and seeded fixture attacks must be labelled separately. The model must not invent CVEs, exploit success, severity or clean results for tests that were not performed.

Tools return structured grouped findings, example evidence, remediation and passed-check counts directly to the model. Simulations return the expected outcome of each vulnerable/hardened case. These summaries survive context excerpting so the model can conclude without rereading every raw report record. The newest tool evidence also keeps a useful context excerpt after multiple report reads. If a local model returns an empty conclusion, Wixal requests a visible answer once using the existing evidence without repeating actions. A second empty answer is reported as an error.

Wixal does not add a topic-based refusal classifier or a cloud moderation service. The selected local model's weights and template still determine its response behaviour. An uncensored Ollama model can be imported and run through the same bundled engine, native tools and workspace approval policy. Tool input validation and project/session boundaries are enforced independently of model choice.

## Reproduce tests

```sh
npm run test:website
npm run test:website-ui
# Actual model; bundled engine; real authorised target; preserves evidence under artifacts:
WIXAL_WEBSITE_MODEL='orcarouter/Qwen3.8-27B-Uncensored:iq4_xs' node scripts/website-model-live.cjs
# Bounded CLI assessment:
node scripts/website-assess.cjs --url https://your-authorised-site.example/ \
  --profile probes --protected /api/session,/api/admin --out /path/to/report
# Browser framing/canary evidence; fresh anonymous Chrome context:
node scripts/website-browser-assess.cjs https://your-authorised-site.example /path/to/browser-report
```

`WIXAL_APP_PATH` selects a packaged Wixal executable for UI/model checks. The browser CLI uses installed Chrome and saves a framing screenshot and JSON cases. It submits no forms.

The source-specific `scripts/jhye-site-security-lab.ts` runs the actual Jhye publishing backend using its installed `tsx`, synthetic owner/session secrets and a temporary local data directory. It tests temporary-password gates, invalid signatures, cross-origin requests, body/schema/media validation, throttling, setup reuse, password rotation and logout replay. Production credentials/storage are not used. This harness requires that site's source and dependencies; it is distinct from Wixal's portable built-in fixture tool.
