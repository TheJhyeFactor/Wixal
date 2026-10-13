import SwiftUI

struct QuietContextSettings: View {
    @ObservedObject var engine: EngineClient
    @ObservedObject var settings: SettingsState
    @Environment(\.wixalTheme) private var colours
    private var account:[String:Any]{engine.state["account"] as? [String:Any] ?? [:]}
    private var profile:[String:Any]{account["profile"] as? [String:Any] ?? [:]}
    private var signedIn:Bool{account["signedIn"] as? Bool ?? false}
    private var owner:String{signedIn ? "account:"+textValue(profile["id"]) : "guest"}
    private var identityLabel:String{signedIn ? "Account · "+textValue(profile["email"]) : "Guest · this Mac"}
    private var memoryWritable:Bool{!signedIn || profile["verified"] as? Bool == true}
    private var locked:Bool{engine.busy || settings.saving || !engine.connected}
    private var projectScope:String{engine.project == nil ? "Personal workspace" : "Project: "+textValue(engine.project?["name"])}
    private var mode:String{textValue(engine.project?["memoryMode"]).isEmpty ? (engine.project == nil ? "global" : "project") : textValue(engine.project?["memoryMode"])}
    private var globalOn:Bool{engine.state["globalMemoryEnabled"] as? Bool ?? true}
    private var historyOn:Bool{(engine.project ?? engine.state)["referenceHistory"] as? Bool ?? true}
    private var draft:String{settings.drafts[owner]?.text ?? engine.activeMemory}
    private var projectEligible:Bool{engine.project != nil && ["project","both"].contains(mode)}
    private var globalEligible:Bool{["global","both"].contains(mode) && globalOn}
    var body:some View {
        VStack(alignment:.leading,spacing:18){
            HStack{Label(projectScope,systemImage:engine.project == nil ? "person.crop.circle" : "folder");Spacer();Text("On this Mac").foregroundStyle(colours.muted)}.wixalFont(size:11)
            QuietSettingsTabs(items:["Context","Instructions","Saved memory","Suggestions"],selection:$settings.contextTab)
            if settings.contextTab=="Context"{
                ViewThatFits(in:.horizontal){
                    HStack(alignment:.top,spacing:16){conversation.frame(width:400);sourceEligibility.frame(width:220)}
                    VStack(alignment:.leading,spacing:16){conversation;sourceEligibility}
                }
                summary
            }
            else if settings.contextTab=="Instructions"{instructions}
            else { MemoryDrawer(engine:engine,close:{},section:settings.contextTab,settings:settings).id(owner+":"+textValue(engine.state["activeProject"])).disabled(settings.saving || !engine.connected) }
        }
    }
    private var conversation:some View {
        SettingsCard {
            SettingsRow(title:"Context window",detail:contextHint,scope:"All workspaces") {
                Picker("Context window",selection:Binding(get:{engine.state["contextSize"] as? Int ?? 8192},set:{save("model-context",["contextSize":$0])})) {
                    let value=engine.state["contextSize"] as? Int ?? 8192
                    if ![4096,8192,16384,32768].contains(value){Text("\(value) tokens · model limit").tag(value)}
                    ForEach([4096,8192,16384,32768],id:\.self){Text("\($0/1024)k tokens").tag($0)}
                }.labelsHidden()
            }
            Divider()
            SettingsRow(title:"Summarise older messages",detail:"Full conversation history remains saved.",scope:"All workspaces") { Toggle("Summarise older messages",isOn:Binding(get:{engine.state["autoSummary"] as? Bool ?? true},set:{save("settings",["autoSummary":$0])})).labelsHidden().toggleStyle(.switch).controlSize(.small) }
            Divider()
            SettingsRow(title:"Recall scope",detail:engine.project == nil ? "Personal chats use global recall. Open a project for project scope." : "Choose the saved sources this project can use.",scope:projectScope) {
                Picker("Recall scope",selection:Binding(get:{mode},set:{save("memory-settings",["mode":$0])})){Text("Project only").tag("project");Text("Global only").tag("global");Text("Project + global").tag("both");Text("Off").tag("off")}.labelsHidden().disabled(engine.project == nil)
            }
            Divider()
            SettingsRow(title:"Use global memory",detail:"Includes global instructions and saved notes when scope allows.",scope:"All workspaces"){Toggle("Use global memory",isOn:Binding(get:{globalOn},set:{save("settings",["globalMemoryEnabled":$0])})).labelsHidden().toggleStyle(.switch).controlSize(.small)}
            Divider()
            SettingsRow(title:"Reference earlier chats",detail:"Uses relevant earlier conversations within the selected scope.",scope:projectScope){Toggle("Reference earlier chats",isOn:Binding(get:{historyOn},set:{save("memory-policy",["referenceHistory":$0])})).labelsHidden().toggleStyle(.switch).controlSize(.small)}
        }.disabled(locked)
    }
    private var sourceEligibility:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Eligible sources").wixalFont(size:13,weight:.medium)
            Text("Sources allowed by these settings. The actual memories used are shown under Saved memory.").wixalFont(size:11).foregroundStyle(colours.muted)
            eligible("Current conversation",enabled:true,status:"Always available")
            eligible("Conversation summary",enabled:engine.session?["summary"] != nil || (engine.state["autoSummary"] as? Bool ?? true),status:engine.session?["summary"] != nil ? "Saved summary available" : "Created when needed")
            eligible("Project notes",enabled:projectEligible)
            eligible("Global instructions & notes",enabled:globalEligible)
            eligible("Earlier chats",enabled:historyOn && (projectEligible || globalEligible))
        }.wixalCard()
    }
    private func eligible(_ title:String,enabled:Bool,status:String="Included when relevant")->some View {
        HStack(alignment:.top){Image(systemName:enabled ? "checkmark.circle" : "minus.circle").foregroundStyle(enabled ? colours.accent : colours.muted);VStack(alignment:.leading,spacing:4){Text(title);Text(enabled ? status : "Excluded").foregroundStyle(colours.muted)};Spacer(minLength:0)}.wixalFont(size:11)
    }
    @ViewBuilder private var summary:some View {
        if let value=engine.session?["summary"] as? [String:Any]{
            DisclosureGroup("Saved conversation summary"){
                Text(textValue(value["content"])).wixalFont(size:11).textSelection(.enabled)
                Text("\(value["messageCount"] as? Int ?? 0) messages · \(textValue(value["method"]))").wixalFont(size:10).foregroundStyle(colours.muted)
                Button("Clear summary"){save("summary-clear",["sessionId":textValue(engine.state["activeSession"])])}.disabled(locked)
            }.wixalFont(size:12).wixalCard()
        }
    }
    private var instructions:some View {
            WixalSection(title:"Global instructions",detail:identityLabel + ". Saved explicitly; drafts are retained when you navigate away.") {
                VStack(alignment:.leading,spacing:10) {
                    TextEditor(text:Binding(get:{draft},set:{settings.updateDraft(owner,text:$0,saved:engine.activeMemory)})).accessibilityLabel("Global instructions").wixalFont(size:12).scrollContentBackground(.hidden).frame(height:110).wixalField().disabled(!memoryWritable || settings.saving)
                    ViewThatFits(in:.horizontal) { HStack { instructionFooter }; VStack(alignment:.leading,spacing:10) { instructionFooter } }
                    if !memoryWritable { Text("Verify your email in Account to save account instructions.").wixalFont(size:11).foregroundStyle(colours.muted); Button("Open Account") { settings.open("Account") }.buttonStyle(WixalButtonStyle(inline:true)) }
                }.wixalCard()
            }
    }
    @ViewBuilder private var instructionFooter: some View {
        Text("\(draft.count) / 1,200").wixalFont(size:10).foregroundStyle(draft.count > 1200 ? .red : colours.muted)
        Text(settings.dirty(owner) ? "Unsaved changes" : "No unsaved changes").wixalFont(size:10).foregroundStyle(settings.dirty(owner) ? colours.accent : colours.muted)
        Button("Save instructions") {
            let key=owner, value=draft
            settings.perform(engine,"global-memory-save",["content":value],success:"Global instructions saved") { _ in settings.drafts[key] = .init(text:value,baseline:value) }
        }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked || !memoryWritable || draft.count > 1200 || !settings.dirty(owner))
    }
    private var contextHint: String {
        let model=records(engine.modelStatus["installed"]).first { textValue($0["name"]) == textValue(engine.state["model"]) }
        if let suggested=model?["suggestedContext"] as? Int { return "Suggested: \(suggested/1024)k for \(textValue(model?["displayName"]).isEmpty ? textValue(model?["name"]) : textValue(model?["displayName"])). Larger windows use more memory." }
        return "Larger windows use more memory. Models shows the selected model’s limits and fit estimates."
    }
    private func save(_ method:String,_ params:[String:Any]){settings.perform(engine,method,params){_ in engine.refreshMemory()}}
}
