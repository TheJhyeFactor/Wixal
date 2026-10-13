import SwiftUI

func engagementText(_ value:Any?) -> String {
    if let text=value as? String {return text}
    if let number=value as? NSNumber {return number.stringValue}
    return ""
}

func engagementCapabilityName(_ value:String) -> String {
    ["analysis":"Evidence analysis","planner":"AI plan builder","software_inventory":"Software inventory","website_assess":"Website assessment","website_simulate":"Local simulations","network_scan":"Network assessment","network_discover":"TCP port discovery","linux_network_scan":"Isolated Linux network assessment","api_observe":"Read-only API observations"][value] ?? value
}

struct EngagementWorkspaceView: View {
    @ObservedObject var engine: EngineClient
    var openInvestigations: () -> Void
    @ViewState private var selection = ""
    @ViewState private var page = "Brief & scope"
    @ViewState private var creating = false
    @ViewState private var editing = false
    @ViewState private var error = ""
    @ViewState private var notice = ""
    @ViewState private var working = false
    @ViewState private var workerSocket = ""
    @Environment(\.wixalTheme) private var theme
    private var engagements: [[String:Any]] { records(engine.state["securityEngagements"]).filter { engagementText($0["projectId"]) == engagementText(engine.state["activeProject"]) } }
    private var selected: [String:Any]? { engagements.first { engagementText($0["id"]) == selection } }
    private let pages = ["Brief & scope", "Objectives", "Attack paths", "Specialists", "Operations", "Evidence & verification", "Report & cleanup","Validation & identities","Cyber toolkit"]
    var body: some View {
        VStack(alignment:.leading, spacing:14) {
            HStack {
                Text("Engagements").wixalFont(size:22,weight:.medium)
                Spacer()
                Button("Investigations",action:openInvestigations)
                Button("New engagement") { creating=true }.disabled(engine.project == nil)
            }.buttonStyle(WixalButtonStyle())
            if !error.isEmpty { Text(error).foregroundStyle(.orange).textSelection(.enabled).accessibilityLabel("Engagement error: "+error) }
            if !notice.isEmpty { Text(notice).foregroundStyle(theme.muted).textSelection(.enabled) }
            if engagements.isEmpty {
                VStack(alignment:.leading,spacing:16) {
                    Text("Connect an objective, authorised scope and retained evidence.").wixalFont(size:18,weight:.medium)
                    Text("Add investigation targets first, then create an engagement. Existing investigations keep their history. New engagement scope requires explicit review before any run starts.")
                    Button("Add investigation targets",action:openInvestigations).buttonStyle(WixalButtonStyle(outlined:true))
                }.padding(24).frame(maxWidth:.infinity,maxHeight:.infinity,alignment:.topLeading)
            } else {
                Picker("Engagement",selection:$selection) {
                    Text("Choose engagement").tag("")
                    ForEach(engagements,id:\.engagementID) { row in Text(engagementText(row["name"])+" · "+engagementText(row["status"])).tag(engagementText(row["id"])) }
                }
                if let selected {
                    HStack {
                        Picker("Engagement view",selection:$page) { ForEach(pages,id:\.self) { Text($0) } }.frame(maxWidth:300)
                        Spacer()
                        if engagementText(selected["status"]) == "running" { Button("Pause") { perform("security-engagement-pause",[:]) } }
                        else if !["completed","closed_incomplete","cancelled"].contains(engagementText(selected["status"])) {
                            Button("Review & start") { perform("security-engagement-approve",["baseRevision":selected["scopeRevision"] ?? 1]) }
                        }
                    }.buttonStyle(WixalButtonStyle(outlined:true))
                    ScrollView {
                        if page == "Brief & scope" { brief(selected) }
                        else if page == "Validation & identities" { EngagementAssuranceView(engine:engine,engagement:selected,perform:perform) }
                        else if page == "Cyber toolkit" { CyberToolkitView(engine:engine,engagement:selected) }
                        else { EngagementRecordsView(engine:engine,engagement:selected,page:page,perform:perform) }
                    }
                }
            }
        }.wixalFont(size:12).padding(24).foregroundStyle(theme.text).background(theme.background)
        .disabled(working || !engine.connected)
        .overlay(alignment:.bottomTrailing) { if working { ProgressView("Waiting for engine or review…").padding().background(theme.panel,in:RoundedRectangle(cornerRadius:8)).wixalSoftDepth(cornerRadius:8) } }
        .sheet(isPresented:$creating) { EngagementSetupView(engine:engine,engagement:nil) { args in perform("security-engagement-create",args);creating=false } }
        .sheet(isPresented:$editing) { if let selected { EngagementSetupView(engine:engine,engagement:selected) { args in perform("security-engagement-scope",args);editing=false } } }
        .task { if selection.isEmpty { selection=engagementText(engagements.first?["id"]) } }
        .onChange(of:engine.state["activeProject"] as? String) { _,_ in selection=engagementText(engagements.first?["id"]);error="";notice="" }
    }
    private func perform(_ method:String,_ values:[String:Any]) {
        var args=values
        if method != "security-engagement-create" { args["engagementId"]=selection }
        working=true;error="";notice=""
        Task { do {
            let result=try await engine.call(method,args)
            if method == "security-engagement-create",let row=result as? [String:Any] { selection=engagementText(row["id"]) }
            if let data=result as? [String:Any], let paths=data["paths"] as? [String] { notice=paths.joined(separator:"\n") }
            else if method == "security-engagement-worker-inspect",let data=result as? [String:Any] { notice=data["available"] as? Bool == true ? "Linux worker ready: "+engagementText(data["imageId"]) : "Linux worker unavailable: "+engagementText(data["error"]) }
            else if method == "security-engagement-skills",let data=result as? [String:Any] { notice="\((data["skillIds"] as? [String] ?? []).count) cyber procedures are available in Skills." }
            else if method == "security-relation-paths",let data=result as? [String:Any] { notice="Candidate paths: \(records(data["paths"]).count). Relationships require evidence; paths do not prove access." }
        } catch { self.error=error.localizedDescription }
            working=false
        }
    }
    private func brief(_ row:[String:Any]) -> some View {
        let scope=(records(row["scopes"]).last?["policy"] as? [String:Any]) ?? [:]
        return VStack(alignment:.leading,spacing:18) {
            Text(engagementText(row["objective"])).wixalFont(size:17,weight:.medium).textSelection(.enabled)
            Text("Scope revision \(engagementText(row["scopeRevision"])) · \(engagementText(row["status"]))").foregroundStyle(theme.muted)
            Text("Execution, observation verification, finding review and cleanup are tracked separately.").foregroundStyle(theme.muted)
            LabeledContent("Authorised targets",value:records(engine.state["securityTargets"]).filter{(row["targetIds"] as? [String] ?? []).contains(engagementText($0["id"]))}.map{engagementText($0["address"])}.joined(separator:", "))
            LabeledContent("Testing window",value:engagementWindow(scope))
            LabeledContent("Capabilities",value:(scope["capabilities"] as? [String] ?? []).map(engagementCapabilityName).joined(separator:", "))
            LabeledContent("Excluded destinations",value:(scope["exclusions"] as? [String] ?? []).joined(separator:", ").isEmpty ? "None specified" : (scope["exclusions"] as? [String] ?? []).joined(separator:", "))
            LabeledContent("Run budget",value:engagementText(scope["maxRuns"]))
            LabeledContent("Run deadline",value:engagementText(scope["maxSeconds"])+" seconds")
            ForEach(["threatProfile","contacts","dataHandling","abortConditions"],id:\.self) { key in if !engagementText(scope[key]).isEmpty { VStack(alignment:.leading,spacing:4) { Text(["threatProfile":"Threat profile","contacts":"Contacts","dataHandling":"Data handling","abortConditions":"Abort conditions"][key] ?? key).bold();Text(engagementText(scope[key])).textSelection(.enabled) } } }
            Text("Local execution uses directly scoped adapters. External autonomous controllers and arbitrary shell commands are excluded from this engagement envelope.").foregroundStyle(theme.muted)
            ViewThatFits(in:.horizontal) {
                HStack { briefActions(row) }
                VStack(alignment:.leading) { briefActions(row) }
            }.buttonStyle(WixalButtonStyle())
            Divider()
            DisclosureGroup("Optional local Linux runtime") {
                TextField("Local Docker Unix socket",text:$workerSocket).wixalField()
                Button("Review local worker runtime") {perform("security-engagement-worker-configure",["socket":workerSocket])}.disabled(workerSocket.isEmpty)
                Text("Docker Desktop is discovered locally. Configure a separate Colima socket here; runtime installation and image build are explicit setup steps.").foregroundStyle(theme.muted)
            }
            Text("Scope history").wixalFont(size:15,weight:.medium)
            ForEach(records(row["scopes"]),id:\.revisionID) { revision in Text("Revision "+engagementText(revision["revision"])+" · retained immutable scope").foregroundStyle(theme.muted) }
        }.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,14)
    }
    private func engagementWindow(_ scope:[String:Any])->String {
        let start=Date(timeIntervalSince1970:((scope["starts"] as? NSNumber)?.doubleValue ?? 0)/1000)
        let end=Date(timeIntervalSince1970:((scope["ends"] as? NSNumber)?.doubleValue ?? 0)/1000)
        let formatter=DateFormatter();formatter.dateStyle = .short;formatter.timeStyle = .short
        return formatter.string(from:start)+" – "+formatter.string(from:end)
    }
    @ViewBuilder private func briefActions(_ row:[String:Any]) -> some View {
        Button("Edit scope") { editing=true }.disabled(["completed","closed_incomplete","cancelled"].contains(engagementText(row["status"])))
        Button("Inspect Linux worker") { perform("security-engagement-worker-inspect",[:]) }
        Button("Add red-team skills") { perform("security-engagement-skills",[:]) }
        Button("Stop engagement") { perform("security-engagement-stop",[:]) }.disabled(["completed","closed_incomplete","cancelled"].contains(engagementText(row["status"])))
    }
}

private extension Dictionary where Key == String, Value == Any {
    var revisionID: String { engagementText(self["revision"]) }
}

extension Dictionary where Key == String, Value == Any {
    var engagementID:String {engagementText(self["id"])}
    var engagementNameID:String {engagementText(self["name"])}
}
