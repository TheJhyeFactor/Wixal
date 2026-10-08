import SwiftUI
import AppKit

struct AgentWorkflowEditor:View {
    let agents:[AgentProfileDraft]
    @ViewState var draft:AgentWorkflowDraft
    let save:(AgentWorkflowDraft)->Void
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @Environment(\.agentDesignReduceMotion) private var reduceMotion
    @ViewState private var selected=0
    @ViewState private var sheetSize=AgentSheetSize.preferred(width:720,height:700)
    @ViewState private var testNote=""
    private var ready:Bool{!draft.name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !draft.stages.isEmpty && draft.stages.allSatisfy{stage in !stage.name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !stage.goal.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && agents.contains{$0.id==stage.agentID}}}
    var body:some View{VStack(spacing:0){AgentEditorHeader(title:"Build a workflow",close:close);Divider();ScrollView{VStack(alignment:.leading,spacing:22){
        AgentRuntimeBanner()
        field("Workflow name",placeholder:"Weekly project review",text:$draft.name)
        Picker("Execution",selection:Binding(get:{draft.execution ?? "Sequential"},set:{draft.execution=$0})){Text("Sequential").tag("Sequential");Text("Dependency graph · isolated branches").tag("Dependency graph")}.wixalFont(size:12)
        field("Goal",placeholder:"Review changes and save an evidence-backed report.",text:$draft.brief)
        VStack(alignment:.leading,spacing:12){HStack{Text("Stages").wixalFont(size:15,weight:.medium);Spacer();Button{withAnimation(reduceMotion ? nil : .easeInOut(duration:0.18)){draft.stages.append(AgentWorkflowStage(name:"New stage",agentID:agents.first?.id ?? ""));selected=draft.stages.count-1}}label:{Label("Add stage",systemImage:"plus")}.buttonStyle(WixalButtonStyle(outlined:true))}
            ForEach(Array(draft.stages.enumerated()),id:\.element.id){index,stage in Button{withAnimation(reduceMotion ? nil : .easeInOut(duration:0.18)){selected=index;testNote=""}}label:{HStack(spacing:12){Text("\(index+1)").wixalFont(size:12,design:.monospaced).frame(width:28,height:28).background(theme.selected,in:Circle());VStack(alignment:.leading,spacing:4){Text(stage.name).wixalFont(size:12,weight:.medium);Text(agents.first(where:{$0.id==stage.agentID})?.name ?? "Choose an agent").wixalFont(size:11).foregroundStyle(theme.muted)};Spacer();if stage.requiresReview{Image(systemName:"hand.raised").foregroundStyle(theme.accent)};Image(systemName:"chevron.right").foregroundStyle(theme.muted)}.padding(12).background(selected==index ? theme.selected : theme.panel,in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(selected==index ? theme.accent.opacity(0.6) : theme.line,lineWidth:1))}.buttonStyle(.plain).accessibilityLabel("Stage \(index+1): \(stage.name)").accessibilityAddTraits(selected==index ? [.isSelected] : [])}
        }
        if draft.stages.indices.contains(selected){stageEditor}
        if !ready{Text(agents.isEmpty ? "Create an agent before assigning workflow stages." : "Give the workflow a name, then add a name, goal and agent to every stage.").wixalFont(size:11).foregroundStyle(theme.muted)}
    }.padding(24)};Divider();HStack{Button("Cancel",action:close);Spacer();Button("Save workflow"){save(draft)}.disabled(!ready).keyboardShortcut(.defaultAction)}.buttonStyle(WixalButtonStyle(outlined:true)).padding(20)}.frame(width:sheetSize.width,height:sheetSize.height).background(theme.background).foregroundStyle(theme.text).onAppear{if draft.stages.isEmpty{draft.stages=[AgentWorkflowStage()]};if draft.stages[0].agentID.isEmpty{draft.stages[0].agentID=agents.first?.id ?? ""}}}
    private var stageEditor:some View{VStack(alignment:.leading,spacing:16){Text("Stage \(selected+1) details").wixalFont(size:16,weight:.medium)
        field("Stage name",placeholder:"Inspect recent changes",text:$draft.stages[selected].name)
        Picker("Agent",selection:$draft.stages[selected].agentID){Text("Choose an agent").tag("");ForEach(agents){agent in Text(agent.name).tag(agent.id)}}.wixalFont(size:12)
        field("Stage goal",placeholder:"Read changed files and identify risks.",text:$draft.stages[selected].goal)
        field("Expected output",placeholder:"Findings with source references",text:$draft.stages[selected].output)
        AgentChecksEditor(checks:Binding(get:{draft.stages[selected].successCriteria ?? []},set:{draft.stages[selected].successCriteria=$0}))
        if draft.execution=="Dependency graph"{
            Picker("Branch scope",selection:Binding(get:{draft.stages[selected].isolation ?? "Read only"},set:{draft.stages[selected].isolation=$0})){Text("Read only").tag("Read only");Text("Changes in an isolated project copy").tag("Isolated changes")}.wixalFont(size:12)
            Text("Dependencies").wixalFont(size:12,weight:.medium)
            ForEach(draft.stages.filter{$0.id != draft.stages[selected].id}){stage in Toggle(stage.name,isOn:Binding(get:{(draft.stages[selected].dependsOn ?? []).contains(stage.id)},set:{enabled in var deps=draft.stages[selected].dependsOn ?? [];deps.removeAll{$0==stage.id};if enabled{deps.append(stage.id)};draft.stages[selected].dependsOn=deps})).wixalFont(size:12)}
            Toggle("Run only when dependency outcomes are verified",isOn:Binding(get:{draft.stages[selected].condition=="dependencies_verified"},set:{draft.stages[selected].condition=$0 ? "dependencies_verified" : "always"})).wixalFont(size:12)
        }
        Toggle("Require review before continuing",isOn:$draft.stages[selected].requiresReview).wixalFont(size:12)
        Picker("If this stage fails",selection:$draft.stages[selected].failurePolicy){Text("Stop and ask").tag("Stop and ask");Text("Retry once, then stop").tag("Retry once, then stop")}.wixalFont(size:12)
        ViewThatFits(in:.horizontal){HStack{stageActions};VStack(alignment:.leading,spacing:8){stageActions}}
        if !testNote.isEmpty{Text(testNote).wixalFont(size:11).foregroundStyle(theme.muted)}
    }.wixalCard().id(draft.stages[selected].id)}
    private var stageActions:some View{Group{Button("Move up"){draft.stages.swapAt(selected,selected-1);selected-=1}.disabled(selected==0);Button("Move down"){draft.stages.swapAt(selected,selected+1);selected+=1}.disabled(selected==draft.stages.count-1);Button("Stage summary"){testNote="This stage uses its assigned agent and should return \(draft.stages[selected].output.lowercased())."};Button("Remove stage",role:.destructive){draft.stages.remove(at:selected);selected=min(selected,draft.stages.count-1)}.disabled(draft.stages.count<=1)}.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11)}
    private func field(_ title:String,placeholder:String,text:Binding<String>)->some View{VStack(alignment:.leading,spacing:7){Text(title).wixalFont(size:12,weight:.medium);TextField(placeholder,text:text).wixalField().accessibilityLabel(title)}}
}

