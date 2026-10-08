import SwiftUI
import AppKit

struct SecurityRecordDesk: View {
    @ObservedObject var engine: EngineClient
    let targetID: String
    let section: String
    @Environment(\.wixalTheme) private var theme
    @ViewState private var search = ""
    private var collection: String {
        ["Inventory":"securityDiscoveries","Findings":"securityFindings","Sources":"securityResearch","History":"securityEvents"][section] ?? "securityDiscoveries"
    }
    private var rows: [[String:Any]] {
        records(engine.state[collection]).filter {
            textValue($0["targetId"]) == targetID && (search.isEmpty || pretty($0).localizedCaseInsensitiveContains(search))
        }.reversed()
    }
    var body: some View {
        VStack(alignment:.leading,spacing:18) {
            Text(section).wixalFont(size:22,weight:.medium)
            TextField("Search " + section.lowercased(),text:$search).wixalField()
            if rows.isEmpty { Text("No matching records yet. Completed assessments populate this view.").foregroundStyle(theme.muted) }
            ForEach(Array(rows.enumerated()),id:\.offset) { _, row in
                if section == "Findings" { SecurityFindingCard(engine:engine,row:row) }
                else if section == "Sources" { SecuritySourceCard(engine:engine,row:row) }
                else if section == "Inventory" { inventoryCard(row) }
                else { VStack(alignment:.leading,spacing:8) {
                    Text(textValue(row["action"]).replacingOccurrences(of:"_",with:" ")).wixalFont(size:13,weight:.medium)
                    Text(pretty(row["detail"] ?? [:])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)
                }.padding(14).wixalCard() }
            }
        }.wixalFont(size:12)
    }
    private func observationSummary(_ row:[String:Any])->String {
        let values=row["values"] as? [String:Any] ?? [:]
        switch textValue(row["kind"]) {
        case "service":
            let service=values["service"] as? [String:Any] ?? [:]
            return [textValue(values["state"]),textValue(service["name"]),textValue(service["product"]),textValue(service["version"])].filter{!$0.isEmpty}.joined(separator:" · ")
        case "route":return "HTTP " + String(describing:values["status"] ?? "unknown") + " · " + textValue(values["contentType"])
        case "component":return textValue(values["name"]) + " · " + textValue(values["version"]) + "\n" + textValue(values["confidence"])
        case "input":return textValue(values["method"]) + " " + textValue(values["action"]) + "\nFields: " + records(values["fields"]).map{textValue($0["name"])}.joined(separator:", ")
        default:return textValue(values["address"]) + " · " + textValue(values["confidence"])
        }
    }
    private func inventoryCard(_ row:[String:Any]) -> some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                Text(textValue(row["key"])).wixalFont(size:14,weight:.medium).textSelection(.enabled)
                Spacer()
                Text(textValue(row["change"])).foregroundStyle(theme.accent)
            }
            Text(textValue(row["kind"]) + (row["simulation"] as? Bool == true ? " · Simulation" : " · Observed evidence")).foregroundStyle(theme.muted)
            Text(observationSummary(row)).textSelection(.enabled)
            DisclosureGroup("Technical evidence"){Text(pretty(row["values"] ?? [:])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}
            DisclosureGroup("Observation history · \(records(row["observations"]).count)") {
                ForEach(Array(records(row["observations"]).enumerated()),id:\.offset) { _, observation in
                    Text("Run " + textValue(observation["runId"]) + "\n" + pretty(observation["values"] ?? [:])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)
                }
            }
            if textValue(row["kind"]) == "host" && row["simulation"] as? Bool != true {
                Button("Create device target") { engine.action("security-discovery-promote",["id":row["id"] ?? ""]) }.buttonStyle(WixalButtonStyle(outlined:true))
            }
        }.padding(16).wixalCard()
    }
}

