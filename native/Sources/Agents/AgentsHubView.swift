import SwiftUI

struct AgentsHubView:View {
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    @Binding var page:String
    let openModels:()->Void
    let openFiles:()->Void
    let newLiveTask:()->Void
    @Environment(\.wixalTheme) private var theme
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @ViewState private var selectedAgent:String?
    @ViewState private var selectedRun:String?
    @ViewState private var editor:AgentProfileDraft?
    @ViewState private var workflowEditor:AgentWorkflowDraft?
    @ViewState private var scheduleEditor:AgentScheduleDraft?
    @ViewState private var taskAgent:AgentProfileDraft?
    @ViewState private var query=""
    @ViewState private var showArchived=false
    private let pages=["Home","Workflows","Runs","Schedules","Tools"]
    private var motion:Animation?{systemReduceMotion || (engine.state["ui"] as? [String:Any])?["reduceMotion"] as? Bool == true ? nil : .easeInOut(duration:0.2)}
    var body:some View{
        VStack(spacing:0){
            toolbar
            if !design.error.isEmpty { Text(design.error).wixalFont(size:11).foregroundStyle(.orange).padding(12).frame(maxWidth:.infinity,alignment:.leading) }
            Rectangle().fill(theme.line).frame(height:1)
            Group{
                switch page {
                case "Conversation":ChatView(engine:engine,openModels:openModels,openFiles:openFiles,openTools:{page="Tools"},agentMode:true)
                case "Live tools":capabilities
                case "Task inbox":TasksView(engine:engine,openConversation:{page="Conversation"})
                case "Tools":capabilities
                case "Workflows":workflows
                case "Runs":runs
                case "Schedules":schedules
                default:home
                }
            }.id(page).transition(motion == nil ? .identity : .opacity).frame(maxWidth:.infinity,maxHeight:.infinity).animation(motion,value:page)
        }
        .foregroundStyle(theme.text)
        .task{design.bind(engine)}
        .onChange(of:engine.connected){_,connected in if connected{design.bind(engine)}}
        .environment(\.agentDesignReduceMotion,motion == nil)
        .sheet(item:$editor){draft in editorContent { AgentBuilderView(engine:engine,draft:draft,save:{value in design.save(value,completion:{success in if success{selectedAgent=value.id;editor=nil}})},close:{editor=nil}) }.environment(\.wixalTheme,theme).environment(\.agentDesignReduceMotion,motion == nil)}
        .sheet(item:$workflowEditor){draft in editorContent { AgentWorkflowEditor(agents:design.agents,draft:draft,save:{value in design.save(value,completion:{success in if success{workflowEditor=nil}})},close:{workflowEditor=nil}) }.environment(\.wixalTheme,theme).environment(\.agentDesignReduceMotion,motion == nil)}
        .sheet(item:$scheduleEditor){draft in editorContent { AgentScheduleEditor(agents:design.agents,workflows:design.workflows,draft:draft,save:{value in design.save(value,completion:{success in if success{scheduleEditor=nil}})},close:{scheduleEditor=nil}) }.environment(\.wixalTheme,theme).environment(\.agentDesignReduceMotion,motion == nil)}
        .sheet(item:$taskAgent){agent in editorContent { AgentTaskSheet(agent:agent,project:engine.project.map{textValue($0["name"])} ?? "Personal workspace",canStart:engine.connected && !engine.busy,start:{title,checks in selectedRun=nil;design.run(agent,title,checks);taskAgent=nil;page="Runs"},queue:{title,checks in design.enqueue(agent,title,checks,completion:{success in if success{taskAgent=nil;page="Runs"}})},close:{taskAgent=nil}) }.environment(\.wixalTheme,theme).environment(\.agentDesignReduceMotion,motion == nil)}
    }
    private func editorContent<Content:View>(@ViewBuilder content:()->Content)->some View{
        VStack(spacing:0){
            if !design.error.isEmpty{Text(design.error).wixalFont(size:12).foregroundStyle(.orange).textSelection(.enabled).padding(14).frame(maxWidth:.infinity,alignment:.leading)}
            if design.saving{ProgressView("Saving…").padding(8)}
            content().disabled(design.saving)
        }.interactiveDismissDisabled(design.saving).onAppear{design.error=""}
    }
    private var toolbar:some View{
        ViewThatFits(in:.horizontal){
            HStack(spacing:5){ForEach(pages,id:\.self){item in pageButton(item)};Spacer(minLength:10);liveMenu}
            HStack{Menu{ForEach(pages,id:\.self){item in Button(item=="Home" ? "Agents" : item){navigate(item)}}}label:{Label(page=="Home" ? "Agents" : page,systemImage:"diamond")};Spacer();liveMenu}
        }.wixalFont(size:11).padding(.horizontal,18).padding(.vertical,12)
    }
    private func pageButton(_ item:String)->some View{Button{navigate(item)}label:{Text(item=="Home" ? "Agents" : item).padding(.horizontal,4)}.buttonStyle(WixalButtonStyle()).background(page==item ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)).foregroundStyle(page==item ? theme.accent : theme.muted).accessibilityAddTraits(page==item ? [.isSelected] : [])}
    private var liveMenu:some View{Menu{Button("Open live conversation"){navigate("Conversation")};Button("New live task",action:newLiveTask).disabled(engine.busy);Button("Existing tasks & schedules"){navigate("Task inbox")};Button("Inspect discovered tools"){navigate("Tools")}}label:{Label("Live workspace",systemImage:"arrow.up.right.square")}.menuStyle(.borderlessButton).fixedSize().help("Open a conversation, inspect tools or view the task inbox")}
    private func navigate(_ value:String){withAnimation(motion){page=value};design.notice=""}
    private var home:some View{
        AgentDesignPage(title:selectedAgent == nil ? "Your agents" : "Agent workspace",subtitle:"Save a way of working, give it a task, and inspect its progress."){
            AgentRuntimeBanner()
            if let id=selectedAgent,let agent=design.agents.first(where:{$0.id==id}){
                Button{withAnimation(motion){selectedAgent=nil}}label:{Label("All agents",systemImage:"arrow.left")}.buttonStyle(WixalButtonStyle())
                AgentProfileDetail(agent:agent,engine:engine,design:design,edit:{editor=agent},giveTask:{taskAgent=agent},schedule:{scheduleEditor=AgentScheduleDraft(name:agent.name+" schedule",agentID:agent.id)},openRun:{selectedRun=$0;page="Runs"})
            }else{
                if design.agents.isEmpty {
                    AgentEmptyState(icon:"diamond",title:"Give an agent a way to work.",detail:"Start with a template or build your own. Choose its instructions, model and memory before saving a reusable agent.",action:"Create an agent"){editor=AgentProfileDraft(model:textValue(engine.state["model"]))}
                    WixalSection(title:"Start with a template",detail:"Templates provide editable instructions and task boundaries. The model chooses its tools."){
                        LazyVGrid(columns:[GridItem(.adaptive(minimum:190),spacing:14)],spacing:14){ForEach(["Project reviewer","Code assistant","Researcher","Security analyst"],id:\.self){name in templateCard(name)}}
                    }
                    Button("Prefer a one-off task? Open the live conversation"){page="Conversation"}.buttonStyle(WixalButtonStyle())
                }else{
                    HStack{TextField("Find an agent",text:$query).wixalField().frame(maxWidth:260);Toggle("Archived",isOn:$showArchived).toggleStyle(.checkbox).wixalFont(size:11);Spacer();Button("Create agent"){editor=AgentProfileDraft(model:textValue(engine.state["model"]))}.buttonStyle(WixalButtonStyle(outlined:true))}
                    let filtered=design.agents.filter{($0.archived == true)==showArchived && (query.isEmpty || $0.name.localizedCaseInsensitiveContains(query) || $0.purpose.localizedCaseInsensitiveContains(query))}
                    if filtered.isEmpty{Text("No agents match this search.").foregroundStyle(theme.muted)}
                    LazyVGrid(columns:[GridItem(.adaptive(minimum:215),spacing:14)],spacing:14){ForEach(filtered){agent in agentCard(agent)}}

                }
            }
            if !design.notice.isEmpty{Text(design.notice).wixalFont(size:11).foregroundStyle(theme.muted).accessibilityLabel(design.notice)}
        }
    }
    private func templateCard(_ name:String)->some View{let draft=AgentProfileDraft.template(name,model:textValue(engine.state["model"]));return Button{editor=draft}label:{VStack(alignment:.leading,spacing:13){AgentAvatar(icon:draft.icon);Text(name).wixalFont(size:14,weight:.medium);Text(draft.purpose).wixalFont(size:11).foregroundStyle(theme.muted).fixedSize(horizontal:false,vertical:true);Label("Use template",systemImage:"arrow.up.right").wixalFont(size:11).foregroundStyle(theme.accent)}.wixalCard()}.buttonStyle(AgentTileButtonStyle(reducedMotion:motion == nil))}
    private func agentCard(_ agent:AgentProfileDraft)->some View{Button{withAnimation(motion){selectedAgent=agent.id}}label:{VStack(alignment:.leading,spacing:12){HStack{AgentAvatar(icon:agent.icon);Spacer();Text("Agent").wixalFont(size:10).foregroundStyle(theme.muted)};Text(agent.name).wixalFont(size:16,weight:.medium);Text(agent.purpose).wixalFont(size:11).foregroundStyle(theme.muted).lineLimit(3);Divider();Text(agent.model.isEmpty ? "Model not selected" : agent.model).wixalFont(size:11,design:.monospaced);Text(agent.reviewPolicy).wixalFont(size:11).foregroundStyle(theme.muted)}.wixalCard()}.buttonStyle(AgentTileButtonStyle(reducedMotion:motion == nil)).contextMenu{Button("Edit"){editor=agent};Button("Duplicate agent"){design.duplicate(agent)};Button("Give task"){taskAgent=agent};Button(agent.archived == true ? "Restore agent" : "Archive agent"){design.archive(agent.id,agent.archived != true)}}}
    private var workflows:some View{AgentDesignPage(title:"Workflows",subtitle:"Define repeatable stages, review points and expected results."){
        AgentRuntimeBanner()
        Button("Add starter agents & workflows"){engine.action("agent-starter-pack",["model":textValue(engine.state["model"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy || !engine.connected)
        if design.workflows.isEmpty{AgentEmptyState(icon:"point.3.connected.trianglepath.dotted",title:"Make repeatable work explicit.",detail:"Build a sequence of stages. Each stage names its agent, goal, output and what to do if it fails.",action:"Create workflow"){workflowEditor=AgentWorkflowDraft()}}
        else{HStack{Spacer();Button("Create workflow"){workflowEditor=AgentWorkflowDraft()}.buttonStyle(WixalButtonStyle(outlined:true))};ForEach(design.workflows){flow in VStack(alignment:.leading,spacing:12){HStack{Text(flow.name).wixalFont(size:16,weight:.medium);Spacer();Text("\(flow.stages.count) stages").foregroundStyle(theme.muted)};Text(flow.brief).foregroundStyle(theme.muted);ForEach(Array(flow.stages.enumerated()),id:\.element.id){i,stage in Label("\(i+1). \(stage.name)",systemImage:stage.requiresReview ? "hand.raised" : "circle").wixalFont(size:11)};HStack{Button("Edit stages"){workflowEditor=flow};Button("Run workflow"){selectedRun=nil;design.runWorkflow(flow);page="Runs"}.disabled(engine.busy || !engine.connected)}.buttonStyle(WixalButtonStyle(outlined:true))}.wixalCard()}}
    }}
    private var runs:some View{AgentDesignPage(title:"Runs",subtitle:"Actual engine runs, tool evidence and workflow results."){
        let jobs=records(engine.state["agentJobs"]).filter{row in design.agents.contains(where:{$0.id==textValue(row["agentId"])})}
        if !jobs.isEmpty{WixalSection(title:"Queued work"){ForEach(Array(jobs.reversed().enumerated()),id:\.offset){_,job in HStack{VStack(alignment:.leading){Text(textValue(job["prompt"])).lineLimit(2);Text(textValue(job["status"])).wixalFont(size:11).foregroundStyle(theme.muted)};Spacer();if textValue(job["status"])=="queued"{Button("Cancel queued task"){engine.action("agent-job-cancel",["id":textValue(job["id"])])}}}.wixalCard()}}}
        let tasks=records(engine.state["tasks"]).filter{row in design.agents.contains(where:{$0.id==textValue(row["agentId"])})}
        let flows=records(engine.state["workflowRuns"]).filter{row in design.workflows.contains(where:{$0.id==textValue(row["workflowId"])})}
        let selection=selectedRun ?? design.liveSelection
        if let run=tasks.first(where:{textValue($0["id"])==selection}){
            Button("All runs"){selectedRun=nil;design.liveSelection=nil}.buttonStyle(WixalButtonStyle())
            AgentLiveRunView(engine:engine,run:run,workflow:false).id(textValue(run["id"]))
        }else if let run=flows.first(where:{textValue($0["id"])==selection}){
            Button("All runs"){selectedRun=nil;design.liveSelection=nil}.buttonStyle(WixalButtonStyle())
            AgentLiveRunView(engine:engine,run:run,workflow:true).id(textValue(run["id"]))
        }else{
            if tasks.isEmpty && flows.isEmpty{Text("No runs yet. Give a saved agent a task or start a workflow.").foregroundStyle(theme.muted)}
            ForEach(Array(flows.reversed().enumerated()),id:\.offset){_,run in Button{selectedRun=textValue(run["id"])}label:{HStack{Text(textValue((run["definition"] as? [String:Any])?["name"]));Spacer();Text(agentOutcomeLabel(run))}.wixalCard()}.buttonStyle(.plain)}
            ForEach(Array(tasks.reversed().enumerated()),id:\.offset){_,run in Button{selectedRun=textValue(run["id"])}label:{HStack{Text(textValue(run["prompt"])).lineLimit(2);Spacer();Text(agentOutcomeLabel(run))}.wixalCard()}.buttonStyle(.plain)}
        }
    }}
    private var schedules:some View{AgentDesignPage(title:"Schedules",subtitle:"Choose recurring work, its timing and what happens after a missed run."){
        AgentRuntimeBanner()
        Toggle("Run schedules while Wixal is closed",isOn:Binding(get:{(engine.state["backgroundScheduler"] as? [String:Any])?["enabled"] as? Bool ?? false},set:{engine.action("background-settings",["enabled":$0])})).disabled(engine.busy || !engine.connected)
        let updates=records(engine.state["notifications"]).filter{row in design.schedules.contains(where:{$0.id==textValue(row["scheduleId"])})}.suffix(5)
        if !updates.isEmpty{WixalSection(title:"Recent routine updates"){
            ForEach(Array(updates.reversed().enumerated()),id:\.offset){_,row in
                Button{selectedRun=textValue(row["taskId"]);page="Runs"}label:{
                    HStack{Text(textValue(row["name"]));Spacer();Text(textValue(row["status"]).capitalized)}
                }
            }
        }}
        if design.schedules.isEmpty{AgentEmptyState(icon:"calendar.badge.clock",title:"Plan recurring work.",detail:"Choose a saved agent and a task. Each routine starts a fresh run.",action:"Create schedule"){scheduleEditor=AgentScheduleDraft(agentID:design.agents.first?.id ?? "")}}
        else{HStack{Spacer();Button("Create schedule"){scheduleEditor=AgentScheduleDraft(agentID:design.agents.first?.id ?? "")}.buttonStyle(WixalButtonStyle(outlined:true))};ForEach(design.schedules){schedule in VStack(alignment:.leading,spacing:12){HStack{Text(schedule.name).wixalFont(size:16,weight:.medium);Spacer();Text(schedule.enabled ? "Active" : "Paused").wixalFont(size:11).foregroundStyle(theme.muted)};Text(schedule.prompt);AgentMetadata(title:"Agent",value:design.agents.first(where:{$0.id==schedule.agentID})?.name ?? "Agent not selected");AgentMetadata(title:"Timing",value:schedule.timing+" at "+schedule.time+" · "+(schedule.timezone ?? "Australia/Sydney"));routineStatus(schedule.id);AgentMetadata(title:"Missed runs",value:schedule.missed);AgentMetadata(title:"Notifications",value:schedule.notification ?? "Completion, failure or review");HStack{Button("Edit"){scheduleEditor=schedule};Button(schedule.enabled ? "Pause" : "Enable"){design.toggleSchedule(schedule.id)};Button("Run now"){selectedRun=nil;design.runSchedule(schedule.id);page="Runs"}.disabled(engine.busy || !engine.connected)}.buttonStyle(WixalButtonStyle(outlined:true))}.wixalCard()}}
        Button("Open existing live tasks and schedules"){page="Task inbox"}.buttonStyle(WixalButtonStyle())
    }}
    @ViewBuilder private func routineStatus(_ id:String)->some View{
        if let row=records(engine.state["schedules"]).first(where:{textValue($0["id"])==id}){
            AgentMetadata(title:"Next run",value:dateLabel(row["nextRun"]))
            if let last=row["lastRun"] as? [String:Any]{AgentMetadata(title:"Last run",value:textValue(last["status"]).capitalized+" · "+dateLabel(last["started"]))}
        }
    }
    private func dateLabel(_ value:Any?)->String{
        guard let stamp=value as? NSNumber else{return "Not scheduled"}
        return Date(timeIntervalSince1970:stamp.doubleValue/1000).formatted(date:.abbreviated,time:.shortened)
    }
    private var capabilities:some View{AgentDesignPage(title:"Tools & skills",subtitle:"The model discovers available tools and chooses how to use them. Inspect capabilities and usage here."){
        AgentRuntimeBanner()
        AgentToolCatalog(engine:engine)
        AgentSkillLearningView(engine:engine,design:design)
        WixalSection(title:"Imported skills"){
            if records(engine.state["skills"]).isEmpty{Text("No skills imported. Agent drafts can be created without a skill.").wixalFont(size:12).foregroundStyle(theme.muted)}
            ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset){_,skill in VStack(alignment:.leading,spacing:5){Text(textValue(skill["name"]));Text(textValue(skill["description"])).wixalFont(size:11).foregroundStyle(theme.muted);if !records(skill["versions"]).isEmpty{Button("Restore previous version"){engine.action("skill-rollback",["id":textValue(skill["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy);DisclosureGroup("Version history"){Text(pretty(skill["versions"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}}}.wixalCard()}
        }
    }}
}
