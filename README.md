![Wixal. Local AI, at home on your Mac.](assets/repo-banner.png)

# Wixal

Wixal brings Ollama, your project files, and a terminal together in a Mac app. Use it to talk through an idea, find your way around a codebase, or work on a change with a local model. When the model wants to edit a file or run a command, you get to review it first.

**0.2.0 · macOS Apple Silicon · Early preview**

[Get started](#get-started) · [See it in action](#take-a-look) · [How it works](docs/architecture.md) · [Contribute](CONTRIBUTING.md) · [What's changed](CHANGELOG.md)

## A little room to work

The conversation sits beside the things you need: your files, local models, saved project notes, and a proper zsh terminal. You can keep it simple and just chat, or give a model access to the project tools when there's work to do.

- **Use the models you already have.** Choose from your Ollama library, with labels for tool use and image support, plus model size and context information.
- **Get to know a project.** Browse files, preview their contents, search the code, and add a file to your prompt.
- **Stay involved in changes.** Switch individual tools on or off. Review proposed file edits and commands before they run.
- **Bring some context along.** Attach a screenshot, save a project preference, and pick up a conversation later. You decide what goes into project memory.
- **Keep your terminal close.** Run an interactive zsh session without leaving the workspace.

![Choose a model, open your project, review changes, and keep working in the terminal.](assets/workflow.svg)

## Take a look

![The Wixal app with a project open, a local model selected, and the new workspace artwork.](docs/screenshots/workspace.png)

These are screenshots of the running app with a small demo project. The model list comes from the models installed on the test Mac; yours will show your own library.

<details>
<summary>Watch a short tour of the app</summary>

The tour shows the workspace, model picker, file browser, tool controls, project memory, and a real terminal. It was recorded from the app with temporary demo data. It does not show model inference.

![A recorded tour through Wixal's workspace, models, files, tools, memory, and terminal.](docs/media/workspace-tour.gif)

</details>

<table>
<tr>
<td width="50%"><img src="docs/screenshots/models.png" alt="The model picker showing the installed Ollama library"><br><strong>Find the right model.</strong><br>See what is installed and what each model supports.</td>
<td width="50%"><img src="docs/screenshots/files.png" alt="The file browser with a README preview"><br><strong>Start with the files.</strong><br>Read the project before asking for a change.</td>
</tr>
<tr>
<td><img src="docs/screenshots/toolkit.png" alt="The tool kit with individual tool controls"><br><strong>Choose the tools.</strong><br>Give the model the access it needs for the task.</td>
<td><img src="docs/screenshots/terminal.png" alt="An interactive zsh terminal in Wixal"><br><strong>Keep working your way.</strong><br>Your shell is there when you need it.</td>
</tr>
</table>

## Get started

You'll need an **Apple Silicon Mac**, [Ollama](https://ollama.com) running locally, and at least one installed model. To run Wixal from source, you'll also need **Node.js 22 or newer** and the Xcode command line tools.

```sh
git clone https://github.com/TheJhyeFactor/Wixal.git
cd Wixal
npm ci
npm run rebuild
npm start
```

Open a project with **⌘O** and choose a model with **⌘L**. Then ask a question or describe what you'd like to work on.

Models labelled **Tools** can use the project tools in Agent mode. Models labelled **Images** can receive image attachments. For a conversation without tools, switch to Chat mode. Wixal also switches to Chat when a model doesn't have confirmed tool support.

Wixal connects to Ollama at `http://127.0.0.1:11434`. It doesn't download models, send prompts to a cloud provider, or collect analytics. If Ollama isn't running, the app shows you how to connect.

This is an early preview. The app is **not Developer ID signed or notarised**; the instructions above are for running it from source.

## What the model can do

| Tool | What happens | Your involvement |
| --- | --- | --- |
| List files | Lists files in the selected project | Read only |
| Read files | Reads project text files | Read only |
| Search files | Finds literal text in the project | Read only |
| Edit or create a file | Creates or replaces a text file | Review the before and after, then approve |
| Run a command | Runs a non-interactive zsh command from the project | Review the command, then approve |

File tools check the project boundary, resolve symlinks, and block common credential paths. **Approved shell commands and the interactive terminal run with your Mac user's access. They are not a filesystem sandbox.**

You can stop a response. Agent commands have a 60 second timeout, and the agent loop is limited to 12 steps. Use the terminal for interactive programs.

Conversations, image attachments, project memories, and preferences are saved locally in `~/Library/Application Support/Wixal/workspace.json`. Project memory is added only when you save it. The file uses private permissions and atomic writes, but the contents are not encrypted.

Image messages accept up to three PNG, JPEG, or WebP files, each under 12 MB. Wixal applies photo orientation and resizes images to a maximum of 1,600 pixels on the longest edge before sending them to the local model. Capability labels describe model metadata; they don't guarantee the quality of a model's answer.

## A few useful shortcuts

| Shortcut | Action |
| --- | --- |
| ⌘O | Open a project |
| ⌘N | Start a conversation |
| ⌘K | Find a command |
| ⌘L | Choose a model |
| ⌘J | Show or hide the terminal |
| ⌘⇧F | Browse project files |
| ⌘⇧T | Open the tool kit |
| ⌘⇧M | Open project memory |
| Enter / Shift+Enter | Send / add a new line |

## Working on Wixal

```sh
npm test
npm run check
npm run test:app
npm run package
```

The app test exercises the real Electron interface and terminal. Its full run also uses an installed local model to request a file edit, checks the approval flow, and verifies image input and memory recall. See the [development guide](docs/development.md) for test prerequisites and packaged app checks.

Browser automation, macOS screen control, MCP connectors, cloud providers, model downloads, and automatic context summarisation aren't implemented yet. Recent complete turns are included within an estimated context budget; older conversations remain saved.

If you'd like to help, start with [CONTRIBUTING](CONTRIBUTING.md) and the [architecture notes](docs/architecture.md). The [artwork and motion guide](docs/visuals.md) includes the editable SVGs, image sources, and instructions for recording a fresh app tour.
