import SwiftUI
import AppKit

struct ConnectionsView: View {
    @ObservedObject var engine: EngineClient
    var navigate: (String) -> Void = { _ in }
    @Environment(\.wixalTheme) private var theme
    @ViewState private var working = false
    @ViewState private var error = ""
    private var companion: [String: Any] { engine.state["companion"] as? [String: Any] ?? [:] }
    private var running: Bool { companion["running"] as? Bool ?? false }
    private var shared: [String] { companion["sharedProjects"] as? [String] ?? [] }
    var body: some View {
        WixalPage(eyebrow: "ACCOUNTS & SHARING", title: "Connections", subtitle: "Choose what other tools can access. Projects remain local until you explicitly share them.") {
            WixalSection(title: "Wixal account", detail: "Cloud presets save preferences across Macs. Local chats and project files are not uploaded by account sign-in.") { Button("Manage Wixal account ↗") { navigate("Account") } }
            WixalSection(title: "Wixal companion", detail: "ChatGPT can inspect shared projects and send tasks to your inbox. Start tasks here; edits and commands keep their review step.") {
                VStack(alignment: .leading, spacing: 16) {
                    HStack { Text(running ? "Running on this Mac" : "Paused").foregroundStyle(running ? theme.accent : theme.muted); Spacer(); Toggle("Enable the local companion", isOn: Binding(get: { running }, set: { run($0 ? "companion-start" : "companion-stop") })).toggleStyle(.switch).controlSize(.small) }
                    if running {
                        Text("1. Install OpenAI’s Secure MCP Tunnel client and create a tunnel in your Platform account.\n2. Use the command below as its --mcp-command. Keep Wixal and the tunnel running.\n3. In ChatGPT developer mode, create a connection using that tunnel.").font(.system(size: 11)).lineSpacing(5)
                        Text(textValue(companion["command"])).font(.system(size: 11, design: .monospaced)).textSelection(.enabled).padding(12).frame(maxWidth: .infinity, alignment: .leading).background(theme.raised, in: RoundedRectangle(cornerRadius: 7))
                        HStack { Button("Copy MCP command") { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(textValue(companion["command"]), forType: .string) }; Button("Stop & revoke pairing") { run("companion-revoke") } }
                        HStack {
                            Link("Tunnel settings ↗", destination: URL(string: "https://platform.openai.com/settings/organization/tunnels")!)
                            Link("Setup guide ↗", destination: URL(string: "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels")!)
                            Link("ChatGPT plugins ↗", destination: URL(string: "https://chatgpt.com/plugins")!)
                        }.font(.system(size: 11))
                        Text("This is a private developer connection. Your account needs tunnel permissions and ChatGPT developer mode.").font(.system(size: 10)).foregroundStyle(theme.muted)
                    }
                }.wixalCard()
            }
            WixalSection(title: "Shared projects", detail: "Only checked projects can be read. Turning sharing off immediately revokes access to that project.") {
                if records(engine.state["projects"]).isEmpty { Text("Open a project folder to choose what to share.").foregroundStyle(theme.muted); Button("Open project folder ↗", action: engine.pickProject) }
                ForEach(Array(records(engine.state["projects"]).enumerated()), id: \.offset) { _, project in
                    Toggle(isOn: Binding(get: { shared.contains(textValue(project["id"])) }, set: { enabled in var ids = shared; let id = textValue(project["id"]); if enabled { ids.append(id) } else { ids.removeAll { $0 == id } }; save(ids, memory: companion["shareMemory"] as? Bool ?? false) })) { VStack(alignment: .leading, spacing: 5) { Text(textValue(project["name"])); Text(textValue(project["root"])).font(.system(size: 10)).foregroundStyle(theme.muted).lineLimit(1) } }.toggleStyle(.checkbox).wixalCard()
                }
                Toggle("Share saved project memory", isOn: Binding(get: { companion["shareMemory"] as? Bool ?? false }, set: { save(shared, memory: $0) })).toggleStyle(.checkbox)
                Text("Global preferences, account credentials and unshared projects are excluded. Remote tasks queue for your review and never start automatically.").font(.system(size: 10)).foregroundStyle(theme.muted)
            }
            WixalSection(title: "Task inbox") { Button("Review companion tasks ↗") { navigate("Tasks") } }
            WixalSection(title: "External tools", detail: "Trusted local MCP servers are configured separately. Connecting one launches its executable on your Mac.") { Button("Manage external tools ↗") { navigate("Settings") } }
            if working { ProgressView().controlSize(.small) }; if !error.isEmpty { Text(error).font(.system(size: 11)).foregroundStyle(theme.muted) }
        }.font(.system(size: 12)).buttonStyle(WixalButtonStyle(outlined: true)).disabled(working)
    }
    private func save(_ ids: [String], memory: Bool) { run("companion-settings", ["sharedProjects": ids, "shareMemory": memory]) }
    private func run(_ method: String, _ params: [String: Any] = [:]) { guard !working else { return }; working = true; error = ""; Task { defer { working = false }; do { _ = try await engine.call(method, params) } catch { self.error = error.localizedDescription } } }
}
