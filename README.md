<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/motion/logo-reveal-still.png">
    <img src="assets/motion/logo-reveal.gif" alt="Wixal — the folded W reveals the rest of the name" width="520">
  </picture>
</p>

<h3 align="center">AI, project files, and a terminal for your Mac.</h3>

<p align="center">
  Use a local model or connect your preferred provider.<br>
  Bring your project, keep your notes, and review changes as you go.
</p>

<p align="center">
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/download/v0.5.1/Wixal-0.5.1-macOS-arm64.dmg"><strong>Download for Mac</strong></a> &nbsp;·&nbsp;
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/download/v0.5.1/Wixal-0.5.1-macOS-arm64.zip">ZIP</a> &nbsp;·&nbsp;
  <a href="https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.5.1">Release notes</a>
  <br>
  <sub>Version 0.5.1 &nbsp;·&nbsp; Apple Silicon &nbsp;·&nbsp; macOS 13 or newer</sub>
</p>

<p align="center">
  <a href="#a-place-for-your-project">Overview</a> &nbsp;/&nbsp;
  <a href="#choose-your-model">Models</a> &nbsp;/&nbsp;
  <a href="#get-started">Get started</a> &nbsp;/&nbsp;
  <a href="#guides--development">Guides</a>
</p>

---

## A place for your project

Open a folder and start a conversation. Your files, saved notes, and terminal are there when you need them.

![The Wixal 0.5.1 workspace, with project and conversation navigation beside the chat composer](docs/screenshots/workspace.png)

- **Bring the context.** Browse and search project files, attach images, and save notes for future conversations.
- **Review the work.** Choose which tools the model can use. Approve file edits and commands before they run.
- **Pick up where you left off.** Search saved chats, archive and restore conversations, and open a zsh terminal beside your project.

<details>
<summary><strong>See Wixal in action</strong> — a short tour of the app</summary>

![Recorded tour of model selection, project files, tool controls, notes, and the terminal in Wixal 0.5.1](docs/media/workspace-tour.gif)

[View the screenshots](docs/screenshots) for a still version of the tour.

</details>

## Choose your model

| Where you work | Connections |
| :--- | :--- |
| **On your Mac** | Ollama, using models you have installed locally |
| **With a cloud provider** | OpenAI, ChatGPT, Claude, Gemini, Grok, DeepSeek, Groq, Mistral, and OpenRouter |
| **With your own endpoint** | A compatible Chat Completions endpoint |

The optional Wixal companion also lets ChatGPT read selected projects and send tasks to your inbox. You choose what to share and start the tasks in Wixal. [Set up providers and ChatGPT →](docs/connections.md)

Conversations and project notes are saved on your Mac. When you use a cloud model, that provider receives the conversation and the project context you allow. Provider keys use macOS encrypted storage.

## Get started

1. **Install Wixal.** [Download the DMG](https://github.com/TheJhyeFactor/Wixal/releases/download/v0.5.1/Wixal-0.5.1-macOS-arm64.dmg) and drag **Wixal.app** into **Applications**.
2. **Connect a model.** Start Ollama with a model installed, or open **Workspace → Connections** to add a provider.
3. **Open your project.** Press **⌘O** to choose a folder and **⌘L** to choose a model. Then start a conversation.

This preview is not Developer ID signed or notarised. If macOS blocks the first launch, see the [installation notes](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.5.1#install).

## Guides & development

| Looking for… | Start here |
| :--- | :--- |
| Everyday use and shortcuts | [User guide](docs/user-guide.md) |
| Providers, sign-in, and project sharing | [Connections](docs/connections.md) |
| Running and building the app | [Development](docs/development.md) · [Architecture](docs/architecture.md) |
| Reporting a bug or making a change | [Issues](https://github.com/TheJhyeFactor/Wixal/issues) · [Contributing](CONTRIBUTING.md) |
| Release history and design assets | [Changelog](CHANGELOG.md) · [Logo & motion](docs/visuals.md) |
