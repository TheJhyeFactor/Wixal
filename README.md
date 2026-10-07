# Wixal

A local AI workspace for Mac. Ask questions, work with project files, and review the tools your model uses.

[Website](https://thejhyefactor.github.io/Wixal/) · [Download for Mac](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.9) · [User guide](docs/user-guide.md) · [Development](docs/development.md)

## Download

**Wixal 0.7.9** is available for Apple Silicon Macs running macOS 14 or newer.

[Download DMG](https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.9/Wixal-0.7.9-macOS-arm64.dmg) · [Download ZIP](https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.9/Wixal-0.7.9-macOS-arm64.zip) · [Release notes](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.9)

The published downloads contain the **Electron app**. A separate **native SwiftUI/Python preview** is being developed in this repository. See the [native README](native/README.md) for its build instructions and limitations.

## What you can do

| Work | How Wixal helps |
| --- | --- |
| Ask and learn | Explain code, explore an idea, and work through questions with a local model. |
| Work on a project | Browse and search files, attach relevant context, review edits, and run commands. |
| Keep useful context | Save project notes, recall earlier chats, and continue a long conversation with a saved summary. |
| Inspect websites and APIs | Use enabled web and browser tools to retrieve evidence and inspect results. |
| Assess authorised targets | Review website checks or Nmap profiles and retain the returned evidence. |
| Connect more tools | Add trusted MCP servers and choose which tools the model can use. |

Local inference uses the bundled **Wixal Local** engine, built on Ollama. You can also use a compatible external Ollama server. Model downloads, file actions, web requests and external connections may use the network; local inference does not make those actions offline.

## Start with one project

1. Install Wixal and open the app.
2. In the released Electron app, open **Models** and download a model or choose **Import & use** for an installed Ollama model.
3. Open your project folder, then ask a question or describe a task.
4. Review requested actions and inspect the returned results.

Choose a model that supports tools when your task needs actions. You control the enabled tools and the workspace approval mode. Declined actions must not be retried another way.

## Native preview

The native macOS app is being developed around Chat, Agents and Cybersecurity workflows, project navigation, local model selection and reviewed tools. Its UI and capabilities continue to change as acceptance work progresses.

It remains a **local development preview**, rather than a public native replacement for the Electron download. Distribution signing and notarisation, broader accessibility acceptance, external account/provider checks and actual two-Mac sync delivery remain incomplete. Native Windows and Linux work is paused.

[Native source and setup](native/README.md) · [Native implementation status](native/IMPLEMENTATION_STATUS_2026-10-07.md)

## Guides

- [Everyday use](docs/user-guide.md)
- [Tools and workflows](docs/tool-workflows.md)
- [Models and local runtime](docs/local-runtime.md)
- [Project context and memory](docs/memory.md)
- [Website assessments](docs/website-assessments.md) and [cybersecurity tools](docs/cyber-tools.md)
- [Accounts and data boundaries](docs/accounts.md)
- [Architecture](docs/architecture.md) and [contributing](CONTRIBUTING.md)

Wixal retains the upstream engine and model licence notices. See [third-party notices](THIRD_PARTY_NOTICES.md).
