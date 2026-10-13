import SwiftUI
import AppKit
import WixalInteractions

struct WorkspaceView: View {
    @ObservedObject var engine: EngineClient
    @ViewState<String> private var tab = "Chat"
    @AppStorage("navigation.workspaceArea") private var workspaceName = "Chats"
    private var workspace:WorkspaceArea { WorkspaceArea(rawValue:workspaceName) ?? .chats }
    @AppStorage("navigation.sidebarWidth") private var sidebarWidth = 248.0
    @AppStorage("navigation.pinnedConversations") private var pinnedConversations = "[]"
    @AppStorage("navigation.expandedProjects") private var expandedProjects = "[]"
    @ViewState<Bool> private var openingContext = false
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
        return WixalPalette.resolve(stored).name
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
                navigationRail.frame(width:48).background(theme.sidebar).zIndex(20)
                Rectangle().fill(theme.line).frame(width:1)
                if !sidebarIsCompact {
                    sidebar.frame(width:CGFloat(SidebarPreferences.width(sidebarWidth))).background(theme.sidebar)
                    SidebarResizeHandle(width:$sidebarWidth)
                }
                VStack(spacing:0) {
                    navigationContextBar
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
                                case "Recents": recentsPage
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
                        if let drawer, canDockInspector {
                            WorkspaceDrawer(engine:engine,kind:drawer,close:{self.drawer=nil})
                                .frame(width:340).background(theme.panel).overlay(alignment:.leading){Rectangle().fill(theme.line).frame(width:1)}
                                .shadow(color:.black.opacity(theme.light ? 0.06 : 0.15),radius:14,x:-5).transition(.move(edge:.trailing).combined(with:.opacity))
                        }
                    }
                    .overlay(alignment:.trailing) {
                        if let drawer, !canDockInspector {
                            ZStack(alignment:.trailing) {
                                theme.background.opacity(0.45).contentShape(Rectangle()).onTapGesture{self.drawer=nil}
                                    .accessibilityHidden(true)
                                WorkspaceDrawer(engine:engine,kind:drawer,close:{self.drawer=nil})
                                    .frame(width:min(380,max(260,windowSize.width-navigationWidth-24)))
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
        .onChange(of:expanded){_,ids in expandedProjects=SidebarPreferences.encodePins(ids.sorted())}
        .animation(motion,value:expanded).animation(motion,value:collapsed).animation(motion,value:drawer).animation(motion,value:tab)
        .overlay{if !introFinished{LaunchView(theme:theme,motion:!reduceMotion && (ui["launchAnimation"] as? Bool ?? true),sound:ui["launchSound"] as? Bool ?? true,done:{introFinished=true})}}
        .onChange(of:engine.connected,initial:true){_,ready in if ready && !preferencesLoaded{preferencesLoaded=true;tab=workspace == .chats ? (textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat") : workspace.route;collapsed=ui["sidebarCollapsed"] as? Bool ?? false;if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] == nil{let setup=engine.state["setup"] as? [String:Any] ?? [:];setupPresented = !(setup["completed"] as? Bool ?? false)}}}
        .onChange(of:tab){_,value in if let area=WorkspaceArea.destination(value){workspaceName=area.rawValue}}
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
        .sheet(isPresented:$palette) {CommandPalette(projects:records(engine.state["projects"]),sessions:records(engine.state["sessions"]),action:{select($0);palette=false})}
        .onAppear {StartupEvidence.record("workspace-mounted");updateIcon();expanded=Set(SidebarPreferences.pins(expandedProjects));expanded.insert(textValue(engine.state["activeProject"]));if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil {terminal=true}}
        .onChange(of:engine.state["activeProject"] as? String) {_,id in expanded.insert(id ?? "")}
        .onChange(of:appearance){_,_ in updateIcon()}
        .onChange(of:engine.state["activeSession"] as? String) {_,_ in engine.browser.closeAll();if ["Chat","Agents"].contains(tab){tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat"}}
        .onGeometryChange(for:CGSize.self){$0.size}action:{windowSize=$0}
        .environment(\.wixalTheme,theme).environment(\.wixalTextSize,CGFloat(ui["textSize"] as? Int ?? 13)).tint(theme.accent).preferredColorScheme(theme.light ? .light : .dark)
    }
    private func updateIcon(){
        let saved=textValue(ui["appIcon"]);let variant = WixalPalette.iconVariants.contains(saved) ? saved : theme.icon
        if let url=Bundle.main.url(forResource:variant,withExtension:"png",subdirectory:"icon-variants"),let image=NSImage(contentsOf:url){NSApp.applicationIconImage=image}
    }
    private var titlebar: some View {
        HStack {Text("wixal").wixalFont(size:13,design:.monospaced);Spacer();Button{palette=true}label:{Label("Search",systemImage:"magnifyingglass")}.buttonStyle(.plain).foregroundStyle(theme.muted).help("Find a command · ⌘ K")}.padding(.leading,98).padding(.trailing,20).frame(height:48).background(theme.background)
    }
    private var sidebarIsCompact: Bool { collapsed }
    private var navigationWidth:CGFloat { 49 + (sidebarIsCompact ? 0 : CGFloat(SidebarPreferences.width(sidebarWidth)) + 7) }
    private var canDockInspector:Bool { windowSize.width-navigationWidth >= 900 }
    private var navigationBusy:Bool { engine.busy || openingContext || creatingConversation }
    private var pinIDs:[String] { SidebarPreferences.pins(pinnedConversations) }
    private var pinnedSessions:[[String:Any]] { pinIDs.compactMap { id in recentSessions.first { textValue($0["id"]) == id } } }
    private func togglePin(_ id:String) {
        var ids=pinIDs
        if ids.contains(id){ids.removeAll{$0==id}}else{ids.append(id)}
        pinnedConversations=SidebarPreferences.encodePins(ids)
    }
    private func chooseWorkspace(_ area:WorkspaceArea) {
        drawer=nil
        switch area {
        case .chats: guard !navigationBusy else{return}; openMode("chat")
        case .agents: tab="Agents"; if agentPage=="Conversation" && textValue(engine.state["mode"]) != "agent"{agentPage="Home"}
        case .cybersecurity:tab="Cybersecurity"
        case .tools:tab="Tools"
        }
    }
    private func toggleSidebar() {
        collapsed.toggle();engine.action("settings",["ui":["sidebarCollapsed":collapsed]])
    }
    private var navigationRail:some View {
        VStack(spacing:6) {
            NavigationRailButton(title:sidebarIsCompact ? "Wixal · Expand sidebar" : "Wixal · Collapse sidebar",wordmark:"W_"){toggleSidebar()}
                .padding(.vertical,4).help("Toggle sidebar · ⌘ B")
            NavigationRailButton(title:"Chats",symbol:"bubble.left",selected:tab=="Chat"){chooseWorkspace(.chats)}.disabled(navigationBusy)
            NavigationRailButton(title:"Projects",symbol:"folder",selected:tab=="Projects"){tab="Projects";drawer=nil}
            NavigationRailButton(title:"Recents",symbol:"clock",selected:tab=="Recents"){tab="Recents";drawer=nil}
            NavigationRailButton(title:sidebarIsCompact ? "Expand sidebar" : "Collapse sidebar",symbol:"sidebar.left"){toggleSidebar()}.help("Toggle sidebar · ⌘ B")
            Spacer(minLength:0)
            NavigationUtilities { route in select(route) }
            NavigationRailButton(title:"Settings",symbol:"gearshape",selected:tab=="Settings"){openSettings()}
            NavigationRailButton(title:accountName,symbol:"person.crop.circle"){select("Account")}
        }.padding(.vertical,6)
    }
    private var navigationContextBar:some View {
        HStack(spacing:12) {
            if sidebarIsCompact {WorkspaceSelector(selected:workspace,busy:navigationBusy,choose:chooseWorkspace)}
            Text(engine.project.map{textValue($0["name"])} ?? "Personal workspace").wixalFont(size:11).foregroundStyle(theme.muted).lineLimit(1)
                .help(engine.root.isEmpty ? "Personal workspace" : engine.root)
            Spacer(minLength:8)
            Menu("Project") {
                Button("Overview"){tab="Projects"}
                Button("Project files"){tab="Files"}
                Button("Project memory"){select("Project memory")}
                Button("Terminal"){terminal.toggle()}
                Button("Open project…"){engine.pickProject()}.disabled(navigationBusy)
            }.fixedSize().wixalFont(size:11)
            if ["Chat","Agents"].contains(tab) {
                Button("Live tools"){if tab=="Agents"{agentPage="Live tools"}else{drawer=drawer=="Tools" ? nil : "Tools"}}.buttonStyle(WixalButtonStyle()).wixalFont(size:11)
            }
        }.padding(.horizontal,18).frame(height:40).background(theme.panel)
    }
    private var sidebar: some View {
        VStack(alignment:.leading,spacing:8) {
            HStack {
                WorkspaceSelector(selected:workspace,busy:navigationBusy,choose:chooseWorkspace)
                Spacer(minLength:0)
                Menu {
                    Button("Narrower sidebar"){sidebarWidth=SidebarPreferences.width(sidebarWidth-16)}
                    Button("Wider sidebar"){sidebarWidth=SidebarPreferences.width(sidebarWidth+16)}
                    Button("Reset sidebar width"){sidebarWidth=248}
                    Button("Collapse sidebar"){toggleSidebar()}
                } label:{Image(systemName:"slider.horizontal.3").frame(width:28,height:32)}.menuStyle(.borderlessButton).menuIndicator(.hidden).accessibilityLabel("Sidebar preferences")
            }.padding(.bottom,6)
            HStack(spacing:7){Image(systemName:"magnifyingglass").foregroundStyle(theme.muted);TextField("Filter projects and chats",text:$search).textFieldStyle(.plain).wixalFont(size:12)}.padding(8).background(theme.panel,in:RoundedRectangle(cornerRadius:5))
            Button {newConversation(workspace == .agents ? "agent" : "chat")} label:{Label(workspace == .agents ? "New agent conversation" : "New chat",systemImage:"square.and.pencil").wixalFont(size:12).frame(maxWidth:.infinity,alignment:.leading).frame(height:32)}.buttonStyle(.plain).disabled(navigationBusy)
            ScrollView {
                LazyVStack(alignment:.leading,spacing:14) {
                    VStack(alignment:.leading,spacing:2){Text("Pinned").wixalFont(size:11).foregroundStyle(theme.muted).padding(6);ForEach(pinnedSessions,id: \.navigationID){session in conversationRow(session)};if pinnedSessions.isEmpty{Text("Pin a conversation from its menu").wixalFont(size:11).foregroundStyle(theme.muted).padding(6)}}
                    VStack(alignment:.leading,spacing:2) {
                        HStack{sectionToggle("Projects",expanded:$projectsExpanded);Button{createProjectPresented=true}label:{Image(systemName:"plus").frame(width:28,height:28)}.buttonStyle(.plain).accessibilityLabel("Add project").disabled(navigationBusy)}
                        if projectsExpanded {
                            ForEach(visibleProjects,id: \.navigationID){project in projectRow(project)}
                            if visibleProjects.isEmpty{Text(search.isEmpty ? "Create a project to begin" : "No matching projects").wixalFont(size:11).foregroundStyle(theme.muted).padding(8)}
                        }
                    }
                    VStack(alignment:.leading,spacing:2) {
                        HStack{sectionToggle("Recents",expanded:$recentsExpanded);Button{archives=true}label:{Image(systemName:"archivebox").frame(width:28,height:28)}.buttonStyle(.plain).accessibilityLabel("Archived chats")}
                        if recentsExpanded {
                            ForEach(Array(recentSessions.prefix(12)),id: \.navigationID){session in conversationRow(session)}
                            if recentSessions.isEmpty{Text(search.isEmpty ? "Your conversations appear here" : "No matching chats").wixalFont(size:11).foregroundStyle(theme.muted).padding(8)}
                            Button("All recent conversations…"){tab="Recents"}.buttonStyle(.plain).wixalFont(size:11).padding(8)
                        }
                    }
                }
            }
        }.padding(12)
    }
    private var recentsPage:some View {
        WixalPage(eyebrow:"RECENTS",title:"Recent conversations",subtitle:"Chats and agent conversations across projects and your personal workspace.") {
            ForEach(allRecentSessions,id: \.navigationID){session in conversationRow(session)}
            if allRecentSessions.isEmpty{Text("No conversations yet.").foregroundStyle(theme.muted)}
            Button("Archived chats"){archives=true}.buttonStyle(WixalButtonStyle(outlined:true))
        }
    }
    private var allRecentSessions:[[String:Any]]{records(engine.state["sessions"]).filter{$0["archivedAt"] == nil || $0["archivedAt"] is NSNull}.reversed()}
    private var recentSessions:[[String:Any]]{allRecentSessions.filter{(search.isEmpty || textValue($0["title"]).localizedCaseInsensitiveContains(search) || projectName($0).localizedCaseInsensitiveContains(search))}}
    private func projectName(_ session:[String:Any])->String{textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(session["projectId"])}?["name"]).isEmpty ? "Personal" : textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(session["projectId"])}?["name"])}
    private var personalSessions:[[String:Any]]{recentSessions.filter{textValue($0["projectId"]).isEmpty}}
    private var visibleProjects:[[String:Any]]{records(engine.state["projects"]).filter{project in search.isEmpty || textValue(project["name"]).localizedCaseInsensitiveContains(search) || recentSessions.contains{textValue($0["projectId"])==textValue(project["id"])}}}
    private func sectionToggle(_ title:String,expanded:Binding<Bool>)->some View {
        Button{expanded.wrappedValue.toggle()}label:{HStack(spacing:7){Image(systemName:expanded.wrappedValue ? "chevron.down" : "chevron.right").wixalFont(size:9);Text(title);Spacer(minLength:0)}.frame(maxWidth:.infinity,alignment:.leading).frame(height:28).contentShape(Rectangle())}.buttonStyle(.plain).accessibilityLabel("\(expanded.wrappedValue ? "Collapse" : "Expand") \(title)").accessibilityValue(expanded.wrappedValue ? "Expanded" : "Collapsed")
    }
    private func projectRow(_ project:[String:Any])->some View {
        let id=textValue(project["id"])
        let isExpanded=expanded.contains(id) || !search.isEmpty
        return VStack(alignment:.leading,spacing:2) {
            HStack(spacing:4) {
                Button{if expanded.contains(id){expanded.remove(id)}else{expanded.insert(id)}}label:{Image(systemName:isExpanded ? "chevron.down" : "chevron.right").wixalFont(size:9).frame(width:24,height:32)}.buttonStyle(.plain)
                    .accessibilityLabel("\(isExpanded ? "Collapse" : "Expand") \(textValue(project["name"])) conversations").accessibilityValue(isExpanded ? "Expanded" : "Collapsed")
                Button{openProject(id)}label:{Label(textValue(project["name"]),systemImage:"folder").wixalFont(size:12).lineLimit(1).frame(maxWidth:.infinity,alignment:.leading).frame(height:32).contentShape(Rectangle())}.buttonStyle(.plain).disabled(navigationBusy)
                    .help(textValue(project["name"])+" · "+textValue(project["root"]))
                    .accessibilityLabel("Open project \(textValue(project["name"]))").accessibilityAddTraits(id==textValue(engine.state["activeProject"]) ? [.isSelected] : [])
                Menu{Button("Open project"){openProject(id)};Divider();Button("Delete project…",role:.destructive){projectDeleteID=id}}label:{Image(systemName:"ellipsis").frame(width:24,height:28)}.menuStyle(.borderlessButton).menuIndicator(.hidden).disabled(navigationBusy).accessibilityLabel("Project actions for \(textValue(project["name"]))")
            }.padding(.horizontal,2)
            if isExpanded {
                ForEach(Array(recentSessions.filter{textValue($0["projectId"])==id}.prefix(5)),id: \.navigationID){session in conversationRow(session).padding(.leading,14)}
                Button("All project conversations…"){openProject(id)}.buttonStyle(.plain).wixalFont(size:11).foregroundStyle(theme.muted).padding(.leading,30).padding(.vertical,5).disabled(navigationBusy)
            }
        }
    }
    private func openProject(_ id:String) {
        guard !navigationBusy else{return};openingContext=true
        Task{defer{openingContext=false};do{_=try await engine.call("project-select",["id":id]);tab="Projects";drawer=nil}catch{engine.error=error.localizedDescription}}
    }
    private func conversationRow(_ session:[String:Any])->some View {
        HStack(alignment:.top){Button{openConversation(session)}label:{VStack(alignment:.leading,spacing:4){Text(textValue(session["title"])).lineLimit(1);Text(projectName(session) + (textValue(session["mode"]) == "agent" ? " · Agent" : "")).wixalFont(size:10).foregroundStyle(theme.muted).lineLimit(1)}.frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(.plain).disabled(navigationBusy).help(textValue(session["title"])).accessibilityAddTraits(textValue(session["id"])==textValue(engine.state["activeSession"]) ? [.isSelected] : []);Menu{Button(pinIDs.contains(textValue(session["id"])) ? "Unpin conversation" : "Pin conversation"){togglePin(textValue(session["id"]))};Button("Rename…"){renameID=textValue(session["id"])};Button("Copy conversation"){copyConversation(textValue(session["id"]))};Button("Archive"){engine.action("session-archive",["id":textValue(session["id"])])};Divider();Button("Delete…",role:.destructive){deleteID=textValue(session["id"])}}label:{Image(systemName:"ellipsis")}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:24).disabled(navigationBusy).accessibilityLabel("Conversation actions for \(textValue(session["title"]))")}.padding(8).background(textValue(session["id"])==textValue(engine.state["activeSession"]) ? theme.panel.opacity(0.7) : .clear,in:RoundedRectangle(cornerRadius:6))
    }
    private func openConversation(_ session:[String:Any],page:String="Conversation"){guard !navigationBusy else{return};openingContext=true;Task{defer{openingContext=false};do{_=try await engine.call("session-select",["id":textValue(session["id"]),"projectId":session["projectId"] ?? NSNull()]);tab=textValue(engine.state["mode"]) == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil}catch{engine.error=error.localizedDescription}}}
    private func newConversation(_ mode:String,page:String="Conversation"){guard !navigationBusy else{return};creatingConversation=true;Task{defer{creatingConversation=false};do{_=try await engine.call("session-new",["mode":mode]);tab=mode == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil}catch{engine.error=error.localizedDescription}}}
    private func openMode(_ mode:String,page:String="Conversation"){
        guard !navigationBusy else{return}
        if textValue(engine.state["mode"]) == mode{tab=mode == "agent" ? "Agents" : "Chat";agentPage=page;drawer=nil;return}
        if let session=records(engine.state["sessions"]).reversed().first(where:{textValue($0["projectId"])==textValue(engine.state["activeProject"]) && textValue($0["mode"])==mode && ($0["archivedAt"] == nil || $0["archivedAt"] is NSNull)}){openConversation(session,page:page)}else{newConversation(mode,page:page)}
    }
    private var agentsPage:some View{
        AgentsHubView(engine:engine,design:agentDesign,page:$agentPage,openModels:{modelPicker=true},openFiles:{tab="Files"},newLiveTask:{newConversation("agent")},openLiveConversation:{openMode("agent")})
    }
    private var projectsPage:some View{
        WixalPage(eyebrow:"PROJECTS",title:engine.project.map{textValue($0["name"])} ?? "Your projects",subtitle:engine.project == nil ? "Add a folder to keep related work together." : engine.root){
            Text("All projects").wixalFont(size:12,weight:.medium)
            ForEach(records(engine.state["projects"]),id: \.navigationID){project in
                Button{openProject(textValue(project["id"]))}label:{Label(textValue(project["name"]),systemImage:"folder").frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(WixalButtonStyle()).disabled(navigationBusy)
            }
            if engine.project != nil {
                HStack{Button("New chat"){newConversation("chat")};Button("Files"){tab="Files"};Button("Terminal"){terminal.toggle()};Menu("Project settings"){Button("Saved context…"){drawer="Memory"};Button("Show folder in Finder"){NSWorkspace.shared.selectFile(nil,inFileViewerRootedAtPath:engine.root)};Divider();Button("Delete project…",role:.destructive){projectDeleteID=textValue(engine.state["activeProject"])}}}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)
                ForEach(recentSessions.filter{textValue($0["projectId"])==textValue(engine.state["activeProject"])},id: \.navigationID){session in conversationRow(session)}
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
        if action.hasPrefix("Conversation:"),let session=records(engine.state["sessions"]).first(where:{textValue($0["id"])==String(action.dropFirst(13))}){openConversation(session);return}
        if action.hasPrefix("Project:"){openProject(String(action.dropFirst(8)));return}
        if action=="Toggle sidebar"{toggleSidebar();return}
        if action=="Chats"{chooseWorkspace(.chats);return}
        if action.hasPrefix("Settings:") {
            let requested=String(action.dropFirst(9))
            let aliases=["Connections":"Connections & sharing","Tools":"Tools & permissions","Data":"Data & sync"]
            let category=aliases[requested] ?? requested
            settings.open(SettingsCategory.all.contains{$0.id==category} ? category : "Data & sync")
            openSettings();return
        }
        if action == "Tools" { drawer=nil;tab="Tools";return }
        switch action{case "Commands":palette=true;case "Settings":openSettings();case "Connections":settings.open("Connections & sharing",detail:"Companion");openSettings();case "Account":settings.open("Account");openSettings();case "Setup":setupPresented=true;case "Terms":legalDocument="terms";case "Privacy":legalDocument="privacy";case "Open project":engine.pickProject();case "New conversation":newConversation("chat");case "Chat":openMode("chat");case "Agents":chooseWorkspace(.agents);case "Tasks":tab="Agents";agentPage="Task inbox";case "Terminal":terminal.toggle();case "Tool kit":openMode("agent",page:"Live tools");case "Project memory":tab="Projects";drawer="Memory";case "Archived chats":archives=true;default:tab=action}}
}

private extension Dictionary where Key == String, Value == Any { var navigationID:String { textValue(self["id"]) } }
