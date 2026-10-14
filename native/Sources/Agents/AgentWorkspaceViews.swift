import SwiftUI

struct AgentWorkspaceNavigation:View {
    @Binding var page:String
    let openConversation:()->Void
    let newConversation:()->Void
    @Environment(\.wixalTheme) private var theme
    private let destinations=[("Home","Agents","person.crop.rectangle.stack"),("Skills","Skills","text.book.closed"),("Nodes","Nodes","desktopcomputer"),("Schedules","Schedules","calendar.badge.clock"),("Runs","Runs","list.bullet.rectangle"),("Workflows","Workflows","point.3.connected.trianglepath.dotted"),("Tools","Tools","wrench.and.screwdriver")]
    var body:some View{VStack(alignment:.leading,spacing:5){
        ForEach(destinations,id:\.0){item in
            Button{page=item.0}label:{HStack(spacing:10){Image(systemName:item.2).frame(width:17);Text(item.1);Spacer()}.padding(.horizontal,10).padding(.vertical,9).frame(maxWidth:.infinity,alignment:.leading).background(page==item.0 ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6))}.buttonStyle(.plain).wixalFont(size:12).foregroundStyle(page==item.0 ? theme.accent : theme.text).accessibilityLabel(item.1+" workspace").accessibilityAddTraits(page==item.0 ? [.isSelected] : [])
        }
        Divider().overlay(theme.line).padding(.vertical,10)
        Button("Live conversation",action:openConversation).buttonStyle(WixalButtonStyle())
        Button("New conversation",action:newConversation).buttonStyle(WixalButtonStyle())
    }}
}

/// These pages use the existing engine records and Wixal theme, never a second registry.
struct AgentSkillsWorkspace:View {
    @ObservedObject var engine:EngineClient
    @ObservedObject var design:AgentDesignStore
    @Environment(\.wixalTheme) private var theme
    private var skills:[[String:Any]]{
        let account=engine.state["account"] as? [String:Any] ?? [:]
        let identity=account["profile"] as? [String:Any] ?? [:]
        let owner=account["signedIn"] as? Bool == true ? "account:"+textValue(identity["id"]) : "guest"
        return records(engine.state["skills"]).filter{(textValue($0["owner"]).isEmpty ? "guest" : textValue($0["owner"]))==owner}
    }
    var body:some View{AgentDesignPage(title:"Skills",subtitle:"Reusable procedures, agent assignments and reviewed learning."){
        HStack{Text("\(skills.count) imported procedures").wixalFont(size:12).foregroundStyle(theme.muted);Spacer();Button("Import skill"){engine.importSkill()}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!engine.connected || engine.busy)}
        if skills.isEmpty{Text("Import a Markdown procedure or SKILL.md with its supporting resources. Then select it in an agent’s Memory & skills setup.").wixalFont(size:12).foregroundStyle(theme.muted)}
        ForEach(Array(skills.enumerated()),id:\.offset){_,skill in
            let name=textValue(skill["name"])
            let assigned=design.agents.filter{$0.archived != true && $0.skills.contains(name)}
            VStack(alignment:.leading,spacing:10){
                Text(name).wixalFont(size:15,weight:.medium)
                if !textValue(skill["description"]).isEmpty{Text(textValue(skill["description"])).wixalFont(size:12).foregroundStyle(theme.muted)}
                AgentMetadata(title:"Used by",value:assigned.isEmpty ? "No agent assigned" : assigned.map(\.name).joined(separator:", "))
                Menu("Assign to agent"){
                    ForEach(design.agents.filter{$0.archived != true}){agent in
                        Button((agent.skills.contains(name) ? "Remove from " : "Add to ")+agent.name){var updated=agent;updated.skills.removeAll{$0==name};if !agent.skills.contains(name){updated.skills.append(name)};design.save(updated)}
                    }
                }.disabled(!engine.connected || design.saving || design.agents.filter{$0.archived != true}.isEmpty)
                DisclosureGroup("Procedure and resources"){
                    Text(textValue(skill["content"])).wixalFont(size:12).textSelection(.enabled)
                    Text("Resources are read as text. Loading a skill does not run its scripts.").wixalFont(size:11).foregroundStyle(theme.muted)
                    ForEach(Array((skill["resources"] as? [String:Any] ?? [:]).keys.sorted()),id:\.self){resource in Text(resource).wixalFont(size:11,design:.monospaced)}
                }
                if !records(skill["versions"]).isEmpty{
                    DisclosureGroup("Version history"){Text(pretty(skill["versions"] ?? [])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)}
                    Button("Restore previous version"){engine.action("skill-rollback",["id":textValue(skill["id"])])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy)
                }
            }.wixalCard()
        }
        WixalSection(title:"Procedure learning",detail:"Evaluate changes against a baseline before promoting them."){AgentSkillLearningView(engine:engine,design:design)}
    }}
}