struct SecurityFindingCard: View {
    @ObservedObject var engine: EngineClient
    let row:[String:Any]
    @Environment(\.wixalTheme) private var theme
    @ViewState private var notes = ""
    @ViewState private var status = "unreviewed"
    private let statuses=["unreviewed","confirmed","false_positive","resolved","accepted_risk","inconclusive"]
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            Text(textValue(row["title"])).wixalFont(size:15,weight:.medium)
            Text(textValue(row["severity"]) + " · " + textValue(row["confidence"]) + (row["simulation"] as? Bool == true ? " · Simulation" : "")).foregroundStyle(theme.muted)
            Text(String(describing:row["evidence"] ?? "")).textSelection(.enabled)
            Text(textValue(row["remediation"])).textSelection(.enabled)
            if row["needsReview"] as? Bool == true {Text("Observed again after resolution · review the retest evidence").foregroundStyle(theme.accent)}
            DisclosureGroup("Review & provenance") {
                Picker("Finding status",selection:$status) { ForEach(statuses,id:\.self) { Text($0.replacingOccurrences(of:"_",with:" ")).tag($0) } }
                TextField("Review notes and supporting evidence",text:$notes,axis:.vertical).wixalField()
                Button("Save review") { engine.action("security-finding-update",["id":row["id"] ?? "","status":status,"notes":notes]) }.buttonStyle(WixalButtonStyle(outlined:true))
                Text("Source runs: " + (row["runIds"] as? [String] ?? []).joined(separator:", ")).wixalFont(size:10,design:.monospaced).textSelection(.enabled)
            }
        }.wixalFont(size:12).padding(16).wixalCard()
        .task { notes=textValue(row["notes"]);status=textValue(row["status"]) }
    }
}

struct SecuritySourceCard: View {
    @ObservedObject var engine: EngineClient
    let row:[String:Any]
    @Environment(\.wixalTheme) private var theme
    @ViewState private var applicability="needs_evidence"
    @ViewState private var rationale=""
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            if let url=URL(string:textValue(row["url"])) { Link(textValue(row["url"]),destination:url).textSelection(.enabled) }
            Text(row["error"] == nil ? "Retrieved source · Review applicability" : textValue(row["error"])).foregroundStyle(theme.muted)
            DisclosureGroup("Source content and applicability") {
                Text(textValue(row["content"])).wixalFont(size:11).textSelection(.enabled)
                if row["truncated"] as? Bool == true { Text("Source excerpt is truncated.").foregroundStyle(theme.muted) }
                Picker("Applicability",selection:$applicability) {
                    ForEach(["needs_evidence","possibly_relevant","applicable","not_applicable"],id:\.self) { Text($0.replacingOccurrences(of:"_",with:" ")).tag($0) }
                }
                TextField("Version/configuration evidence and rationale",text:$rationale,axis:.vertical).wixalField()
                Button("Save applicability") { engine.action("security-research-update",["id":row["id"] ?? "","applicability":applicability,"rationale":rationale]) }.buttonStyle(WixalButtonStyle(outlined:true))
                Text("Source run: " + textValue(row["runId"]) + "\nExcerpt SHA-256: " + textValue(row["contentSHA256"])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)
            }
        }.wixalFont(size:12).padding(16).wixalCard()
        .task { applicability=textValue(row["applicability"]);rationale=textValue(row["rationale"]) }
    }
}

