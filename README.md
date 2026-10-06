<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/motion/logo-reveal-still.png">
    <img src="assets/motion/logo-reveal.gif" alt="Wixal — the folded W reveals the rest of the name" width="520">
  </picture>
</p>

<h3 align="center">AI, project files, and a terminal for your Mac.</h3>

<p align="center">
  Run local models with the engine included in Wixal, or connect your preferred provider.<br>
  Work on real files, recall your project, and connect tools you can review.
</p>

<p align="center">
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.3/Wixal-0.7.3-macOS-arm64.dmg"><strong>Download for Mac</strong></a> &nbsp;·&nbsp;
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.3/Wixal-0.7.3-macOS-arm64.zip">ZIP</a> &nbsp;·&nbsp;
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.3">Release notes</a>
  <br>
  <sub>Version 0.7.3 &nbsp;·&nbsp; Apple Silicon &nbsp;·&nbsp; macOS 14 or newer</sub>
</p>

<p align="center">
  <a href="#a-place-for-your-project">Overview</a> &nbsp;/&nbsp;
  <a href="#new-in-072">What’s new</a> &nbsp;/&nbsp;
  <a href="#choose-your-model">Models</a> &nbsp;/&nbsp;
  <a href="#get-started">Get started</a> &nbsp;/&nbsp;
  <a href="#guides--development">Guides</a>
</p>

---

## A place for your project

Open a folder and start a conversation. Your files, saved notes, and terminal are there when you need them.

![The Wixal 0.7.3 workspace, with project and conversation navigation beside the chat composer](docs/screenshots/workspace.png)

- **Bring the context.** Browse and search project files, attach images, and save notes for future conversations.
- **Review the work.** Choose which tools the model can use. Approve file edits and commands before they run.
- **Pick up where you left off.** Search saved chats, archive and restore conversations, and open a zsh terminal beside your project.

<details>
<summary><strong>See Wixal in action</strong> — a short tour of the app</summary>

![Recorded tour of model selection, project files, tool controls, notes, and the terminal in Wixal 0.7.3](docs/media/workspace-tour.gif)

![Recorded collapse and expansion of the Wixal 0.7.3 sidebar](docs/media/sidebar-motion.gif)

[View the screenshots](docs/screenshots) for a still version of the tour.

</details>

## Workspace refinements in 0.7.3

**A more useful main workspace, introduced in 0.7.2 and refined in 0.7.3.** Project and model readiness sit beside the composer, with Files, Tools, Memory and Terminal directly in the header. The local provider remains **Wixal Local**.

- **Move between layouts.** The sidebar fades and moves together, reverses smoothly, and respects reduced motion.
- **Keep your place.** Text drafts save on this Mac and return when you switch chats or reopen the app.
- **Work through long replies.** Copy individual code blocks, jump to the latest message and read earlier content while a reply streams.
- **Choose deliberately.** Chat and Agent have explicit choices with descriptions. The Models page still handles selection, in-app downloads and measured performance.

Streaming updates the pending reply without rebuilding saved messages on each frame. This reduces renderer work; model inference speed depends on the model and your Mac.

[0.7.3 release notes](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.3) · [Models and performance guide](docs/performance.md) · [How Wixal Local works](docs/local-runtime.md)

Wixal Local is built on pinned open-source Ollama 0.35.1, with its original credits and notices preserved. A separate Ollama server and cloud providers remain optional. [Upstream credits](THIRD_PARTY_NOTICES.md)

## Project tools, memory and connections

![Wixal 0.6.0: project recall, reviewed web and API tools, external MCP tools, and local model downloads](assets/features-0.6.svg)

| Feature | What you can do |
| :--- | :--- |
| **Memory that carries forward** | Keep project notes, search earlier chats, and continue long conversations with automatic saved summaries. |
| **Real project work** | Read files in chunks, review edits, and execute commands with output, exit status and cancellation. |
| **Web pages and APIs** | Enable web search or HTTP tools, review the request, and get real source links, page text or JSON. |
| **External MCP tools** | Connect trusted local servers for additional capabilities and choose which tools the model can call. |
| **Models on your terms** | Download and manage local models in Wixal, and choose context windows up to 128k when supported. |

Built-in tools start enabled. Search or filter them in **Tools in the workspace header**, or type **@tool_name** in chat to explicitly select a tool. Actions that edit files, run commands, save memories or use external services still come to you for review. Local inference, chats and notes stay on your Mac unless you enable a cloud provider or approve an external action.

<p align="center">
  <a href="docs/features.md"><strong>Explore the new features →</strong></a> &nbsp;·&nbsp;
  <a href="docs/features.md">0.6.0 feature guide</a>
</p>

<details>
<summary><strong>External tools, ready for your project</strong></summary>

![Wixal's external MCP tool connection dialog](docs/screenshots/extensions.png)

Save a server executable and arguments, then click Connect to start the server and enable its tools. Calls show the server, tool and arguments before you approve them. See [the MCP setup guide](docs/features.md#external-mcp-tools).

</details>

## Choose your model

| Where you work | Connections |
| :--- | :--- |
| **On your Mac** | Wixal Local, included in the app; external Ollama is also supported |
| **With a cloud provider** | OpenAI, ChatGPT, Claude, Gemini, Grok, DeepSeek, Groq, Mistral, and OpenRouter |
| **With your own endpoint** | A compatible Chat Completions endpoint |

The optional Wixal companion also lets ChatGPT read selected projects and send tasks to your inbox. You choose what to share and start the tasks in Wixal. [Set up providers and ChatGPT →](docs/connections.md)

Conversations and project notes are saved on your Mac. When you use a cloud model, that provider receives the conversation and the project context you allow. Provider keys use macOS encrypted storage.

## Get started

1. **Install Wixal.** [Download the DMG](https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.3/Wixal-0.7.3-macOS-arm64.dmg) and drag **Wixal.app** into **Applications**.
2. **Connect a model.** Open **Models** in the sidebar and download or import a model with Wixal Local, or open **Workspace → Connections** to add a provider.
3. **Open your project.** Press **⌘O** to choose a folder and **⌘L** to choose a model. Then start a conversation.

This preview is not Developer ID signed or notarised. If macOS blocks the first launch, see the [installation notes](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.3#install).

## Guides & development

| Looking for… | Start here |
| :--- | :--- |
| Tools, project recall, summaries and model downloads | [Feature guide](docs/features.md) |
| Everyday use and shortcuts | [User guide](docs/user-guide.md) |
| Providers, sign-in, and project sharing | [Connections](docs/connections.md) |
| Running and building the app | [Development](docs/development.md) · [Architecture](docs/architecture.md) |
| Reporting a bug or making a change | [Issues](https://github.com/TheJhyeFactor/Wixal/issues) · [Contributing](CONTRIBUTING.md) |
| Release history and design assets | [Changelog](CHANGELOG.md) · [Logo & motion](docs/visuals.md) |

Wixal Local is built on Ollama. Upstream engine licenses and model publisher licenses are retained. See [third-party notices](THIRD_PARTY_NOTICES.md) and [local runtime development](docs/local-runtime.md).