struct AgentScheduleEditor:View{
    let agents:[AgentProfileDraft]
    let workflows:[AgentWorkflowDraft]
    @ViewState var draft:AgentScheduleDraft
    let save:(AgentScheduleDraft)->Void
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var hour=Date()
    @ViewState private var sheetSize=AgentSheetSize.preferred(width:650,height:650)
    private var ready:Bool{!draft.name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !draft.prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && agents.contains{$0.id==draft.agentID}}
    var body:some View{VStack(spacing:0){AgentEditorHeader(title:"Schedule recurring work",close:close);Divider();ScrollView{VStack(alignment:.leading,spacing:20){
        AgentRuntimeBanner()
        field("Schedule name",placeholder:"Morning project review",text:$draft.name)
        Picker("Work",selection:Binding(get:{draft.workflowID ?? ""},set:{identifier in draft.workflowID=identifier.isEmpty ? nil : identifier;if let flow=workflows.first(where:{$0.id==identifier}),let stage=flow.stages.first{draft.agentID=stage.agentID;draft.prompt=flow.brief}})){Text("Agent task").tag("");ForEach(workflows){flow in Text(flow.name).tag(flow.id)}}.wixalFont(size:12)
        Picker("Agent",selection:$draft.agentID){Text("Choose an agent").tag("");ForEach(agents){agent in Text(agent.name).tag(agent.id)}}.wixalFont(size:12)
        VStack(alignment:.leading,spacing:7){Text("Task brief").wixalFont(size:12,weight:.medium);TextEditor(text:$draft.prompt).scrollContentBackground(.hidden).wixalFont(size:12).padding(8).frame(height:100).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel("Scheduled task brief")}
        Picker("Repeat",selection:$draft.timing){ForEach(["Every weekday","Every day","Every Monday","Every hour"],id:\.self){Text($0)}}.wixalFont(size:12)
        if draft.timing != "Every hour"{DatePicker("Local time",selection:$hour,displayedComponents:.hourAndMinute).wixalFont(size:12)}
        field("Timezone",placeholder:"Australia/Sydney",text:Binding(get:{draft.timezone ?? "Australia/Sydney"},set:{draft.timezone=$0}))
        Picker("After missed runs",selection:$draft.missed){ForEach(["Run once for latest","Skip missed runs"],id:\.self){Text($0)}}.wixalFont(size:12)
        Picker("In-app updates",selection:Binding(get:{draft.notification ?? "Completion, failure or review"},set:{draft.notification=$0})){ForEach(["Completion, failure or review","Only when attention is needed","No notifications"],id:\.self){Text($0)}}.wixalFont(size:12)
        AgentChecksEditor(checks:Binding(get:{draft.successCriteria ?? []},set:{draft.successCriteria=$0}))
        AgentAuthorityEditor(authority:Binding(get:{draft.authority ?? AgentAuthorityDraft()},set:{draft.authority=$0}))
        Toggle("Enable this routine",isOn:$draft.enabled).wixalFont(size:12)
        Text("Each run starts fresh with the agent's saved configuration. Updates appear in Schedules and Tasks. Enable background scheduling to run while Wixal is closed. The Mac must be awake. Actions requiring review pause for you.").wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)
        if agents.isEmpty{Text("Create an agent first to assign recurring work.").wixalFont(size:12).foregroundStyle(theme.muted)}
    }.padding(24)};Divider();HStack{Button("Cancel",action:close);Spacer();Button("Save routine"){let format=DateFormatter();format.dateFormat="HH:mm";draft.time=format.string(from:hour);save(draft)}.disabled(!ready).keyboardShortcut(.defaultAction)}.buttonStyle(WixalButtonStyle(outlined:true)).padding(20)}.frame(width:sheetSize.width,height:sheetSize.height).background(theme.background).foregroundStyle(theme.text).onAppear{let format=DateFormatter();format.dateFormat="HH:mm";if let date=format.date(from:draft.time){hour=date}}}
    private func field(_ title:String,placeholder:String,text:Binding<String>)->some View{VStack(alignment:.leading,spacing:7){Text(title).wixalFont(size:12,weight:.medium);TextField(placeholder,text:text).wixalField().accessibilityLabel(title)}}
}