struct SecurityTargetEditor:View {
    @ObservedObject var engine:EngineClient
    let target:[String:Any]
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var objective=""
    @ViewState private var notes=""
    @ViewState private var archived=false
    @ViewState private var models:[String:String]=[:]
    @ViewState private var error=""
    var body: some View {
        VStack(alignment:.leading,spacing:18) {
            Text("Investigation settings").wixalFont(size:22,weight:.medium)
            Text(textValue(target["address"])).textSelection(.enabled)
            ScrollView {
                VStack(alignment:.leading,spacing:14) {
                    TextField("Objective",text:$objective,axis:.vertical).wixalField()
                    TextField("Investigation notes",text:$notes,axis:.vertical).wixalField()
                    ForEach(["default","Recon","Research","Attacks"],id:\.self) { role in
                        Picker(role == "default" ? "Default model" : role + " model",selection:Binding(get:{models[role] ?? ""},set:{models[role]=$0})) {
                            Text("Use default").tag("")
                            ForEach(engine.models,id:\.securityModelID) { Text(textValue($0["name"])).tag(textValue($0["name"])) }
                        }
                    }
                    Toggle("Archive target",isOn:$archived)
                    Text("The address stays fixed to preserve evidence provenance. Add a new target for a different address. Archived targets can be restored.").wixalFont(size:11).foregroundStyle(theme.muted)
                    if !error.isEmpty { Text(error).foregroundStyle(theme.accent) }
                }
            }
            HStack { Button("Cancel",action:close);Spacer();Button("Save") {
                Task { do { _=try await engine.call("security-target-update",["id":target["id"] ?? "","objective":objective,"notes":notes,"archived":archived,"models":models]);close() } catch { self.error=error.localizedDescription } }
            }.buttonStyle(WixalButtonStyle(outlined:true)) }
        }.padding(26).frame(width:540,height:570).foregroundStyle(theme.text).background(theme.background)
        .task { objective=textValue(target["objective"]);notes=textValue(target["notes"]);archived=target["archived"] as? Bool ?? false;models=target["models"] as? [String:String] ?? [:] }
    }
}

