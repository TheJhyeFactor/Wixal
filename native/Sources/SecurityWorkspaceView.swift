import SwiftUI
import AppKit

struct SecurityWorkspaceView: View {
    @ObservedObject var engine: EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var selected = ""
    @ViewState<String> private var stage = "Recon"
    @ViewState<String> private var model = ""
    @ViewState<Bool> private var showTarget = false
    @ViewState<Bool> private var showPlan = false
    @ViewState<Bool> private var showAI = false
    @ViewState<Bool> private var showRuns = false
    @ViewState<String> private var address = ""
    @ViewState<String> private var type = "Website / API"
    @ViewState<String> private var objective = ""
    @ViewState<String> private var parent = ""
    @ViewState<String> private var stepName = ""
    @ViewState<String> private var capability = "network_scan"
    @ViewState<String> private var profile = "services"
    @ViewState<String> private var coverage = "selected"
    @ViewState<String> private var pace = "careful"
    @ViewState<Bool> private var inspectDiscovered = false
    @ViewState<Int> private var discoveryDeadline = 180
    @ViewState<String> private var ports = "22,80,443,8080,8443"
    @ViewState<String> private var dependency = ""
    @ViewState<String> private var prompt = ""
    @ViewState<String> private var selectedRun = ""
    @ViewState<String> private var localError = ""
    @ViewState<Bool> private var submitting = false
    @ViewState<Bool?> private var nmap = nil
    @ViewState private var showTargetSettings = false
    @ViewState private var showStudio = false
    @ViewState private var showContract = false
    @ViewState private var targetSearch = ""
    @ViewState private var includeArchived = false
    @ViewState private var recordPage = "Runs"
    @ViewState private var capabilities: [[String:Any]] = []
    @ViewState private var selectedEvidence: Set<String> = []
    @ViewState private var useSelectedEvidence = false
    @ViewState private var researchURLs = ""
    @ViewState private var customArguments = "{}"
    private let stages = ["Recon", "Research", "Attacks", "Results"]
    private let types = ["Website / API", "Network", "Server", "Network device", "Software"]
    private var projectID: String { textValue(engine.state["activeProject"]) }
    private var targets: [[String:Any]] { records(engine.state["securityTargets"]).filter{textValue($0["projectId"]) == projectID && (includeArchived || $0["archived"] as? Bool != true)} }
    private var target: [String:Any]? { targets.first{textValue($0["id"]) == selected} }
    private var allRuns: [[String:Any]] { records(engine.state["securityRuns"]).filter{textValue($0["projectId"]) == projectID} }
    private var targetRuns: [[String:Any]] { allRuns.filter{textValue($0["targetId"]) == selected} }
    private var busyRuns: [[String:Any]] { allRuns.filter{["running","waiting_review","waiting_model","queued","blocked"].contains(textValue($0["status"]))} }
    private var queue: [String:Any] { engine.state["securityQueue"] as? [String:Any] ?? [:] }
    private var paused: Bool { queue["paused"] as? Bool ?? false }
    private var chosenRun: [String:Any]? { allRuns.first{textValue($0["id"]) == selectedRun} }
    private var toolsEnabled: [String] { engine.state["enabledTools"] as? [String] ?? [] }
    private var availableCapabilities: [String] { capabilities.map{textValue($0["id"])} }
    private var recordPages:[String] {stage == "Recon" ? ["Runs","Inventory"] : stage == "Research" ? ["Runs","Sources"] : stage == "Results" ? ["Findings","Runs","History"] : ["Runs"]}
    private var chosenCapability:[String:Any]? {capabilities.first{textValue($0["id"]) == capability}}
    private func title(_ name:String)->String {
        ["software_inventory":"Software inventory","planner":"AI plan builder","network_discover":"Discover TCP ports","network_scan":"Network assessment", "website_assess":"Website assessment", "website_simulate":"Local attack simulations", "research":"Research & AI analysis", "analysis":"AI evidence analysis"][name] ?? textValue(capabilities.first{textValue($0["id"]) == name}?["title"])
    }
    var body: some View {
        VStack(spacing:0) {
            header
            if !localError.isEmpty { HStack{Image(systemName:"exclamationmark.triangle");Text(localError).textSelection(.enabled);Spacer();Button("Dismiss"){localError=""}}.wixalFont(size:11).padding(12).background(theme.panel) }
            if engine.project == nil {
                VStack(spacing:16){Image(systemName:"scope").font(.system(size:30)).foregroundStyle(theme.muted);Text("Start a security investigation").wixalFont(size:20,weight:.medium);Text("Choose a project to keep targets, research, runs and evidence together.").foregroundStyle(theme.muted);Button("Choose project",action:engine.pickProject).buttonStyle(WixalButtonStyle(outlined:true))}.frame(maxWidth:.infinity,maxHeight:.infinity)
            } else if targets.isEmpty {
                VStack(alignment:.leading,spacing:18){Text("What are you investigating?").wixalFont(size:24,weight:.medium);Text("Add a website, network, server, device or software target. Gather evidence, research what you discover, and build a test plan.").wixalFont(size:13).foregroundStyle(theme.muted).frame(maxWidth:490);Button("Add target"){showTarget=true}.buttonStyle(WixalButtonStyle(outlined:true));Button("Show archived targets"){includeArchived=true;repairSelection()}.buttonStyle(WixalButtonStyle());HStack(spacing:22){ForEach(stages,id:\.self){Text($0).foregroundStyle(theme.muted)}}.wixalFont(size:11)}.frame(maxWidth:.infinity,maxHeight:.infinity)
            } else {
                HStack(spacing:0){targetSidebar;Divider().overlay(theme.line);investigation}
            }
            executionBar
        }.foregroundStyle(theme.text).background(theme.background)
        .sheet(isPresented:$showTarget){targetSheet}
        .sheet(isPresented:$showPlan){planSheet}
        .sheet(isPresented:$showTargetSettings){if let target {SecurityTargetEditor(engine:engine,target:target,close:{showTargetSettings=false})}}
        .sheet(isPresented:$showStudio){SecurityPlanStudio(engine:engine,targetID:selected,model:model,close:{showStudio=false})}
        .sheet(isPresented:$showContract){SecurityContractEditor(engine:engine,targetID:selected,targetType:textValue(target?["type"]),close:{showContract=false})}
        .task { repairSelection();model=textValue(engine.state["model"]);if engine.connected {engine.loadModels();await readiness();await loadCapabilities()} }
        .onChange(of:projectID){_,_ in selected="";selectedRun="";repairSelection()}
        .onChange(of:targets.count){_,_ in repairSelection()}
        .onChange(of:records(engine.state["securityContracts"]).count){_,_ in Task{await loadCapabilities()}}
        .onChange(of:records(engine.state["addonJobs"]).map{textValue($0["id"])+textValue($0["status"])}.joined(separator:"|")){_,_ in Task{await loadCapabilities()}}
        .onChange(of:(engine.state["enabledTools"] as? [String] ?? []).joined(separator:",")){_,_ in Task{await loadCapabilities()}}
        .onChange(of:selected){_,_ in selectedRun="";selectedEvidence=[];let prefs=target?["models"] as? [String:String] ?? [:];model=prefs[stage].flatMap{$0.isEmpty ? nil : $0} ?? prefs["default"].flatMap{$0.isEmpty ? nil : $0} ?? textValue(engine.state["model"]);Task{await loadCapabilities()}}
        .onChange(of:stage){_,_ in recordPage=stage == "Results" ? "Findings" : "Runs";if let saved=(target?["models"] as? [String:String])?[stage],!saved.isEmpty{model=saved}}
        .onChange(of:engine.connected){_,connected in if connected {if model.isEmpty{model=textValue(engine.state["model"])};engine.loadModels();Task{await readiness();await loadCapabilities()}}else{nmap=nil}}
    }
    private var header: some View {
        HStack(spacing:16){VStack(alignment:.leading,spacing:5){Text("SECURITY").wixalFont(size:9,design:.monospaced).tracking(1).foregroundStyle(theme.muted);Text("Cybersecurity").wixalFont(size:21,weight:.medium)};Spacer();Text(engine.project.map{textValue($0["name"])} ?? "Choose project").wixalFont(size:11).foregroundStyle(theme.muted);Button("Manage tools"){NotificationCenter.default.post(name:.wixalNavigate,object:"Tools")}.buttonStyle(WixalButtonStyle());Button("Add target"){showTarget=true}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.project == nil || !engine.connected)}.padding(.horizontal,24).padding(.vertical,20)
    }
    private var targetSidebar: some View {
        VStack(alignment:.leading,spacing:12){TextField("Find target",text:$targetSearch).wixalField();Toggle("Show archived",isOn:$includeArchived).wixalFont(size:10);Text("TARGETS").wixalFont(size:9,design:.monospaced).foregroundStyle(theme.muted);ScrollView{VStack(spacing:6){ForEach(targets.filter{targetSearch.isEmpty || pretty($0).localizedCaseInsensitiveContains(targetSearch)},id:\.selfID){item in Button{selected=textValue(item["id"]);selectedRun=""}label:{VStack(alignment:.leading,spacing:6){Text(textValue(item["address"])).lineLimit(2);Text(textValue(item["type"])).wixalFont(size:10).foregroundStyle(theme.muted)}.frame(maxWidth:.infinity,alignment:.leading).padding(10).background(textValue(item["id"]) == selected ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7))}.buttonStyle(.plain)}}}}.wixalFont(size:11).padding(16).frame(width:190).frame(maxHeight:.infinity,alignment:.top).background(theme.sidebar)
    }
    private var investigation: some View {
        VStack(alignment:.leading,spacing:0){
            HStack(alignment:.top){VStack(alignment:.leading,spacing:6){Text(textValue(target?["address"])).wixalFont(size:21,weight:.medium).textSelection(.enabled);Text(textValue(target?["objective"])).wixalFont(size:11).foregroundStyle(theme.muted);if !textValue(target?["parentId"]).isEmpty{Text("Part of " + textValue(targets.first{textValue($0["id"]) == textValue(target?["parentId"])}?["address"])).wixalFont(size:10).foregroundStyle(theme.muted)}};Spacer();VStack(alignment:.trailing,spacing:5){Picker("AI model",selection:$model){Text("Choose model").tag("");ForEach(engine.models,id:\.nameID){m in Text(textValue(m["name"])).tag(textValue(m["name"]))}}.frame(maxWidth:230);Text("New runs use this model").wixalFont(size:9).foregroundStyle(theme.muted)}}.padding(.bottom,25)
            HStack(spacing:22){ForEach(stages,id:\.self){s in Button{stage=s;selectedRun=""}label:{Text(s).foregroundStyle(stage == s ? theme.accent : theme.muted).padding(.vertical,10).overlay(alignment:.bottom){Rectangle().fill(stage == s ? theme.accent : .clear).frame(height:2)}}.buttonStyle(.plain)}}.wixalFont(size:12)
            Divider().overlay(theme.line)
            HStack {
                Picker("Evidence view",selection:$recordPage){ForEach(recordPages,id:\.self){Text($0).tag($0)}}.pickerStyle(.segmented).frame(maxWidth:320)
                Spacer()
                Menu("Investigation") {
                    Button("Start AI investigation"){startInvestigation()}
                    Button("Build AI test plan"){stage="Research";capability="planner";stepName="AI test plan";prompt="Build a test plan from the observed evidence and investigation objective";dependency="";showPlan=true}
                    Button("Chain studio"){showStudio=true}
                    Button("Target settings"){showTargetSettings=true}
                    Button("Register capability"){showContract=true}
                    Button("Export report"){exportReport()}
                }.menuStyle(.borderlessButton).frame(width:115)
            }.wixalFont(size:10).padding(.top,12)
            ScrollView{VStack(alignment:.leading,spacing:22){
                if let run=chosenRun {runDetail(run)}
                else if recordPage != "Runs" {SecurityRecordDesk(engine:engine,targetID:selected,section:recordPage)}
                else if stage == "Attacks" {attackStage}
                else if stage == "Results" {resultsStage}
                else {evidenceStage}
                if showAI {aiPanel}
            }.padding(.vertical,26).frame(maxWidth:760,alignment:.leading).frame(maxWidth:.infinity,alignment:.leading)}
            HStack{Text(nmap == true ? "Nmap ready" : nmap == false ? "Nmap missing" : "Checking Nmap").foregroundStyle(theme.muted);Text("·");Text(textValue(engine.project?["approvalMode"]) == "bypass" ? "Approved all" : "Review actions").foregroundStyle(theme.muted);Spacer();Button(showAI ? "Hide AI discussion" : "Ask AI"){showAI.toggle()}.buttonStyle(WixalButtonStyle())}.wixalFont(size:10).padding(.top,10)
        }.padding(24).frame(maxWidth:.infinity,maxHeight:.infinity)
    }
    private var evidenceStage: some View {
        let rows=targetRuns.filter{textValue($0["stage"]) == stage}
        return VStack(alignment:.leading,spacing:20){Text(stage == "Recon" ? "Gather information" : "Research what you discovered").wixalFont(size:22,weight:.medium);Text(stage == "Recon" ? "Collect service, version, protocol and input evidence. Each run retains its target and exact tool arguments." : "Research specific versions, protocols or behaviour. Search sources and AI analysis remain attached to their originating evidence.").wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(5);if rows.isEmpty{Text(stage == "Recon" ? "No recon runs yet. Choose an available tool to begin." : "No research runs yet. Supply a focused question based on recon evidence.").wixalFont(size:11).foregroundStyle(theme.muted)};ForEach(rows,id:\.selfID){run in runRow(run)};Button(stage == "Recon" ? "Prepare recon" : "Prepare research"){prepare()}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!engine.connected);if stage == "Research"{Button("Analyse collected evidence"){capability="analysis";stepName="Evidence analysis";prompt="Review the collected recon evidence. Identify unknowns and propose relevant research and prerequisite-based tests. Do not claim attack success.";dependency="";showPlan=true}.buttonStyle(WixalButtonStyle())}}
    }
    private var attackStage: some View {
        let rows=targetRuns.filter{textValue($0["stage"]) == "Attacks"}
        return VStack(alignment:.leading,spacing:20){HStack{Text("Attack plan").wixalFont(size:22,weight:.medium);Spacer();Button("Chain studio"){showStudio=true}.buttonStyle(WixalButtonStyle());Button("Add step"){prepare()}.buttonStyle(WixalButtonStyle(outlined:true))};Text("Independent steps can run together. Chained steps wait for successful execution of their prerequisite. Completion records evidence; it does not establish exploitation.").wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(5);if rows.isEmpty{VStack(alignment:.leading,spacing:12){Text("Build a test plan from research").wixalFont(size:14,weight:.medium);Text("Connect the available network checks, website probes or local simulations. Register installed tools as capabilities to extend the plan.").wixalFont(size:11).foregroundStyle(theme.muted);Button("Ask AI to review the evidence"){showAI=true;prompt="Review the recon and research evidence. Suggest testable hypotheses, their prerequisites and suitable next steps. Distinguish available checks from missing attack capabilities."}.buttonStyle(WixalButtonStyle())}.padding(18).wixalCard()};ForEach(rows,id:\.selfID){run in VStack(alignment:.leading,spacing:8){if !textValue(run["dependency"]).isEmpty{Label("After " + textValue(targetRuns.first{textValue($0["id"]) == textValue(run["dependency"])}?["name"]),systemImage:"arrow.turn.down.right").wixalFont(size:10).foregroundStyle(theme.muted)};runRow(run)}}}
    }
    private var resultsStage: some View {
        let rows=targetRuns.filter{["completed","failed","cancelled","interrupted","skipped"].contains(textValue($0["status"]))}
        return VStack(alignment:.leading,spacing:20){Text("Results & evidence").wixalFont(size:22,weight:.medium);if rows.isEmpty{Text("Completed, stopped and failed runs appear here with their evidence and limitations.").wixalFont(size:12).foregroundStyle(theme.muted)};ForEach(rows.reversed(),id:\.selfID){run in runRow(run)};let legacy=records(engine.state["assessmentResults"]).filter{textValue($0["projectId"]) == projectID};if !legacy.isEmpty{DisclosureGroup("Earlier project assessments · \(legacy.count)"){ForEach(Array(legacy.enumerated()),id:\.offset){_,item in Text(pretty(item)).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}}.wixalFont(size:11)}}
    }
    private func runRow(_ run:[String:Any])->some View {
        Button{selectedRun=textValue(run["id"])}label:{HStack(alignment:.top,spacing:16){VStack(alignment:.leading,spacing:6){Text(textValue(run["name"])).wixalFont(size:13,weight:.medium);Text(title(textValue(run["capability"])) + " · " + textValue(run["model"])).wixalFont(size:10).foregroundStyle(theme.muted);if let timestamp=run["created"] as? Double{Text(Date(timeIntervalSince1970:timestamp/1000),style:.date).wixalFont(size:10).foregroundStyle(theme.muted)}};Spacer();Text(textValue(run["status"]).replacingOccurrences(of:"_",with:" ").capitalized).wixalFont(size:10).foregroundStyle(theme.accent);Image(systemName:"chevron.right").font(.system(size:9))}.padding(.vertical,15).overlay(alignment:.bottom){Rectangle().fill(theme.line).frame(height:1)}}.buttonStyle(.plain)
    }
    private func runDetail(_ run:[String:Any])->some View {
        let result=run["result"] as? [String:Any] ?? [:]
        let report=result["report"] as? [String:Any] ?? result
        return VStack(alignment:.leading,spacing:18){Button("← Back to \(stage)"){selectedRun=""}.buttonStyle(.plain).foregroundStyle(theme.muted);Text(textValue(run["name"])).wixalFont(size:22,weight:.medium);HStack{Text("Execution: " + textValue(run["status"]));Spacer();if ["running","waiting_review","waiting_model","queued","blocked"].contains(textValue(run["status"])){Button("Stop run"){engine.action("security-run-stop",["id":run["id"] ?? ""])}.buttonStyle(WixalButtonStyle(outlined:true))}}.wixalFont(size:11);Text(textValue(run["outcome"])).wixalFont(size:11).foregroundStyle(theme.muted);if !textValue(run["error"]).isEmpty{Text(textValue(run["error"])).wixalFont(size:12).textSelection(.enabled)};if !textValue(result["analysis"]).isEmpty{Text(textValue(result["analysis"])).wixalFont(size:13).textSelection(.enabled).lineSpacing(5)};ForEach(Array(records(report["findings"]).enumerated()),id:\.offset){_,finding in VStack(alignment:.leading,spacing:8){Text(textValue(finding["title"])).wixalFont(size:14,weight:.medium);Text(textValue(finding["severity"]) + " · " + textValue(finding["confidence"])).wixalFont(size:10).foregroundStyle(theme.muted);Text(textValue(finding["remediation"])).wixalFont(size:12).textSelection(.enabled)}.padding(14).wixalCard()};if !textValue(result["coverage"]).isEmpty{Text("Coverage: " + textValue(result["coverage"]).replacingOccurrences(of:"_",with:" ")).wixalFont(size:11).foregroundStyle(theme.muted)};serviceResults(result);DisclosureGroup("Output & technical evidence"){Text(textValue(run["output"])).wixalFont(size:10,design:.monospaced).textSelection(.enabled);Text(pretty(run)).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}.wixalFont(size:11);Button("Open project evidence folder"){NSWorkspace.shared.open(URL(fileURLWithPath:engine.root))}.buttonStyle(WixalButtonStyle());Button("Retry or duplicate as draft"){duplicateRun(run)}.buttonStyle(WixalButtonStyle());Button("Discuss this evidence"){prompt="Explain the evidence from run " + textValue(run["name"]) + ". Separate observations and validated outcomes, and identify relevant next steps.";showAI=true}.buttonStyle(WixalButtonStyle())}
    }
    private var aiPanel: some View {
        VStack(alignment:.leading,spacing:12){Divider().overlay(theme.line);HStack{Text("AI investigation").wixalFont(size:14,weight:.medium);Spacer();Text(model).wixalFont(size:10).foregroundStyle(theme.muted)};Text("Context: selected target and compact evidence from completed runs. Choose source runs when preparing analysis.").wixalFont(size:10).foregroundStyle(theme.muted);TextEditor(text:$prompt).frame(height:90).padding(8).background(theme.panel).overlay(RoundedRectangle(cornerRadius:7).stroke(theme.line));Button("Analyse & discuss"){capability="analysis";stepName="AI discussion";dependency="";showPlan=true}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(model.isEmpty || prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || !engine.connected)}
    }
    private var executionBar: some View {
        VStack(spacing:0){Divider().overlay(theme.line);HStack{Button{showRuns.toggle()}label:{Label("\(busyRuns.count) active · \(allRuns.filter{textValue($0["status"]) == "completed"}.count) completed",systemImage:showRuns ? "chevron.down" : "chevron.up")}.buttonStyle(.plain);Spacer();if showRuns{Picker("Parallel slots",selection:Binding(get:{queue["limit"] as? Int ?? 2},set:{engine.action("security-queue-settings",["limit":$0])})){ForEach(1...4,id:\.self){Text("\($0)").tag($0)}}.frame(width:145);Button(paused ? "Resume queue" : "Pause queue"){engine.action("security-queue-settings",["paused":!paused])}.buttonStyle(WixalButtonStyle())}}.wixalFont(size:11).padding(14);if showRuns{ScrollView{VStack(spacing:0){if busyRuns.isEmpty{Text("No active runs. Prepare a step in the selected investigation.").foregroundStyle(theme.muted).padding(16)};ForEach(busyRuns,id:\.selfID){run in HStack{Button{selected=textValue(run["targetId"]);stage=textValue(run["stage"]);selectedRun=textValue(run["id"])}label:{VStack(alignment:.leading,spacing:4){Text(textValue(run["name"]));Text(textValue(run["address"])+" · "+textValue(run["model"])).wixalFont(size:10).foregroundStyle(theme.muted)}}.buttonStyle(.plain);Spacer();Text(textValue(run["status"])).foregroundStyle(theme.accent);Button("Stop"){engine.action("security-run-stop",["id":run["id"] ?? ""])}.buttonStyle(WixalButtonStyle())}.padding(.horizontal,16).padding(.vertical,8)}}}.frame(maxHeight:170).wixalFont(size:11)}}.background(theme.panel)
    }
    private var targetSheet: some View {
        VStack(alignment:.leading,spacing:18){Text("Add investigation target").wixalFont(size:22,weight:.medium);Picker("Type",selection:$type){ForEach(types,id:\.self){Text($0)}};TextField(type == "Software" ? "Project-relative software path" : "URL, host or private subnet",text:$address).wixalField();TextField("Investigation objective",text:$objective).wixalField();Picker("Parent target",selection:$parent){Text("None").tag("");ForEach(targets,id:\.selfID){item in Text(textValue(item["address"])).tag(textValue(item["id"]))}};Text("Targets and runs stay in this project. Network discovery supports private IPv4 /24–/32 subnets. Software paths must be inside the project.").wixalFont(size:11).foregroundStyle(theme.muted);if !localError.isEmpty{Text(localError).foregroundStyle(theme.accent)};HStack{Button("Cancel"){showTarget=false};Spacer();Button(submitting ? "Adding…" : "Add target"){addTarget()}.disabled(submitting || address.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)}}.padding(26).frame(width:520).foregroundStyle(theme.text).background(theme.background)
    }
    private var planSheet: some View {
        VStack(alignment:.leading,spacing:16){Text("Prepare \(stage.lowercased()) step").wixalFont(size:22,weight:.medium);Text(textValue(target?["address"])).wixalFont(size:12,design:.monospaced).textSelection(.enabled);ScrollView{VStack(alignment:.leading,spacing:14){TextField("Step name",text:$stepName).wixalField();Picker("Capability",selection:$capability){ForEach(availableCapabilities,id:\.self){Text(title($0)).tag($0)}}.onChange(of:capability){_,value in if value == "network_discover"{coverage="selected";inspectDiscovered=false;profile="services";if let url=URL(string:textValue(target?["address"])),["http","https"].contains(url.scheme ?? ""){ports=String(url.port ?? (url.scheme == "https" ? 443 : 80))}}else if value == "website_assess"{profile="baseline"}else if value == "network_scan"{profile=textValue(target?["type"]) == "Network" ? "discovery" : "services"}};if capability == "network_discover"{discoveryControls};if capability == "network_scan"{Picker("Scan profile",selection:$profile){ForEach(["discovery","ports","services","web","tls","ssh","enumeration","checks"],id:\.self){Text($0.capitalized)}}.onChange(of:profile){_,p in ports=p == "ssh" ? "22" : p == "tls" ? "443,8443" : ["web","enumeration","checks"].contains(p) ? "80,443,8080,8443" : "22,80,443,8080,8443"};if profile != "discovery"{TextField("TCP ports",text:$ports).wixalField()};Text("\(profile) · fixed Nmap profile · 180 second limit. TLS and enumeration make repeated connections.").wixalFont(size:10).foregroundStyle(theme.muted)};if capability == "website_assess"{Picker("Website profile",selection:$profile){Text("Headers & protected paths").tag("baseline");Text("Bounded unauthenticated probes").tag("probes")};Text("Same-origin GET observations; up to 12 pages. Saves reviewed JSON and Markdown reports.").wixalFont(size:10).foregroundStyle(theme.muted)};if capability == "website_simulate"{Text("Disposable local fixtures only. This does not attack the selected live target.").wixalFont(size:11).foregroundStyle(theme.accent)};if ["research","analysis","planner"].contains(capability){Text(capability == "research" ? "Research query" : "Analysis instructions").wixalFont(size:11);TextEditor(text:$prompt).frame(height:100).overlay(RoundedRectangle(cornerRadius:7).stroke(theme.line));Text("Research searches the web and retains returned source links. AI analysis uses the selected model and completed target evidence. Model inference is serialised; independent scanner runs can execute in parallel.").wixalFont(size:10).foregroundStyle(theme.muted)};if capability == "research"{TextField("Optional source URLs, one per line (up to three)",text:$researchURLs,axis:.vertical).wixalField()};if capability.hasPrefix("contract:"){Text("Capability arguments (JSON)").wixalFont(size:11);TextEditor(text:$customArguments).frame(height:90).wixalFont(size:11,design:.monospaced)};if ["research","analysis","planner"].contains(capability){DisclosureGroup("Evidence selection"){Toggle("Use selected completed runs",isOn:$useSelectedEvidence);if useSelectedEvidence{ForEach(targetRuns.filter{textValue($0["status"]) == "completed"},id:\.selfID){r in let id=textValue(r["id"]);Toggle(textValue(r["name"]),isOn:Binding(get:{selectedEvidence.contains(id)},set:{if $0{selectedEvidence.insert(id)}else{selectedEvidence.remove(id)}}))}}}};if let chosenCapability,chosenCapability["available"] as? Bool == false{Text("Unavailable: enable " + (chosenCapability["missing"] as? [String] ?? []).joined(separator:", ")).foregroundStyle(theme.accent)};Picker("Run after",selection:$dependency){Text("Independent step").tag("");ForEach(targetRuns,id:\.selfID){r in Text(textValue(r["name"]) + " · " + textValue(r["status"])).tag(textValue(r["id"]))}};Text("Dependent steps require completed execution. Failed, stopped or interrupted prerequisites keep the step blocked. Only chain steps whose required evidence you have established.").wixalFont(size:10).foregroundStyle(theme.muted);Text("Assigned model: " + (model.isEmpty ? "None (manual tool execution)" : model)).wixalFont(size:11);if !localError.isEmpty{Text(localError).foregroundStyle(theme.accent)}}};HStack{Button("Cancel"){showPlan=false};Spacer();Button(submitting ? "Queuing…" : "Queue step"){queueStep()}.disabled(submitting || !engine.connected || (["research","analysis","planner"].contains(capability) && (model.isEmpty || prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)) || (useSelectedEvidence && selectedEvidence.isEmpty && ["research","analysis","planner"].contains(capability)) || (chosenCapability?["available"] as? Bool == false) || (capability == "network_scan" && nmap != true))}.buttonStyle(WixalButtonStyle(outlined:true));Text("Actions follow this project's approval setting. Disabled tools remain disabled.").wixalFont(size:10).foregroundStyle(theme.muted)}.padding(26).frame(width:580,height:650).foregroundStyle(theme.text).background(theme.background)
    }
    private var discoveryControls: some View {
        VStack(alignment:.leading,spacing:12) {
            Picker("Coverage",selection:$coverage) { Text("Selected TCP ports").tag("selected");Text("All TCP ports (1–65535)").tag("all_tcp") }
            if coverage == "selected" { TextField("TCP ports",text:$ports).wixalField() }
            Text(coverage == "all_tcp" ? "65,535 ports per resolved address, with up to two attempts per port." : "Only the selected ports are attempted, with up to two attempts per port.").wixalFont(size:11).foregroundStyle(theme.muted)
            Picker("Pace",selection:$pace) { Text("Careful (32 concurrent sockets)").tag("careful");Text("Balanced (128 concurrent sockets)").tag("balanced") }
            Stepper("Overall deadline: \(discoveryDeadline) seconds",value:$discoveryDeadline,in:10...600,step:10)
            Toggle("Inspect discovered ports with Nmap",isOn:$inspectDiscovered).disabled(nmap != true)
            if inspectDiscovered { Picker("Inspection profile",selection:$profile) { ForEach(["services","ports","web","tls","ssh"],id:\.self) { Text($0.capitalized) } } }
            Text("Discovery records observed open ports. Service identities come from a separate inspection. Each stage follows project review settings.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
    }
    private func serviceResults(_ result:[String:Any])->some View {
        let services=records(result["services"])
        return VStack(alignment:.leading,spacing:12){if !services.isEmpty{Text("Observed services").wixalFont(size:14,weight:.medium);ForEach(Array(services.enumerated()),id:\.offset){_,row in let service=row["service"] as? [String:Any] ?? [:];HStack(alignment:.top){Text(textValue(row["port"])+"/"+textValue(row["protocol"])).wixalFont(size:11,design:.monospaced).frame(width:85,alignment:.leading);VStack(alignment:.leading,spacing:5){Text([textValue(service["name"]),textValue(service["product"]),textValue(service["version"])].filter{!$0.isEmpty}.joined(separator:" · "));Text(textValue(row["host"])).foregroundStyle(theme.muted)};Spacer();Text(textValue(row["state"])).foregroundStyle(theme.accent)}.wixalFont(size:11).padding(.vertical,6)}}}
    }
    private func loadCapabilities() async {guard engine.connected,!selected.isEmpty else{return};do{capabilities=records(try await engine.call("security-capabilities",["targetId":selected]))}catch{localError=error.localizedDescription}}
    private func startInvestigation(){guard !model.isEmpty else{localError="Choose a model for the AI investigation";return};Task{do{_=try await engine.call("security-investigate",["targetId":selected,"model":model]);showRuns=true}catch{localError=error.localizedDescription}}}
    private func exportReport(){Task{do{let result=try await engine.call("security-report-export",["targetId":selected]) as? [String:Any] ?? [:];if let path=(result["paths"] as? [String])?.first{NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath:path)])}}catch{localError=error.localizedDescription}}}
    private func duplicateRun(_ run:[String:Any]){Task{do{_=try await engine.call("security-run-copy",["id":run["id"] ?? ""]);showStudio=true}catch{localError=error.localizedDescription}}}
    private func repairSelection(){if target == nil{selected=textValue(targets.first?["id"])}}
    private func readiness() async {guard engine.connected else{return};do{let r=try await engine.call("security-readiness") as? [String:Any] ?? [:];nmap=r["installed"] as? Bool}catch{nmap=nil}}
    private func prepare(){localError="";researchURLs="";customArguments="{}";useSelectedEvidence=false;dependency="";stepName=stage == "Attacks" ? "Validation check" : stage + " assessment";prompt="";capability=stage == "Research" ? "research" : textValue(target?["type"]) == "Software" ? "software_inventory" : textValue(target?["type"]) == "Website / API" ? "website_assess" : "network_scan";profile=textValue(target?["type"]) == "Network" ? "discovery" : "services";if capability == "analysis"{prompt="Analyse the supplied software evidence and identify what information is needed next."};showPlan=true}
    private func addTarget(){submitting=true;localError="";Task{defer{submitting=false};do{let t=try await engine.call("security-target-add",["type":type,"address":address,"objective":objective,"parentId":parent]) as? [String:Any] ?? [:];selected=textValue(t["id"]);stage="Recon";showTarget=false;address="";objective="";parent=""}catch{localError=error.localizedDescription}}}
    private func queueStep(){submitting=true;localError="";var args:[String:Any]=[:];if capability == "network_scan"{args=["profile":profile,"ports":ports,"timeout_seconds":180]};if capability == "network_discover"{args=["coverage":coverage,"pace":pace,"timeout_seconds":discoveryDeadline];if coverage == "selected"{args["ports"]=ports}};if capability == "website_assess"{args=["profile":["baseline","probes"].contains(profile) ? profile : "baseline","max_pages":12]};if capability == "research"{args=["urls":researchURLs.split(separator:"\n").map(String.init).filter{!$0.isEmpty}]};if capability.hasPrefix("contract:"){guard let data=customArguments.data(using:.utf8),let parsed=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else{localError="Arguments must be a JSON object";submitting=false;return};args=parsed};Task{defer{submitting=false};do{if capability == "network_discover"{_=try await engine.call("security-discover-inspect",["targetId":selected,"arguments":args,"inspect":inspectDiscovered,"profile":profile]);showPlan=false;showRuns=true;return};let run=try await engine.call("security-run-add",["targetId":selected,"stage":stage,"capability":capability,"name":stepName,"model":model,"prompt":prompt,"arguments":args,"dependency":dependency,"evidenceIds":useSelectedEvidence ? Array(selectedEvidence) : []]) as? [String:Any] ?? [:];selectedRun=textValue(run["id"]);showPlan=false;showRuns=true}catch{localError=error.localizedDescription}}}
}

private extension Dictionary where Key == String, Value == Any {
    var selfID: String { textValue(self["id"]) }
    var nameID: String { textValue(self["name"]) }
}
