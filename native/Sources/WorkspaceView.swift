import SwiftUI
import AppKit

struct WorkspaceView: View {
    @ObservedObject var engine: EngineClient
    @ViewState<String> private var tab = "Chat"
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @ViewState<Bool> private var introFinished=true
    @ViewState<Bool> private var preferencesLoaded=false
    @ViewState<Bool> private var terminal = false
    @ViewState<Bool> private var modelPicker=false
    @AppStorage("navigation.projectsExpanded") private var projectsExpanded=true
    @AppStorage("navigation.recentsExpanded") private var recentsExpanded=true
    @ViewState<String?> private var projectDeleteID=nil
    @ViewState<String> private var agentPage="Home"
    @StateObject private var agentDesign = AgentDesignStore()
    @StateObject private var settings = SettingsState()
    @ViewState<Bool> private var archives = false
    @ViewState<Bool> private var creatingConversation=false
    @ViewState<Bool> private var createProjectPresented=false
    @ViewState<Bool> private var accountPresented=false
    @ViewState<Bool> private var connectionsPresented=false
    @ViewState<Bool> private var setupPresented=false
    @ViewState<String?> private var legalDocument=nil
    @ViewState<String?> private var renameID=nil
    @ViewState<String?> private var deleteID=nil
    @ViewState<CGSize> private var windowSize=CGSize(width:1320,height:880)
    @ViewState<Bool> private var collapsed = false
    @ViewState<String> private var search = ""
    @ViewState<Set<String>> private var expanded = []
    @ViewState<String?> private var drawer = nil
    @ViewState<Bool> private var palette = false
    private var appearance: String {
        let stored = textValue((engine.state["ui"] as? [String:Any])?["theme"])
        return ["paper":"Paper","midnight":"Midnight","forest":"Forest","sakura":"Sakura"][stored] ?? "Sakura"
    }
    private var ui:[String:Any]{engine.state["ui"] as? [String:Any] ?? [:]}
    private var reduceMotion:Bool{systemReduceMotion || (ui["reduceMotion"] as? Bool ?? false)}
    private var motion:Animation?{reduceMotion ? nil : .easeInOut(duration:0.18)}
    private var theme: WixalTheme { WixalTheme(name:appearance) }
    private var appearanceBinding: Binding<String> { Binding(get:{appearance},set:{engine.action("settings",["ui":["theme":$0.lowercased()]])}) }
    var body: some View {
        VStack(spacing:0) {
            titlebar
            HStack(spacing:0) {
                sidebar.frame(width:sidebarIsCompact ? 56 : 224).background(theme.sidebar)
                Rectangle().fill(theme.line).frame(width:1)
                VStack(spacing:0) {
                    if ["Chat","Agents","Files"].contains(tab){workspaceHeader}
                    HStack(spacing:0) {
                        VSplitView {
                            ZStack {
                                CybersecurityAgentWorkspace(engine:engine,design:agentDesign)
                                    .opacity(tab == "Cybersecurity" ? 1 : 0)
                                    .allowsHitTesting(tab == "Cybersecurity")
                                    .accessibilityHidden(tab != "Cybersecurity")
                                Group {
                                switch tab {
                                case "Files": FilesView(engine:engine,onUse:addFileContext)
                                case "Models": ModelsView(engine:engine)
                                case "Performance": PerformanceView(engine:engine)
                                case "Projects": projectsPage
                                case "Cybersecurity": EmptyView()
                                case "Tools": AddonLibraryView(engine:engine)
                                case "Agents": agentsPage
                                case "Tasks": TasksView(engine:engine,openConversation:{tab="Agents";agentPage="Conversation";drawer=nil})
                                case "Settings": SettingsView(engine:engine,settings:settings,navigate:{select($0)},previewLaunch:{introFinished=false})
                                default: ChatView(engine:engine,openModels:{modelPicker=true},openFiles:{tab="Files"},openTools:{drawer=drawer == "Tools" ? nil : "Tools"})
                                }
                                }
                            }.frame(maxWidth:.infinity,maxHeight:.infinity)
                            if terminal {
                                VStack(spacing:0) {
                                    HStack(spacing:8) { Text("›_").wixalFont(size:12,design:.monospaced); Text("Terminal"); Text(engine.root.isEmpty ? "Home" : engine.root).lineLimit(1).foregroundStyle(theme.muted); Spacer(); Text("Host shell").foregroundStyle(theme.muted); Button("Clear"){engine.terminalSession.clear()}.buttonStyle(.plain); Button {terminal=false} label:{Image(systemName:"xmark")}.buttonStyle(.plain).help("Hide terminal").accessibilityLabel("Hide terminal") }.wixalFont(size:11).padding(.horizontal,14).frame(height:34).background(theme.panel)
                                    TerminalPanel(session:engine.terminalSession,root:engine.root,theme:theme,textSize:CGFloat(ui["textSize"] as? Int ?? 13)).id(engine.root)
                                }.frame(minHeight:120,idealHeight:min(200,windowSize.height*0.28),maxHeight:windowSize.height*0.32)
                            }
                        }
                        if let drawer, windowSize.width >= 1200 {
                            WorkspaceDrawer(engine:engine,kind:drawer,close:{self.drawer=nil})
                                .frame(width:340).background(theme.panel).overlay(alignment:.leading){Rectangle().fill(theme.line).frame(width:1)}
                                .shadow(color:.black.opacity(theme.light ? 0.06 : 0.15),radius:14,x:-5).transition(.move(edge:.trailing).combined(with:.opacity))
                        }
                    }
                    .overlay(alignment:.trailing) {
                        if let drawer, windowSize.width < 1200 {
                            ZStack(alignment:.trailing) {
                                theme.background.opacity(0.45).contentShape(Rectangle()).onTapGesture{self.drawer=nil}
                                    .accessibilityHidden(true)
                                WorkspaceDrawer(engine:engine,kind:drawer,close:{self.drawer=nil})
                                    .frame(width:min(380,windowSize.width-(collapsed ? 56 : 224)-24))
                                    .background(theme.panel).overlay(alignment:.leading){Rectangle().fill(theme.line).frame(width:1)}
                                    .shadow(color:.black.opacity(theme.light ? 0.06 : 0.15),radius:14,x:-5)
                            }
                        }
                    }
                    if !engine.connected {
                        HStack { Text(engine.activity); Spacer(); Button(engine.restarting ? "Restarting…" : "Restart engine") { engine.restart() }.disabled(engine.restarting) }.wixalFont(size:12).padding(12).background(theme.panel)
                    }
                    if !engine.error.isEmpty {
                        HStack { Image(systemName:"exclamationmark.triangle"); Text(engine.error).textSelection(.enabled); Spacer(); Button("Dismiss") {engine.error=""}.buttonStyle(.plain) }.wixalFont(size:11).padding(12).background(.red.opacity(0.08))
                    }
                }.background(theme.background)
            }
        }.foregroundStyle(theme.text).wixalFont(size:13).background(theme.background)
        .background(SheetFocusRestorer().frame(width:0,height:0))
        .ignoresSafeArea(.container,edges:.top)
        .animation(motion,value:expanded).animation(motion,value:collapsed).animation(motion,value:drawer).animation(motion,value:tab)
        .overlay{if !introFinished{LaunchView(theme:theme,motion:!reduceMotion && (ui["launchAnimation"] as? Bool ?? true),sound:ui["launchSound"] as? Bool ?? true,done:{introFinished=true})}}
        .onChange(of:engine.connected,initial:true){_,ready in if ready && !preferencesLoaded{preferencesLoaded=true;tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat";collapsed=ui["sidebarCollapsed"] as? Bool ?? false;if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] == nil{let setup=engine.state["setup"] as? [String:Any] ?? [:];setupPresented = !(setup["completed"] as? Bool ?? false)}}}
        .onChange(of:ui["sidebarCollapsed"] as? Bool){_,value in collapsed=value ?? false}
        .onChange(of:ui["appIcon"] as? String){_,_ in updateIcon()}
        .onExitCommand{if drawer != nil{drawer=nil}else{tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat"}}
        .onReceive(NotificationCenter.default.publisher(for:.wixalOpenSettings)){_ in openSettings()}
        .onReceive(NotificationCenter.default.publisher(for:.wixalNavigate)){message in if let action=message.object as? String{select(action)}}
        .sheet(isPresented:$archives){dialog("Close archived chats",close:{archives=false}){ArchivedChatsView(engine:engine,open:{archives=false;tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat"})}}
        .sheet(isPresented:Binding(get:{engine.projectCandidate != nil},set:{if !$0{engine.projectCandidate=nil}})){ProjectEntryView(engine:engine,path:engine.projectCandidate ?? "").environment(\.wixalTheme,theme)}
        .sheet(isPresented:$createProjectPresented){CreateProjectView(engine:engine,close:{createProjectPresented=false}).environment(\.wixalTheme,theme)}
        .sheet(isPresented:$accountPresented){dialog("Close account",close:{accountPresented=false}){AccountView(engine:engine,navigate:{accountPresented=false;deferredSelect($0)})}}
        .sheet(isPresented:$connectionsPresented){dialog("Close connections",close:{connectionsPresented=false}){ConnectionsView(engine:engine,navigate:{connectionsPresented=false;deferredSelect($0)})}}
        .sheet(isPresented:$setupPresented){
            VStack(spacing:0) {
                if (engine.state["setup"] as? [String:Any])?["completed"] as? Bool == true { HStack { Spacer(); Button("Close setup"){setupPresented=false} }.padding(16) }
                SetupView(engine:engine,navigate:{route in Task { do { _ = try await engine.call("setup-complete"); setupPresented=false; deferredSelect(route) } catch { engine.error=error.localizedDescription } }},complete:{setupPresented=false})
            }.frame(width:min(720,windowSize.width-40),height:min(760,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme).interactiveDismissDisabled((engine.state["setup"] as? [String:Any])?["completed"] as? Bool != true)
        }
        .sheet(isPresented:Binding(get:{legalDocument != nil},set:{if !$0{legalDocument=nil}})){dialog("Close legal document",close:{legalDocument=nil}){LegalView(engine:engine,document:legalDocument ?? "terms")}}
        .sheet(isPresented:Binding(get:{renameID != nil},set:{if !$0{renameID=nil}})){RenameConversationView(engine:engine,id:renameID ?? "",close:{renameID=nil})}
        .sheet(isPresented:Binding(get:{deleteID != nil},set:{if !$0{deleteID=nil}})){DeleteConversationView(engine:engine,id:deleteID ?? "",close:{deleteID=nil})}
        .sheet(item:$engine.review) {review in ReviewView(engine:engine,review:review)}
        .sheet(isPresented:Binding(get:{projectDeleteID != nil},set:{if !$0{projectDeleteID=nil}})){DeleteProjectView(engine:engine,id:projectDeleteID ?? "",close:{projectDeleteID=nil;tab="Projects"})}
        .sheet(isPresented:$modelPicker){VStack(spacing:0){HStack{Text("Choose your model").wixalFont(size:15,weight:.medium);Spacer();Button{modelPicker=false}label:{Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel("Close model picker")}.padding(20).background(theme.panel);ModelsView(engine:engine)}.frame(width:min(980,windowSize.width-40),height:min(680,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme)}
        .sheet(isPresented:$palette) {CommandPalette(action:{select($0);palette=false})}
        .onAppear {StartupEvidence.record("workspace-mounted");updateIcon();expanded.insert(textValue(engine.state["activeProject"]));if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil {terminal=true}}
        .onChange(of:engine.state["activeProject"] as? String) {_,id in expanded.insert(id ?? "")}
        .onChange(of:appearance){_,_ in updateIcon()}
        .onChange(of:engine.state["activeSession"] as? String) {_,_ in engine.browser.closeAll();if ["Chat","Agents"].contains(tab){tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat"}}
        .onGeometryChange(for:CGSize.self){$0.size}action:{windowSize=$0}
        .environment(\.wixalTheme,theme).environment(\.wixalTextSize,CGFloat(ui["textSize"] as? Int ?? 13)).tint(theme.accent).preferredColorScheme(theme.light ? .light : .dark)
    }
    private func updateIcon(){
        let saved=textValue(ui["appIcon"]);let variant = !saved.isEmpty && saved != "theme" ? saved : ["Paper":"pearl","Midnight":"midnight","Forest":"copper","Sakura":"sakura"][appearance] ?? "sakura"
        if let url=Bundle.main.url(forResource:variant,withExtension:"png",subdirectory:"icon-variants"),let image=NSImage(contentsOf:url){NSApp.applicationIconImage=image}
    }
    private var titlebar: some View {
        HStack {Text("wixal").wixalFont(size:13,design:.monospaced);Spacer();Button{palette=true}label:{Label("Search",systemImage:"magnifyingglass")}.buttonStyle(.plain).foregroundStyle(theme.muted).help("Find a command · ⌘ K")}.padding(.leading,98).padding(.trailing,20).frame(height:48).background(theme.background)
    }
    private var sidebarIsCompact: Bool { collapsed || tab == "Settings" }
    private var sidebar: some View {
        VStack(alignment:.leading,spacing:10){
            HStack{if !sidebarIsCompact{Text("Workspace").foregroundStyle(theme.muted);Spacer()};Button{if tab == "Settings" { tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat";collapsed=false } else { collapsed.toggle() };engine.action("settings",["ui":["sidebarCollapsed":collapsed]])}label:{Image(systemName:"sidebar.left")}.buttonStyle(.plain).accessibilityLabel(sidebarIsCompact ? "Expand sidebar" : "Collapse sidebar")}.padding(.vertical,8)
            if !sidebarIsCompact {
                HStack(spacing:7){Image(systemName:"magnifyingglass").foregroundStyle(theme.muted);TextField("Search projects and chats",text:$search).textFieldStyle(.plain).wixalFont(size:11)}.padding(10).background(theme.panel,in:RoundedRectangle(cornerRadius:8))
            }
            SidebarRailButton(title:"New conversation",symbol:"+",collapsed:sidebarIsCompact){newConversation("chat")}.disabled(engine.busy || creatingConversation)
            SidebarRailButton(title:"Chat",symbol:"◌",collapsed:sidebarIsCompact,selected:tab=="Chat"){openMode("chat")}.disabled(engine.busy)
            SidebarRailButton(title:"Agents",symbol:"◇",collapsed:sidebarIsCompact,selected:tab=="Agents"){openMode("agent",page:"Home")}.disabled(engine.busy)
            SidebarRailButton(title:"Cybersecurity",symbol:"⛨",collapsed:sidebarIsCompact,selected:tab=="Cybersecurity"){tab="Cybersecurity";drawer=nil}
            SidebarRailButton(title:"Tools",symbol:"▦",collapsed:sidebarIsCompact,selected:tab=="Tools"){select("Tools")}
            if sidebarIsCompact{SidebarRailButton(title:"Projects",symbol:"▱",collapsed:true,selected:tab=="Projects"){tab="Projects"};SidebarRailButton(title:"Recents",symbol:"◷",collapsed:true){collapsed=false;recentsExpanded=true;engine.action("settings",["ui":["sidebarCollapsed":false]])}}
            if !sidebarIsCompact {
                ScrollView {
                    VStack(alignment:.leading,spacing:18){
                        VStack(alignment:.leading,spacing:4){
                            HStack{sectionToggle("Projects",expanded:$projectsExpanded);Button{createProjectPresented=true}label:{Image(systemName:"plus").frame(width:24,height:26)}.buttonStyle(.plain).accessibilityLabel("Add project").disabled(engine.busy)}
                            if projectsExpanded {
                                ForEach(Array(visibleProjects.enumerated()),id:\.offset){_,project in projectRow(project)}
                                if visibleProjects.isEmpty{Text(search.isEmpty ? "Create a project to begin" : "No matching projects").wixalFont(size:11).foregroundStyle(theme.muted).padding(8)}
                            }
                        }
                        VStack(alignment:.leading,spacing:4){
                            HStack{sectionToggle("Recents",expanded:$recentsExpanded);Button{archives=true}label:{Image(systemName:"archivebox").frame(width:24,height:26)}.buttonStyle(.plain).accessibilityLabel("Archived chats")}
                            if recentsExpanded {
                                ForEach(Array(personalSessions.enumerated()),id:\.offset){_,session in conversationRow(session)}
                                if personalSessions.isEmpty{Text(search.isEmpty ? "Your personal chats appear here" : "No matching chats").wixalFont(size:11).foregroundStyle(theme.muted).padding(8)}
                            }
                        }
                    }.wixalFont(size:12).padding(.top,8)
                }.scrollIndicators(.hidden)
            }
            Spacer(minLength:0)
            SidebarRailButton(title:"Settings",symbol:"⚙",collapsed:sidebarIsCompact,selected:tab=="Settings"){openSettings()}
        }.padding(.horizontal,collapsed ? 8 : 14).padding(.vertical,12)
    }
    private var recentSessions:[[String:Any]]{records(engine.state["sessions"]).filter{($0["archivedAt"] == nil || $0["archivedAt"] is NSNull) && (search.isEmpty || textValue($0["title"]).localizedCaseInsensitiveContains(search) || projectName($0).localizedCaseInsensitiveContains(search))}.reversed()}
    private func projectName(_ session:[String:Any])->String{textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(session["projectId"])}?["name"]).isEmpty ? "Personal" : textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(session["projectId"])}?["name"])}
    private var personalSessions:[[String:Any]]{recentSessions.filter{textValue($0["projectId"]).isEmpty}}
    private var visibleProjects:[[String:Any]]{records(engine.state["projects"]).filter{project in search.isEmpty || textValue(project["name"]).localizedCaseInsensitiveContains(search) || recentSessions.contains{textValue($0["projectId"])==textValue(project["id"])}}}
    private func sectionToggle(_ title:String,expanded:Binding<Bool>)->some View {
        Button{expanded.wrappedValue.toggle()}label:{HStack(spacing:7){Image(systemName:expanded.wrappedValue ? "chevron.down" : "chevron.right").wixalFont(size:9);Text(title);Spacer(minLength:0)}.frame(maxWidth:.infinity,alignment:.leading).frame(height:28).contentShape(Rectangle())}.buttonStyle(.plain).accessibilityLabel("\(expanded.wrappedValue ? "Collapse" : "Expand") \(title)")
    }
    private func projectRow(_ project:[String:Any])->some View {
        let id=textValue(project["id"])
        let isExpanded=expanded.contains(id) || !search.isEmpty
        return VStack(alignment:.leading,spacing:2){
            HStack{
                Button{if expanded.contains(id){expanded.remove(id)}else{expanded.insert(id)}}label:{HStack(spacing:7){Image(systemName:isExpanded ? "chevron.down" : "chevron.right").wixalFont(size:9);Label(textValue(project["name"]),systemImage:"folder").lineLimit(1);Spacer(minLength:0)}.frame(maxWidth:.infinity,alignment:.leading).contentShape(Rectangle())}.buttonStyle(.plain).accessibilityLabel("\(isExpanded ? "Collapse" : "Expand") \(textValue(project["name"]))")
                Menu{Button("Open project"){engine.action("project-select",["id":id]);tab="Projects"};Divider();Button("Delete project…",role:.destructive){projectDeleteID=id}}label:{Image(systemName:"ellipsis")}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:20).disabled(engine.busy)
            }.padding(.vertical,9).padding(.horizontal,6)
            if isExpanded {
                ForEach(Array(recentSessions.filter{textValue($0["projectId"])==id}.enumerated()),id:\.offset){_,session in conversationRow(session).padding(.leading,14)}
            }
        }
    }
    private func conversationRow(_ session:[String:Any])->some View {
        HStack(alignment:.top){Button{openConversation(session)}label:{VStack(alignment:.leading,spacing:4){Text(textValue(session["title"])).lineLimit(1);Text(projectName(session) + (textValue(session["mode"]) == "agent" ? " · Agent" : "")).wixalFont(size:10).foregroundStyle(theme.muted).lineLimit(1)}.frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(.plain).disabled(engine.busy);Menu{Button("Rename…"){renameID=textValue(session["id"])};Button("Copy conversation"){copyConversation(textValue(session["id"]))};Button("Archive"){engine.action("session-archive",["id":textValue(session["id"])])};Divider();Button("Delete…",role:.destructive){deleteID=textValue(session["id"])}}label:{Image(systemName:"ellipsis")}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:20).disabled(engine.busy)}.padding(8).background(textValue(session["id"])==textValue(engine.state["activeSession"]) ? theme.panel.opacity(0.7) : .clear,in:RoundedRectangle(cornerRadius:6))
    }
    private func openConversation(_ session:[String:Any],page:String="Conversation"){Task{do{_=try await engine.call("project-select",["id":session["projectId"] ?? NSNull()]);_=try await engine.call("session-select",["id":textValue(session["id"])]);tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil}catch{engine.error=error.localizedDescription}}}
    private func newConversation(_ mode:String,page:String="Conversation"){guard !creatingConversation && !engine.busy else{return};creatingConversation=true;Task{defer{creatingConversation=false};do{_=try await engine.call("session-new",["mode":mode]);tab=mode == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil}catch{engine.error=error.localizedDescription}}}
    private func openMode(_ mode:String,page:String="Conversation"){
        if textValue(engine.state["mode"]) == mode{tab=mode == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil;return}
        if let session=recentSessions.first(where:{textValue($0["projectId"])==textValue(engine.state["activeProject"]) && textValue($0["mode"])==mode}){openConversation(session,page:page)}else{newConversation(mode,page:page)}
    }
    private var agentsPage:some View{
        AgentsHubView(engine:engine,design:agentDesign,page:$agentPage,openModels:{modelPicker=true},openFiles:{tab="Files"},newLiveTask:{newConversation("agent")})
    }
    private var projectsPage:some View{
        WixalPage(eyebrow:"PROJECTS",title:engine.project.map{textValue($0["name"])} ?? "Your projects",subtitle:engine.project == nil ? "Add a folder to keep related work together." : engine.root){
            if engine.project != nil {
                HStack{Button("New chat"){newConversation("chat")};Button("Files"){tab="Files"};Button("Terminal"){terminal.toggle()};Menu("Project settings"){Button("Saved context…"){drawer="Memory"};Button("Show folder in Finder"){NSWorkspace.shared.selectFile(nil,inFileViewerRootedAtPath:engine.root)};Divider();Button("Delete project…",role:.destructive){projectDeleteID=textValue(engine.state["activeProject"])}}}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)
                ForEach(Array(recentSessions.filter{textValue($0["projectId"])==textValue(engine.state["activeProject"])}.enumerated()),id:\.offset){_,session in conversationRow(session)}
            }else{Button("Create project"){createProjectPresented=true}.buttonStyle(WixalButtonStyle(outlined:true))}
        }
    }
    private var workspaceHeader:some View {
        HStack{VStack(alignment:.leading,spacing:4){Text(engine.project.map{textValue($0["name"])} ?? "Personal workspace").wixalFont(size:11).foregroundStyle(theme.muted);Text(tab=="Agents" && agentPage != "Conversation" ? "Agents" : ["Chat","Agents"].contains(tab) ? textValue(engine.session?["title"]) : tab).wixalFont(size:14,weight:.medium).lineLimit(1)};Spacer();if tab=="Chat" || tab=="Agents" && agentPage=="Conversation"{Menu{Button("Rename conversation…"){renameID=textValue(engine.state["activeSession"])};Button("Copy conversation"){copyConversation(textValue(engine.state["activeSession"]))}}label:{Image(systemName:"ellipsis")}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:24).accessibilityLabel("Conversation options")}}.padding(.horizontal,24).frame(height:62)
    }
    private func headerButton(_ title:String,icon:String,selected:Bool,action:@escaping()->Void)->some View {
        Button(action:action){Label(title,systemImage:icon).wixalFont(size:11).labelStyle(.titleAndIcon)}.buttonStyle(WixalButtonStyle()).background(selected ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)).foregroundStyle(selected ? theme.accent : theme.muted)
    }
    private var accountName:String{let account=engine.state["account"] as? [String:Any] ?? [:];let profile=account["profile"] as? [String:Any] ?? [:];return account["signedIn"] as? Bool ?? false ? textValue(profile["name"]).isEmpty ? "Account" : textValue(profile["name"]) : "Account"}
    private func deferredSelect(_ action:String){Task{try? await Task.sleep(for:.milliseconds(180));select(action)}}
    private func addFileContext(_ file:[String:Any]){let draft=engine.session?["draft"] as? [String:Any] ?? [:];var attachments=records(draft["attachments"]);guard attachments.count<8 else{engine.error="Attach at most eight files or images";return};attachments.append(file);Task{do{_=try await engine.call("draft-save",["sessionId":textValue(engine.state["activeSession"]),"text":textValue(draft["text"]),"attachments":attachments]);tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat"}catch{engine.error=error.localizedDescription}}}
    private func copyConversation(_ id:String){Task{do{let text=try await engine.call("session-copy",["id":id]) as? String ?? "";NSPasteboard.general.clearContents();NSPasteboard.general.setString(text,forType:.string)}catch{engine.error=error.localizedDescription}}}
    private func dialog<Content:View>(_ label:String,close:@escaping()->Void,@ViewBuilder content:()->Content)->some View{VStack(spacing:0){HStack{Spacer();Button(action:close){Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel(label)}.padding(18);content()}.frame(width:min(720,windowSize.width-40),height:min(760,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme)}
    private func openSettings(){drawer=nil;tab="Settings"}
    private func select(_ action:String){
        if action.hasPrefix("Settings:") { settings.open(action == "Settings:Connections" ? "Connections & sharing" : action == "Settings:Tools" ? "Tools & permissions" : "Data & sync");openSettings();return }
        if action == "Tools" { drawer=nil;tab="Tools";return }
        switch action{case "Commands":palette=true;case "Settings":openSettings();case "Connections":settings.open("Connections & sharing",detail:"Companion");openSettings();case "Account":settings.open("Account");openSettings();case "Setup":setupPresented=true;case "Terms":legalDocument="terms";case "Privacy":legalDocument="privacy";case "Open project":engine.pickProject();case "New conversation":newConversation("chat");case "Chat":openMode("chat");case "Agents":openMode("agent",page:"Home");case "Tasks":tab="Agents";agentPage="Task inbox";case "Terminal":terminal.toggle();case "Tool kit":openMode("agent",page:"Live tools");case "Project memory":tab="Projects";drawer="Memory";case "Archived chats":archives=true;default:tab=action}}
}
