import SwiftUI
import AppKit

struct AgentBuilderView:View {
    @ObservedObject var engine:EngineClient
    @ViewState var draft:AgentProfileDraft
    let save:(AgentProfileDraft)->Void
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @ViewState private var step=0
    @ViewState private var sheetSize=AgentSheetSize.preferred(width:700,height:640)
    private let steps=["Purpose","Model & tools","Memory & skills","Review"]
    private var motion:Animation?{systemReduceMotion || (engine.state["ui"] as? [String:Any])?["reduceMotion"] as? Bool == true ? nil : .easeInOut(duration:0.2)}
    private var ready:Bool{!draft.name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !draft.purpose.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !draft.instructions.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && !draft.model.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty}
    var body:some View{
        VStack(spacing:0){AgentEditorHeader(title:"Build an agent",close:close)
            HStack(spacing:8){ForEach(steps.indices,id:\.self){i in Button{withAnimation(motion){step=i}}label:{HStack(spacing:7){Text("\(i+1)").frame(width:21,height:21).background(step==i ? theme.accent : theme.selected,in:Circle()).foregroundStyle(step==i ? theme.background : theme.muted);Text(steps[i]).wixalFont(size:11)}.frame(maxWidth:.infinity)}.buttonStyle(.plain).accessibilityLabel("Step \(i+1): \(steps[i])").accessibilityAddTraits(step==i ? [.isSelected] : [])}}.padding(.horizontal,22).padding(.bottom,18)
            Divider()
            ScrollView{VStack(alignment:.leading,spacing:22){
                switch step{case 0:purpose;case 1:access;case 2:memory;default:review}
            }.padding(24).frame(maxWidth:.infinity,alignment:.leading)}.animation(motion,value:step)
            Divider()
            HStack{Button("Cancel",action:close).buttonStyle(WixalButtonStyle());Spacer();if step>0{Button("Back"){withAnimation(motion){step-=1}}.buttonStyle(WixalButtonStyle())};if step<3{Button("Continue"){withAnimation(motion){step+=1}}.buttonStyle(WixalButtonStyle(outlined:true)).keyboardShortcut(.defaultAction)}else{Button("Save agent"){draft.name=draft.name.trimmingCharacters(in:.whitespacesAndNewlines);save(draft)}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!ready).keyboardShortcut(.defaultAction)}}.padding(20)
        }.frame(width:sheetSize.width,height:sheetSize.height).background(theme.background).foregroundStyle(theme.text)
    }
    private var purpose:some View{
        VStack(alignment:.leading,spacing:18){Text("What should this agent do?").wixalFont(size:23,weight:.medium);Text("Its instructions and defaults will be reusable across tasks.").wixalFont(size:12).foregroundStyle(theme.muted)
            field("Name",placeholder:"Project reviewer",text:$draft.name)
            field("Purpose",placeholder:"Inspect code and return findings.",text:$draft.purpose)
            VStack(alignment:.leading,spacing:7){Text("Instructions").wixalFont(size:12,weight:.medium);TextEditor(text:$draft.instructions).wixalFont(size:12).scrollContentBackground(.hidden).padding(8).frame(minHeight:130).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel("Agent instructions")}
            Picker("Identity icon",selection:$draft.icon){Text("Reviewer").tag("doc.text.magnifyingglass");Text("Code").tag("chevron.left.forwardslash.chevron.right");Text("Research").tag("book.closed");Text("General").tag("sparkle.magnifyingglass")}.wixalFont(size:12)
        }
    }
    private var access:some View{VStack(alignment:.leading,spacing:18){Text("Choose its model. Tools follow the task.").wixalFont(size:23,weight:.medium)
        field("Default model",placeholder:"Choose or enter an installed model",text:$draft.model)
        let available=engine.models.compactMap{$0["name"] as? String}
        if !available.isEmpty{Menu("Choose an installed model"){ForEach(available,id:\.self){name in Button(name){draft.model=name}}}.wixalFont(size:12)}
        Text("The engine checks model tool capabilities and availability before a run.").wixalFont(size:11).foregroundStyle(theme.muted)
        Picker("Project scope",selection:$draft.projectScope){Text("Choose a project per run").tag("Choose per run");Text("Current project only").tag("Current project only")}.wixalFont(size:12)
        Picker("Action policy",selection:$draft.reviewPolicy){ForEach(["Review actions","Read only","Pre-approved actions"],id:\.self){Text($0)}}.wixalFont(size:12)
        WixalSection(title:"Automatic tool selection",detail:"The model sees tool descriptions and inputs, decides what it needs, and chooses tools as it works."){
            Label("Model chooses tools",systemImage:"sparkles").wixalFont(size:13)
            Text("You describe the job and its boundaries. Available project, command, web, memory and connected tools are discovered from the workspace.").wixalFont(size:12).foregroundStyle(theme.muted)
            Text("Tool calls and their results appear in the run activity so you can inspect what happened.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
        AgentChecksEditor(checks:Binding(get:{draft.successCriteria ?? []},set:{draft.successCriteria=$0}))
        AgentAuthorityEditor(authority:Binding(get:{draft.authority ?? AgentAuthorityDraft()},set:{draft.authority=$0}))
        Toggle("Restrict network actions to authorised targets",isOn:Binding(get:{draft.restrictTargets ?? false},set:{draft.restrictTargets=$0})).wixalFont(size:12)
        Stepper("Maximum model turns: \(draft.maxTurns ?? 20)",value:Binding(get:{draft.maxTurns ?? 20},set:{draft.maxTurns=$0}),in:1...100).wixalFont(size:12)
        Stepper("Maximum tool calls: \(draft.maxCalls ?? 100)",value:Binding(get:{draft.maxCalls ?? 100},set:{draft.maxCalls=$0}),in:1...500).wixalFont(size:12)
        Stepper("Time budget: \(draft.timeoutSeconds ?? 600) seconds",value:Binding(get:{draft.timeoutSeconds ?? 600},set:{draft.timeoutSeconds=$0}),in:10...1800,step:10).wixalFont(size:12)
        if draft.reviewPolicy=="Read only"{Text("This agent's task boundary prevents changes. The model still chooses the tools needed to inspect and report.").wixalFont(size:11).foregroundStyle(theme.muted)}
    }}
    private var memory:some View{VStack(alignment:.leading,spacing:18){Text("Choose what carries forward.").wixalFont(size:23,weight:.medium)
        Picker("Memory scope",selection:$draft.memoryScope){ForEach(["Project only","Project + global preferences","Global preferences only","Memory off"],id:\.self){Text($0)}}.wixalFont(size:12)
        Toggle("Recall relevant earlier conversations",isOn:$draft.recallHistory).wixalFont(size:12).disabled(draft.memoryScope=="Memory off")
        Toggle("Suggest durable notes for review",isOn:$draft.suggestMemory).wixalFont(size:12).disabled(draft.memoryScope=="Memory off")
        Text("Project notes stay with the project selected for the run. Suggestions require review before saving.").wixalFont(size:11).foregroundStyle(theme.muted)
        VStack(alignment:.leading,spacing:7){Text("Private agent notes · maximum 2,000 characters").wixalFont(size:12);TextEditor(text:Binding(get:{draft.privateNotes ?? ""},set:{draft.privateNotes=String($0.prefix(2000))})).scrollContentBackground(.hidden).wixalFont(size:12).padding(8).frame(height:90).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel("Private agent notes");Text("These notes belong to this saved agent. They are excluded when memory is off.").wixalFont(size:11).foregroundStyle(theme.muted)}
        WixalSection(title:"Skills",detail:"Select imported instructions this agent can use. Skills do not grant tool permissions."){
            if records(engine.state["skills"]).isEmpty{Text("No imported skills yet. You can still build the agent.").foregroundStyle(theme.muted).wixalFont(size:12)}
            ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset){_,skill in let name=textValue(skill["name"]);Toggle(name,isOn:Binding(get:{draft.skills.contains(name)},set:{enabled in draft.skills.removeAll{$0==name};if enabled{draft.skills.append(name)}})).wixalFont(size:12)}
        }
    }}
    private var review:some View{VStack(alignment:.leading,spacing:18){HStack(spacing:14){AgentAvatar(icon:draft.icon,size:48);VStack(alignment:.leading,spacing:5){Text(draft.name.isEmpty ? "Unnamed agent" : draft.name).wixalFont(size:23,weight:.medium);Text(draft.purpose).wixalFont(size:12).foregroundStyle(theme.muted)}}
        VStack(alignment:.leading,spacing:0){AgentMetadata(title:"Model",value:draft.model.isEmpty ? "Required" : draft.model);AgentMetadata(title:"Project",value:draft.projectScope);AgentMetadata(title:"Actions",value:draft.reviewPolicy);AgentMetadata(title:"Tool selection",value:"Automatic · Chosen by the model");AgentMetadata(title:"Memory",value:draft.memoryScope);AgentMetadata(title:"Skills",value:draft.skills.isEmpty ? "None selected" : draft.skills.joined(separator:", "))}.wixalCard()
        DisclosureGroup("Review instructions"){Text(draft.instructions).wixalFont(size:12).textSelection(.enabled).padding(.top,8)}
        if !ready{Text("Add a name, purpose, instructions and model before saving.").wixalFont(size:12).foregroundStyle(.orange)}
        AgentRuntimeBanner()
    }}
    private func field(_ label:String,placeholder:String,text:Binding<String>)->some View{VStack(alignment:.leading,spacing:7){Text(label).wixalFont(size:12,weight:.medium);TextField(placeholder,text:text).wixalField().accessibilityLabel(label)}}
}

