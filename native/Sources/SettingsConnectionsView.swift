import SwiftUI

struct SettingsConnectionsView: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    @Environment(\.wixalTheme) private var theme
    @ViewState private var editor = false
    @ViewState private var editingID = ""
    @ViewState private var name = ""
    @ViewState private var endpoint = ""
    @ViewState private var transport = "stdio"
    @ViewState private var arguments = ""
    @ViewState private var oauth = false
    @ViewState private var clientID = ""
    @ViewState private var statuses: [[String:Any]] = []
    @ViewState private var statusError = ""
    @ViewState private var removing: String?
    private var locked: Bool { engine.busy || settings.saving || !engine.connected }
    var body: some View {
        WixalSection(title:"External tools",detail:"Connect trusted local executables or remote HTTPS MCP servers. Connect starts the executable or contacts the endpoint; Chat and Agents discover advertised tools automatically and choose them within the task scope.") {
            HStack { Button("Add MCP server…") { clear(); editor=true }.disabled(locked); Spacer(); Button("Refresh status") { Task { await refresh() } }.disabled(!engine.connected || settings.saving) }.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11)
            if !statusError.isEmpty { Text(statusError).foregroundStyle(.red).wixalFont(size:11) }
            if records(engine.state["mcpServers"]).isEmpty { Text("No servers configured. Add a local executable or HTTPS endpoint to connect external tools.").wixalFont(size:11).foregroundStyle(theme.muted) }
            ForEach(Array(records(engine.state["mcpServers"]).enumerated()),id:\.offset) { _,server in serverCard(server) }
            if editor { form }
        }
        WixalSection(title:"Wixal companion",detail:"Allow a connected client to inspect only the projects you explicitly share. Credentials and global instructions are excluded.") {
            let companion = engine.state["companion"] as? [String:Any] ?? [:]
            SettingsRow(title:companion["running"] as? Bool == true ? "Running on this Mac" : "Companion paused",detail:"\((companion["sharedProjects"] as? [String] ?? []).count) projects selected for sharing. Remote tasks arrive in your inbox for review.") {
                Button("Companion & sharing →") { settings.detail="Companion" }.buttonStyle(WixalButtonStyle(outlined:true))
            }.wixalCard()
        }
        .task {
            await refresh()
            while !Task.isCancelled {
                do { try await Task.sleep(for:.seconds(5)) } catch { break }
                if engine.connected && !settings.saving { await refresh() }
            }
        }
        .alert("Remove this MCP server?",isPresented:Binding(get:{removing != nil},set:{if !$0 { removing=nil }})) {
            Button("Cancel",role:.cancel) { removing=nil }
            Button("Remove server",role:.destructive) { if let id=removing { action("mcp-delete",id,success:"Server removed") }; removing=nil }
        } message: { Text("Disconnects the server, removes its tool permissions and forgets its saved OAuth sign-in. You can configure it again.") }
    }
    private func serverCard(_ server: [String:Any]) -> some View {
        let id=textValue(server["id"]), status=statuses.first { textValue($0["id"]) == id } ?? [:], connected=status["connected"] as? Bool ?? false
        return VStack(alignment:.leading,spacing:12) {
            ViewThatFits(in:.horizontal) {
                HStack { Text(textValue(server["name"])).wixalFont(size:12,weight:.medium); Spacer(); statusLabel(connected,status) }
                VStack(alignment:.leading,spacing:6) { Text(textValue(server["name"])).wixalFont(size:12,weight:.medium); statusLabel(connected,status) }
            }
            Text(textValue(server["transport"]) == "http" ? textValue(server["url"]) : textValue(server["command"])).wixalFont(size:11,design:.monospaced).foregroundStyle(theme.muted).textSelection(.enabled)
            DisclosureGroup("Configuration & advertised tools") {
                if textValue(server["transport"]) != "http" { Text((server["args"] as? [String] ?? []).joined(separator:"\n")).textSelection(.enabled) }
                if server["oauth"] as? Bool == true { Text("OAuth sign-in · credentials stored in Keychain") }
                ForEach(status["toolNames"] as? [String] ?? [],id:\.self) { Text($0).textSelection(.enabled) }
                if !connected { Text("Connect to discover this server’s tools.").foregroundStyle(theme.muted) }
            }.wixalFont(size:11)
            ViewThatFits(in:.horizontal) { HStack { serverActions(server,connected:connected) }; VStack(alignment:.leading) { serverActions(server,connected:connected) } }
        }.wixalCard()
    }
    private func statusLabel(_ connected: Bool, _ status: [String:Any]) -> some View {
        Label(connected ? "Connected · \(status["tools"] as? Int ?? 0) tools" : "Disconnected",systemImage:connected ? "checkmark.circle" : "circle").wixalFont(size:10).foregroundStyle(connected ? theme.accent : theme.muted)
    }
    @ViewBuilder private func serverActions(_ server: [String:Any], connected: Bool) -> some View {
        let id=textValue(server["id"])
        Button(connected ? "Disconnect" : "Connect & discover") { action(connected ? "mcp-disconnect" : "mcp-connect",id,success:connected ? "Server disconnected" : "Server connected; its tools are available to Chat and Agents") }.disabled(locked)
        Button("Edit…") { edit(server) }.disabled(locked)
        if server["oauth"] as? Bool == true { Button("Forget sign-in") { action("mcp-oauth-clear",id,success:"Saved sign-in forgotten") }.disabled(locked) }
        Button("Remove…",role:.destructive) { removing=id }.disabled(locked)
        if connected { Button("Inspect tools →") { settings.open("Tools & permissions",detail:"Tools") } }
    }
    private var form: some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { Text(editingID.isEmpty ? "Add MCP server" : "Edit MCP server").wixalFont(size:14,weight:.medium); Spacer(); Button("Cancel") { editor=false }.buttonStyle(.plain) }
            Picker("Connection type",selection:$transport) { Text("Local executable").tag("stdio"); Text("Remote HTTPS").tag("http") }.pickerStyle(.segmented)
            TextField("Server name",text:$name).wixalField().accessibilityLabel("MCP server name")
            TextField(transport == "http" ? "https://server.example/mcp" : "Executable path or command",text:$endpoint).wixalField().accessibilityLabel(transport == "http" ? "MCP endpoint" : "MCP executable")
            if transport == "stdio" {
                Text("Arguments · one per line").wixalFont(size:11)
                TextEditor(text:$arguments).accessibilityLabel("MCP arguments, one per line").wixalFont(size:12,design:.monospaced).scrollContentBackground(.hidden).frame(height:90).wixalField()
                Text("Spaces on one line stay within one argument. No shell is used.").wixalFont(size:10).foregroundStyle(theme.muted)
            } else {
                Toggle("Sign in with OAuth",isOn:$oauth)
                if oauth { TextField("Registered client ID (optional)",text:$clientID).wixalField(); Text("Leave empty if the server supports automatic client registration.").wixalFont(size:10).foregroundStyle(theme.muted) }
            }
            Text(editingID.isEmpty ? "Saving does not connect or launch the server." : "Saving disconnects this server. Connect again to test the updated configuration.").wixalFont(size:11).foregroundStyle(theme.muted)
            Button("Save server") { saveServer() }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked || name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || endpoint.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
        }.wixalFont(size:11).wixalCard()
    }
    private func clear() { editingID=""; name=""; endpoint=""; transport="stdio"; arguments=""; oauth=false; clientID="" }
    private func edit(_ server: [String:Any]) {
        editingID=textValue(server["id"]); name=textValue(server["name"]); transport=textValue(server["transport"]) == "http" ? "http" : "stdio"; endpoint=textValue(server[transport == "http" ? "url" : "command"]); arguments=(server["args"] as? [String] ?? []).joined(separator:"\n"); oauth=server["oauth"] as? Bool ?? false; clientID=textValue(server["clientId"]); editor=true
    }
    private func saveServer() {
        var params:[String:Any] = ["name":name,"transport":transport]
        if transport == "http" { params["url"]=endpoint; params["oauth"]=oauth; params["clientId"]=clientID }
        else { params["command"]=endpoint; params["args"]=arguments.split(separator:"\n",omittingEmptySubsequences:true).map(String.init) }
        if !editingID.isEmpty { params["id"]=editingID }
        settings.perform(engine,editingID.isEmpty ? "mcp-add" : "mcp-update",params,success:"Server saved; connect to discover its tools") { _ in editor=false; Task { await refresh() } }
    }
    private func action(_ method: String, _ id: String, success: String) { settings.perform(engine,method,["id":id],success:success) { _ in Task { await refresh() } } }
    private func refresh() async {
        guard engine.connected else { statusError="Engine disconnected. Reconnect to inspect server status."; return }
        do { statuses=records(try await engine.call("mcp-status")); statusError="" } catch { statusError=error.localizedDescription }
    }
}
