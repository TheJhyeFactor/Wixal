import SwiftUI

struct CybersecurityAgentsView:View {
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    @ViewState private var brief=""
    @ViewState private var showAssessments=false
    @ViewState private var targetID=""
    @ViewState private var model=""
    @ViewState private var investigationError=""
    var openInvestigations:()->Void = {}
    private var investigationTargets:[[String:Any]] {records(engine.state["securityTargets"]).filter{textValue($0["projectId"]) == textValue(engine.state["activeProject"]) && $0["archived"] as? Bool != true}}
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(spacing:0){
        HStack{Button("Security agent"){showAssessments=false};Button("Manual assessments & evidence"){showAssessments=true}}.buttonStyle(WixalButtonStyle()).padding(16)
        if showAssessments{ToolsDrawer(engine:engine,close:{showAssessments=false},cybersecurity:true)}
        else{AgentDesignPage(title:"Security agent",subtitle:"Choose an investigation target and goal. Recon, research and proposed checks share the same evidence records."){
            Text("Selected project: "+(engine.project.map{textValue($0["name"])} ?? "Choose a project before project or assessment work")).wixalFont(size:12).foregroundStyle(theme.muted)
            Picker("Investigation target",selection:$targetID){Text("Choose target").tag("");ForEach(Array(investigationTargets.enumerated()),id:\.offset){_,target in Text(textValue(target["address"])).tag(textValue(target["id"]))}}
            Picker("Investigation model",selection:$model){Text("Choose model").tag("");ForEach(Array(engine.models.enumerated()),id:\.offset){_,entry in Text(textValue(entry["name"])).tag(textValue(entry["name"]))}}
            TextEditor(text:$brief).wixalFont(size:13).scrollContentBackground(.hidden).padding(12).frame(height:130).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel("Security agent task and authorised scope")
            HStack{Button("Choose project",action:engine.pickProject);Button("Start security agent"){
                Task{do{
                    if !brief.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty{_=try await engine.call("security-target-update",["id":targetID,"objective":brief])}
                    _=try await engine.call("security-investigate",["targetId":targetID,"model":model]);openInvestigations()
                }catch{investigationError=error.localizedDescription}}
            }.disabled(engine.busy || !engine.connected || targetID.isEmpty || model.isEmpty)}.buttonStyle(WixalButtonStyle(outlined:true))
            Text("Network and website tools retain their existing scope validation and action review. Background runs pause when a required action cannot be reviewed.").wixalFont(size:11).foregroundStyle(theme.muted)
            if !investigationError.isEmpty{Text(investigationError).foregroundStyle(.orange)}
            Text("Uses the same target, discovery inventory, source research and editable plans as Investigations. The AI proposes connected checks; run them from the chain studio.").wixalFont(size:11).foregroundStyle(theme.muted)
            Button("Open investigation records",action:openInvestigations).buttonStyle(WixalButtonStyle())
        }}
    }.task{design.bind(engine);targetID=textValue(investigationTargets.first?["id"]);model=textValue(engine.state["model"]);engine.loadModels()}.onChange(of:engine.connected){_,ready in if ready{design.bind(engine)}}}
}

struct CybersecurityAgentWorkspace:View {
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    @ViewState private var section="Investigations"
    var body:some View{VStack(spacing:0){
        Picker("Security workspace",selection:$section){Text("Agents").tag("Agents");Text("Investigations").tag("Investigations")}.pickerStyle(.segmented).padding(.horizontal,24).padding(.top,12)
        if section=="Agents"{CybersecurityAgentsView(engine:engine,design:design,openInvestigations:{section="Investigations"})}else{SecurityWorkspaceView(engine:engine)}
    }}
}
