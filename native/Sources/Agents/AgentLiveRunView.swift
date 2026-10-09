import SwiftUI

struct AgentLiveRunView:View {
    @ObservedObject var engine:EngineClient
    let run:[String:Any]
    let workflow:Bool
    @Environment(\.wixalTheme) private var theme
    @ViewState private var showContext=false
    @ViewState private var guidance=""
    @ViewState private var sendingGuidance=false
    private var status:String{textValue(run["status"])}
    private var active:Bool{["running","waiting_review","queued"].contains(status)}
    var body:some View{VStack(alignment:.leading,spacing:20){
        HStack(alignment:.top){Text(workflow ? textValue((run["definition"] as? [String:Any])?["name"]) : textValue(run["prompt"])).wixalFont(size:23,weight:.medium).textSelection(.enabled);Spacer();Label(agentOutcomeLabel(run),systemImage:active ? "circle.dotted" : status=="completed" ? "checkmark.circle" : "exclamationmark.circle").wixalFont(size:11).foregroundStyle(theme.accent)}
        Button(showContext ? "Hide run context" : "Show run context"){showContext.toggle()}.buttonStyle(WixalButtonStyle())
        if showContext{Text(pretty(run["agentSnapshot"] ?? run["definition"] ?? [:])).wixalFont(size:11,design:.monospaced).textSelection(.enabled).wixalCard()}
        if active{Label(engine.activity,systemImage:"bolt").wixalFont(size:12);if !engine.streaming.isEmpty{Text(engine.streaming).wixalFont(size:13).textSelection(.enabled)}}
        if !textValue(run["error"]).isEmpty{Text(textValue(run["error"])).wixalFont(size:12).foregroundStyle(.orange).textSelection(.enabled).wixalCard()}
        if workflow{ForEach(Array(records(run["stages"]).enumerated()),id:\.offset){_,stage in VStack(alignment:.leading,spacing:9){HStack{Text(textValue(stage["name"])).wixalFont(size:15,weight:.medium);Spacer();Text(textValue(stage["status"]).capitalized).foregroundStyle(theme.muted)};if let changes=stage["changes"]{DisclosureGroup("Isolated changes"){Text(pretty(changes)).wixalFont(size:11,design:.monospaced).textSelection(.enabled)};if textValue(stage["mergeStatus"])=="pending_review"{Button("Review and merge branch"){engine.action("workflow-merge",["runId":textValue(run["id"]),"stageId":textValue(stage["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)}};Text(textValue(stage["result"])).wixalFont(size:12).textSelection(.enabled);if let task=records(engine.state["tasks"]).first(where:{textValue($0["id"])==textValue(stage["taskId"])}){DisclosureGroup("Stage tool evidence"){Text(pretty(task["checkpoints"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}};if !textValue(stage["error"]).isEmpty{Text(textValue(stage["error"])).foregroundStyle(.orange)}}.wixalCard()}}
        if !textValue(run["result"]).isEmpty{WixalSection(title:"Agent result"){MarkdownMessage(content:textValue(run["result"]))}}
        if !records(run["securityEvidence"]).isEmpty{WixalSection(title:"Security observations",detail:"Tool-produced findings and raw evidence references. An observation does not establish a verified exploit."){Text(pretty(run["securityFindings"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled);DisclosureGroup("Assessment evidence"){Text(pretty(run["securityEvidence"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}}}
        if run["verification"] != nil{DisclosureGroup("Verification evidence"){Text(pretty(run["verification"]!)).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}}
        WixalSection(title:"Tool requests & results",detail:"Actual engine checkpoints. A final response is a conclusion; inspect the evidence to assess task success."){
            if records(run["checkpoints"]).isEmpty && !workflow{Text("No tool calls recorded for this run.").wixalFont(size:12).foregroundStyle(theme.muted)}
            ForEach(Array(records(run["checkpoints"]).enumerated()),id:\.offset){_,event in DisclosureGroup(textValue(event["name"])+" · "+textValue(event["status"])){VStack(alignment:.leading,spacing:10){Text(pretty(event["arguments"] ?? [:])).wixalFont(size:11,design:.monospaced);Text(textValue(event["result"])).wixalFont(size:12)}.textSelection(.enabled).padding(.top,10)}.wixalCard()}
        }
        if active && !workflow{HStack{TextField("Guide this run…",text:$guidance).wixalField();Button("Queue guidance"){let submitted=guidance;sendingGuidance=true;engine.action("agent-guide",["id":textValue(run["id"]),"text":submitted],completion:{success in sendingGuidance=false;if success && guidance==submitted{guidance=""}})}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(sendingGuidance || guidance.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)};if !((run["pendingGuidance"] as? [String]) ?? []).isEmpty{Text("Guidance queued for the next model step.").wixalFont(size:11).foregroundStyle(theme.muted)}}
        if !active && !workflow && !(records(run["successCriteria"]).isEmpty){Button("Recheck outcomes"){engine.action("agent-verify",["id":textValue(run["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)}
        if active{Button("Stop run",role:.destructive){let parent=textValue(run["workflowRunId"]);engine.action("stop",workflow ? ["runId":textValue(run["id"])] : parent.isEmpty ? ["taskId":textValue(run["id"])] : ["runId":parent])}.buttonStyle(WixalButtonStyle(outlined:true))}
        else if workflow && ["paused","interrupted","failed","cancelled","needs_attention"].contains(status){Button("Inspect and continue workflow"){engine.action("workflow-resume",["runId":textValue(run["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)}
        else if !workflow && ["paused","interrupted","failed","cancelled","needs_attention"].contains(status){Text("Before restarting, inspect the current files and retained tool outcomes. The new run will be told not to replay uncertain actions.").wixalFont(size:11).foregroundStyle(theme.muted);Button("Inspect and restart agent"){engine.action("agent-resume",["id":textValue(run["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)}
    }}
}