struct AgentNodesWorkspace:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState private var inspecting=false
    @ViewState private var error=""
    private var worker:[String:Any]{engine.state["securityWorkerReadiness"] as? [String:Any] ?? [:]}
    var body:some View{AgentDesignPage(title:"Nodes",subtitle:"Execution environments and their supported capabilities."){
        WixalSection(title:"This Mac",detail:"Native local execution"){
            AgentMetadata(title:"Engine",value:engine.connected ? "Connected" : "Disconnected")
            AgentMetadata(title:"Model",value:textValue(engine.state["model"]).isEmpty ? "Not selected" : textValue(engine.state["model"]))
            AgentMetadata(title:"Model runtime",value:engine.modelReady ? "Ready for selected model" : "Not ready for selected model")
            AgentMetadata(title:"Capabilities",value:"Project files, tracked commands, local tools")
            Text("Actions use this Mac’s permissions and the task’s review policy. Isolated workflow commands use their existing sandbox.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
        WixalSection(title:"Linux worker",detail:"Optional local Linux environment"){
            AgentMetadata(title:"Last inspection",value:worker.isEmpty ? "Not inspected" : worker["available"] as? Bool == true ? "Available at last inspection" : "Unavailable at last inspection")
            AgentMetadata(title:"Capabilities",value:"Bounded ports and services scans")
            if !textValue(worker["imageId"]).isEmpty{Text(textValue(worker["imageId"])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}
            if !textValue(worker["error"]).isEmpty{Text(textValue(worker["error"])).wixalFont(size:11).foregroundStyle(theme.muted)}
            Button(inspecting ? "Inspecting…" : "Inspect Linux worker"){
                Task{inspecting=true;defer{inspecting=false};do{_ = try await engine.call("security-engagement-worker-inspect",[:]);error=""}catch{self.error=error.localizedDescription}}
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(inspecting || !engine.connected || engine.busy)
            Text("Inspection checks the configured local runtime and worker image. Run scoped operations and configure the runtime in Cybersecurity → Engagements.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
        if !error.isEmpty{Text(error).wixalFont(size:12).foregroundStyle(.orange)}
    }}
}

struct AgentReadinessView:View {
    @ObservedObject var engine:EngineClient
    let agent:AgentProfileDraft
    @ViewState private var report:[String:Any]=[:]
    @ViewState private var inspecting=false
    @ViewState private var error=""
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:9){
        Button(inspecting ? "Checking setup…" : "Check setup"){
            Task{inspecting=true;defer{inspecting=false};do{report=try await engine.call("agent-readiness",["id":agent.id]) as? [String:Any] ?? [:];error=""}catch{self.error=error.localizedDescription}}
        }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(inspecting || !engine.connected || engine.busy)
        ForEach(Array(records(report["checks"]).enumerated()),id:\.offset){_,check in
            VStack(alignment:.leading,spacing:3){HStack{Text(textValue(check["name"]));Spacer();Text(textValue(check["status"]).capitalized).foregroundStyle(theme.muted)};Text(textValue(check["detail"])).foregroundStyle(theme.muted)}.wixalFont(size:11)
        }
        if !error.isEmpty{Text(error).wixalFont(size:11).foregroundStyle(.orange)}
    }.onChange(of:agent){_,_ in report=[:]}}
}
