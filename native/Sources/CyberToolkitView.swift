import SwiftUI
import AppKit

struct CyberToolkitView: View {
    @ObservedObject var engine: EngineClient
    let engagement: [String:Any]
    @ViewState private var section = "Findings"
    @ViewState private var target = ""
    @ViewState private var findingID = ""
    @ViewState private var objectiveID = ""
    @ViewState private var vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"
    @ViewState private var severityReason = ""
    @ViewState private var identityDetails: [String:String] = [:]
    @ViewState private var cveIDs = ""
    @ViewState private var title = ""
    @ViewState private var kind = "observation"
    @ViewState private var confidence = "low"
    @ViewState private var details: [String:String] = [:]
    @ViewState private var selectedEvidence: Set<String> = []
    @ViewState private var plan: [String:String] = [:]
    @ViewState private var includeEvidence = false
    @ViewState private var sensorPath = ""
    @ViewState private var binaryPath = ""
    @ViewState private var reportImportPath = ""
    @ViewState private var analysisPath = ""
    @ViewState private var verificationIDs: Set<String> = []
    @ViewState private var fix = ""
    @ViewState private var limitations = ""
    @ViewState private var message = ""
    @ViewState private var failure = ""
    @ViewState private var working = false
    @ViewState private var exportPaths: [String] = []
    @Environment(\.wixalTheme) private var theme
    private let findingFields = ["description","impact","assumptions","counterevidence","confidenceRationale","severityChangeConditions","remediation","retestPlan"]
    private let planningFields = ["threatProfile","acceptanceCriteria","deconfliction","contacts","dataHandling","abortConditions","deliverables","retention","retestCriteria"]
    private let identityFields = ["component","componentVersion","rootCause","surface","identityId"]
    private var id: String { engagementText(engagement["id"]) }
    private var closed: Bool { ["completed","closed_incomplete","cancelled"].contains(engagementText(engagement["status"])) }
    private func rows(_ key: String) -> [[String:Any]] {
        records(engine.state[key]).filter { engagementText($0["engagementId"]) == id && engagementText($0["projectId"]) == engagementText(engagement["projectId"]) }
    }
    private var targets: [[String:Any]] {
        records(engine.state["securityTargets"]).filter { (engagement["targetIds"] as? [String] ?? []).contains(engagementText($0["id"])) && engagementText($0["projectId"]) == engagementText(engagement["projectId"]) }
    }
    private var findings: [[String:Any]] {
        records(engine.state["securityFindings"]).filter { row in
            targets.contains { engagementText($0["id"]) == engagementText(row["targetId"]) } && engagementText(row["projectId"]) == engagementText(engagement["projectId"]) && (row["engagementId"] == nil || engagementText(row["engagementId"]) == id)
        }
    }
    private var currentFinding: [String:Any]? { findings.first { engagementText($0["id"]) == findingID } }
    private func caption(_ key: String) -> String {
        ["confidenceRationale":"Confidence rationale","severityChangeConditions":"What would change severity?","retestPlan":"Retest plan","threatProfile":"Threat profile","acceptanceCriteria":"Acceptance criteria","dataHandling":"Data handling","abortConditions":"Abort conditions","retestCriteria":"Retest criteria","componentVersion":"Component version","rootCause":"Root cause","identityId":"Identity reference"][key] ?? key.prefix(1).uppercased()+key.dropFirst()
    }
    private func field(_ key: String, values: Binding<[String:String]>) -> some View {
        VStack(alignment:.leading,spacing:4) {
            Text(caption(key)).foregroundStyle(theme.muted)
            TextField(caption(key),text:Binding(get:{values.wrappedValue[key] ?? ""},set:{values.wrappedValue[key]=$0}),axis:.vertical).wixalField()
        }
    }
    private var targetPicker: some View {
        Picker("Target",selection:$target) { Text("Choose…").tag("");ForEach(targets,id:\.engagementID) { row in Text(engagementText(row["address"])).tag(engagementText(row["id"])) } }
    }
    var body: some View {
        VStack(alignment:.leading,spacing:16) {
            Text("Cyber toolkit").wixalFont(size:18,weight:.medium)
            Text("Evidence-grounded findings, planning, reports and local defensive observations.").foregroundStyle(theme.muted)
            Picker("Toolkit section",selection:$section) { ForEach(["Findings","Planning","Reports","Monitoring","Binary analysis"],id:\.self) { Text($0).tag($0) } }
            if !failure.isEmpty { Text(failure).foregroundStyle(.orange).textSelection(.enabled) }
            if !message.isEmpty { Text(message).textSelection(.enabled) }
            if !exportPaths.isEmpty { Button("Show exported files in Finder") { NSWorkspace.shared.activateFileViewerSelecting(exportPaths.map { URL(fileURLWithPath:$0) }) } }
            if working { ProgressView("Working…") }
            switch section {
            case "Findings":findingEditor
            case "Planning":planningEditor
            case "Reports":reports
            case "Monitoring":monitoring
            default:analysis
            }
        }.buttonStyle(WixalButtonStyle()).wixalFont(size:12).padding(.vertical,14).disabled(working)
        .task { loadPlan() }
        .onChange(of:id) { _,_ in target="";findingID="";selectedEvidence=[];verificationIDs=[];message="";failure="";loadPlan() }
        .onChange(of:section) { _,_ in message="";failure="";exportPaths=[] }
        .onChange(of:findingID) { _,_ in loadFinding() }
    }
    private func loadPlan() { let saved=engagement["planning"] as? [String:Any] ?? [:];plan=Dictionary(uniqueKeysWithValues:planningFields.map { ($0,engagementText(saved[$0])) }) }
    private func loadFinding() {
        let row=currentFinding ?? [:];title=engagementText(row["title"]);target=engagementText(row["targetId"])
        kind=engagementText(row["resultKind"]).isEmpty ? "observation" : engagementText(row["resultKind"])
        confidence=["low","medium","high"].contains(engagementText(row["confidence"])) ? engagementText(row["confidence"]) : "low"
        details=Dictionary(uniqueKeysWithValues:findingFields.map { ($0,engagementText(row[$0])) });selectedEvidence=Set(row["evidenceIds"] as? [String] ?? [])
        objectiveID=engagementText(row["objectiveId"])
        cveIDs=(row["cveIds"] as? [String] ?? []).joined(separator:", ")
        identityDetails=Dictionary(uniqueKeysWithValues:identityFields.map {($0,engagementText(row[$0]))})
        vector=engagementText(row["cvssVector"]).isEmpty ? "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N" : engagementText(row["cvssVector"])
        severityReason=engagementText(row["severityRationale"])
    }
    private var findingEditor: some View {
        VStack(alignment:.leading,spacing:12) {
            Picker("Finding",selection:$findingID) { Text("New finding draft").tag("");ForEach(findings,id:\.engagementID) { row in Text(engagementText(row["title"])).tag(engagementText(row["id"])) } }
            targetPicker;TextField("Finding title",text:$title).wixalField()
            Picker("Linked objective for retesting",selection:$objectiveID) { Text("Choose…").tag("");ForEach(rows("securityObjectives"),id:\.engagementID) {row in Text(engagementText(row["title"])).tag(engagementText(row["id"]))} }
            Picker("Result kind",selection:$kind) { ForEach(["vulnerability","observation","hypothesis","negative_result","dependency_cve"],id:\.self) { Text($0.replacingOccurrences(of:"_",with:" ")).tag($0) } }
            Picker("Confidence",selection:$confidence) { ForEach(["low","medium","high"],id:\.self) { Text($0.capitalized).tag($0) } }
            ForEach(findingFields,id:\.self) { field($0,values:$details) }
            DisclosureGroup("Component, CVE and identity details") {
                TextField("CVE IDs, separated by commas",text:$cveIDs).wixalField()
                ForEach(identityFields,id:\.self) { field($0,values:$identityDetails) }
            }
            DisclosureGroup("Retained evidence (\(selectedEvidence.count) selected)") {
                ForEach(rows("securityEvidence"),id:\.engagementID) { row in
                    let value=engagementText(row["id"])
                    Toggle(engagementText(row["kind"])+" · "+engagementText(row["source"]),isOn:Binding(get:{selectedEvidence.contains(value)},set:{if $0 {selectedEvidence.insert(value)} else {selectedEvidence.remove(value)}}))
                }
            }
            Button("Save finding draft") {
                var values: [String:Any]=details
                for key in identityFields {values[key]=identityDetails[key] ?? ""}
                values["cveIds"]=cveIDs.split(separator:",").map {String($0).trimmingCharacters(in:.whitespacesAndNewlines)}.filter {!$0.isEmpty}
                values.merge(["targetId":target,"title":title,"resultKind":kind,"confidence":confidence,"evidenceIds":Array(selectedEvidence),"objectiveId":objectiveID]) { _,new in new }
                if !findingID.isEmpty { values["findingId"]=findingID;values["baseRevision"]=currentFinding?["revision"] ?? 0 }
                call("finding_save",values:values)
            }.disabled(closed || target.isEmpty || title.isEmpty || selectedEvidence.isEmpty || findingFields.contains { (details[$0] ?? "").isEmpty })
            if !findingID.isEmpty {
                if ["vulnerability","dependency_cve"].contains(kind) {
                    TextField("CVSS 3.1 vector",text:$vector).wixalField()
                    TextField("Severity rationale",text:$severityReason,axis:.vertical).wixalField()
                    Button("Compute and retain severity") {call("finding_score",values:["findingId":findingID,"vector":vector,"rationale":severityReason])}.disabled(closed || severityReason.isEmpty)
                }
                Button("Check report quality") { call("finding_quality",values:["findingId":findingID],read:true) }
                Button("Find possible duplicates") { call("duplicates",values:["findingId":findingID],read:true) }
                Button("Mark report complete") { call("finding_complete",values:["findingId":findingID,"baseRevision":currentFinding?["revision"] ?? 0]) }.disabled(closed)
                DisclosureGroup("Record a remediation retest") {
                    TextField("What changed?",text:$fix,axis:.vertical).wixalField()
                    TextField("Retest limitations",text:$limitations,axis:.vertical).wixalField()
                    ForEach(rows("securityVerifications").filter { $0["contractId"] != nil },id:\.engagementID) { row in
                        let value=engagementText(row["id"])
                        Toggle(engagementText(row["validator"])+" · "+engagementText(row["status"]),isOn:Binding(get:{verificationIDs.contains(value)},set:{if $0 {verificationIDs.insert(value)} else {verificationIDs.remove(value)}}))
                    }
                    Button("Evaluate declared retest checks") {call("retest",values:["findingId":findingID,"verificationIds":Array(verificationIDs),"fixDescription":fix,"limitations":limitations])}.disabled(closed || fix.isEmpty || limitations.isEmpty || verificationIDs.isEmpty)
                }
            }
            Text("Report completeness and confidence do not establish technical verification. Retests evaluate only the selected validation contracts.").foregroundStyle(theme.muted)
        }
    }
    private var planningEditor: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Planning documents share one versioned engagement record.").foregroundStyle(theme.muted)
            ForEach(planningFields,id:\.self) { field($0,values:$plan) }
            Button("Save planning revision") {
                var values:[String:Any]=plan;values["baseRevision"]=(engagement["planning"] as? [String:Any])?["revision"] ?? 0
                call("planning_save",values:values)
            }.disabled(closed || planningFields.contains { (plan[$0] ?? "").isEmpty })
            Button("Check planning completeness") {call("dossier",read:true)}
            Text("Planning never replaces review of the active scope.").foregroundStyle(theme.muted)
        }
    }
    private var reports: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Export technical and executive reports in Markdown, PDF and Word, SARIF results, a timeline and a manifest-backed ZIP.")
            Toggle("Include redacted copies of retained evidence",isOn:$includeEvidence)
            Text("Automatic redaction is limited. Review client content before sharing. Original evidence stays in Wixal; exported copies have separate hashes.").foregroundStyle(theme.muted)
            Button("Export engagement package") {call("export",values:["includeEvidence":includeEvidence])}
            TextField("Project-relative report ZIP path",text:$reportImportPath).wixalField()
            Button("Import report as untrusted evidence") {call("report_import",values:["path":reportImportPath])}.disabled(closed || reportImportPath.isEmpty)
            Button("Add assessment procedures to Skills") {call("skills")}.disabled(closed)
            Button("Inspect operation recovery") {call("sessions",read:true)}
        }
    }
    private var monitoring: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Observe an explicitly enrolled project log. Collection reads local files and never blocks traffic or changes the service.").foregroundStyle(theme.muted)
            targetPicker;TextField("Project-relative log path",text:$sensorPath).wixalField()
            Button("Review log enrollment") {call("sensor_enroll",values:["targetId":target,"path":sensorPath])}.disabled(closed || target.isEmpty || sensorPath.isEmpty)
            ForEach(rows("securitySensors"),id:\.engagementID) { row in
                VStack(alignment:.leading,spacing:8) {
                    Text(engagementText(row["path"])+" · "+engagementText(row["status"])).bold()
                    Text("Delivered: "+engagementText(row["delivered"])+" · malformed: "+engagementText(row["malformed"]))
                    Text(engagementText(row["gap"])).foregroundStyle(theme.muted)
                    DisclosureGroup("Detection rules (changing rules pauses collection)") {
                        ForEach(["server_error","authentication_failure","http_server_error"],id:\.self) { rule in
                            Toggle(rule.replacingOccurrences(of:"_",with:" "),isOn:Binding(get:{(row["rules"] as? [String] ?? ["server_error","authentication_failure","http_server_error"]).contains(rule)},set:{enabled in
                                var rules=row["rules"] as? [String] ?? ["server_error","authentication_failure","http_server_error"]
                                rules.removeAll {$0 == rule};if enabled {rules.append(rule)}
                                call("sensor_configure",values:["sensorId":row["id"] ?? "","rules":rules])
                            })).disabled(closed || row["archived"] != nil)
                        }
                    }
                    ViewThatFits(in:.horizontal) {
                        HStack { sensorButtons(row) }
                        VStack(alignment:.leading) { sensorButtons(row) }
                    }
                }.padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:7)).wixalSoftDepth(cornerRadius:7)
            }
            Text("Incident leads").bold()
            ForEach(Array(rows("securityIncidents").suffix(50)),id:\.engagementID) { row in
                Text((row["rules"] as? [String] ?? []).joined(separator:", ")+" · "+engagementText(row["count"] ?? 1)+" matching records · "+engagementText(row["sample"]))
            }
        }
    }
    @ViewBuilder private func sensorButtons(_ row:[String:Any]) -> some View {
        Button("Review ten-minute monitoring") {call("sensor_start",values:["sensorId":row["id"] ?? ""])}.disabled(closed)
        Button("Stop") {call("sensor_stop",values:["sensorId":row["id"] ?? ""])}
        Button("Archive source") {call("sensor_archive",values:["sensorId":row["id"] ?? ""])}.disabled(closed)
    }
    private var analysis: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Static triage hashes the selected file, identifies common headers and retains bounded strings. It does not execute the binary.").foregroundStyle(theme.muted)
            targetPicker;TextField("Project-relative binary path",text:$binaryPath).wixalField()
            Button("Retain static triage") {call("binary_triage",values:["targetId":target,"path":binaryPath])}.disabled(closed || target.isEmpty || binaryPath.isEmpty)
            Button("Inspect configured analysis providers") {call("analysis_readiness",read:true)}
            Button("Review Ghidra decompilation") {call("binary_decompile",values:["targetId":target,"path":binaryPath])}.disabled(closed || target.isEmpty || binaryPath.isEmpty)
            TextField("Project-relative analysis export path",text:$analysisPath).wixalField()
            Button("Import source-bound analysis") {call("analysis_import",values:["targetId":target,"path":analysisPath,"binaryPath":binaryPath])}.disabled(closed || target.isEmpty || binaryPath.isEmpty || analysisPath.isEmpty)
            Text("External analysis exports must identify their provider, observations and the exact binary SHA-256. Imported results remain external assertions.").foregroundStyle(theme.muted)
        }
    }
    private func call(_ action:String,values:[String:Any]=[:],read:Bool=false) {
        working=true;message="";failure="";exportPaths=[]
        Task {do {
            let result=try await engine.call(read ? "security-cyber-read" : "security-cyber-manage",["engagementId":id,"action":action,"parameters":values]) as? [String:Any] ?? [:]
            if let paths=result["paths"] as? [String] {exportPaths=paths;message="Exported the engagement package and \(max(0,paths.count-1)) companion files."}
            else if let errors=result["errors"] as? [String] {message=errors.isEmpty ? "Report structure and evidence references passed. Technical verification is separate." : errors.joined(separator:"\n")}
            else if let missing=result["missingFields"] as? [String] {message=missing.isEmpty ? (result["stale"] as? Bool == true ? "Planning belongs to an older scope revision." : "All planning fields are present.") : "Still needed: "+missing.map(caption).joined(separator:", ")}
            else if let matches=result["matches"] as? [[String:Any]] {message=matches.isEmpty ? "No duplicate candidates found." : matches.map {engagementText($0["reason"])}.joined(separator:"\n")}
            else if let sessions=result["sessions"] as? [[String:Any]] {message=sessions.map {engagementText($0["name"])+": "+engagementText($0["status"])+" · "+engagementText($0["recovery"])}.joined(separator:"\n")}
            else if action == "analysis_readiness" {message=result["externalProviderReady"] as? Bool == true ? "Configured analysis tools are available through Connections. Review provider calls separately." : "Native static triage is available. Configure an external analysis provider in Connections for deeper analysis."}
            else {message="Saved: "+action.replacingOccurrences(of:"_",with:" ")}
            if action == "finding_save",let row=result["finding"] as? [String:Any] {findingID=engagementText(row["id"])}
        }catch {failure=error.localizedDescription}
            working=false
        }
    }
}
