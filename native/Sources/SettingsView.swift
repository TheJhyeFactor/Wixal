import SwiftUI
import AppKit

struct SettingsView: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    var navigate: (String)->Void
    var previewLaunch: ()->Void
    @Environment(\.wixalTheme) private var colours
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @ViewState private var resetAppearance = false
    private var ui: [String:Any] { engine.state["ui"] as? [String:Any] ?? [:] }
    private var account: [String:Any] { engine.state["account"] as? [String:Any] ?? [:] }
    private var signedIn: Bool { account["signedIn"] as? Bool ?? false }
    private var profile: [String:Any] { account["profile"] as? [String:Any] ?? [:] }
    private var owner: String { signedIn ? "account:" + textValue(profile["id"]) : "guest" }
    private var identityLabel: String { signedIn ? "Account · " + textValue(profile["email"]) : "Guest · this Mac" }
    private var memoryWritable: Bool { !signedIn || profile["verified"] as? Bool == true }
    private var locked: Bool { engine.busy || settings.saving || !engine.connected }
    private var appearanceLocked: Bool { settings.saving || !engine.connected }
    private var projectScope: String { engine.project == nil ? "Personal workspace" : "Project: " + textValue(engine.project?["name"]) }
    private var mode: String { textValue(engine.project?["memoryMode"]).isEmpty ? (engine.project == nil ? "global" : "project") : textValue(engine.project?["memoryMode"]) }
    private var globalOn: Bool { engine.state["globalMemoryEnabled"] as? Bool ?? true }
    private var draft: String { settings.drafts[owner]?.text ?? engine.activeMemory }
    private var category: SettingsCategory { SettingsCategory.all.first { $0.id == settings.category } ?? SettingsCategory.all[0] }
    private var matches: [SettingsCategory] {
        SettingsCategory.all.filter { settings.search.isEmpty || ($0.id + " " + $0.terms).localizedCaseInsensitiveContains(settings.search) }
    }
    var body: some View {
        GeometryReader { geometry in
            HStack(spacing:0) {
                navigation.frame(width:geometry.size.width < 720 ? 174 : 204)
                Rectangle().fill(colours.line).frame(width:1)
                VStack(spacing:0) {
                    if !settings.search.isEmpty { searchResults }
                    else if let detail = settings.detail { detailView(detail) }
                    else if settings.category == "Models & performance" { ModelsView(engine:engine) }
                    else if settings.category == "Account" { AccountView(engine:engine,navigate:navigate).disabled(settings.saving || engine.busy) }
                    else { ScrollView { VStack(alignment:.leading,spacing:24) { heading; categoryContent }.padding(geometry.size.width < 720 ? 20 : 28).frame(maxWidth:820,alignment:.leading).frame(maxWidth:.infinity) }.id(settings.category) }
                    feedback
                }.frame(maxWidth:.infinity,maxHeight:.infinity)
            }.background(colours.background)
        }
        .onAppear { syncDraft(); engine.refreshMemory() }
        .onChange(of:engine.activeMemory) { _,_ in syncDraft() }
        .onChange(of:owner) { _,_ in syncDraft() }
        .alert("Reset appearance to defaults?",isPresented:$resetAppearance) {
            Button("Cancel",role:.cancel) {}
            Button("Reset appearance") { save("settings",["ui":["theme":"sakura","textSize":13,"reduceMotion":false,"launchAnimation":true,"launchSound":true,"appIcon":"theme"]]) }
        } message: { Text("Restores Sakura, default text size, theme-matched icon and the launch intro. Workspace, memory and account preferences are kept.") }
    }
    private var navigation: some View {
        VStack(alignment:.leading,spacing:18) {
            Text("Settings").wixalFont(size:20,weight:.medium)
            HStack(spacing:7) {
                Image(systemName:"magnifyingglass").foregroundStyle(colours.muted)
                TextField("Find a setting…",text:$settings.search).textFieldStyle(.plain).wixalFont(size:11).accessibilityLabel("Find a setting")
                if !settings.search.isEmpty { Button { settings.search="" } label:{Image(systemName:"xmark.circle.fill")}.buttonStyle(WixalButtonStyle(inline:true)).accessibilityLabel("Clear settings search") }
            }.padding(9).background(colours.background,in:RoundedRectangle(cornerRadius:6)).overlay(RoundedRectangle(cornerRadius:6).stroke(colours.line,lineWidth:1))
            ScrollView {
                VStack(spacing:4) {
                    ForEach(SettingsCategory.all) { item in
                        Button { settings.open(item.id) } label: {
                            HStack(spacing:10) { Image(systemName:item.symbol).frame(width:18).accessibilityHidden(true); Text(item.id).fixedSize(horizontal:false,vertical:true); Spacer(minLength:0) }
                                .wixalFont(size:11).padding(10).frame(maxWidth:.infinity,alignment:.leading)
                                .background(settings.category == item.id ? colours.selected : .clear,in:RoundedRectangle(cornerRadius:6))
                                .overlay(RoundedRectangle(cornerRadius:6).stroke(settings.category == item.id ? colours.line : .clear,lineWidth:1))
                                .foregroundStyle(settings.category == item.id ? colours.accent : colours.text)
                        }.buttonStyle(WixalNavigationButtonStyle(selected:settings.category == item.id)).accessibilityAddTraits(settings.category == item.id ? .isSelected : [])
                    }
                }
            }.scrollIndicators(.hidden)
            VStack(alignment:.leading,spacing:6) {
                Label(signedIn ? "Wixal account" : "Guest workspace",systemImage:signedIn ? "person.crop.circle" : "externaldrive").wixalFont(size:10)
                if settings.drafts.values.contains(where: { $0.text != $0.baseline }) { Text("Unsaved instructions retained").wixalFont(size:10).foregroundStyle(colours.accent) }
            }.foregroundStyle(colours.muted)
        }.padding(14).background(colours.panel)
    }
    private var heading: some View {
        VStack(alignment:.leading,spacing:8) {
            Text(category.id).wixalFont(size:25,weight:.medium).tracking(-0.5)
            Text(category.detail).wixalFont(size:12).foregroundStyle(colours.muted)
        }
    }
    private var feedback: some View {
        VStack(alignment:.leading,spacing:6) {
            if !settings.failure.isEmpty { Label(settings.failure,systemImage:"exclamationmark.triangle").foregroundStyle(.red).textSelection(.enabled) }
            if !settings.status.isEmpty { HStack { if settings.saving { ProgressView().controlSize(.small) } else { Image(systemName:settings.failure.isEmpty ? "checkmark" : "exclamationmark.circle") }; Text(settings.status); Spacer(); if !settings.saving { Button("Dismiss") { settings.status=""; settings.failure="" }.buttonStyle(WixalButtonStyle(inline:true)) } } }
            if engine.busy { Text("A task is running. Appearance and navigation remain available; changes to its context, tools and data wait until it finishes.") }
        }.wixalFont(size:11).foregroundStyle(colours.muted).padding(settings.status.isEmpty && settings.failure.isEmpty && !engine.busy ? 0 : 12).frame(maxWidth:.infinity,alignment:.leading).background(colours.panel).accessibilityElement(children:.contain)
    }
    private var searchResults: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                Text("Search settings").wixalFont(size:25,weight:.medium)
                Text("\(matches.count) matching categories").wixalFont(size:11).foregroundStyle(colours.muted)
                ForEach(matches) { item in Button { settings.open(item.id) } label: { HStack { Image(systemName:item.symbol); VStack(alignment:.leading,spacing:6) { Text(item.id); Text(item.detail).wixalFont(size:11).foregroundStyle(colours.muted) }; Spacer(); Image(systemName:"chevron.right") }.frame(maxWidth:.infinity,alignment:.leading).wixalCard() }.buttonStyle(WixalButtonStyle(inline:true)) }
                if matches.isEmpty { Text("No matching settings. Try memory, sound, tools or backup.").foregroundStyle(colours.muted) }
            }.padding(24).frame(maxWidth:.infinity,alignment:.leading)
        }
    }
    @ViewBuilder private var categoryContent: some View {
        switch settings.category {
        case "Models & performance": EmptyView()
        case "Context & memory": context
        case "Tools & permissions": permissions
        case "Connections & sharing": SettingsConnectionsView(engine:engine,settings:settings)
        case "Data & sync": SettingsDataView(engine:engine,settings:settings)
        case "General & about": general
        default: appearance
        }
    }
    @ViewBuilder private func detailView(_ detail: String) -> some View {
        VStack(spacing:0) {
            HStack { Button { settings.detail=nil } label:{Label(settings.category,systemImage:"chevron.left")}.buttonStyle(WixalButtonStyle(inline:true)); Spacer() }.wixalFont(size:11).padding(16).background(colours.panel)
            switch detail {
            case "Models": ModelsView(engine:engine)
            case "Performance": PerformanceView(engine:engine)
            case "Tools": ToolsDrawer(engine:engine,close:{settings.detail=nil})
            case "Memory": MemoryDrawer(engine:engine,close:{settings.detail=nil})
            default: ConnectionsView(engine:engine,navigate:{ route in if route == "Settings:Connections" { settings.detail=nil } else { navigate(route) } })
            }
        }
    }
    private var appearance: some View {
        QuietAppearanceSettings(ui:ui,locked:appearanceLocked,systemReduceMotion:systemReduceMotion,
            save:saveUI,previewLaunch:previewLaunch,reset:{resetAppearance=true})
    }
    private var context: some View { QuietContextSettings(engine:engine,settings:settings) }
    private var permissions: some View {
        Group {
            WixalSection(title:"Tool installation") {
                SettingsRow(title:"Allow AI to install tools automatically",detail:"Chat and agents can install missing programs from the approved catalogue. Applies to all projects on this Mac.",scope:"Global") {
                    Toggle("Allow AI to install tools automatically",isOn:Binding(get:{(engine.state["addonPolicy"] as? [String:Any])?["automaticInstall"] as? Bool ?? false},set:{save("addon-policy",["automaticInstall":$0])})).labelsHidden().toggleStyle(.switch).controlSize(.small)
                }.wixalCard().disabled(locked)
                Text("When off, AI requests ask before installation. Installed tools are available in Cybersecurity, Chat and Agents. New download sources and system setup still need review; execution follows the task's existing permissions.").wixalFont(size:11).foregroundStyle(colours.muted)
                Button("Open Tools →") { navigate("Tools") }.buttonStyle(WixalButtonStyle(outlined:true))
            }
            WixalSection(title:"Action review") {
                SettingsRow(title:"Review policy",detail:"Edits, commands and network actions follow this workspace’s policy.",scope:projectScope) {
                    Picker("Review policy",selection:Binding(get:{textValue(engine.project?["approvalMode"] ?? engine.state["personalApprovalMode"]).isEmpty ? "review" : textValue(engine.project?["approvalMode"] ?? engine.state["personalApprovalMode"])},set:{save("settings",["approvalMode":$0])})) { Text("Review each action").tag("review"); Text("Allow without individual review").tag("bypass") }.labelsHidden()
                }.wixalCard().disabled(locked)
                Text(textValue(engine.project?["approvalMode"] ?? engine.state["personalApprovalMode"]) == "bypass" ? "Actions can run without individual review in this workspace." : "Applicable actions pause for your review. The model chooses available tools within the current task scope.").wixalFont(size:11).foregroundStyle(colours.muted)
            }
            WixalSection(title:"Available tools") {
                SettingsRow(title:"Available tools",detail:"The model discovers and chooses project, command, web, memory and connected tools. No tool switches are needed for Chat or Agents.",scope:"Current workspace") { Button("Inspect tools →") { settings.detail="Tools" }.buttonStyle(WixalButtonStyle(outlined:true)) }.wixalCard()
            }
            WixalSection(title:"Skills",detail:"Import Markdown instructions, then select a skill in the composer to use it.") {
                Button("Import Markdown skill…",action:engine.importSkill).buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked)
                if records(engine.state["skills"]).isEmpty { Text("No skills imported. Imported skills appear here with their instructions and source.").wixalFont(size:11).foregroundStyle(colours.muted) }
                ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset) { _,skill in
                    SettingsSkillCard(engine:engine,settings:settings,skill:skill)
                }
            }
        }
    }
    private var general: some View {
        Group {
            WixalSection(title:"Workspace behaviour") {
                SettingsCard {
                    SettingsRow(title:"Compact sidebar",detail:"Keep more space for conversations. Settings uses a compact workspace rail.") { Toggle("Compact sidebar",isOn:bool("sidebarCollapsed")).labelsHidden().toggleStyle(.switch).controlSize(.small).disabled(appearanceLocked) }
                    Divider()
                    SettingsRow(title:"Background schedules",detail:"Run configured schedules while Wixal is closed, when your Mac is awake. Actions requiring review pause.") { Toggle("Background schedules",isOn:Binding(get:{(engine.state["backgroundScheduler"] as? [String:Any])?["enabled"] as? Bool ?? false},set:{save("background-settings",["enabled":$0])})).labelsHidden().toggleStyle(.switch).controlSize(.small).disabled(locked) }
                }
                Button("Manage recurring tasks →") { navigate("Tasks") }.buttonStyle(WixalButtonStyle(inline:true))
            }
            SettingsDiagnosticsView(engine:engine,settings:settings)
            WixalSection(title:"Keyboard shortcuts") {
                SettingsCard { ForEach([("New conversation","⌘ N"),("Open project","⌘ O"),("Settings","⌘ ,"),("Find a command","⌘ K"),("Models","⌘ L"),("Project files","⌘ ⇧ F"),("Tool kit","⌘ ⇧ T"),("Terminal","⌘ J")],id:\.0) { shortcut in HStack { Text(shortcut.0); Spacer(); Text(shortcut.1).foregroundStyle(colours.muted) }.wixalFont(size:11).padding(.vertical,7) } }
            }
            WixalSection(title:"About Wixal") {
                Text("Wixal · \(Bundle.main.object(forInfoDictionaryKey:"WixalReleaseVersion") as? String ?? "Local preview")").wixalFont(size:12)
                Text("Native alpha. Updates are available from GitHub; install them manually.").wixalFont(size:11).foregroundStyle(colours.muted)
                Link("Releases ↗",destination:URL(string:"https://github.com/TheJhyeFactor/Wixal/releases")!).wixalFont(size:11)
                ViewThatFits(in:.horizontal) { HStack { aboutButtons }; VStack(alignment:.leading) { aboutButtons } }
            }
        }
    }
    @ViewBuilder private var aboutButtons: some View {
        Button("Run setup…") { navigate("Setup") }
        Button("Terms · draft") { navigate("Terms") }
        Button("Privacy · draft") { navigate("Privacy") }
    }
    private func syncDraft() { settings.syncDraft(owner,saved:engine.activeMemory) }
    private func save(_ method: String, _ params: [String:Any]) { settings.perform(engine,method,params) }
    private func saveUI(_ value: [String:Any]) { save("settings",["ui":value]) }
    private func bool(_ key: String, default fallback: Bool = false) -> Binding<Bool> { Binding(get:{ui[key] as? Bool ?? fallback},set:{saveUI([key:$0])}) }

}

private struct SettingsSkillCard: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    let skill: [String:Any]
    @ViewState private var confirmRemove = false
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            Text(textValue(skill["name"])).wixalFont(size:12,weight:.medium)
            Text(textValue(skill["description"])).wixalFont(size:11).foregroundStyle(theme.muted)
            DisclosureGroup("Instructions & source") { Text(textValue(skill["source"])).wixalFont(size:10).foregroundStyle(theme.muted).textSelection(.enabled); Text(textValue(skill["content"])).wixalFont(size:12).textSelection(.enabled) }
            Button("Remove skill…",role:.destructive) { confirmRemove=true }.disabled(engine.busy || settings.saving)
        }.wixalFont(size:11).wixalCard().alert("Remove this imported skill?",isPresented:$confirmRemove) { Button("Cancel",role:.cancel) {}; Button("Remove skill",role:.destructive) { settings.perform(engine,"skill-delete",["id":textValue(skill["id"])],success:"Skill removed") } } message: { Text("The original Markdown file is kept. Import it again to restore the skill.") }
    }
}
