import SwiftUI

struct TasksView:View {
    @ObservedObject var engine:EngineClient
    var openConversation:()->Void = {}
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var schedulePrompt=""
    @ViewState<String> private var minutes="60"
    @ViewState<String> private var filter="All"
    @ViewState<String> private var missedPolicy="latest"
    private var tasks:[[String:Any]]{records(engine.state["tasks"]).reversed().filter{filter=="All" || (filter=="Inbox" ? textValue($0["status"])=="queued" : ["paused","interrupted","failed"].contains(textValue($0["status"])))}}
    var body:some View {
        WixalPage(eyebrow:"WORKSPACE",title:"Task inbox",subtitle:"Review incoming work, inspect results and continue in its conversation."){
            Picker("Show tasks",selection:$filter){ForEach(["All","Inbox","Needs attention"],id:\.self){Text($0)}}.pickerStyle(.segmented).frame(maxWidth:440)
            if tasks.isEmpty{Text("No tasks in this view. Companion tasks arrive here for you to start.").font(.system(size:12)).foregroundStyle(theme.muted).wixalCard()}
            ForEach(Array(tasks.enumerated()),id:\.offset){_,task in taskCard(task)}
            WixalSection(title:"Recurring tasks",detail:"Runs while Wixal is open, or while it is closed when background scheduling is enabled. Runs after wake; the Mac must be awake. Actions needing review pause for you."){
                Toggle("Run schedules while Wixal is closed",isOn:Binding(get:{(engine.state["backgroundScheduler"] as? [String:Any])?["enabled"] as? Bool ?? false},set:{engine.action("background-settings",["enabled":$0])})).disabled(engine.busy)
                Picker("After missed intervals",selection:$missedPolicy){Text("Run once for the latest interval").tag("latest");Text("Skip missed intervals").tag("skip")}.font(.system(size:11))
                VStack(alignment:.leading,spacing:12){TextField("Describe the task…",text:$schedulePrompt).wixalField();HStack{Text("Every");TextField("Minutes",text:$minutes).wixalField().frame(width:80);Text("minutes");Spacer();Button("Schedule",action:addSchedule).buttonStyle(WixalButtonStyle(outlined:true)).disabled(schedulePrompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || (Int(minutes) ?? 0)<1 || (Int(minutes) ?? 0)>44640 || engine.busy)}}.font(.system(size:11)).wixalCard()
                ForEach(Array(records(engine.state["schedules"]).enumerated()),id:\.offset){_,item in
                    HStack{VStack(alignment:.leading,spacing:6){Text(textValue(item["prompt"]));Text("Every \((item["intervalSeconds"] as? Int ?? 0)/60) minutes · \((item["enabled"] as? Bool ?? false) ? "Enabled" : "Paused")").font(.system(size:10)).foregroundStyle(theme.muted);if let last=item["lastRun"] as? [String:Any]{Text("Last run: \(textValue(last["status"])) · \(last["missed"] as? Int ?? 0) missed intervals").font(.system(size:10)).foregroundStyle(theme.muted)}};Spacer();Button((item["enabled"] as? Bool ?? false) ? "Pause" : "Enable"){engine.action("schedule-toggle",["id":textValue(item["id"]),"enabled":!(item["enabled"] as? Bool ?? false)])};Button("Remove",role:.destructive){engine.action("schedule-delete",["id":textValue(item["id"])])}}.font(.system(size:12)).buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy).wixalCard()
                }
            }
        }
    }
    private func taskCard(_ task:[String:Any])->some View {
        let status=textValue(task["status"]),project=records(engine.state["projects"]).first{textValue($0["id"])==textValue(task["projectId"])}
        return VStack(alignment:.leading,spacing:14){
            HStack(alignment:.top){Text(textValue(task["title"]).isEmpty ? String(textValue(task["prompt"]).prefix(100)) : textValue(task["title"])).font(.system(size:13,weight:.medium));Spacer();Text(status.replacingOccurrences(of:"_",with:" ").capitalized).font(.system(size:10)).padding(6).background(theme.selected,in:Capsule())}
            Text("\(textValue(project?["name"]).isEmpty ? "Personal workspace" : textValue(project?["name"])) · from \(textValue(task["source"]).isEmpty ? "Wixal" : textValue(task["source"]))").font(.system(size:10)).foregroundStyle(theme.muted)
            DisclosureGroup("Read task brief"){Text(textValue(task["prompt"])).font(.system(size:12)).textSelection(.enabled).padding(.top,8)}
            if let error=task["error"] as? String{Text(error).foregroundStyle(.red).textSelection(.enabled)}
            if let result=task["result"]{DisclosureGroup("Completed response"){MarkdownMessage(content:result as? String ?? pretty(result)).padding(.top,8)}}
            if !records(task["checkpoints"]).isEmpty{DisclosureGroup("\(records(task["checkpoints"]).count) tool checkpoints"){Text(pretty(task["checkpoints"] ?? [])).font(.system(size:11,design:.monospaced)).textSelection(.enabled).padding(.top,8)}}
            HStack{
                if ["queued","failed","interrupted","cancelled","paused"].contains(status){Button(status=="queued" ? "Start in Wixal" : "Retry in new conversation"){start(task)};Button("Dismiss"){engine.action("task-dismiss",["id":textValue(task["id"])])}}
                if !textValue(task["sessionId"]).isEmpty{Button("Open conversation ↗"){open(task)}}
                Spacer()
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)
        }.font(.system(size:11)).wixalCard()
    }
    private func addSchedule(){Task{do{_=try await engine.call("schedule-add",["prompt":schedulePrompt,"intervalSeconds":(Int(minutes) ?? 60)*60,"missedRunPolicy":missedPolicy]);schedulePrompt=""}catch{engine.error=error.localizedDescription}}}
    private func open(_ task:[String:Any]){Task{do{if textValue(engine.state["activeProject"]) != textValue(task["projectId"]){_=try await engine.call("project-select",["id":task["projectId"] ?? NSNull()])};_=try await engine.call("session-select",["id":textValue(task["sessionId"])]);openConversation()}catch{engine.error=error.localizedDescription}}}
    private func start(_ task:[String:Any]){openConversation();engine.action("task-start",["id":textValue(task["id"])])}
}
