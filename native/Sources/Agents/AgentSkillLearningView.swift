import SwiftUI

struct AgentSkillLearningView:View {
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    @ViewState private var name=""
    @ViewState private var procedure=""
    @ViewState private var candidateID=""
    @ViewState private var agentID=""
    @ViewState private var prompt=""
    @ViewState private var checks:[AgentSuccessCheck]=[]
    @ViewState private var evaluating=false
    @ViewState private var error=""
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:16){
        DisclosureGroup("Propose and evaluate a procedure"){
            VStack(alignment:.leading,spacing:12){
                TextField("Skill name",text:$name).wixalField().accessibilityLabel("Candidate skill name")
                TextEditor(text:$procedure).scrollContentBackground(.hidden).wixalFont(size:12).padding(8).frame(height:110).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel("Candidate skill procedure")
                Button("Save candidate"){engine.action("skill-propose",["name":name,"content":procedure]);name="";procedure=""}.disabled(name.isEmpty || procedure.isEmpty || engine.busy).buttonStyle(WixalButtonStyle(outlined:true))
                Picker("Candidate",selection:$candidateID){Text("Choose a candidate").tag("");ForEach(Array(records(engine.state["skillCandidates"]).enumerated()),id:\.offset){_,row in Text(textValue(row["name"])).tag(textValue(row["id"]))}}
                Picker("Evaluation agent",selection:$agentID){Text("Choose an agent").tag("");ForEach(design.agents.filter{$0.archived != true}){agent in Text(agent.name).tag(agent.id)}}
                TextField("Real evaluation task",text:$prompt).wixalField().accessibilityLabel("Skill evaluation task")
                AgentChecksEditor(checks:$checks)
                Text("Evaluation compares the current procedure and candidate against the same project task. Changes use separate sandboxed project copies. Two passing evaluations are required before promotion. Read-only cases require a tool evidence check.").wixalFont(size:11).foregroundStyle(theme.muted)
                Button(evaluating ? "Evaluating…" : "Run baseline and candidate"){
                    Task{evaluating=true;engine.operationRunning=true;engine.busy=true;defer{evaluating=false;engine.operationRunning=false;engine.busy=false}
                        do{let data=try JSONEncoder().encode(checks);var params:[String:Any]=["id":candidateID,"agentID":agentID,"cases":[["prompt":prompt,"successCriteria":try JSONSerialization.jsonObject(with:data)]]];if let project=engine.project{params["projectId"]=project["id"]};_ = try await engine.call("skill-evaluate",params);error=""}catch{self.error=error.localizedDescription}}
                }.disabled(engine.busy || evaluating || candidateID.isEmpty || agentID.isEmpty || prompt.isEmpty || checks.isEmpty).buttonStyle(WixalButtonStyle(outlined:true))
            }.padding(.top,10)
        }
        if !error.isEmpty{Text(error).foregroundStyle(.orange)}
        ForEach(Array(records(engine.state["skillCandidates"]).enumerated()),id:\.offset){_,row in VStack(alignment:.leading,spacing:8){
            HStack{Text(textValue(row["name"])).wixalFont(size:13,weight:.medium);Spacer();Text(textValue(row["status"]))}
            let evaluations=records(row["evaluations"])
            Text("\(evaluations.count) evaluations · \(evaluations.filter{textValue($0["status"])=="passed"}.count) passed").wixalFont(size:11).foregroundStyle(theme.muted)
            DisclosureGroup("Evaluation evidence"){Text(pretty(evaluations)).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}
            Button("Promote verified procedure"){engine.action("skill-promote",["id":textValue(row["id"])])}.disabled(engine.busy || evaluations.suffix(2).count<2 || evaluations.suffix(2).contains{textValue($0["status"]) != "passed"} || textValue(row["status"])=="promoted").buttonStyle(WixalButtonStyle(outlined:true))
        }.wixalCard()}
    }.wixalFont(size:12)}
}
