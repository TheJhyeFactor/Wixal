import SwiftUI
import AppKit

struct SettingsView:View {
    @ObservedObject var engine:EngineClient
    @Binding var theme:String
    var navigate:(String)->Void
    var previewLaunch:()->Void
    @Environment(\.wixalTheme) private var colours
    @ViewState<String> private var notes=""
    @ViewState<String> private var mcpName=""
    @ViewState<String> private var mcpCommand=""
    @ViewState<String> private var mcpArgs="[]"
    @ViewState<String> private var mcpTransport="stdio"
    @ViewState<Bool> private var mcpOAuth=false
    @ViewState<String> private var mcpClientID=""
    @ViewState<[[String:Any]]> private var mcpStatus=[]
    private var ui:[String:Any]{engine.state["ui"] as? [String:Any] ?? [:]}
    private var memoryWritable:Bool{let account=engine.state["account"] as? [String:Any] ?? [:];return account["signedIn"] as? Bool != true || (account["profile"] as? [String:Any])?["verified"] as? Bool == true}
    private func bool(_ key:String,default fallback:Bool=false)->Binding<Bool>{Binding(get:{ui[key] as? Bool ?? fallback},set:{engine.action("settings",["ui":[key:$0]])})}
    var body:some View {
        WixalPage(eyebrow:"MAKE WIXAL YOURS",title:"Settings",subtitle:"Preferences save automatically on this Mac."){
            WixalSection(title:"Account & setup"){HStack{Button("Manage Wixal account ↗"){navigate("Account")};Button("Run setup again ↗"){navigate("Setup")}}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))}
            WixalSection(title:"Appearance"){
                HStack(spacing:10){ForEach(["Sakura","Midnight","Forest","Paper"],id:\.self){name in themeCard(name)}}
                VStack(spacing:0){
                    PreferenceRow(title:"Conversation text size",detail:"Applies to messages and the terminal."){
                        Picker("Conversation text size",selection:Binding(get:{ui["textSize"] as? Int ?? 13},set:{engine.action("settings",["ui":["textSize":$0]])})){Text("Default").tag(13);Text("Large").tag(15);Text("Extra large").tag(17)}.labelsHidden().frame(width:145)
                    }
                    Divider().overlay(colours.line)
                    PreferenceRow(title:"Reduce motion",detail:"Turn off interface animations. Your Mac’s preference also applies."){Toggle("Reduce motion",isOn:bool("reduceMotion")).labelsHidden().toggleStyle(.switch).controlSize(.small)}
                }.wixalCard()
            }
            WixalSection(title:"App icon",detail:"Changes Wixal’s icon in the Mac Dock while the app is running."){
                PreferenceRow(title:"Match icon to theme",detail:"Sakura → Sakura, Midnight → Midnight, Paper → Pearl, Forest → Copper."){Toggle("Match icon to theme",isOn:Binding(get:{textValue(ui["appIcon"]).isEmpty || textValue(ui["appIcon"])=="theme"},set:{engine.action("settings",["ui":["appIcon":$0 ? "theme" : iconVariant]])})).labelsHidden().toggleStyle(.switch).controlSize(.small)}
                HStack(spacing:10){ForEach(["sakura","midnight","pearl","copper"],id:\.self){variant in iconCard(variant)}}
            }
            WixalSection(title:"Launch"){
                VStack(spacing:0){PreferenceRow(title:"Launch animation",detail:"The original Wixal wordmark reveal when the window opens."){Toggle("Launch animation",isOn:bool("launchAnimation",default:true)).labelsHidden().toggleStyle(.switch).controlSize(.small)};Divider().overlay(colours.line);PreferenceRow(title:"Launch sound",detail:"Play the quiet Wixal chime when the app opens."){Toggle("Launch sound",isOn:bool("launchSound",default:true)).labelsHidden().toggleStyle(.switch).controlSize(.small)}}.wixalCard()
            }
            Button("Preview launch intro ↗",action:previewLaunch).buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))
            WixalSection(title:"Workspace"){
                PreferenceRow(title:"Summarize older messages",detail:"Keep conversation context as chats grow. Full history remains saved."){Toggle("Summarize older messages",isOn:Binding(get:{engine.state["autoSummary"] as? Bool ?? true},set:{engine.action("settings",["autoSummary":$0])})).labelsHidden().toggleStyle(.checkbox)}
                VStack(spacing:0){PreferenceRow(title:"Compact sidebar",detail:"Keep more space for your conversation."){Toggle("Compact sidebar",isOn:bool("sidebarCollapsed")).labelsHidden().toggleStyle(.switch).controlSize(.small)};Divider().overlay(colours.line);PreferenceRow(title:"Context window",detail:"Larger windows keep more detail and use more memory."){Picker("Context window",selection:Binding(get:{engine.state["contextSize"] as? Int ?? 8192},set:{engine.action("settings",["contextSize":$0])})){ForEach([4096,8192,16384,32768],id:\.self){Text("\($0/1024)k tokens").tag($0)}}.labelsHidden().frame(width:145)}}.wixalCard()
            }
            WixalSection(title:"Legal"){HStack{Button("Terms & Conditions"){navigate("Terms")};Button("Privacy Policy"){navigate("Privacy")}}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))}
            WixalSection(title:"Models & tools"){HStack{Button("Models & local engine ↗"){navigate("Models")};Button("Accounts & sharing ↗"){navigate("Connections")};Button("Enabled tools ↗"){navigate("Tool kit")}}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))}
            WixalSection(title:"Action review",detail:"Applies to this workspace. Enabled edits, commands and network actions use this setting."){
                Picker("Review mode",selection:Binding(get:{textValue(engine.project?["approvalMode"] ?? engine.state["personalApprovalMode"])},set:{engine.action("settings",["approvalMode":$0])})){Text("Review each action").tag("review");Text("Approved all").tag("bypass")}.frame(width:260)
            }
            WixalSection(title:"Memory",detail:"Global instructions and saved project notes are included when recall is enabled."){
                Picker("Project recall",selection:Binding(get:{textValue(engine.project?["memoryMode"]).isEmpty ? "project" : textValue(engine.project?["memoryMode"])},set:{engine.action("settings",["memoryMode":$0])})){Text("Project notes").tag("project");Text("Global only").tag("global");Text("Project + global").tag("both");Text("Off").tag("off")}.frame(width:260).disabled(engine.project==nil)
                Toggle("Use global preferences",isOn:Binding(get:{engine.state["globalMemoryEnabled"] as? Bool ?? true},set:{engine.action("settings",["globalMemoryEnabled":$0])})).font(.system(size:11))
                TextEditor(text:$notes).font(.system(size:12)).scrollContentBackground(.hidden).frame(height:100).wixalField()
                Text("\(notes.count) / 1,200 characters").font(.system(size:10)).foregroundStyle(notes.count>1200 ? .red : colours.muted)
                Button("Save global instructions"){engine.action("global-memory-save",["content":notes])}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11)).disabled(notes.count>1200 || !memoryWritable)
                if !memoryWritable{Text("Verify your email in Account to save account preferences.").font(.system(size:11)).foregroundStyle(colours.muted)}
                Button("Edit project memory ↗"){navigate("Project memory")}.buttonStyle(.plain).font(.system(size:11))
            }
            WixalSection(title:"Skills",detail:"Import a Markdown skill, then select it in the composer to load its instructions."){
                Button("Import Markdown skill ↗",action:engine.importSkill).buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))
                ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset){_,skill in HStack{VStack(alignment:.leading,spacing:4){Text(textValue(skill["name"])).font(.system(size:12));Text(textValue(skill["description"])).font(.system(size:10)).foregroundStyle(colours.muted)};Spacer();Button("Remove"){engine.action("skill-delete",["id":textValue(skill["id"])])}.buttonStyle(.plain).font(.system(size:10))}.wixalCard()}
            }
            connections
            WorkspaceSyncView(engine:engine)
            WixalSection(title:"Existing Wixal workspace",detail:"Import projects, conversations with images, notes, tasks, appearance, summary preferences, skills, paused schedules and MCP commands. Sign in and pair companion connections again."){
                Button("Import existing workspace ↗"){engine.action("legacy-import")}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))
                let migration=engine.state["migration"] as? [String:Any] ?? [:]
                ForEach(migration["warnings"] as? [String] ?? [],id:\.self){warning in Text(warning).font(.system(size:11)).foregroundStyle(colours.muted)}
            }
            Text(engine.busy ? "Preferences are available when the current task finishes." : "Changes are saved automatically.").font(.system(size:10)).foregroundStyle(colours.muted)
        }.disabled(engine.busy).onAppear{notes=engine.activeMemory}.onChange(of:engine.activeMemory){_,value in notes=value}.task{await refreshMCP()}
    }
    private var iconVariant:String{let saved=textValue(ui["appIcon"]);return !saved.isEmpty && saved != "theme" ? saved : ["Paper":"pearl","Forest":"copper","Midnight":"midnight","Sakura":"sakura"][theme] ?? "sakura"}
    private func themeCard(_ name:String)->some View {
        let preview=WixalTheme(name:name)
        return Button{theme=name}label:{VStack(alignment:.leading,spacing:9){HStack(spacing:0){preview.sidebar.frame(width:22);VStack(alignment:.leading,spacing:6){RoundedRectangle(cornerRadius:2).fill(preview.accent).frame(width:32,height:5);RoundedRectangle(cornerRadius:2).fill(preview.line).frame(height:4);RoundedRectangle(cornerRadius:2).fill(preview.line).frame(width:48,height:4)}.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(preview.background)}.frame(height:60).clipShape(RoundedRectangle(cornerRadius:5));Text(name).font(.system(size:12,weight:.medium));Text(["Sakura":"Charcoal & pink","Midnight":"Cool blue","Forest":"Quiet green","Paper":"Warm & light"][name] ?? "").font(.system(size:10)).foregroundStyle(colours.muted)}.padding(12).frame(maxWidth:.infinity).background(colours.panel,in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(theme==name ? colours.accent : colours.line,lineWidth:theme==name ? 2 : 1))}.buttonStyle(.plain).accessibilityLabel("\(name) theme").accessibilityValue(theme==name ? "Selected" : "Not selected")
    }
    private func iconCard(_ variant:String)->some View {
        Button{engine.action("settings",["ui":["appIcon":variant]])}label:{VStack(spacing:8){if let url=Bundle.main.url(forResource:variant,withExtension:"png",subdirectory:"icon-variants"),let image=NSImage(contentsOf:url){Image(nsImage:image).resizable().scaledToFit().frame(width:64,height:64)};Text(variant.capitalized).font(.system(size:11))}.padding(12).frame(maxWidth:.infinity).background(colours.panel,in:RoundedRectangle(cornerRadius:10)).overlay(RoundedRectangle(cornerRadius:10).stroke(iconVariant==variant ? colours.accent : colours.line,lineWidth:iconVariant==variant ? 2 : 1))}.buttonStyle(.plain).accessibilityLabel("\(variant.capitalized) app icon").accessibilityValue(iconVariant==variant ? "Selected" : "Not selected")
    }
    private var connections:some View {
        WixalSection(title:"External tools",detail:"Connect trusted local or HTTPS MCP servers. Authorisation opens your browser; credentials are kept in Keychain. Enable connected tools in the tool kit."){
            VStack(alignment:.leading,spacing:10) {
                Picker("Connection",selection:$mcpTransport){Text("Local executable").tag("stdio");Text("Remote HTTPS").tag("http")}.pickerStyle(.segmented)
                TextField("Server name",text:$mcpName).wixalField()
                TextField(mcpTransport == "http" ? "https://server.example/mcp" : "Executable",text:$mcpCommand).wixalField().accessibilityLabel(mcpTransport == "http" ? "MCP endpoint" : "MCP executable")
                if mcpTransport == "stdio" { TextField("Arguments as a JSON array",text:$mcpArgs).wixalField() }
                else {
                    Toggle("Sign in with OAuth",isOn:$mcpOAuth)
                    if mcpOAuth { TextField("Registered client ID (optional)",text:$mcpClientID).wixalField();Text("Leave the client ID empty for servers that allow automatic client registration.").font(.system(size:10)).foregroundStyle(colours.muted) }
                }
                Button("Save server",action:saveMCP).buttonStyle(WixalButtonStyle(outlined:true)).disabled(mcpCommand.isEmpty)
            }.wixalCard()
            ForEach(Array(records(engine.state["mcpServers"]).enumerated()),id:\.offset){_,server in
                let status=mcpStatus.first{textValue($0["id"])==textValue(server["id"])} ?? [:],connected=status["connected"] as? Bool ?? false
                VStack(alignment:.leading,spacing:10){HStack{Text(textValue(server["name"])).font(.system(size:12));Spacer();Text(connected ? "Connected · \(status["tools"] as? Int ?? 0) tools" : "Disconnected").font(.system(size:10)).foregroundStyle(colours.muted)};HStack{Button(connected ? "Disconnect" : "Connect"){mcpAction(connected ? "mcp-disconnect" : "mcp-connect",textValue(server["id"]))};if server["oauth"] as? Bool == true{Button("Forget sign-in"){mcpAction("mcp-oauth-clear",textValue(server["id"]))}};Button("Remove",role:.destructive){mcpAction("mcp-delete",textValue(server["id"]))}}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11))}.wixalCard()
            }
        }
    }
    private func saveMCP() {
        var params:[String:Any] = ["name":mcpName,"transport":mcpTransport]
        if mcpTransport == "http" { params["url"]=mcpCommand;params["oauth"]=mcpOAuth;params["clientId"]=mcpClientID }
        else {
            guard let data=mcpArgs.data(using:.utf8),let args=try? JSONSerialization.jsonObject(with:data) as? [String] else{engine.error="Arguments must be a JSON array of strings";return}
            params["command"]=mcpCommand;params["args"]=args
        }
        Task{do{_=try await engine.call("mcp-add",params);mcpName="";mcpCommand="";mcpClientID="";await refreshMCP()}catch{engine.error=error.localizedDescription}}
    }
    private func refreshMCP()async{mcpStatus=records(try? await engine.call("mcp-status"))}
    private func mcpAction(_ method:String,_ id:String){Task{do{_=try await engine.call(method,["id":id]);await refreshMCP()}catch{engine.error=error.localizedDescription}}}
}
