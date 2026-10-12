import SwiftUI

struct EngagementSetupView: View {
    @ObservedObject var engine:EngineClient
    let engagement:[String:Any]?
    let save:([String:Any])->Void
    @Environment(\.dismiss) private var dismiss
    @ViewState private var name:String
    @ViewState private var objective:String
    @ViewState private var selected:Set<String>
    @ViewState private var capabilities:Set<String>
    @ViewState private var exclusions:String
    @ViewState private var starts:Date
    @ViewState private var ends:Date
    @ViewState private var maxRuns:Int
    @ViewState private var maxSeconds:Int
    @ViewState private var threat:String
    @ViewState private var contacts:String
    @ViewState private var dataHandling:String
    @ViewState private var abort:String
    private let supported=["analysis","planner","software_inventory","website_assess","website_simulate","network_scan","network_discover","linux_network_scan"]
    init(engine:EngineClient,engagement:[String:Any]?,save:@escaping ([String:Any])->Void) {
        self.engine=engine;self.engagement=engagement;self.save=save
        let scope=records(engagement?["scopes"]).last?["policy"] as? [String:Any] ?? [:]
        _name=ViewState(initialValue:engagementText(engagement?["name"]))
        _objective=ViewState(initialValue:engagementText(engagement?["objective"]))
        _selected=ViewState(initialValue:Set(engagement?["targetIds"] as? [String] ?? []))
        _capabilities=ViewState(initialValue:Set(scope["capabilities"] as? [String] ?? ["analysis","planner","software_inventory","website_assess","website_simulate"]))
        _exclusions=ViewState(initialValue:(scope["exclusions"] as? [String] ?? []).joined(separator:"\n"))
        _starts=ViewState(initialValue:Date(timeIntervalSince1970:(scope["starts"] as? Double ?? Date().timeIntervalSince1970*1000)/1000))
        _ends=ViewState(initialValue:Date(timeIntervalSince1970:(scope["ends"] as? Double ?? (Date().timeIntervalSince1970+86400)*1000)/1000))
        _maxRuns=ViewState(initialValue:scope["maxRuns"] as? Int ?? 32);_maxSeconds=ViewState(initialValue:scope["maxSeconds"] as? Int ?? 180)
        _threat=ViewState(initialValue:engagementText(scope["threatProfile"]));_contacts=ViewState(initialValue:engagementText(scope["contacts"]))
        _dataHandling=ViewState(initialValue:engagementText(scope["dataHandling"]));_abort=ViewState(initialValue:engagementText(scope["abortConditions"]))
    }
    private var targets:[[String:Any]] {records(engine.state["securityTargets"]).filter {engagementText($0["projectId"]) == engagementText(engine.state["activeProject"]) && $0["archived"] as? Bool != true}}
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            Text(engagement == nil ? "New engagement" : "Revise engagement scope").wixalFont(size:21,weight:.medium)
            ScrollView {
                VStack(alignment:.leading,spacing:14) {
                    if engagement == nil {
                        TextField("Engagement name",text:$name).textFieldStyle(.roundedBorder)
                        TextField("Objective",text:$objective,axis:.vertical).textFieldStyle(.roundedBorder)
                        Text("Authorised targets").bold()
                        ForEach(targets,id:\.engagementID) { target in Toggle(engagementText(target["address"]),isOn:Binding(get:{selected.contains(engagementText(target["id"]))},set:{if $0{selected.insert(engagementText(target["id"]))}else{selected.remove(engagementText(target["id"]))}})) }
                        if targets.isEmpty { Text("Add a target in Investigations first.").foregroundStyle(.secondary) }
                    }
                    Text("Permitted capabilities").bold()
                    ForEach(supported,id:\.self) { capability in Toggle(engagementCapabilityName(capability),isOn:Binding(get:{capabilities.contains(capability)},set:{if $0{capabilities.insert(capability)}else{capabilities.remove(capability)}})) }
                    TextField("Excluded hosts, origins or IP ranges — one per line",text:$exclusions,axis:.vertical).textFieldStyle(.roundedBorder)
                    DatePicker("Testing starts",selection:$starts)
                    DatePicker("Testing ends",selection:$ends)
                    Stepper("Run budget: \(maxRuns)",value:$maxRuns,in:1...128)
                    Stepper("Run deadline: \(maxSeconds) seconds",value:$maxSeconds,in:10...600,step:10)
                    TextField("Threat profile",text:$threat,axis:.vertical).textFieldStyle(.roundedBorder)
                    TextField("Contacts and deconfliction",text:$contacts,axis:.vertical).textFieldStyle(.roundedBorder)
                    TextField("Evidence handling and retention",text:$dataHandling,axis:.vertical).textFieldStyle(.roundedBorder)
                    TextField("Abort conditions",text:$abort,axis:.vertical).textFieldStyle(.roundedBorder)
                    Text("Saving creates an unapproved scope revision. Revising scope revokes approval and stops owned work. Review & start requests explicit approval of the current revision.").font(.caption).foregroundStyle(.secondary)
                }
            }
            HStack { Button("Cancel") {dismiss()};Spacer();Button("Save scope") {
                let scope:[String:Any] = ["targetIds":Array(selected).sorted(),"capabilities":Array(capabilities).sorted(),"exclusions":exclusions.split(separator:"\n").map{String($0).trimmingCharacters(in:.whitespaces)},"starts":Int(starts.timeIntervalSince1970*1000),"ends":Int(ends.timeIntervalSince1970*1000),"maxRuns":maxRuns,"maxSeconds":maxSeconds,"threatProfile":threat,"contacts":contacts,"dataHandling":dataHandling,"abortConditions":abort]
                if let engagement {save(["scope":scope,"baseRevision":engagement["scopeRevision"] ?? 1])}
                else {save(["name":name,"objective":objective,"targetIds":Array(selected).sorted(),"scope":scope])}
            }.disabled(selected.isEmpty || capabilities.isEmpty || ends<=starts || name.trimmingCharacters(in:.whitespaces).isEmpty || objective.trimmingCharacters(in:.whitespaces).isEmpty) }
        }.padding(24).frame(width:560,height:610)
    }
}
