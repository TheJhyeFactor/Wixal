import SwiftUI
import AppKit

struct WorkspaceView: View {
    @ObservedObject var engine: EngineClient
    @ViewState<String> private var tab = "Chat"
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @ViewState<Bool> private var introFinished=false
    @ViewState<Bool> private var preferencesLoaded=false
    @ViewState<Bool> private var terminal = false
    @ViewState<Bool> private var modelPicker=false
    @ViewState<Bool> private var workspaceMenu=false
    @ViewState<Bool> private var settingsPresented=false
    @ViewState<Bool> private var archives = false
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
                sidebar.frame(width:collapsed ? 56 : 260).background(theme.sidebar)
                Rectangle().fill(theme.line).frame(width:1)
                VStack(spacing:0) {
                    workspaceHeader
                    HStack(spacing:0) {
                        VSplitView {
                            Group {
                                switch tab {
                                case "Files": FilesView(engine:engine,onUse:addFileContext)
                                case "Models": ModelsView(engine:engine)
                                case "Performance": PerformanceView(engine:engine)
                                case "Tasks": TasksView(engine:engine,openConversation:{tab="Chat";drawer=nil})
                                case "Settings": SettingsView(engine:engine,theme:appearanceBinding,navigate:{select($0)},previewLaunch:{introFinished=false})
                                default: ChatView(engine:engine,openModels:{modelPicker=true},openFiles:{tab="Files"},openTools:{drawer=drawer == "Tools" ? nil : "Tools"})
                                }
                            }.frame(maxWidth:.infinity,maxHeight:.infinity)
                            if terminal {
                                VStack(spacing:0) {
                                    HStack(spacing:8) { Text("›_").font(.system(size:12,design:.monospaced)); Text("Terminal"); Text(engine.root.isEmpty ? "Home" : engine.root).lineLimit(1).foregroundStyle(theme.muted); Spacer(); Text("Host shell").foregroundStyle(theme.muted); Button("Clear"){engine.terminalSession.clear()}.buttonStyle(.plain); Button {terminal=false} label:{Image(systemName:"xmark")}.buttonStyle(.plain).help("Hide terminal").accessibilityLabel("Hide terminal") }.font(.system(size:11)).padding(.horizontal,14).frame(height:34).background(theme.panel)
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
                                    .frame(width:min(380,windowSize.width-(collapsed ? 56 : 260)-24))
                                    .background(theme.panel).overlay(alignment:.leading){Rectangle().fill(theme.line).frame(width:1)}
                                    .shadow(color:.black.opacity(theme.light ? 0.06 : 0.15),radius:14,x:-5)
                            }
                        }
                    }
                    if !engine.connected {
                        HStack { Text(engine.activity); Spacer(); Button(engine.restarting ? "Restarting…" : "Restart engine") { engine.restart() }.disabled(engine.restarting) }.font(.system(size:12)).padding(12).background(theme.panel)
                    }
                    if !engine.error.isEmpty {
                        HStack { Image(systemName:"exclamationmark.triangle"); Text(engine.error).textSelection(.enabled); Spacer(); Button("Dismiss") {engine.error=""}.buttonStyle(.plain) }.font(.system(size:11)).padding(12).background(.red.opacity(0.08))
                    }
                }.background(theme.background)
            }
        }.foregroundStyle(theme.text).font(.system(size:13)).background(theme.background)
        .background(SheetFocusRestorer().frame(width:0,height:0))
        .ignoresSafeArea(.container,edges:.top)
        .animation(motion,value:expanded).animation(motion,value:collapsed).animation(motion,value:drawer).animation(motion,value:tab)
        .overlay{if preferencesLoaded && !introFinished{LaunchView(theme:theme,motion:!reduceMotion && (ui["launchAnimation"] as? Bool ?? true),sound:ui["launchSound"] as? Bool ?? true,done:{introFinished=true})}}
        .task{try? await Task.sleep(for:.seconds(3));if !preferencesLoaded{introFinished=true}}
        .onChange(of:engine.connected){_,ready in if ready && !preferencesLoaded{preferencesLoaded=true;collapsed=ui["sidebarCollapsed"] as? Bool ?? false;if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil{introFinished=true};if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] == nil{let setup=engine.state["setup"] as? [String:Any] ?? [:];setupPresented = !(setup["completed"] as? Bool ?? false)}}}
        .onChange(of:ui["sidebarCollapsed"] as? Bool){_,value in collapsed=value ?? false}
        .onChange(of:ui["appIcon"] as? String){_,_ in updateIcon()}
        .overlay(alignment:.bottomLeading){
            if workspaceMenu {
                ZStack(alignment:.bottomLeading){
                    Color.clear.contentShape(Rectangle()).onTapGesture{workspaceMenu=false}
                    SidebarWorkspaceMenu(engine:engine,action:{workspaceMenu=false;select($0)},dismissMenu:{workspaceMenu=false}).padding(.leading,12).padding(.bottom,66).transition(.opacity.combined(with:.offset(y:4)))
                }
            }
        }
        .animation(motion,value:workspaceMenu)
        .onExitCommand{if workspaceMenu{workspaceMenu=false}else if drawer != nil{drawer=nil}else if tab != "Chat"{tab="Chat"}}
        .onReceive(NotificationCenter.default.publisher(for:.wixalOpenSettings)){_ in openSettings()}
        .onReceive(NotificationCenter.default.publisher(for:.wixalNavigate)){message in if let action=message.object as? String{select(action)}}
        .sheet(isPresented:$settingsPresented){
            VStack(spacing:0){HStack{Spacer();Button{settingsPresented=false}label:{Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel("Close settings")}.padding(.horizontal,20).padding(.top,18);SettingsView(engine:engine,theme:appearanceBinding,navigate:{settingsPresented=false;deferredSelect($0)},previewLaunch:{settingsPresented=false;introFinished=false})}.frame(width:min(720,windowSize.width-40),height:min(760,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme)
        }
        .sheet(isPresented:$archives){dialog("Close archived chats",close:{archives=false}){ArchivedChatsView(engine:engine,open:{archives=false;tab="Chat"})}}
        .sheet(isPresented:Binding(get:{engine.projectCandidate != nil},set:{if !$0{engine.projectCandidate=nil}})){ProjectEntryView(engine:engine,path:engine.projectCandidate ?? "").environment(\.wixalTheme,theme)}
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
        .sheet(isPresented:$modelPicker){VStack(spacing:0){HStack{Text("Choose your model").font(.system(size:15,weight:.medium));Spacer();Button{modelPicker=false}label:{Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel("Close model picker")}.padding(20).background(theme.panel);ModelsView(engine:engine)}.frame(width:min(980,windowSize.width-40),height:min(680,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme)}
        .sheet(isPresented:$palette) {CommandPalette(action:{select($0);palette=false})}
        .onAppear {updateIcon();expanded.insert(textValue(engine.state["activeProject"]));if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil {terminal=true}}
        .onChange(of:engine.state["activeProject"] as? String) {_,id in expanded.insert(id ?? "")}
        .onChange(of:appearance){_,_ in updateIcon()}
        .onChange(of:engine.state["activeSession"] as? String) {_,_ in engine.browser.closeAll()}
        .onGeometryChange(for:CGSize.self){$0.size}action:{windowSize=$0}
        .environment(\.wixalTheme,theme).environment(\.wixalTextSize,CGFloat(ui["textSize"] as? Int ?? 13)).tint(theme.accent).preferredColorScheme(theme.light ? .light : .dark)
    }
    private func updateIcon(){
        let saved=textValue(ui["appIcon"]);let variant = !saved.isEmpty && saved != "theme" ? saved : ["Paper":"pearl","Midnight":"midnight","Forest":"copper","Sakura":"sakura"][appearance] ?? "sakura"
        if let url=Bundle.main.url(forResource:variant,withExtension:"png",subdirectory:"icon-variants"),let image=NSImage(contentsOf:url){NSApp.applicationIconImage=image}
    }
    private var titlebar: some View {
        ZStack {
            HStack(spacing:18) { Text("wixal").font(.system(size:12,design:.monospaced));Text("/").foregroundStyle(theme.muted.opacity(0.5));Text(engine.project.map{textValue($0["name"])} ?? "workspace").font(.system(size:12,design:.monospaced));Spacer();Text("0.7.8").font(.system(size:10,design:.monospaced)).foregroundStyle(theme.muted) }.padding(.leading,98).padding(.trailing,20)
            Button {palette=true} label:{HStack{Text("Find a command");Spacer();Text("⌘ K").font(.system(size:10,design:.monospaced))}.frame(width:224).font(.system(size:11)).foregroundStyle(theme.muted)}.buttonStyle(WixalButtonStyle(outlined:true))
        }.frame(height:48).background(theme.panel).overlay(alignment:.bottom){Rectangle().fill(theme.line).frame(height:1)}
    }
    private var sidebar: some View {
        VStack(alignment:.leading,spacing:0) {
            HStack {
                if !collapsed {Wordmark();Spacer()}
                Button {workspaceMenu=false;collapsed.toggle();engine.action("settings",["ui":["sidebarCollapsed":collapsed]])} label:{Image(systemName:collapsed ? "sidebar.left" : "sidebar.left").font(.system(size:16)).frame(width:30,height:30)}.buttonStyle(.plain).accessibilityLabel(collapsed ? "Expand sidebar" : "Collapse sidebar")
            }.frame(height:43).padding(.bottom,18)
            Button {engine.action("session-new");tab="Chat"} label:{HStack(spacing:8){Image(systemName:"plus").font(.system(size:16));if !collapsed {Text("New conversation");Spacer();Text("⌘ N").font(.system(size:9,design:.monospaced)).foregroundStyle(theme.muted)}}.frame(maxWidth:.infinity).frame(height:24)}.buttonStyle(WixalButtonStyle(outlined:!collapsed)).disabled(engine.busy).accessibilityLabel("New conversation")
            if !collapsed {
                HStack(spacing:6){TextField("Find a project or chat…",text:$search).textFieldStyle(.plain).font(.system(size:11));if !search.isEmpty{Button{search=""}label:{Image(systemName:"xmark.circle.fill")}.buttonStyle(.plain)}}.padding(10).background(theme.background,in:RoundedRectangle(cornerRadius:7)).overlay(RoundedRectangle(cornerRadius:7).stroke(theme.line,lineWidth:1)).padding(.top,16).padding(.bottom,18)
                HStack{Text("PROJECTS").font(.system(size:10,weight:.medium)).tracking(1.3).foregroundStyle(theme.muted);Spacer();Button(action:engine.pickProject){Image(systemName:"plus").font(.system(size:16))}.buttonStyle(.plain).help("Open project folder").disabled(engine.busy)}.padding(.horizontal,7).padding(.bottom,12)
                ScrollView {
                    VStack(alignment:.leading,spacing:10) {
                        ForEach(Array(records(engine.state["projects"]).filter{matchesProject($0)}.enumerated()),id:\.offset) {_,project in projectGroup(project)}
                        if matchesProject(["id":"","name":"Personal chats"]){projectGroup(["id":"","name":"Personal chats","personal":true])}
                    }
                }.scrollIndicators(.hidden)
            } else {Spacer()}
            Spacer(minLength:0)
            Rectangle().fill(theme.line).frame(height:1).padding(.horizontal,-12)
            VStack(alignment:.leading,spacing:4) {
                SidebarRailButton(title:"Models",symbol:"◈",collapsed:collapsed,selected:tab=="Models"){workspaceMenu=false;tab="Models";drawer=nil}
                SidebarRailButton(title:accountName,symbol:"◎",collapsed:collapsed){workspaceMenu=false;accountPresented=true}
                SidebarRailButton(title:"Settings",symbol:"⚙",collapsed:collapsed,selected:settingsPresented){openSettings()}
                SidebarRailButton(title:"Workspace",symbol:"☰",collapsed:collapsed,selected:workspaceMenu){workspaceMenu.toggle()}
            }.padding(.top,8)
        }.padding(.horizontal,collapsed ? 8 : 12).padding(.top,18).padding(.bottom,10)
    }
    private func matchesProject(_ project:[String:Any])->Bool {
        search.isEmpty || textValue(project["name"]).localizedCaseInsensitiveContains(search) || records(engine.state["sessions"]).contains { textValue($0["projectId"])==textValue(project["id"]) && $0["archivedAt"] as? Int == nil && textValue($0["title"]).localizedCaseInsensitiveContains(search) }
    }
    private func projectGroup(_ project:[String:Any]) -> some View {
        let id=textValue(project["id"]),selected=id == textValue(engine.state["activeProject"])
        let sessions=records(engine.state["sessions"]).filter{textValue($0["projectId"])==id && (archives || $0["archivedAt"] == nil || $0["archivedAt"] is NSNull) && (search.isEmpty || textValue(project["name"]).localizedCaseInsensitiveContains(search) || textValue($0["title"]).localizedCaseInsensitiveContains(search))}
        return VStack(alignment:.leading,spacing:6){
            HStack(spacing:5){
                Button{if expanded.contains(id){expanded.remove(id)}else{expanded.insert(id)}}label:{Image(systemName:expanded.contains(id) ? "chevron.down" : "chevron.right").font(.system(size:10,weight:.semibold)).frame(width:16,height:26)}.buttonStyle(.plain).accessibilityLabel("\(expanded.contains(id) ? "Collapse" : "Expand") \(textValue(project["name"]))")
                Button{engine.action("project-select",id.isEmpty ? [:] : ["id":id]);tab="Chat";expanded.insert(id)}label:{HStack(spacing:7){Image(systemName:id.isEmpty ? "circle.dotted" : "folder").font(.system(size:14));Text(textValue(project["name"])).lineLimit(1);Spacer()}}.buttonStyle(.plain).disabled(engine.busy)
                Button{Task{do{_=try await engine.call("project-select",id.isEmpty ? [:] : ["id":id]);_=try await engine.call("session-new");tab="Chat";expanded.insert(id)}catch{engine.error=error.localizedDescription}}}label:{Image(systemName:"plus").font(.system(size:15)).frame(width:22,height:26)}.buttonStyle(.plain).disabled(engine.busy).accessibilityLabel("New chat in \(textValue(project["name"]))")
            }.font(.system(size:12)).padding(.horizontal,6).padding(.vertical,8).background(selected ? theme.panel.opacity(0.75) : .clear,in:RoundedRectangle(cornerRadius:8))
            if expanded.contains(id) || !search.isEmpty {
                VStack(alignment:.leading,spacing:2){
                    if selected && !id.isEmpty {Button{drawer="Memory"}label:{HStack{Image(systemName:"diamond");Text("Project memory");Spacer();Text("\(records(engine.state["memories"]).filter{textValue($0["projectId"])==id}.count)").font(.system(size:10,design:.monospaced))}}.buttonStyle(WixalButtonStyle()).font(.system(size:11)).foregroundStyle(theme.muted)}
                    ForEach(Array(sessions.enumerated()),id:\.offset){_,session in
                        HStack(spacing:5){Text("↳").foregroundStyle(theme.muted);Button{Task{do{if !selected{_=try await engine.call("project-select",id.isEmpty ? [:] : ["id":id])};_=try await engine.call("session-select",["id":textValue(session["id"])]);tab="Chat"}catch{engine.error=error.localizedDescription}}}label:{Text(textValue(session["title"])).font(.system(size:11)).lineLimit(1).frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(.plain).disabled(engine.busy)
                            Menu{Button("Rename…"){renameID=textValue(session["id"])};Button("Copy conversation"){copyConversation(textValue(session["id"]))};if session["archivedAt"] != nil && !(session["archivedAt"] is NSNull){Button("Restore"){engine.action("session-archive",["id":textValue(session["id"]),"restore":true])}}else{Button("Archive"){engine.action("session-archive",["id":textValue(session["id"])])}};Divider();Button("Delete…",role:.destructive){deleteID=textValue(session["id"])}}label:{Text("•••").font(.system(size:10))}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:22)
                        }.padding(.horizontal,10).padding(.vertical,9).background(textValue(session["id"])==textValue(engine.state["activeSession"]) ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)).overlay(alignment:.leading){if textValue(session["id"])==textValue(engine.state["activeSession"]){RoundedRectangle(cornerRadius:1).fill(theme.accent).frame(width:2,height:16).offset(x:-8)}}
                    }
                }.padding(.leading,22).overlay(alignment:.leading){Rectangle().fill(theme.line).frame(width:1).padding(.leading,13)}
            }
        }
    }
    private var workspaceHeader: some View {
        HStack(spacing:16){
            VStack(alignment:.leading,spacing:6){
                HStack(spacing:7){Image(systemName:"folder").font(.system(size:13));Button(engine.project.map{textValue($0["name"])} ?? "Personal workspace",action:engine.pickProject).buttonStyle(.plain);if !engine.root.isEmpty{Button{NSWorkspace.shared.selectFile(nil,inFileViewerRootedAtPath:engine.root)}label:{Image(systemName:"arrow.up.right")}.buttonStyle(.plain).help("Show project in Finder")}}.font(.system(size:10)).foregroundStyle(theme.muted)
                Button(tab == "Chat" ? textValue(engine.session?["title"]).isEmpty ? "New conversation" : textValue(engine.session?["title"]) : tab){if tab=="Chat"{renameID=textValue(engine.state["activeSession"])}}.buttonStyle(.plain).help(tab=="Chat" ? "Rename conversation" : tab).font(.system(size:14,weight:.medium)).lineLimit(1)
            }
            Spacer(minLength:8)
            if tab != "Chat"{Button("Back to chat →"){tab="Chat";drawer=nil}.buttonStyle(WixalButtonStyle()).font(.system(size:11))}
            else{
                headerButton("Files",icon:"folder",selected:tab=="Files"){tab="Files";drawer=nil}
                headerButton("Tools",icon:"wrench",selected:drawer=="Tools"){drawer=drawer == "Tools" ? nil : "Tools"}
                headerButton("Memory",icon:"diamond",selected:drawer=="Memory"){drawer=drawer == "Memory" ? nil : "Memory"}
                headerButton("Terminal",icon:"terminal",selected:terminal){terminal.toggle()}
            }
        }.padding(.horizontal,28).frame(height:74).background(theme.panel.opacity(0.3)).overlay(alignment:.bottom){Rectangle().fill(theme.line).frame(height:1)}
    }
    private func headerButton(_ title:String,icon:String,selected:Bool,action:@escaping()->Void)->some View {
        Button(action:action){Label(title,systemImage:icon).font(.system(size:11)).labelStyle(.titleAndIcon)}.buttonStyle(WixalButtonStyle()).background(selected ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)).foregroundStyle(selected ? theme.accent : theme.muted)
    }
    private var accountName:String{let account=engine.state["account"] as? [String:Any] ?? [:];let profile=account["profile"] as? [String:Any] ?? [:];return account["signedIn"] as? Bool ?? false ? textValue(profile["name"]).isEmpty ? "Account" : textValue(profile["name"]) : "Account"}
    private func deferredSelect(_ action:String){Task{try? await Task.sleep(for:.milliseconds(180));select(action)}}
    private func addFileContext(_ file:[String:Any]){let draft=engine.session?["draft"] as? [String:Any] ?? [:];var attachments=records(draft["attachments"]);guard attachments.count<8 else{engine.error="Attach at most eight files or images";return};attachments.append(file);Task{do{_=try await engine.call("draft-save",["sessionId":textValue(engine.state["activeSession"]),"text":textValue(draft["text"]),"attachments":attachments]);tab="Chat"}catch{engine.error=error.localizedDescription}}}
    private func copyConversation(_ id:String){Task{do{let text=try await engine.call("session-copy",["id":id]) as? String ?? "";NSPasteboard.general.clearContents();NSPasteboard.general.setString(text,forType:.string)}catch{engine.error=error.localizedDescription}}}
    private func dialog<Content:View>(_ label:String,close:@escaping()->Void,@ViewBuilder content:()->Content)->some View{VStack(spacing:0){HStack{Spacer();Button(action:close){Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel(label)}.padding(18);content()}.frame(width:min(720,windowSize.width-40),height:min(760,windowSize.height-60)).background(theme.background).environment(\.wixalTheme,theme)}
    private func openSettings(){workspaceMenu=false;drawer=nil;settingsPresented=true}
    private func select(_ action:String){switch action{case "Commands":palette=true;case "Settings":openSettings();case "Connections":workspaceMenu=false;connectionsPresented=true;case "Account":accountPresented=true;case "Setup":setupPresented=true;case "Terms":legalDocument="terms";case "Privacy":legalDocument="privacy";case "Open project":engine.pickProject();case "New conversation":engine.action("session-new");tab="Chat";case "Terminal":terminal.toggle();case "Tool kit":tab="Chat";drawer="Tools";case "Project memory":tab="Chat";drawer="Memory";case "Archived chats":archives=true;default:tab=action}}
}