struct SecurityPlanStudio:View {
    @ObservedObject var engine:EngineClient
    let targetID:String
    let model:String
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var selected=""
    @ViewState private var name="New test plan"
    @ViewState private var nodes:[[String:Any]]=[]
    @ViewState private var editor=""
    @ViewState private var error=""
    @ViewState private var working=false
    @ViewState private var selectedNode=""
    @ViewState private var advanced=false
    private var plans:[[String:Any]] { records(engine.state["securityPlans"]).filter{textValue($0["targetId"]) == targetID} }
    private var templates:[[String:Any]] { records(engine.state["securityTemplates"]).filter{textValue($0["projectId"]) == textValue(engine.state["activeProject"])} }
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack { Text("Chain studio").wixalFont(size:23,weight:.medium);Spacer();Button("Done",action:close) }
            HStack(alignment:.top,spacing:20) {
                VStack(alignment:.leading,spacing:12) {
                    Button("New plan") { selected="";name="New test plan";nodes=[];editor="[]" }
                    ScrollView {
                        VStack(alignment:.leading,spacing:12) {
                            ForEach(plans,id:\.securityRecordID) { plan in
                                Button { selected=textValue(plan["id"]);name=textValue(plan["name"]);nodes=records(plan["nodes"]);editor=pretty(nodes) } label:{
                                    VStack(alignment:.leading,spacing:5) { Text(textValue(plan["name"]));Text(textValue(plan["status"])).foregroundStyle(theme.muted) }.frame(maxWidth:.infinity,alignment:.leading)
                                }.buttonStyle(.plain)
                            }
                            Divider()
                            Text("Reusable templates").foregroundStyle(theme.muted)
                            ForEach(templates,id:\.securityRecordID) { template in
                                Button(textValue(template["name"])) { perform("security-template-apply",["id":template["id"] ?? "","targetId":targetID]) }
                            }
                        }
                    }
                }.frame(width:170)
                Divider()
                VStack(alignment:.leading,spacing:14) {
                    TextField("Plan name",text:$name).wixalField()
                    if plans.first(where:{textValue($0["id"]) == selected})?["reviewRequired"] as? Bool == true {Text("AI proposal · verify steps and evidence before running").wixalFont(size:11).foregroundStyle(theme.muted)}
                    SecurityChainGraph(nodes:nodes).frame(height:150)
                    HStack {
                        Menu("Add step") {
                            ForEach(["network_scan","website_assess","software_inventory","research","analysis","website_simulate"],id:\.self) { capability in
                                Button(capability.replacingOccurrences(of:"_",with:" ")) {
                                    nodes.append(["id":"step-"+String(UUID().uuidString.prefix(6)),"name":capability.replacingOccurrences(of:"_",with:" "),"stage":capability == "research" || capability == "analysis" ? "Research" : "Recon","capability":capability,"arguments":[:],"prompt":capability == "research" || capability == "analysis" ? "Review the collected evidence" : "","dependencies":nodes.last.map{[textValue($0["id"])]} ?? []])
                                    editor=pretty(nodes);selectedNode=textValue(nodes.last?["id"])
                                }
                            }
                        }
                        Button("Remove selected step") {nodes.removeAll{textValue($0["id"]) == selectedNode};selectedNode="";editor=pretty(nodes)}.disabled(selectedNode.isEmpty)
                        Spacer()
                        Button("Duplicate as draft") { selected="" }
                    }.buttonStyle(WixalButtonStyle())
                    Text("Select a step to edit it. Multiple prerequisites create joins; independent steps can run together.").wixalFont(size:11).foregroundStyle(theme.muted)
                    Picker("Edit step",selection:$selectedNode) {
                        Text("Choose a step").tag("")
                        ForEach(nodes,id:\.securityRecordID){node in Text(textValue(node["name"])).tag(textValue(node["id"]))}
                    }
                    if let index=nodes.firstIndex(where:{textValue($0["id"]) == selectedNode}) {
                        SecurityPlanNodeEditor(engine:engine,nodes:$nodes,index:index,targetID:targetID)
                    } else {Text("Add or select a step to edit its capability, arguments and prerequisites.").foregroundStyle(theme.muted).frame(maxHeight:.infinity)}
                    DisclosureGroup("Advanced plan JSON",isExpanded:$advanced) {
                        TextEditor(text:$editor).wixalFont(size:10,design:.monospaced).frame(height:100)
                        Button("Apply JSON"){if parseEditor(){advanced=false}}
                    }
                    DisclosureGroup("Condition examples") {
                        Text("{\"kind\":\"service_open\",\"value\":\"443\"}\n{\"kind\":\"http_status\",\"value\":\"200\"}\n{\"kind\":\"finding_present\",\"value\":\"frame-protection\"}\nA condition that does not match skips the branch. Dependencies must belong to this plan.").wixalFont(size:10,design:.monospaced).textSelection(.enabled)
                    }
                    if !error.isEmpty { Text(error).wixalFont(size:11).foregroundStyle(theme.accent).textSelection(.enabled) }
                    HStack {
                        Button("Save draft") { save(false,false) }
                        Button("Save template") { save(true,false) }
                        if let plan=plans.first(where:{textValue($0["id"]) == selected}),["running","blocked"].contains(textValue(plan["status"])) {Button("Stop plan"){engine.action("security-plan-stop",["id":selected])}}
                        Spacer()
                        Button("Run plan") { save(false,true) }.disabled(working)
                    }.buttonStyle(WixalButtonStyle(outlined:true))
                }
            }
        }.padding(24).frame(width:940,height:730).foregroundStyle(theme.text).background(theme.background)
        .task { if let plan=plans.last { selected=textValue(plan["id"]);name=textValue(plan["name"]);nodes=records(plan["nodes"]);editor=pretty(nodes) } else {editor="[]"} }
    }
    @discardableResult private func parseEditor()->Bool {
        do { guard let data=editor.data(using:.utf8),let value=try JSONSerialization.jsonObject(with:data) as? [[String:Any]] else { throw NSError(domain:"Plan",code:1,userInfo:[NSLocalizedDescriptionKey:"Enter an array of plan steps"]) };nodes=value;error="";return true }
        catch {self.error=error.localizedDescription;return false}
    }
    private func save(_ template:Bool,_ run:Bool) {
        if advanced {guard parseEditor() else{return}} else {editor=pretty(nodes)}
        working=true;error=""
        Task { defer{working=false};do {
            var params:[String:Any]=["targetId":targetID,"name":name,"nodes":nodes]
            if !template && !selected.isEmpty {
                let existing=plans.first{textValue($0["id"]) == selected}
                if textValue(existing?["status"]) != "draft" { selected="" } else {params["id"]=selected}
            }
            let value=try await engine.call(template ? "security-template-save" : "security-plan-save",params) as? [String:Any] ?? [:]
            if !template { selected=textValue(value["id"]);nodes=records(value["nodes"]);editor=pretty(nodes) }
            if run { _=try await engine.call("security-plan-run",["id":selected,"model":model]);close() }
        } catch {self.error=error.localizedDescription} }
    }
    private func perform(_ method:String,_ params:[String:Any]) {
        Task {do {let plan=try await engine.call(method,params) as? [String:Any] ?? [:];selected=textValue(plan["id"]);name=textValue(plan["name"]);nodes=records(plan["nodes"]);editor=pretty(nodes)}catch{self.error=error.localizedDescription}}
    }
}

