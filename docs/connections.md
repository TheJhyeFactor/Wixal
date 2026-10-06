# Connections in the local-only app

All model inference now uses Wixal’s bundled local engine. Provider sign-in, API keys and cloud model selection are hidden and rejected for inference. Historical connection records are retained locally. Use the [local model guide](local-runtime.md) to import Ollama weights or download model tags.

The optional companion remains available for explicitly shared projects and queued tasks. It sends shared information to the connected service when you enable it; model tasks started in Wixal run locally and follow the workspace approval policy.

The following provider setup notes describe earlier releases and do not enable cloud inference in this build.

# Connect Wixal to an AI provider

Wixal starts with Ollama, which runs models on your Mac. You can also connect an API account, sign in to an eligible ChatGPT account, or use a compatible endpoint.

## Add a provider

1. Open **Connections** and choose a provider.
2. Add its API key, or choose **Continue with ChatGPT** to sign in in your browser.
3. Allow cloud context for the workspace or project you want to use.
4. Open the model picker, select the provider, refresh the list, and choose a model.

Each provider uses its own account and billing. Model support for images and tools varies; check the labels in the picker.

## Available providers

Ollama · OpenAI · ChatGPT · Anthropic (Claude) · Google (Gemini) · xAI (Grok) · DeepSeek · Groq · Mistral · OpenRouter · Custom endpoint

For a custom endpoint, enter its API base URL and model ID in **Connections**. HTTPS is required except for local addresses. You can set whether the model supports tools and images.

## What gets sent

Ollama requests stay on your Mac. When you use a cloud provider, Wixal sends that conversation and the project context you allowed. This can include attached images, saved project notes, and results from tools you ask the model to use. You can turn off cloud access for a project in **Connections**.

Provider API keys and ChatGPT sign-in credentials are stored separately using macOS encrypted storage. Your chats and project notes are saved locally.

## Sign in to ChatGPT

Choose **Continue with ChatGPT** in **Connections**. Sign in through the browser and review the requested access. OpenAI determines whether your account is eligible. Return to Wixal, allow cloud context for a workspace, then choose the connected ChatGPT account in the model picker.

Connections can be switched, reconnected, or signed out in the same panel. ChatGPT conversations are not imported into Wixal.

## Use the ChatGPT companion

The companion lets ChatGPT read projects you choose to share and send tasks to Wixal. It does not provide ChatGPT with a terminal or direct file-writing tools. You start queued tasks in Wixal and review requested file changes and commands there.

To connect it, share a project in **Connections**, enable the local companion, and copy the setup command. You can separately choose whether to share saved project notes. Keep Wixal running while the companion is in use.

Connecting from ChatGPT requires the OpenAI Secure MCP Tunnel client, Platform tunnel access, and ChatGPT developer mode. This is a private developer connection; it is not a public ChatGPT plugin. Follow the steps below to connect it.

### Set up Secure MCP Tunnel

1. Install and configure the current tunnel client using [OpenAI's Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
2. Create a tunnel for the Platform organization and ChatGPT workspace you use.
3. Set the required Platform runtime key as `CONTROL_PLANE_API_KEY` in your terminal. Do not paste it into ChatGPT or Wixal.
4. Copy the actual MCP command from Wixal, then configure and start the tunnel:

```sh
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile wixal \
  --tunnel-id YOUR_TUNNEL_ID \
  --mcp-command "PASTE_THE_MCP_COMMAND_FROM_WIXAL"

tunnel-client doctor --profile wixal --explain
tunnel-client run --profile wixal
```

Replace the capitalised values with your tunnel ID and the command copied from Wixal. Keep both Wixal and the tunnel client running. In ChatGPT, enable developer mode and add Wixal as a tunnel connection.

Files, optional project notes, and task results requested through the companion are sent to ChatGPT. Share only projects you want to make available.

[Back to Wixal](../README.md) · [Development guide](development.md)
