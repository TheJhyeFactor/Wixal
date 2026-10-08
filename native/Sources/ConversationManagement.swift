import SwiftUI

struct RenameConversationView:View {
    @ObservedObject var engine:EngineClient
    let id:String
    let close:()->Void
    @ViewState<String> private var title=""
    @FocusState private var focused:Bool
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:20){Text("Rename conversation").wixalFont(size:22,weight:.medium);TextField("Conversation name",text:$title).wixalField().focused($focused).onSubmit(save);HStack{Button("Cancel",action:close).keyboardShortcut(.cancelAction);Spacer();Button("Save",action:save).keyboardShortcut(.defaultAction).disabled(title.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || title.count>120 || engine.busy)}}.buttonStyle(WixalButtonStyle(outlined:true)).padding(24).frame(width:480).background(theme.background).onAppear{title=textValue(records(engine.state["sessions"]).first{textValue($0["id"])==id}?["title"]);focused=true}}
    private func save(){Task{do{_=try await engine.call("session-rename",["id":id,"title":title]);close()}catch{engine.error=error.localizedDescription}}}
}
struct DeleteConversationView:View {
    @ObservedObject var engine:EngineClient
    let id:String
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:20){Text("Delete this conversation?").wixalFont(size:22,weight:.medium);Text("This permanently removes the conversation, its draft and associated task records from Wixal Native. Project files are kept.").wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(4);HStack{Button("Cancel",action:close).keyboardShortcut(.cancelAction);Spacer();Button("Delete conversation",role:.destructive){Task{do{_=try await engine.call("session-delete",["id":id]);close()}catch{engine.error=error.localizedDescription}}}.disabled(engine.busy)}}.buttonStyle(WixalButtonStyle(outlined:true)).padding(24).frame(width:480).background(theme.background)}
}
struct ArchivedChatsView:View {
    @ObservedObject var engine:EngineClient
    let open:()->Void
    @ViewState<String> private var query=""
    @FocusState private var searchFocused:Bool
    @Environment(\.wixalTheme) private var theme
    private var sessions:[[String:Any]]{records(engine.state["sessions"]).filter{($0["archivedAt"] != nil && !($0["archivedAt"] is NSNull)) && (query.isEmpty || textValue($0["title"]).localizedCaseInsensitiveContains(query))}.reversed()}
    var body:some View{WixalPage(eyebrow:"WORKSPACE",title:"Archived chats",subtitle:"Search your saved conversations and restore one to continue."){
        TextField("Find an archived chat…",text:$query).wixalField().focused($searchFocused)
        if sessions.isEmpty{Text(query.isEmpty ? "No archived conversations yet." : "No matching archived conversations.").wixalFont(size:12).foregroundStyle(theme.muted)}
        ForEach(Array(sessions.enumerated()),id:\.offset){_,item in HStack{VStack(alignment:.leading,spacing:6){Text(textValue(item["title"])).wixalFont(size:13,weight:.medium);Text(textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(item["projectId"])}?["name"]).isEmpty ? "Personal workspace" : textValue(records(engine.state["projects"]).first{textValue($0["id"])==textValue(item["projectId"])}?["name"])).wixalFont(size:10).foregroundStyle(theme.muted)};Spacer();Button("Restore & open ↗"){restore(item)}.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11).disabled(engine.busy)}.wixalCard()}
    }.onAppear{searchFocused=true}}
    private func restore(_ item:[String:Any]){Task{do{_=try await engine.call("session-archive",["id":textValue(item["id"]),"restore":true]);if textValue(engine.state["activeProject"]) != textValue(item["projectId"]){_=try await engine.call("project-select",["id":item["projectId"] ?? NSNull()])};_=try await engine.call("session-select",["id":textValue(item["id"])]);open()}catch{engine.error=error.localizedDescription}}}
}

struct DeleteProjectView:View {
    @ObservedObject var engine:EngineClient
    let id:String
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    private var count:Int{records(engine.state["sessions"]).filter{textValue($0["projectId"])==id}.count}
    var body:some View {
        VStack(alignment:.leading,spacing:20){
            Text("Delete this project?").wixalFont(size:22,weight:.medium)
            Text("This permanently removes the project from Wixal, including its \(count) conversations, archived chats, saved project context, schedules and assessment evidence. The folder and its files stay on your Mac.").wixalFont(size:13).foregroundStyle(theme.muted).lineSpacing(4)
            HStack{Button("Cancel",action:close).keyboardShortcut(.cancelAction);Spacer();Button("Delete project",role:.destructive){Task{do{_=try await engine.call("project-delete",["id":id,"confirmed":true]);close()}catch{engine.error=error.localizedDescription}}}.disabled(engine.busy)}
        }.buttonStyle(WixalButtonStyle(outlined:true)).padding(24).frame(width:480).background(theme.background)
    }
}