struct SecurityPlanNodeEditor:View {
    @ObservedObject var engine:EngineClient
    @Binding var nodes:[[String:Any]]
    let index:Int
    let targetID:String
    @Environment(\.wixalTheme) private var theme
    @ViewState private var boundDiscovery=""
    @ViewState private var arguments=""
    @ViewState private var error=""
    private var id:String {index<nodes.count ? textValue(nodes[index]["id"]) : ""}
    private func field(_ key:String)->Binding<String> {Binding(get:{index<nodes.count ? textValue(nodes[index][key]) : ""},set:{if index<nodes.count{nodes[index][key]=$0}})}
    private var conditionKind:Binding<String> {Binding(get:{textValue((nodes[index]["condition"] as? [String:Any])?["kind"])},set:{value in if value.isEmpty{nodes[index].removeValue(forKey:"condition")}else{var row=nodes[index]["condition"] as? [String:Any] ?? [:];row["kind"]=value;row["value"]=row["value"] ?? "";nodes[index]["condition"]=row}})}
    private var conditionValue:Binding<String> {Binding(get:{String(describing:(nodes[index]["condition"] as? [String:Any])?["value"] ?? "")},set:{var row=nodes[index]["condition"] as? [String:Any] ?? [:];row["value"]=$0;nodes[index]["condition"]=row})}
    var body:some View {
        ScrollView {
            VStack(alignment:.leading,spacing:12) {
                TextField("Step name",text:field("name")).wixalField()
                HStack {
                    Picker("Stage",selection:field("stage")) {ForEach(["Recon","Research","Attacks"],id:\.self){Text($0).tag($0)}}
                    Picker("Capability",selection:field("capability")) {
                        ForEach(["network_scan","website_assess","software_inventory","research","analysis","website_simulate"],id:\.self){Text($0.replacingOccurrences(of:"_",with:" ")).tag($0)}
                        ForEach(records(engine.state["securityContracts"]).filter{textValue($0["projectId"]) == textValue(engine.state["activeProject"])},id:\.securityRecordID){row in Text(textValue(row["name"])).tag(textValue(row["id"]))}
                    }
                }
                Picker("Step model",selection:field("model")) {
                    Text("Use investigation model").tag("")
                    ForEach(engine.models,id:\.securityModelID){Text(textValue($0["name"])).tag(textValue($0["name"]))}
                }
                TextField("Why this step",text:field("reason"),axis:.vertical).wixalField()
                TextField("Analysis or research instructions",text:field("prompt"),axis:.vertical).wixalField()
                DisclosureGroup("Prerequisites") {
                    ForEach(nodes.filter{textValue($0["id"]) != id},id:\.securityRecordID) {other in
                        let otherID=textValue(other["id"])
                        Toggle(textValue(other["name"]),isOn:Binding(get:{(nodes[index]["dependencies"] as? [String] ?? []).contains(otherID)},set:{enabled in var deps=nodes[index]["dependencies"] as? [String] ?? [];deps.removeAll{$0==otherID};if enabled{deps.append(otherID)};nodes[index]["dependencies"]=deps}))
                    }
                }
                Picker("Required evidence",selection:conditionKind) {
                    Text("No additional condition").tag("")
                    Text("Open service port").tag("service_open")
                    Text("HTTP status").tag("http_status")
                    Text("Finding identifier").tag("finding_present")
                }
                if !conditionKind.wrappedValue.isEmpty {TextField("Required value",text:conditionValue).wixalField()}
                if textValue(nodes[index]["capability"]) == "network_scan" {
                    Picker("Bind TCP port to discovery",selection:$boundDiscovery) {
                        Text("Enter ports manually").tag("")
                        ForEach(records(engine.state["securityDiscoveries"]).filter{textValue($0["targetId"]) == targetID && textValue($0["kind"]) == "service"},id:\.securityRecordID) {row in Text(textValue(row["key"])).tag(textValue(row["id"]))}
                    }.onChange(of:boundDiscovery){_,value in if value.isEmpty{nodes[index].removeValue(forKey:"bindings")}else{nodes[index]["bindings"]=["ports":["discoveryId":value,"field":"port"]]}}
                }
                DisclosureGroup("Tool arguments") {
                    TextEditor(text:$arguments).wixalFont(size:10,design:.monospaced).frame(height:85)
                    Button("Apply arguments"){
                        do {guard let data=arguments.data(using:.utf8),let row=try JSONSerialization.jsonObject(with:data) as? [String:Any] else{throw NSError(domain:"Arguments",code:1,userInfo:[NSLocalizedDescriptionKey:"Enter a JSON object"])};nodes[index]["arguments"]=row;error=""}catch{self.error=error.localizedDescription}
                    }
                    if !error.isEmpty {Text(error).foregroundStyle(theme.accent)}
                }
            }.wixalFont(size:11)
        }.frame(minHeight:200)
        .task(id:id){boundDiscovery=textValue(((nodes[index]["bindings"] as? [String:Any])?["ports"] as? [String:Any])?["discoveryId"]);arguments=pretty(index<nodes.count ? nodes[index]["arguments"] ?? [:] : [:]);error=""}
    }
}

