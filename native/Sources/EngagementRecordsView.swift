import SwiftUI

struct EngagementRecordsView:View {
    @ObservedObject var engine:EngineClient
    let engagement:[String:Any]
    let page:String
    let perform:(String,[String:Any])->Void
    @ViewState private var target=""
    @ViewState private var title=""
    @ViewState private var hypothesis=""
    @ViewState private var signal=""
    @ViewState private var objective=""
    @ViewState private var parent=""
    @ViewState private var replaces=""
    @ViewState private var role="recon_analyst"
    @ViewState private var question=""
    @ViewState private var model=""
    @ViewState private var selectedEvidence:Set<String>=[]
    @ViewState private var from=""
    @ViewState private var to=""
    @ViewState private var kind="may_enable"
    @ViewState private var relationState="inferred"
    @ViewState private var rationale=""
    @ViewState private var positive=""
    @ViewState private var baseline=""
    @ViewState private var pointer="/report/requests/0/status"
    @ViewState private var expected="200"
    @ViewState private var verification=""
    @ViewState private var cleanupTitle=""
    @ViewState private var cleanupDescription=""
    @ViewState private var closure=""
    @ViewState private var importPath=""
    @ViewState private var evidenceContent=""
    @ViewState private var evidenceID=""
    @ViewState private var evidenceOffset=0
    @ViewState private var more=false
    @ViewState private var candidatePaths:[[String:Any]]=[]
    @ViewState private var localError=""
    @ViewState private var vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"
    @ViewState private var finding=""
    @Environment(\.wixalTheme) private var theme
    private var id:String {engagementText(engagement["id"])}
    private var targetIDs:[String] {engagement["targetIds"] as? [String] ?? []}
    private func rows(_ key:String)->[[String:Any]] {records(engine.state[key]).filter{engagementText($0["engagementId"]) == id && engagementText($0["projectId"]) == engagementText(engagement["projectId"])}}
    private var targets:[[String:Any]] {records(engine.state["securityTargets"]).filter{targetIDs.contains(engagementText($0["id"])) && engagementText($0["projectId"]) == engagementText(engagement["projectId"])}}
    private var entities:[[String:Any]] {targets + rows("securityObjectives") + records(engine.state["securityDiscoveries"]).filter{targetIDs.contains(engagementText($0["targetId"])) && engagementText($0["projectId"]) == engagementText(engagement["projectId"])}}
    private var evidence:[[String:Any]] {rows("securityEvidence")}
    private var liveEvidence:[[String:Any]] {evidence.filter{engagementText($0["kind"]) == "run"}}
    private var closed:Bool {["completed","closed_incomplete","cancelled"].contains(engagementText(engagement["status"]))}
    private func label(_ row:[String:Any])->String {
        if engagementText(row["kind"]) == "run",let run=records(engine.state["securityRuns"]).first(where:{engagementText($0["id"]) == engagementText(row["source"])}) {return engagementText(run["name"])}
        return engagementText(row["title"] ?? row["address"] ?? row["name"] ?? row["source"] ?? row["id"])
    }
    var body:some View {
        VStack(alignment:.leading,spacing:18) {
            if !localError.isEmpty {Text(localError).foregroundStyle(.orange).textSelection(.enabled)}
            switch page {
            case "Objectives":objectives
            case "Attack paths":relations
            case "Specialists":specialists
            case "Operations":operations
            case "Evidence & verification":verificationView
            default:cleanup
            }
        }.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,14)
        .buttonStyle(WixalButtonStyle()).wixalFont(size:12)
        .onChange(of:id) { _,_ in candidatePaths=[];target="";objective="";selectedEvidence=[];positive="";baseline="";from="";to="";evidenceContent="";evidenceID="";evidenceOffset=0;more=false;verification="";finding="";parent="" }
        .task {engine.loadModels()}
    }
    private func picker(_ title:String,selection:Binding<String>,items:[[String:Any]])->some View {
        Picker(title,selection:selection) {Text("Choose…").tag("");ForEach(items,id:\.engagementID){row in Text(label(row)).tag(engagementText(row["id"]))}}
    }
    private var targetPicker:some View {picker("Target",selection:$target,items:targets)}
    private var evidencePicker:some View {
        DisclosureGroup("Select retained evidence (\(selectedEvidence.count))") {
            ForEach(liveEvidence,id:\.engagementID) { row in
                Toggle(label(row),isOn:Binding(get:{selectedEvidence.contains(engagementText(row["id"]))},set:{if $0{selectedEvidence.insert(engagementText(row["id"]))}else{selectedEvidence.remove(engagementText(row["id"]))}}))
            }
            if liveEvidence.isEmpty {Text("Run a scoped assessment to collect evidence first.").foregroundStyle(theme.muted)}
        }
    }
    private var objectives:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Objectives and hypotheses").wixalFont(size:18,weight:.medium)
            Text("Define a question, observable success signal and prerequisites. Completion needs an associated discriminating observation check; it does not confirm exploitation.").foregroundStyle(theme.muted)
            ForEach(rows("securityObjectives"),id:\.engagementID) { row in
                VStack(alignment:.leading,spacing:5) {
                    Text(label(row)).bold();Text(engagementText(row["hypothesis"]))
                    Text("Expected: "+engagementText(row["successSignal"])).foregroundStyle(theme.muted)
                    Text("Status: "+engagementText(row["status"])).foregroundStyle(theme.muted)
                }.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:7))
            }
            Divider();targetPicker
            TextField("Objective title",text:$title).wixalField()
            TextField("Hypothesis to test",text:$hypothesis,axis:.vertical).wixalField()
            TextField("Observable success signal",text:$signal,axis:.vertical).wixalField()
            picker("Prerequisite (optional)",selection:$parent,items:rows("securityObjectives"))
            picker("Replace earlier objective (optional)",selection:$replaces,items:rows("securityObjectives").filter{engagementText($0["status"]) != "superseded"})
            Button("Add objective") {perform("security-objective-save",["targetId":target,"title":title,"hypothesis":hypothesis,"successSignal":signal,"dependsOn":parent.isEmpty ? [] : [parent],"replacesId":replaces])}.disabled(closed || target.isEmpty || title.isEmpty || hypothesis.isEmpty || signal.isEmpty)
            Divider()
            picker("Objective to complete",selection:$objective,items:rows("securityObjectives"))
            picker("Observation check",selection:$verification,items:rows("securityVerifications").map{var row=$0;row["title"]=engagementText(row["status"])+" · "+engagementText(row["pointer"]);return row})
            Button("Record objective completion") {perform("security-objective-complete",["objectiveId":objective,"verificationId":verification])}.disabled(closed || objective.isEmpty || verification.isEmpty)
        }
    }
    private var relations:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Evidence-linked attack paths").wixalFont(size:18,weight:.medium)
            Text("Relationships connect assets, observations and objectives. Candidate paths describe possible progression; they execute no actions and establish no access.").foregroundStyle(theme.muted)
            ForEach(rows("securityRelations"),id:\.engagementID) { row in
                VStack(alignment:.leading,spacing:5) {
                    Text(entityName(engagementText(row["fromId"]))+" → "+entityName(engagementText(row["toId"]))).bold()
                    Text(engagementText(row["kind"])+" · "+engagementText(row["state"]));Text(engagementText(row["rationale"]))
                    Text("Evidence references: \((row["evidenceIds"] as? [String] ?? []).count)").foregroundStyle(theme.muted)
                }.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:7))
            }
            ForEach(Array(candidatePaths.enumerated()),id:\.offset) { index,path in
                VStack(alignment:.leading,spacing:8) {
                    Text("Candidate path \(index+1) · \(engagementText(path["hops"])) hops").bold()
                    ForEach(path["edgeIds"] as? [String] ?? [],id:\.self) { edgeID in
                        if let edge=rows("securityRelations").first(where:{engagementText($0["id"]) == edgeID}) {
                            Label(entityName(engagementText(edge["fromId"]))+" → "+entityName(engagementText(edge["toId"]))+" · "+engagementText(edge["state"]),systemImage:"arrow.triangle.branch")
                        }
                    }
                    Text(engagementText(path["limitation"])).foregroundStyle(theme.muted)
                }.padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:7))
            }
            picker("From",selection:$from,items:entities);picker("To",selection:$to,items:entities)
            Picker("Relationship",selection:$kind) {ForEach(["runs_on","exposes","may_enable","requires","can_access","supports","contradicts"],id:\.self){Text($0.replacingOccurrences(of:"_",with:" "))}}
            Picker("Evidence state",selection:$relationState){ForEach(["inferred","observed","disproved"],id:\.self){Text($0)}}
            TextField("Evidence rationale",text:$rationale,axis:.vertical).wixalField();evidencePicker
            HStack {
                Button("Add relationship") {perform("security-relation-add",["fromId":from,"toId":to,"kind":kind,"state":relationState,"rationale":rationale,"evidenceIds":Array(selectedEvidence)])}.disabled(closed || from.isEmpty || to.isEmpty || rationale.isEmpty)
                Button("Find candidate paths") {Task {do {let result=try await engine.call("security-relation-paths",["engagementId":id,"fromId":from,"toId":to]) as? [String:Any] ?? [:];candidatePaths=records(result["paths"]);localError=candidatePaths.isEmpty ? "No connected candidate path found." : ""}catch{localError=error.localizedDescription}}}.disabled(from.isEmpty || to.isEmpty)
            }
        }
    }
    private func entityName(_ value:String)->String {entities.first{engagementText($0["id"]) == value}.map(label) ?? value}
    private var specialists:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Restricted specialists").wixalFont(size:18,weight:.medium)
            Text("Each assignment receives selected retained target evidence and a question. It runs through the existing model queue with no tool execution, credentials or parent private context. A verifier's opinion is not an independent check.").foregroundStyle(theme.muted)
            ForEach(rows("securityAssignments"),id:\.engagementID) { row in VStack(alignment:.leading,spacing:5){Text(engagementText(row["role"])+" · "+engagementText(row["status"])).bold();Text(engagementText(row["question"]));Text(engagementText(row["authority"])).foregroundStyle(theme.muted)}.padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:7)) }
            targetPicker
            Picker("Role",selection:$role) {ForEach(["planner","recon_analyst","researcher","verifier","reporter"],id:\.self){Text($0.replacingOccurrences(of:"_",with:" "))}}
            Picker("Local model",selection:$model) {Text("Choose model").tag("");ForEach(engine.models,id:\.engagementNameID){Text(engagementText($0["name"])).tag(engagementText($0["name"]))}}
            TextField("Assignment question",text:$question,axis:.vertical).wixalField();evidencePicker
            Button("Assign specialist") {perform("security-specialist-assign",["targetId":target,"role":role,"question":question,"model":model,"evidenceIds":Array(selectedEvidence)])}.disabled(closed || target.isEmpty || model.isEmpty || question.isEmpty || selectedEvidence.isEmpty)
        }
    }
    private var operations:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Owned operations").wixalFont(size:18,weight:.medium)
            Text("Queue scoped capabilities in Investigations. Runs retain their scope revision, execution receipt and evidence. Stop does not establish cleanup; interrupted effects require reconciliation.").foregroundStyle(theme.muted)
            ForEach(rows("securityRuns"),id:\.engagementID) { row in
                VStack(alignment:.leading,spacing:8) {
                    HStack {Text(label(row)).bold();Spacer();Text(engagementText(row["status"]))}
                    Text("Scope \(engagementText(row["scopeRevision"])) · effect \(engagementText(row["effectState"])) · \(engagementText(row["environment"]))").foregroundStyle(theme.muted)
                    if !engagementText(row["error"]).isEmpty {Text(engagementText(row["error"])).foregroundStyle(.orange)}
                    if !engagementText(row["output"]).isEmpty {DisclosureGroup("Retained output excerpt"){Text(String(engagementText(row["output"]).suffix(12000))).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}}
                    if row["workerContainer"] != nil {Button("Inspect owned environment"){perform("security-engagement-worker-reconcile",["runId":row["id"] ?? ""])};Button("Review worker cleanup"){perform("security-engagement-worker-cleanup",["runId":row["id"] ?? ""])}}
                    if ["queued","blocked","running","waiting_review","waiting_model"].contains(engagementText(row["status"])) {Button("Stop operation"){perform("security-run-stop",["id":row["id"] ?? ""])}}
                }.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:7))
            }
        }
    }
    private var verificationView:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Evidence and independent observation checks").wixalFont(size:18,weight:.medium)
            ForEach(evidence,id:\.engagementID) { row in
                HStack {VStack(alignment:.leading){Text(engagementText(row["kind"])+" · "+label(row));Text(String(engagementText(row["sha256"]).prefix(16))).wixalFont(size:10,design:.monospaced).foregroundStyle(theme.muted)};Spacer();Button("Inspect") {loadEvidence(engagementText(row["id"]),0)}}
            }
            if !evidenceContent.isEmpty {DisclosureGroup("Evidence contents"){Text(evidenceContent).wixalFont(size:10,design:.monospaced).textSelection(.enabled);if more{Button("Next evidence page"){loadEvidence(evidenceID,evidenceOffset)}}}}
            TextField("External JSON artifact inside project",text:$importPath).wixalField()
            Button("Import as untrusted evidence"){perform("security-evidence-import",["path":importPath])}.disabled(closed || importPath.isEmpty)
            Divider()
            Text("Compare an observable signal in two retained runs of the same target, capability, profile and scope. These checks establish a difference in collected observations; they never automatically confirm a vulnerability.").foregroundStyle(theme.muted)
            picker("Objective",selection:$objective,items:rows("securityObjectives"))
            picker("Positive observation",selection:$positive,items:liveEvidence)
            picker("Baseline observation",selection:$baseline,items:liveEvidence)
            TextField("Signal location (JSON pointer)",text:$pointer).wixalField()
            TextField("Expected signal (JSON scalar, e.g. 200 or \"open\")",text:$expected).wixalField()
            Button("Evaluate retained observations") {
                do {
                    let value=try JSONSerialization.jsonObject(with:Data(expected.utf8),options:.fragmentsAllowed)
                    perform("security-verification-add",["objectiveId":objective,"positiveId":positive,"baselineId":baseline,"pointer":pointer,"expected":value])
                }catch{localError="Expected signal must be a JSON string, number or boolean."}
            }.disabled(closed || objective.isEmpty || positive.isEmpty || baseline.isEmpty || positive == baseline)
            ForEach(rows("securityVerifications"),id:\.engagementID){row in Text(engagementText(row["status"])+" · "+engagementText(row["pointer"])).foregroundStyle(theme.muted)}
            Divider()
            picker("Finding to score",selection:$finding,items:records(engine.state["securityFindings"]).filter{targetIDs.contains(engagementText($0["targetId"])) && engagementText($0["projectId"]) == engagementText(engagement["projectId"])})
            if let scored=records(engine.state["securityFindings"]).first(where:{engagementText($0["id"]) == finding}),scored["cvssScore"] != nil { Text("CVSS 3.1: "+engagementText(scored["cvssScore"])+" · "+engagementText(scored["cvssVector"])).textSelection(.enabled);Text("Scoring does not establish independent verification.").foregroundStyle(theme.muted) }
            TextField("CVSS 3.1 vector",text:$vector).wixalField()
            TextField("Impact and severity rationale",text:$rationale,axis:.vertical).wixalField()
            Button("Compute and retain severity") {perform("security-engagement-finding",["findingId":finding,"vector":vector,"rationale":rationale])}.disabled(closed || finding.isEmpty || rationale.isEmpty)
        }
    }
    private func loadEvidence(_ value:String,_ offset:Int) {
        Task {do {let result=try await engine.call("security-evidence-read",["engagementId":id,"evidenceId":value,"offset":offset]) as? [String:Any] ?? [:];evidenceID=value;evidenceContent=engagementText(result["content"]);evidenceOffset=result["nextOffset"] as? Int ?? 0;more=result["more"] as? Bool ?? false}catch{localError=error.localizedDescription}}
    }
    private var cleanup:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("Report and cleanup").wixalFont(size:18,weight:.medium)
            Text("A stopped operation can leave effects behind. Record each cleanup requirement, inspect evidence, and explicitly review its disposition. Accepted cleanup retains the rationale; it is separate from verified cleanup.").foregroundStyle(theme.muted)
            ForEach(rows("securityCleanup"),id:\.engagementID) { row in VStack(alignment:.leading,spacing:8){Text(label(row)+" · "+engagementText(row["status"])).bold();Text(engagementText(row["description"]));HStack{Button("Review acceptance"){perform("security-cleanup-update",["cleanupId":row["id"] ?? "","status":"accepted","rationale":rationale,"evidenceIds":Array(selectedEvidence)])};Button("Review collected evidence"){perform("security-cleanup-update",["cleanupId":row["id"] ?? "","status":"verified","rationale":rationale,"evidenceIds":Array(selectedEvidence)])}}.disabled(closed || rationale.isEmpty).padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:7)) } }
            picker("Operation to reconcile (optional)",selection:$parent,items:rows("securityRuns"))
            TextField("Cleanup item",text:$cleanupTitle).wixalField()
            TextField("Required removal or reconciliation",text:$cleanupDescription,axis:.vertical).wixalField()
            Button("Add cleanup item"){perform("security-cleanup-add",["title":cleanupTitle,"description":cleanupDescription,"runId":parent])}.disabled(closed || cleanupTitle.isEmpty || cleanupDescription.isEmpty)
            TextField("Disposition rationale",text:$rationale,axis:.vertical).wixalField();evidencePicker
            Divider()
            Button("Export JSON and Markdown report"){perform("security-engagement-export",[:])}
            TextField("Closure rationale",text:$closure,axis:.vertical).wixalField()
            HStack {
                Button("Complete engagement"){perform("security-engagement-close",["reason":closure])}
                Button("Close incomplete"){perform("security-engagement-close",["reason":closure,"incomplete":true])}
            }.disabled(closed || closure.isEmpty)
            Text("Ordinary completion requires completed objectives and reviewed cleanup. Reports include scope history, source identities, limitations and separate finding review states.").foregroundStyle(theme.muted)
        }
    }
}
