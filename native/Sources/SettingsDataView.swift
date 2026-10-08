import SwiftUI
import AppKit
import UniformTypeIdentifiers

struct SettingsDataView: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    @Environment(\.wixalTheme) private var theme
    @ViewState private var preview: [String:Any] = [:]
    @ViewState private var storage: [String:Any] = [:]
    @ViewState private var importPresented = false
    private var locked: Bool { settings.saving || engine.busy || !engine.connected }
    var body: some View {
        WorkspaceSyncView(engine:engine)
        WixalSection(title:"Workspace backup",detail:"Save projects, conversations with images, project notes, tasks, skills and paused schedules. Account credentials, global account preferences, models, project files and tool permissions are excluded. The backup file is not encrypted; saved chats may contain private information.") {
            Button("Create backup…",action:backup).buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked)
        }
        WixalSection(title:"Restore or import",detail:"Choose a native backup or an existing Electron workspace file. Review records before merging. Existing IDs and preferences are retained; schedules are paused and imported projects require action review.") {
            Button("Choose source…",action:chooseSource).buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked)
            let migration=engine.state["migration"] as? [String:Any] ?? [:]
            if !migration.isEmpty {
                DisclosureGroup("Last import") {
                    Text(textValue(migration["source"])).textSelection(.enabled)
                    ForEach((migration["counts"] as? [String:Int] ?? [:]).keys.sorted(),id:\.self) { key in Text("\(key): \((migration["counts"] as? [String:Int])?[key] ?? 0) imported · \((migration["skippedExisting"] as? [String:Int])?[key] ?? 0) already present") }
                    ForEach(migration["warnings"] as? [String] ?? [],id:\.self) { Text($0) }
                }.wixalFont(size:11).foregroundStyle(theme.muted)
            }
        }
        WixalSection(title:"Storage") {
            let path=textValue(storage["workspace"])
            Text(path.isEmpty ? "Reading storage location…" : path).wixalFont(size:11,design:.monospaced).textSelection(.enabled)
            Text("Workspace data: \(bytes(storage["workspaceBytes"])) · Model library: \(bytes(storage["modelBytes"]))").wixalFont(size:11).foregroundStyle(theme.muted)
            ViewThatFits(in:.horizontal) { HStack { storageButtons }; VStack(alignment:.leading) { storageButtons } }
            Text("Project files live in their original folders. Manage model downloads and removal from Models.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
        .task { await refreshStorage() }
        .sheet(isPresented:$importPresented) {
            VStack(alignment:.leading,spacing:16) {
                Text("Review workspace import").wixalFont(size:21,weight:.medium)
                Text(textValue(preview["source"])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)
                ScrollView {
                    VStack(alignment:.leading,spacing:10) {
                        ForEach((preview["counts"] as? [String:Int] ?? [:]).keys.sorted(),id:\.self) { key in Text("\(key.capitalized): \((preview["counts"] as? [String:Int])?[key] ?? 0) new · \((preview["skippedExisting"] as? [String:Int])?[key] ?? 0) already present") }
                        ForEach(Array((preview["warnings"] as? [String] ?? []).enumerated()),id:\.offset) { _,warning in Text(warning).foregroundStyle(theme.muted) }
                    }.wixalFont(size:12).frame(maxWidth:.infinity,alignment:.leading)
                }
                Text("Merges saved work without replacing existing records or preferences. Schedules remain paused. Account sign-ins and companion pairing are excluded.").wixalFont(size:11).foregroundStyle(theme.muted)
                HStack {
                    Button("Cancel") { importPresented=false }.keyboardShortcut(.cancelAction)
                    Spacer()
                    Button("Import saved work") {
                        settings.perform(engine,"workspace-import",["path":textValue(preview["source"]),"digest":textValue(preview["digest"])],success:"Saved work imported; existing records and preferences kept") { _ in importPresented=false; Task { await refreshStorage() } }
                    }.disabled(locked || (preview["counts"] as? [String:Int] ?? [:]).values.reduce(0,+) == 0)
                }
                if !settings.failure.isEmpty { Text(settings.failure).foregroundStyle(.red).wixalFont(size:11) }
            }.padding(24).frame(width:540,height:450).background(theme.background).foregroundStyle(theme.text).environment(\.wixalTheme,theme).interactiveDismissDisabled(settings.saving)
        }
    }
    @ViewBuilder private var storageButtons: some View {
        Button("Show workspace in Finder") { show(textValue(storage["workspace"])) }.disabled(textValue(storage["workspace"]).isEmpty)
        Button("Show models in Finder") { show(textValue(storage["models"])) }.disabled(textValue(storage["models"]).isEmpty)
        Button("Refresh") { Task { await refreshStorage() } }.disabled(settings.saving || !engine.connected)
    }
    private func bytes(_ value: Any?) -> String { guard let number=value as? NSNumber else { return "Unavailable" }; return ByteCountFormatter.string(fromByteCount:number.int64Value,countStyle:.file) }
    private func show(_ path: String) { NSWorkspace.shared.open(URL(fileURLWithPath:path)) }
    private func backup() {
        let panel=NSSavePanel(); panel.nameFieldStringValue="Wixal-backup-\(Date().formatted(.iso8601.year().month().day())).json"; panel.allowedContentTypes=[.json]
        panel.begin { answer in guard answer == .OK,let url=panel.url else { return }; settings.perform(engine,"workspace-backup",["path":url.path],success:"Workspace backup saved") }
    }
    private func chooseSource() {
        let panel=NSOpenPanel(); panel.canChooseDirectories=false; panel.allowsMultipleSelection=false; panel.allowedContentTypes=[.json]
        panel.begin { answer in guard answer == .OK,let url=panel.url else { return }; settings.perform(engine,"workspace-import-preview",["path":url.path],success:"Import preview ready") { value in preview=value as? [String:Any] ?? [:]; importPresented=true } }
    }
    private func refreshStorage() async {
        do { storage=try await engine.call("workspace-storage") as? [String:Any] ?? [:] }
        catch { settings.failure=error.localizedDescription }
    }
}