private struct SecurityGraphPlacement:Identifiable {
    let id:String
    let row:[String:Any]
    let point:CGPoint
}
struct SecurityChainGraph:View {
    let nodes:[[String:Any]]
    @Environment(\.wixalTheme) private var theme
    private var placements:[SecurityGraphPlacement] {
        func level(_ id:String,_ visited:Set<String>)->Int {
            guard !visited.contains(id),let node=nodes.first(where:{textValue($0["id"]) == id}) else{return 0}
            let deps=node["dependencies"] as? [String] ?? []
            return deps.isEmpty ? 0 : 1 + (deps.map{level($0,visited.union([id]))}.max() ?? 0)
        }
        var counts:[Int:Int]=[:]
        return nodes.map {node in
            let id=textValue(node["id"]);let column=level(id,[])
            let position=counts[column] ?? 0;counts[column]=position+1
            return SecurityGraphPlacement(id:id,row:node,point:CGPoint(x:110+column*235,y:55+position*112))
        }
    }
    var body:some View {
        let layout=placements
        let width=(layout.map{$0.point.x}.max() ?? 110)+115
        let height=(layout.map{$0.point.y}.max() ?? 55)+60
        ScrollView([.horizontal,.vertical]) {
            ZStack(alignment:.topLeading) {
                Canvas {context,_ in
                    for item in layout {
                        for dependency in item.row["dependencies"] as? [String] ?? [] {
                            guard let parent=layout.first(where:{$0.id==dependency}) else{continue}
                            let start=CGPoint(x:parent.point.x+95,y:parent.point.y)
                            let end=CGPoint(x:item.point.x-95,y:item.point.y)
                            var path=Path();path.move(to:start)
                            path.addCurve(to:end,control1:CGPoint(x:start.x+22,y:start.y),control2:CGPoint(x:end.x-22,y:end.y))
                            context.stroke(path,with:.color(theme.accent.opacity(0.7)),lineWidth:1.5)
                            var arrow=Path();arrow.move(to:CGPoint(x:end.x-5,y:end.y-4));arrow.addLine(to:end);arrow.addLine(to:CGPoint(x:end.x-5,y:end.y+4))
                            context.stroke(arrow,with:.color(theme.accent),lineWidth:1.5)
                        }
                    }
                }.frame(width:width,height:height)
                ForEach(layout){item in
                    VStack(alignment:.leading,spacing:6) {
                        Text(textValue(item.row["name"])).wixalFont(size:12,weight:.medium).lineLimit(2)
                        Text(textValue(item.row["stage"]) + " · " + textValue(item.row["capability"])).wixalFont(size:9).foregroundStyle(theme.muted).lineLimit(1)
                        if let condition=item.row["condition"] as? [String:Any],!condition.isEmpty{Text(textValue(condition["kind"])+": "+String(describing:condition["value"] ?? "")).wixalFont(size:9).foregroundStyle(theme.accent)}
                    }.padding(10).frame(width:190,height:88,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(theme.line,lineWidth:1)).position(item.point)
                }
            }.frame(width:width,height:height)
        }.background(theme.panel.opacity(0.4),in:RoundedRectangle(cornerRadius:8))
    }
}