struct AgentProfileDetail:View{
    let agent:AgentProfileDraft
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    let edit:()->Void
    let giveTask:()->Void
    let schedule:()->Void
    let openRun:(String)->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var tab="Work"
    @Environment(\.agentDesignReduceMotion) private var reduceMotion
    var body:some View{VStack(alignment:.leading,spacing:22){
        ViewThatFits(in:.horizontal){HStack{identity;Spacer();actions};VStack(alignment:.leading,spacing:16){identity;actions}}
        ViewThatFits(in:.horizontal){HStack(spacing:4){tabs};VStack(alignment:.leading,spacing:4){tabs}}
        Group{switch tab{
        case "Configuration":configuration
        case "Skills & tools":VStack(alignment:.leading,spacing:16){AgentToolCatalog(engine:engine);WixalSection(title:"Selected skills"){Text(agent.skills.isEmpty ? "No skills selected." : agent.skills.joined(separator:", ")).wixalFont(size:12)}}
        case "Memory":VStack(alignment:.leading,spacing:16){AgentMetadata(title:"Scope",value:agent.memoryScope);AgentMetadata(title:"History recall",value:agent.recallHistory ? "Relevant conversations" : "Off");AgentMetadata(title:"Suggestions",value:agent.suggestMemory ? "Review before saving" : "Off");Text("The engine applies this agent's scope during each run. Project notes are shared within their project.").wixalFont(size:12).foregroundStyle(theme.muted)}
        case "Schedules":VStack(alignment:.leading,spacing:16){let schedules=design.schedules.filter{$0.agentID==agent.id};if schedules.isEmpty{Text("No schedule drafts for this agent.").foregroundStyle(theme.muted)};ForEach(schedules){item in HStack{Text(item.name);Spacer();Text(item.timing+" · "+item.time).foregroundStyle(theme.muted)}.wixalCard()};Button("Create schedule",action:schedule).buttonStyle(WixalButtonStyle(outlined:true))}
        default:work
        }}.frame(maxWidth:.infinity,alignment:.leading).animation(reduceMotion ? nil : .easeInOut(duration:0.18),value:tab)
    }}
    private var identity:some View{HStack(spacing:14){AgentAvatar(icon:agent.icon,size:48);VStack(alignment:.leading,spacing:6){Text(agent.name).wixalFont(size:23,weight:.medium);Text(agent.purpose).wixalFont(size:12).foregroundStyle(theme.muted)}}}
    private var actions:some View{HStack{Button("Edit agent",action:edit);Button("Give task",action:giveTask)}.buttonStyle(WixalButtonStyle(outlined:true))}
    private var tabs:some View{ForEach(["Work","Configuration","Skills & tools","Memory","Schedules"],id:\.self){item in Button(item){tab=item}.buttonStyle(WixalButtonStyle()).background(tab==item ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)).accessibilityAddTraits(tab==item ? [.isSelected] : [])}}
    private var configuration:some View{VStack(alignment:.leading,spacing:14){AgentMetadata(title:"Model",value:agent.model);AgentMetadata(title:"Project",value:agent.projectScope);AgentMetadata(title:"Actions",value:agent.reviewPolicy);WixalSection(title:"Instructions"){Text(agent.instructions).wixalFont(size:12).textSelection(.enabled).lineSpacing(4)}}.wixalCard()}
    private var work:some View{VStack(alignment:.leading,spacing:18){
        let tasks=records(engine.state["tasks"]).filter{textValue($0["agentId"])==agent.id}
        if tasks.isEmpty{AgentEmptyState(icon:"play.rectangle",title:"Ready for its first task.",detail:"Give this agent a task. It will choose tools and retain results and evidence.",action:"Give a task",perform:giveTask)}
        ForEach(Array(tasks.reversed().enumerated()),id:\.offset){_,run in Button{openRun(textValue(run["id"]))}label:{HStack{Text(textValue(run["prompt"])).lineLimit(2);Spacer();Text(agentOutcomeLabel(run))}.wixalCard()}.buttonStyle(.plain)}
    }}
}