struct SettingsDiagnosticsView: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    @Environment(\.wixalTheme) private var theme
    @ViewState private var report: [String:Any] = [:]
    @ViewState private var presented = false
    @ViewState private var restart = false
    var body: some View {
        WixalSection(title:"Diagnostics") {
            SettingsCard {
                SettingsRow(title:engine.connected ? "Workspace engine connected" : "Workspace engine disconnected",detail:engine.busy ? "A task is running. Finish or stop it before restarting." : "Check engine health and copy a report without chat content, paths or credentials.") {
                    Button("Inspect diagnostics") { settings.perform(engine,"workspace-diagnostics",success:"Diagnostics ready") { value in report=value as? [String:Any] ?? [:]; presented=true } }.disabled(!engine.connected || settings.saving)
                }
                Divider()
                SettingsRow(title:"Restart engine",detail:"Reconnect the workspace engine. Pending actions are not replayed.") { Button("Restart…") { restart=true }.disabled(engine.busy || engine.restarting || settings.saving) }
            }
        }
        .alert("Restart the workspace engine?",isPresented:$restart) { Button("Cancel",role:.cancel) {}; Button("Restart engine") { engine.restart() } } message: { Text("Closes engine connections and starts a fresh helper. Saved work is retained; uncertain actions are not replayed.") }
        .sheet(isPresented:$presented) {
            VStack(alignment:.leading,spacing:16) {
                Text("Workspace diagnostics").wixalFont(size:21,weight:.medium)
                ScrollView { Text(pretty(report)).wixalFont(size:12,design:.monospaced).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading) }
                Text("Includes versions, counts and engine status. Excludes chat content, project names and paths, account identifiers and credentials.").wixalFont(size:11).foregroundStyle(theme.muted)
                HStack { Button("Copy report") { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(pretty(report),forType:.string); settings.status="Diagnostic report copied" }; Spacer(); Button("Done") { presented=false }.keyboardShortcut(.cancelAction) }
            }.padding(24).frame(width:540,height:460).background(theme.background).foregroundStyle(theme.text).environment(\.wixalTheme,theme)
        }
    }
}
