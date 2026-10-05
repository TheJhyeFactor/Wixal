# Models, usage and benchmarks

Open **⌘L** for the model manager. Wixal Local is included; external Ollama remains optional. Model downloads and imports are described in [the runtime guide](local-runtime.md).

## Choose a model for this Mac

Installed model cards show actual disk size, publisher-reported tool/image/thinking capabilities and context limits. Filter by capability, sizes up to 4/8/16 GB, estimated memory fit, completed benchmarks on this Mac, or benchmark throughput of at least 20 tokens per second. Sort by name, size or measured speed. Benchmarks match the installed model digest, this machine's CPU/architecture/memory identity and the selected local runtime mode; replacing model weights prevents an older result from appearing as a measurement of the replacement.

**Discover downloads for this Mac** includes registry tags for Qwen3 and Gemma3 in several sizes. Choosing a suggestion fills the Download field; clicking **Download** starts the network request. The bundled catalog is a snapshot checked on 6 October 2026 against the [Qwen3 registry](https://ollama.com/library/qwen3) and [Gemma3 registry](https://ollama.com/library/gemma3). Sizes and publisher capabilities can change; installed metadata becomes authoritative after downloading.

Memory fit is an estimate, not a successful run. It reserves 25% of total RAM for macOS and other work, adds 15% weight overhead and 1 GiB workspace, and includes context cache. Where the engine reports attention dimensions, the estimate uses those dimensions for the managed q8 cache; otherwise it uses a conservative per-token fallback. External Ollama may use a different cache format. Architecture, vision inputs, active applications, temperature and engine version can change memory and speed. Benchmark a candidate at your intended context before relying on it.

## Run a benchmark

Click **Benchmark** on an installed local model. Wixal runs the same fixed generation prompt twice, at the selected context clamped to the model's limit, with a 128-token output cap per run. No project files, saved chats or tools are sent. The first run records its actual load conditions; the second measures warm generation. A first run may already have the model cached, so it is not presented as a guaranteed cold start.

Results preserve both samples, reported input/output token counts, generation tokens/sec, time to first text, load time, context, model digest, engine version, machine identity, date and loaded/GPU memory when reported by the engine. The card shows warm generation throughput. This is a speed/memory measurement, not an answer-quality evaluation or proof that every workload will fit. Runs have a three-minute limit and a **Cancel** button. Failed/cancelled runs do not become successful results. Chats and model changes are blocked while a benchmark is active.

## Inspect usage

Click the token/speed status below the chat composer to open **Usage & performance**. It shows reported input/output tokens for the current chat, saved output totals, request count, last generation speed, first output timing when available, hardware and saved benchmark results.

Usage includes model calls for tool steps, automatic summaries and retries. Older chats contribute their saved message metrics where available; historical summary usage cannot be reconstructed. The app retains the last 2,000 request records locally; these are processed-token totals, so repeated context counts again. Missing provider usage is marked unavailable and is not guessed from text. Benchmark token counts are recorded in benchmark results separately. Local generation speed comes from the engine's evaluation duration; cloud speed uses request wall time, so those measurements should not be compared as identical metrics. No billing cost is inferred.

## Delete a model

Click **Delete** on a local model and review its name and active library in the confirmation dialog. Cancelling makes no request. Confirming removes the model from that library through the engine's delete API; layers shared by other models are retained. Deleting a model in Wixal Local does not delete its original copy in the external Ollama library. External mode deletes from the external library named in the dialog. Chats, notes and historical benchmark records stay saved. A deleted model can be downloaded or imported again.

## Explicit tools in chat

Built-in tools start enabled. Use the tool kit's search, categories and **Enable all** control to manage availability; connected MCP tools are enabled after their explicit connection. Preferences then persist. File edits, commands, memory writes, network and external-tool calls retain their review steps.

Type `@` in the composer and choose a tool with the mouse or Arrow keys and Enter/Tab. For example:

```text
@read_file read package.json and explain the scripts
@web_search find the official documentation for this API
@write_file create a README using the project we discussed
```

An explicit mention makes that request use the selected tool(s), including from Chat mode, and constrains its available tool list to those names. Project file and command tools require an open folder. The selected model must support tools. A switched-off tool remains unavailable until enabled. Wixal retries a model that skips the requested call, then reports failure if it still refuses; it does not silently accept an answer that bypassed the selection. Tool failures and declined approvals are returned honestly. Requests without mentions retain the chosen Chat/Agent behavior.
