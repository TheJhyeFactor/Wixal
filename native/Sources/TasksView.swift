import SwiftUI

struct TasksView:View {
    @ObservedObject var engine:EngineClient
    var openConversation:()->Void = {}
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var schedulePrompt=""
    @ViewState<String> private var minutes="60"
    @ViewState<String> private var filter="All"
    @ViewState<String> private var missedPolicy="latest"
    private var tasks:[[String:Any]]{records(engine.state["tasks"]).reversed().filter{filter=="All" || (filter=="Inbox" ? textValue($0["status"])=="queued" : ["paused","interrupted","failed","needs_attention"].contains(textValue($0["status"])))}}
    var body:some View {
        WixalPage(eyebrow:"WORKSPACE",title:"Task inbox",subtitle:"Review incoming work, inspect results and continue in its conversation."){
            Picker("Show tasks",selection:$filter){ForEach(["All","Inbox","Needs attention"],id:\.self){Text($0)}}.pickerStyle(.segmented).frame(maxWidth:440)
            if tasks.isEmpty{Text("No tasks in this view. Companion tasks arrive here for you to start.").wixalFont(size:12).foregroundStyle(theme.muted).wixalCard()}
            ForEach(Array(tasks.enumerated()),id:\.offset){_,task in taskCard(task)}
            WixalSection(title:"Recurring tasks",detail:"Runs while Wixal is open, or while it is closed when background scheduling is enabled. Runs after wake; the Mac must be awake. Actions needing review pause for you."){
                Toggle("Run schedules while Wixal is closed",isOn:Binding(get:{(engine.state["backgroundScheduler"] as? [String:Any])?["enabled"] as? Bool ?? false},set:{engine.action("background-settings",["enabled":$0])})).disabled(engine.busy)
                Picker("After missed intervals",selection:$missedPolicy){Text("Run once for the latest interval").tag("latest");Text("Skip missed intervals").tag("skip")}.wixalFont(size:11)
                VStack(alignment:.leading,spacing:12){TextField("Describe the task…",text:$schedulePrompt).wixalField();HStack{Text("Every");TextField("Minutes",text:$minutes).wixalField().frame(width:80);Text("minutes");Spacer();Button("Schedule",action:addSchedule).buttonStyle(WixalButtonStyle(outlined:true)).disabled(schedulePrompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || (Int(minutes) ?? 0)<1 || (Int(minutes) ?? 0)>44640 || engine.busy)}}.wixalFont(size:11).wixalCard()
                ForEach(Array(records(engine.state["schedules"]).enumerated()),id:\.offset){_,item in
                    scheduleCard(item)
                }
            }
        }
    }
    private func scheduleCard(_ item:[String:Any])->some View {
        let project=records(engine.state["projects"]).first{textValue($0["id"])==textValue(item["projectId"])}
        let last=item["lastRun"] as? [String:Any] ?? [:]
        let task=records(engine.state["tasks"]).first{textValue($0["id"])==textValue(last["taskId"])}
        let background=(engine.state["backgroundScheduler"] as? [String:Any])?["enabled"] as? Bool ?? false
        return VStack(alignment:.leading,spacing:10) {
            Text(textValue(item["prompt"])).textSelection(.enabled)
            Text("\(textValue(project?["name"]).isEmpty ? "Personal workspace" : textValue(project?["name"])) · Model: \(textValue(item["model"]).isEmpty ? "Current model at run time" : textValue(item["model"]))").foregroundStyle(theme.muted)
            Text("\(textValue(item["timing"]).isEmpty ? "Every \((item["intervalSeconds"] as? Int ?? 0)/60) minutes" : textValue(item["timing"])+" · "+textValue(item["time"])+" "+textValue(item["timezone"])) · \((item["enabled"] as? Bool ?? false) ? "Enabled" : "Paused") · Next: \(scheduleDate(item["nextRun"]))").foregroundStyle(theme.muted)
            Text("Missed intervals: \(textValue(item["missedRunPolicy"])=="skip" ? "Skip" : "Run once for latest") · \(background ? "Can run while closed, when Mac is awake" : "Runs while Wixal is open")").foregroundStyle(theme.muted)
            if !last.isEmpty {
                Text("Last result: \(textValue(last["status"]).capitalized) · \(scheduleDate(last["finished"] ?? last["started"])) · \(last["missed"] as? Int ?? 0) missed intervals").foregroundStyle(theme.muted)
                if !textValue(last["error"] ?? task?["error"]).isEmpty {Text(textValue(last["error"] ?? task?["error"])).foregroundStyle(.red).textSelection(.enabled)}
                let reviews=last["reviewsRequired"] as? [String] ?? []
                if !reviews.isEmpty {Text("Needs your review: \(reviews.joined(separator:", ")). Open the run and retry to review actions.").foregroundStyle(theme.muted)}
            }
            ViewThatFits(in:.horizontal) {
                HStack{scheduleActions(item,task:task)}
                VStack(alignment:.leading){scheduleActions(item,task:task)}
            }
        }.wixalFont(size:11).buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy).wixalCard()
    }
    @ViewBuilder private func scheduleActions(_ item:[String:Any],task:[String:Any]?)->some View {
        if let task,!textValue(task["sessionId"]).isEmpty {Button("Open last run ↗"){open(task)}}
        Button((item["enabled"] as? Bool ?? false) ? "Pause" : "Enable"){engine.action("schedule-toggle",["id":textValue(item["id"]),"enabled":!(item["enabled"] as? Bool ?? false)])}
        Button("Remove",role:.destructive){engine.action("schedule-delete",["id":textValue(item["id"])])}
    }
    private func scheduleDate(_ value:Any?)->String {
        guard let stamp=value as? NSNumber else{return "Not recorded"}
        return Date(timeIntervalSince1970:stamp.doubleValue/1000).formatted(date:.abbreviated,time:.shortened)
    }
    private func taskCard(_ task:[String:Any])->some View {
        let status=textValue(task["status"]),project=records(engine.state["projects"]).first{textValue($0["id"])==textValue(task["projectId"])}
        return VStack(alignment:.leading,spacing:14){
            HStack(alignment:.top){Text(textValue(task["title"]).isEmpty ? String(textValue(task["prompt"]).prefix(100)) : textValue(task["title"])).wixalFont(size:13,weight:.medium);Spacer();Text(agentOutcomeLabel(task)).wixalFont(size:10).padding(6).background(theme.selected,in:Capsule())}
            Text("\(textValue(project?["name"]).isEmpty ? "Personal workspace" : textValue(project?["name"])) · from \(textValue(task["source"]).isEmpty ? "Wixal" : textValue(task["source"]))").wixalFont(size:10).foregroundStyle(theme.muted)
            DisclosureGroup("Read task brief"){Text(textValue(task["prompt"])).wixalFont(size:12).textSelection(.enabled).padding(.top,8)}
            if let error=task["error"] as? String{Text(error).foregroundStyle(.red).textSelection(.enabled)}
            if let result=task["result"]{DisclosureGroup("Agent response"){MarkdownMessage(content:result as? String ?? pretty(result)).padding(.top,8)}}
            if task["verification"] != nil{DisclosureGroup("Outcome checks"){Text(pretty(task["verification"] ?? [:])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}}
            if !records(task["checkpoints"]).isEmpty{DisclosureGroup("\(records(task["checkpoints"]).count) tool checkpoints"){Text(pretty(task["checkpoints"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled).padding(.top,8)}}
            HStack{
                if ["queued","failed","interrupted","cancelled","paused","needs_attention"].contains(status){Button(status=="queued" ? "Start in Wixal" : "Inspect and continue"){start(task)};Button("Dismiss"){engine.action("task-dismiss",["id":textValue(task["id"])])}}
                if !textValue(task["sessionId"]).isEmpty{Button("Open conversation ↗"){open(task)}}
                Spacer()
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)
        }.wixalFont(size:11).wixalCard()
    }
    private func addSchedule(){Task{do{_=try await engine.call("schedule-add",["prompt":schedulePrompt,"intervalSeconds":(Int(minutes) ?? 60)*60,"missedRunPolicy":missedPolicy]);schedulePrompt=""}catch{engine.error=error.localizedDescription}}}
    private func open(_ task:[String:Any]){Task{do{if textValue(engine.state["activeProject"]) != textValue(task["projectId"]){_=try await engine.call("project-select",["id":task["projectId"] ?? NSNull()])};_=try await engine.call("session-select",["id":textValue(task["sessionId"])]);openConversation()}catch{engine.error=error.localizedDescription}}}
    private func start(_ task:[String:Any]){openConversation();if task["agentId"] != nil{engine.action("agent-resume",["id":textValue(task["id"])])}else{engine.action("task-start",["id":textValue(task["id"])])}}
}
