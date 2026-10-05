# Using Wixal

## Start a conversation

Open a project with **⌘O**, choose a model with **⌘L**, and type a message. Wixal supports Ollama on your Mac, several cloud providers, and compatible endpoints. See [provider setup](connections.md).

Switch between Chat and Agent mode in the composer. Agent mode can use the project tools you enable. Wixal shows file changes and commands for your review before running them.

## Work with a project

Browse and search project files, preview their contents, and attach images to a conversation. Add notes in **Project memory** when you want Wixal to include them in later conversations for that project. Use the terminal for interactive commands.

Chats and project notes are saved on this Mac. Ollama requests stay local. When you use a cloud provider, Wixal sends the conversation and project context you allow, including attachments or tool results used in that conversation.

## Tools, recall and long chats

Open **Workspace → Tool kit** to enable web search, web pages and JSON APIs, conversation recall, reviewed memory saves, or tools from a connected MCP server. File edits, shell commands, memories, network requests and external tool calls show their proposed action for review. Network and external tools start disabled.

Project memory includes a switch for automatic long-conversation summaries and an inspector for the current chat's saved summary. Full messages remain saved. To download a local model, open **⌘L**, choose Ollama and use the Download form; progress and cancellation are available there.

Read the [feature guide](features.md) for setup, examples, MCP servers, context behaviour and service limits.

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
