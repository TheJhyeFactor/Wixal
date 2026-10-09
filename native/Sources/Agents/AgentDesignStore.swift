import Foundation
import Combine

// Editable profiles register with the engine; the engine owns execution and durable runs.
struct AgentProfileDraft: Identifiable, Codable, Equatable {
    var id = UUID().uuidString
    var name = ""
    var purpose = ""
    var instructions = ""
    var icon = "sparkle.magnifyingglass"
    var model = ""
    var projectScope = "Choose per run"
    var reviewPolicy = "Review actions"
    var memoryScope = "Project only"
    var recallHistory = true
    var suggestMemory = false
    var tools = ["Project files"]
    var skills: [String] = []
    var archived: Bool? = nil
    var successCriteria:[AgentSuccessCheck]?=nil
    var authority:AgentAuthorityDraft?=nil
    var restrictTargets:Bool?=nil
    var privateNotes:String?=nil
    var maxCalls:Int?=nil
    var maxTurns:Int?=nil
    var timeoutSeconds:Int?=nil
    static func template(_ name: String, model: String = "") -> Self {
        switch name {
        case "Code assistant": return Self(name:name,purpose:"Inspect, change and verify project code.",instructions:"Inspect the issue first. Propose focused changes, review edits and commands, verify the result, and report remaining work.",icon:"chevron.left.forwardslash.chevron.right",model:model,tools:["Project files","Commands"])
        case "Researcher": return Self(name:name,purpose:"Read sources and return a grounded brief.",instructions:"Compare relevant sources. Cite evidence, separate observations from inference, and ask before saving durable notes.",icon:"book.closed",model:model,tools:["Web","Memory"])
        case "Project reviewer": return Self(name:name,purpose:"Investigate project files without changing them.",instructions:"Read the selected project, cite file references, and return actionable findings. Do not edit files or run commands.",icon:"doc.text.magnifyingglass",model:model,reviewPolicy:"Read only",tools:["Project files"])
        case "Security analyst": return Self(name:name,purpose:"Assess authorised scope and produce reproducible security evidence.",instructions:"Confirm the authorised target and project first. Inspect sources, choose appropriate security tools, retain raw evidence, verify findings and explain limitations. Do not expand the target scope. Use disposable loopback fixtures for simulations.",icon:"shield.lefthalf.filled",model:model,tools:[])
        default: return Self(model:model)
        }
    }
}
struct AgentWorkflowStage: Identifiable, Codable, Equatable {
    var id = UUID().uuidString
    var name = "Inspect the project"
    var agentID = ""
    var goal = ""
    var output = "Findings with source references"
    var requiresReview = false
    var failurePolicy = "Stop and ask"
    var successCriteria:[AgentSuccessCheck]?=nil
    var dependsOn:[String]?=nil
    var condition:String?=nil
    var isolation:String?=nil
}
struct AgentWorkflowDraft: Identifiable, Codable, Equatable {
    var id = UUID().uuidString
    var name = ""
    var brief = ""
    var stages = [AgentWorkflowStage()]
    var execution:String?=nil
}
struct AgentScheduleDraft: Identifiable, Codable, Equatable {
    var id = UUID().uuidString
    var name = ""
    var agentID = ""
    var prompt = ""
    var timing = "Every weekday"
    var time = "09:00"
    var missed = "Run once for latest"
    var enabled = true
    var notification: String? = "Completion, failure or review"
    var timezone: String? = "Australia/Sydney"
    var workflowID: String? = nil
    var successCriteria:[AgentSuccessCheck]?=nil
    var authority:AgentAuthorityDraft?=nil
}
@MainActor final class AgentDesignStore: ObservableObject {
    private struct Snapshot: Codable {
        var version = 1
        var agents: [AgentProfileDraft] = []
        var workflows: [AgentWorkflowDraft] = []
        var schedules: [AgentScheduleDraft] = []
    }
    @Published var agents: [AgentProfileDraft] = []
    @Published var workflows: [AgentWorkflowDraft] = []
    @Published var schedules: [AgentScheduleDraft] = []
    @Published var liveSelection:String?
    @Published var engineReady=false
    private weak var engine:EngineClient?
    private var subscription:AnyCancellable?
    @Published var notice = ""
    @Published var error = ""
    @Published var saving = false
    private let file: URL
    init() {
        let location = ProcessInfo.processInfo.environment["WIXAL_AGENTS_DESIGN_DATA"] ?? (Bundle.main.object(forInfoDictionaryKey:"WixalPreviewData") as? String).map{$0+"/drafts"}
        let base = location.map { URL(fileURLWithPath:$0) } ?? FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("Wixal Agents Design",isDirectory:true)
        file = base.appendingPathComponent("drafts.json")
        guard FileManager.default.fileExists(atPath:file.path) else{return}
        do {
            let data = try JSONDecoder().decode(Snapshot.self,from:Data(contentsOf:file))
            guard data.version == 1 else {throw CocoaError(.fileReadCorruptFile)}
            agents=data.agents;workflows=data.workflows;schedules=data.schedules
        } catch { self.error="Could not load Agents design drafts. The existing file is preserved. \(error.localizedDescription)" }
    }
    private func persist() {
        do {
            // Do not replace an unreadable file with an empty snapshot.
            guard error.isEmpty, !engineReady else {return}
            try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
            let snapshot=Snapshot(agents:agents,workflows:workflows,schedules:schedules)
            try JSONEncoder().encode(snapshot).write(to:file,options:.atomic)
            notice="Saved locally. Engine registration is reported separately."
        }catch{self.error="Could not save design drafts: \(error.localizedDescription)"}
    }
    private func encoded<T:Encodable>(_ value:T)->[String:Any]{
        guard let data=try? JSONEncoder().encode(value),let object=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else{return [:]};return object
    }
    private func decode<T:Decodable>(_ values:Any?,as type:T.Type)->T?{
        guard let value=values,JSONSerialization.isValidJSONObject(value),let data=try? JSONSerialization.data(withJSONObject:value) else{return nil};return try? JSONDecoder().decode(type,from:data)
    }
    func bind(_ client:EngineClient){
        guard engine == nil,client.connected else{return}
        engine=client;engineReady=true
        let guest=(client.state["account"] as? [String:Any])?["signedIn"] as? Bool != true
        let localAgents=guest ? agents : [],localFlows=guest ? workflows : [],localSchedules=guest ? schedules : []
        subscription=client.$state.sink{[weak self] state in
            guard let self,state["agentProfiles"] != nil else{return}
            let account=state["account"] as? [String:Any] ?? [:],accountProfile=account["profile"] as? [String:Any] ?? [:]
            let owner=account["signedIn"] as? Bool == true ? "account:"+textValue(accountProfile["id"]) : "guest"
            func owned(_ key:String)->[[String:Any]]{records(state[key]).filter{textValue($0["owner"]).isEmpty ? owner=="guest" : textValue($0["owner"])==owner}}
            let profileRows=owned("agentProfiles").map{row -> [String:Any] in var value=self.encoded(AgentProfileDraft());value.merge(row){_,server in server};return value}
            self.agents=self.decode(profileRows,as:[AgentProfileDraft].self) ?? self.agents
            self.workflows=self.decode(owned("agentWorkflows"),as:[AgentWorkflowDraft].self) ?? self.workflows
            let routineRows=owned("schedules").filter{$0["agentID"] != nil}.map{row -> [String:Any] in var next=row;next["missed"]=textValue(row["missedRunPolicy"])=="skip" ? "Skip missed runs" : "Run once for latest";return next}
            self.schedules=self.decode(routineRows,as:[AgentScheduleDraft].self) ?? self.schedules
            if let latest=records(state["tasks"]).last(where:{row in self.agents.contains(where:{$0.id==textValue(row["agentId"])}) && ["running","waiting_review"].contains(textValue(row["status"]))}){self.liveSelection=textValue(latest["id"])}
        }
        // Preserve the user's earlier local drafts. Register only missing records;
        // old preview routines are imported paused, never silently activated.
        Task{
            do{
                for draft in localAgents where !records(client.state["agentProfiles"]).contains(where:{textValue($0["id"])==draft.id}){_ = try await client.call("agent-save",encoded(draft))}
                for flow in localFlows where !records(client.state["agentWorkflows"]).contains(where:{textValue($0["id"])==flow.id}){_ = try await client.call("workflow-save",encoded(flow))}
                for item in localSchedules where !records(client.state["schedules"]).contains(where:{textValue($0["id"])==item.id}){var paused=item;paused.enabled=false;_ = try await client.call("agent-schedule-save",encoded(paused))}
            }catch{self.error="Could not register earlier local drafts: \(error.localizedDescription)"}
        }
    }
    private func send<T:Encodable>(_ method:String,_ value:T,completion:((Bool)->Void)?=nil){
        guard let engine,engine.connected else{error="Connect the engine before saving. Your editor remains open.";completion?(false);return}
        guard !saving else{completion?(false);return}
        saving=true;error=""
        Task{defer{saving=false};do{_ = try await engine.call(method,encoded(value));notice="Saved to the local agent engine.";self.error="";completion?(true)}catch{self.error=error.localizedDescription;completion?(false)}}
    }
    func run(_ agent:AgentProfileDraft,_ prompt:String,_ checks:[AgentSuccessCheck]?=nil){
        guard let engine else{return}
        Task{do{
            _ = try await engine.call("agent-save",encoded(agent))
            engine.operationRunning=true;engine.busy=true
            defer{engine.operationRunning=false;engine.busy=false}
            var params:[String:Any]=["id":agent.id,"prompt":prompt]
            if let project=engine.project{params["projectId"]=project["id"]}
            if let checks,let data=try? JSONEncoder().encode(checks){params["successCriteria"]=try JSONSerialization.jsonObject(with:data)}
            let result=try await engine.call("agent-run",params) as? [String:Any] ?? [:];liveSelection=textValue(result["id"])
        }catch{self.error=error.localizedDescription}}
    }
    func enqueue(_ agent:AgentProfileDraft,_ prompt:String,_ checks:[AgentSuccessCheck]){
        guard let engine else{return}
        Task{do{let data=try JSONEncoder().encode(checks);var params:[String:Any]=["agentID":agent.id,"prompt":prompt,"successCriteria":try JSONSerialization.jsonObject(with:data)];if let project=engine.project{params["projectId"]=project["id"]};_ = try await engine.call("agent-enqueue",params);notice="Task queued. Its agent configuration is retained."}catch{self.error=error.localizedDescription}}
    }
    func runWorkflow(_ flow:AgentWorkflowDraft){
        guard let engine else{return}
        Task{do{
            engine.operationRunning=true;engine.busy=true;defer{engine.operationRunning=false;engine.busy=false}
            var params:[String:Any]=["id":flow.id];if let project=engine.project{params["projectId"]=project["id"]}
            let result=try await engine.call("workflow-run",params) as? [String:Any] ?? [:];liveSelection=textValue(result["id"])
        }catch{self.error=error.localizedDescription}}
    }
    func runSchedule(_ id:String){
        guard let engine else{return}
        Task{do{engine.operationRunning=true;engine.busy=true;defer{engine.operationRunning=false;engine.busy=false}
            let result=try await engine.call("agent-schedule-run",["id":id]) as? [String:Any] ?? [:];liveSelection=textValue(result["id"])
        }catch{self.error=error.localizedDescription}}
    }
    func save(_ profile:AgentProfileDraft,completion:((Bool)->Void)?=nil){send("agent-save",profile,completion:completion)}
    func save(_ workflow:AgentWorkflowDraft,completion:((Bool)->Void)?=nil){send("workflow-save",workflow,completion:completion)}
    func save(_ schedule:AgentScheduleDraft,completion:((Bool)->Void)?=nil){send("agent-schedule-save",schedule,completion:completion)}
    func toggleSchedule(_ id:String){guard let row=schedules.first(where:{$0.id==id}),let engine else{return};engine.action("agent-schedule-toggle",["id":id,"enabled":!row.enabled])}
    func duplicate(_ profile:AgentProfileDraft){var next=profile;next.id=UUID().uuidString;next.name += " copy";save(next)}
    func archive(_ id:String,_ archived:Bool){guard var row=agents.first(where:{$0.id==id})else{return};row.archived=archived;send("agent-save",row)}
}
