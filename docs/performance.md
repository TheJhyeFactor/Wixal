# Models, usage and benchmarks

Open **⌘L** for the model manager. All models use the included Wixal local engine. Model downloads and imports are described in [the runtime guide](local-runtime.md).

## Choose a model for this Mac

The **Models** sidebar page and **⌘L** selector open on **Installed**. Current model, context and hardware sit in the setup panel; **Local engine** expands for runtime settings and imports. Installed model cards show actual disk size, publisher-reported tool/image/thinking capabilities and context limits. Expand **Filters** to filter by capability, sizes up to 4/8/16 GB, estimated memory fit, completed benchmarks on this Mac, or benchmark throughput of at least 20 tokens per second. Sort by name, size or measured speed. Benchmarks match the installed model digest, this machine's CPU/architecture/memory identity and the selected local runtime mode; replacing model weights prevents an older result from appearing as a measurement of the replacement.

The **Downloads** tab includes registry tags for Qwen3 and Gemma3 in several sizes. Search and filters apply to the active tab, with independent filter selections for Installed and Downloads. Download suggestions can be sorted by name or size. Choosing a tag fills **Download by model tag**, or click **Download** on a catalog card to queue it directly. Each transfer supports pause, resume, cancellation and retry; completed downloads are checked against the actual installed library before **Use model** becomes available. Unfinished jobs are saved as paused on restart. The bundled catalog is a snapshot checked on 6 October 2026 against the [Qwen3 registry](https://ollama.com/library/qwen3) and [Gemma3 registry](https://ollama.com/library/gemma3). Sizes and publisher capabilities can change; installed metadata becomes authoritative after downloading.

Memory fit is an estimate, not a successful run. It reserves 25% of total RAM for macOS and other work, adds 15% weight overhead and 1 GiB workspace, and includes context cache. Where the engine reports attention dimensions, the estimate uses those dimensions for the managed q8 cache; otherwise it uses a conservative per-token fallback. Architecture, vision inputs, active applications, temperature and engine version can change memory and speed. Benchmark a candidate at your intended context before relying on it.

## Run a benchmark

Click **Benchmark** on an installed local model. Wixal runs the same fixed generation prompt twice, at the selected context clamped to the model's limit, with a 128-token output cap per run. No project files, saved chats or tools are sent. The first run records its actual load conditions; the second measures warm generation. A first run may already have the model cached, so it is not presented as a guaranteed cold start.

Results preserve both samples, reported input/output token counts, generation tokens/sec, time to first text, load time, context, model digest, engine version, machine identity, date and loaded/GPU memory when reported by the engine. The card shows warm generation throughput. This is a speed/memory measurement, not an answer-quality evaluation or proof that every workload will fit. Runs have a three-minute limit and a **Cancel** button. Failed/cancelled runs do not become successful results. Chats and model changes are blocked while a benchmark is active.

## Inspect usage

Click the token/speed status below the chat composer to open **Usage & performance**. It shows reported input/output tokens for the current chat, saved output totals, request count, last generation speed, first output timing when available, hardware and saved benchmark results.

Usage includes model calls for tool steps, automatic summaries and retries. Older chats contribute their saved message metrics where available; historical summary usage cannot be reconstructed. The app retains the last 2,000 request records locally; these are processed-token totals, so repeated context counts again. Missing provider usage is marked unavailable and is not guessed from text. Benchmark token counts are recorded in benchmark results separately. Generation speed comes from the local engine's evaluation duration. No billing cost is inferred.

## Delete a model

Open the **•••** menu on a local model, choose **Delete model…** and review its name and active library in the confirmation dialog. Cancelling makes no request. Confirming removes the model from that library through the engine's delete API; layers shared by other models are retained. Deleting a model in Wixal Local does not delete its original copy in the external Ollama library. Chats, notes and historical benchmark records stay saved. A deleted model can be downloaded or imported again.

## Explicit tools in chat

Built-in tools start enabled. Use the tool kit's search, categories and **Enable all** control to manage availability; connected MCP tools are enabled after their explicit connection. Preferences then persist. File edits, commands, memory writes, network and external-tool calls follow the workspace approval policy.

Type `@` in the composer and choose a tool with the mouse or Arrow keys and Enter/Tab. For example:

```text
@read_file read package.json and explain the scripts
@web_search find the official documentation for this API
@write_file create a README using the project we discussed
```

Enabled tools are available to tool-capable models in both Chat and Agent. Chat uses them when your request needs an action or fresh evidence; Agent works through a task using tool results. An `@tool_name` mention requests that tool while keeping other enabled tools available for preparation and follow-up, such as `command_read` after `command_start` or `http_request` after `web_search`. If a required URL, path, command or target is missing, the model can ask for it without a forced-call retry loop. Project file and command tools require an open folder; web, memory and connected tools are available in personal workspaces. The selected model must support tools, and switched-off tools remain unavailable. Review each action prompts for these actions. Approved all runs enabled tools without individual prompts in the selected workspace. A model response is not evidence that an action ran: inspect the actual tool result.

## Model-manager performance

Unchanged model metadata is reused by endpoint/tag/digest for five minutes. Refresh bypasses the cache, deleted/replaced models invalidate it, and concurrent metadata lookups stay bounded. Progress changes update only the download rows; they do not rerender conversations or write the workspace file for every network chunk. Downloads run serially to avoid simultaneous network/disk contention.

The managed engine retains its one-model/one-request configuration, Flash Attention and q8 context cache. Suggested context chooses 16k or 8k when the model's context limit and estimated memory budget permit it; it is applied only when clicked and does not guarantee workload quality or measured fit. The Models page reads available model-drive space and loaded-model memory, and can explicitly unload models using the engine's `keep_alive: 0` request.

## Context ceiling

Context defaults to 8k. Selection uses up to 16k; explicit settings can use up to 32k where model limits and RAM estimates allow. Macs under 24 GiB have a 16k ceiling. Model size and context cache estimates can lower effective context further. The composer meter is a tokenizer estimate, includes memory/tools/instructions and reserves roughly 15% (512–2,048 tokens) for output. Larger windows use more RAM and prompt processing; they do not guarantee better answers. See [memory and limits](memory.md).