struct SecurityContractEditor:View {
    @ObservedObject var engine:EngineClient
    let targetID:String
    let targetType:String
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var name=""
    @ViewState private var tool=""
    @ViewState private var binding=""
    @ViewState private var instructions=""
    @ViewState private var defaults="{}"
    @ViewState private var error=""
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            Text("Register investigation capability").wixalFont(size:22,weight:.medium)
            TextField("Capability name",text:$name).wixalField()
            Picker("Installed tool",selection:$tool) {
                Text("Choose tool").tag("")
                ForEach(engine.tools,id:\.securityToolID) { item in let function=item["function"] as? [String:Any] ?? [:];Text(textValue(function["name"])).tag(textValue(function["name"])) }
            }
            TextField("Target argument (url, target, path…); optional",text:$binding).wixalField()
            TextField("Skill instructions and prerequisites",text:$instructions,axis:.vertical).wixalField()
            Text("Default arguments (JSON)").wixalFont(size:11)
            TextEditor(text:$defaults).wixalFont(size:11,design:.monospaced).frame(height:100)
            Text("Uses the installed tool's input schema and normal action review. Target binding pins that input to this investigation. These instructions are provided to the AI planner; the tool performs execution.").wixalFont(size:11).foregroundStyle(theme.muted)
            if !error.isEmpty {Text(error).foregroundStyle(theme.accent)}
            HStack {Button("Cancel",action:close);Spacer();Button("Register") {
                Task {do {
                    guard let data=defaults.data(using:.utf8),let args=try JSONSerialization.jsonObject(with:data) as? [String:Any] else {throw NSError(domain:"Contract",code:1,userInfo:[NSLocalizedDescriptionKey:"Defaults must be a JSON object"])}
                    _=try await engine.call("security-contract-save",["targetId":targetID,"name":name,"tool":tool,"binding":binding,"defaults":args,"instructions":instructions,"types":[targetType]]);close()
                }catch{self.error=error.localizedDescription}}
            }.disabled(name.isEmpty || tool.isEmpty).buttonStyle(WixalButtonStyle(outlined:true))}
        }.padding(26).frame(width:620,height:570).foregroundStyle(theme.text).background(theme.background)
    }
}

private extension Dictionary where Key == String, Value == Any {
    var securityRecordID:String {textValue(self["id"])}
    var securityModelID:String {textValue(self["name"])}
    var securityToolID:String {textValue((self["function"] as? [String:Any])?["name"])}
}
