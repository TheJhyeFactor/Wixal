# Using Wixal

## Models and conversations

Choose a model from your installed Ollama library with **⌘L**. Use Chat mode for conversations, or Agent mode to let a model work with your project tools. Agent mode needs a model labelled **Tools**. Models labelled **Images** accept image attachments.

Open a project with **⌘O**, then type a message. You can browse files, preview their contents, and add a file to your message. Earlier conversations remain available in the sidebar.

## Project tools

The tool kit lets you choose what the model can do. File reads and searches run within the selected project. Wixal asks you to review file edits and model-requested commands before they run.

File tools block paths outside the project, including external symlinks and common credential files. Approved commands and the terminal run with your Mac user's access, so they can reach files outside the project.

Use the stop button to cancel a response. Model-requested commands time out after 60 seconds, and the agent can take up to 12 steps per response. Use the terminal for interactive programs.

## Notes and images

Save project notes in the memory panel. Wixal includes those notes in later conversations for that project. Notes are saved only when you add them.

You can attach up to three PNG, JPEG, or WebP images, each under 12 MB. Wixal applies photo orientation and resizes them to a maximum of 1,600 pixels on the longest edge before sending them to a vision model. Image attachments remain in saved conversations.

## Local data

Chats run through Ollama at `http://127.0.0.1:11434`. This release uses local models and does not collect analytics. Install and manage models in Ollama.

Conversations, images, project notes, and preferences are saved in `~/Library/Application Support/Wixal/workspace.json`. The file has private permissions but is not encrypted.

The model receives recent conversation turns within the selected context size. Older conversations stay saved, but are not automatically summarised.

## Keyboard shortcuts

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

[Download Wixal](https://github.com/TheJhyeFactor/Wixal/releases/latest) · [Back to the project](../README.md)
