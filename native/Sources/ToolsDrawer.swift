import SwiftUI
import AppKit

struct ToolsDrawer:View {
    @ObservedObject var engine:EngineClient
    let close:()->Void
    var cybersecurity=false
    @ViewState<String> private var securityPage="Assessments"
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var query=""
    @ViewState<String> private var category="All"
    @ViewState<String> private var target=""
    @ViewState<String> private var profile="services"
    @ViewState<String> private var ports="1-1024"
    @ViewState<String> private var url=""
    @ViewState<String> private var websiteProfile="baseline"
    @ViewState<String> private var paths=""
    @ViewState<String> private var prefix="website-assessment"
    @ViewState<Bool?> private var nmap=nil
    @ViewState<String> private var readinessError=""
    private var automaticSelection:Bool{textValue(engine.state["mode"])=="agent" && !cybersecurity}
    private func enabled(_ name:String)->Bool { (engine.state["enabledTools"] as? [String] ?? []).contains(name) }
    private var readinessLabel:String { if !readinessError.isEmpty { return "Readiness unavailable: " + readinessError }; guard let nmap else { return "Checking Nmap…" }; return nmap ? (enabled("security_tools") ? "Nmap ready · results return to this chat" : "Nmap ready · discovery tool disabled") : "Nmap missing · install with brew install nmap" }
    private func refreshReadiness() async { nmap=nil; readinessError=""; do { let result=try await engine.call("security-readiness") as? [String:Any] ?? [:]; nmap=result["installed"] as? Bool } catch { readinessError=error.localizedDescription } }
    private func group(_ name:String)->String{if name.hasPrefix("mcp_"){return "Connected"};if name.hasPrefix("network_") || name=="security_tools"{return "Network"};if name.hasPrefix("website_") || name.hasPrefix("browser_") || ["web_search","http_request"].contains(name){return "Web"};if name.hasPrefix("command_") || name=="run_command"{return "Commands"};if ["search_history","save_memory","recall_memory","forget_memory","load_skill","delegate_task"].contains(name){return "Memory & skills"};return "Project"}
    private var filtered:[[String:Any]]{engine.tools.filter{let function=$0["function"] as? [String:Any] ?? [:],name=textValue(function["name"]);return (category=="All" || group(name)==category) && (query.isEmpty || name.localizedCaseInsensitiveContains(query) || textValue(function["description"]).localizedCaseInsensitiveContains(query))}}
    var body:some View {
        VStack(alignment:.leading,spacing:16){
            HStack{VStack(alignment:.leading,spacing:6){Text(cybersecurity ? "SECURITY" : "AGENTS").wixalFont(size:9,design:.monospaced).tracking(1).foregroundStyle(theme.muted);Text(cybersecurity ? "Cybersecurity" : automaticSelection ? "Agent capabilities" : "Tool permissions").wixalFont(size:21,weight:.medium)};Spacer();if !cybersecurity{Button(action:close){Image(systemName:"xmark")}.buttonStyle(.plain).accessibilityLabel("Close tools")}}
            if engine.busy && !engine.assessmentProgress.isEmpty {
                HStack(alignment:.top){ProgressView().controlSize(.small);VStack(alignment:.leading,spacing:4){Text(textValue(engine.assessmentProgress["state"]).capitalized);if let completed=engine.assessmentProgress["completed"] as? Int{Text("\(completed) checks completed").foregroundStyle(theme.muted)}};Spacer();Button(textValue(engine.assessmentProgress["state"]) == "stopping" ? "Stopping…" : "Stop assessment"){engine.cancelAssessment()}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(textValue(engine.assessmentProgress["state"]) == "stopping")}.wixalFont(size:11).accessibilityElement(children:.contain).accessibilityLabel("Assessment progress")
            }
            if cybersecurity{Picker("Cybersecurity section",selection:$securityPage){Text("Assessments").tag("Assessments");Text("Evidence").tag("Evidence")}.pickerStyle(.segmented).labelsHidden()}
            ScrollView{VStack(alignment:.leading,spacing:18){
                if !cybersecurity{Text(automaticSelection ? "The model discovers these tools and chooses how to use them. Task scope and action review control effects." : "Enabled tools are available to models marked Tools. Manual assessments run without model inference. Each action uses its workspace’s review setting.").wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)
                TextField("Find a tool…",text:$query).wixalField()
                Picker("Category",selection:$category){ForEach(["All","Project","Commands","Network","Web","Memory & skills","Connected"],id:\.self){Text($0)}}.wixalFont(size:11)
                if automaticSelection{Text("\(engine.tools.count) discovered capabilities · model chooses tools").wixalFont(size:10).foregroundStyle(theme.muted)}else{HStack{Text("\((engine.state["enabledTools"] as? [String] ?? []).count) enabled").wixalFont(size:10).foregroundStyle(theme.muted);Spacer();Button("Disable all"){engine.action("settings",["enabledTools":[]])}.buttonStyle(.plain).wixalFont(size:10).disabled(engine.busy);Button("Enable all"){engine.action("settings",["enabledTools":engine.tools.compactMap{($0["function"] as? [String:Any])?["name"] as? String}])}.buttonStyle(.plain).wixalFont(size:10).disabled(engine.busy)}}
                ForEach(Array(filtered.enumerated()),id:\.offset){_,tool in toolRow(tool)}
                if filtered.isEmpty{Text("No matching tools.").wixalFont(size:11).foregroundStyle(theme.muted)}
                }
                if cybersecurity && securityPage=="Assessments"{
                if engine.project==nil{Button("Choose a project to save assessment evidence",action:engine.pickProject).buttonStyle(WixalButtonStyle(outlined:true))}
                DisclosureGroup("Assessment tools"){ForEach(Array(engine.tools.filter{["network_scan","website_assess","website_simulate"].contains(textValue(($0["function"] as? [String:Any])?["name"]))}.enumerated()),id:\.offset){_,tool in toolRow(tool)}}
                scanForm
                Divider().overlay(theme.line)
                websiteForm
                if let output=engine.assessmentProgress["output"] as? String,!output.isEmpty{DisclosureGroup("Live scanner output"){Text(output).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}}
                }
                if cybersecurity && securityPage=="Evidence"{results}
            }}
        }.padding(24).frame(maxWidth:cybersecurity ? 920 : .infinity).frame(maxWidth:.infinity,maxHeight:.infinity,alignment:.top).foregroundStyle(theme.text).task{await refreshReadiness()}.onChange(of:engine.connected){_,ready in if ready{Task{await refreshReadiness()}}else{nmap=nil;readinessError="Engine disconnected"}}
    }
    @ViewBuilder private func toolRow(_ tool:[String:Any])->some View {
        let function=tool["function"] as? [String:Any] ?? [:],name=textValue(function["name"])
        if automaticSelection{VStack(alignment:.leading,spacing:5){Label(name.replacingOccurrences(of:"_",with:" ").capitalized,systemImage:"sparkles").wixalFont(size:11,weight:.medium);Text(textValue(function["description"])).wixalFont(size:10).foregroundStyle(theme.muted)}.accessibilityLabel(name+" · chosen by the model")}else{Toggle(isOn:Binding(get:{(engine.state["enabledTools"] as? [String] ?? []).contains(name)},set:{value in var names=engine.state["enabledTools"] as? [String] ?? [];names.removeAll{$0==name};if value{names.append(name)};engine.action("settings",["enabledTools":names])})){VStack(alignment:.leading,spacing:5){Text(name.replacingOccurrences(of:"_",with:" ").capitalized).wixalFont(size:11,weight:.medium);Text(textValue(function["description"])).wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)}}.toggleStyle(.switch).controlSize(.mini).disabled(engine.busy).accessibilityLabel(name.replacingOccurrences(of:"_",with:" ")).accessibilityHint(textValue(function["description"]))}
    }
    private var scanForm:some View {
        VStack(alignment:.leading,spacing:12){Text("Network assessment").wixalFont(size:14,weight:.medium);Text(readinessLabel).wixalFont(size:10).foregroundStyle(theme.muted);Button("Refresh readiness"){Task{await refreshReadiness()}};if !enabled("network_scan"){Text("Enable Network Scan above to run an assessment.").foregroundStyle(theme.muted)};TextField("Authorised host or private subnet",text:$target).wixalField();Picker("Profile",selection:$profile){ForEach(["discovery","ports","services","web","tls","ssh","enumeration","checks"],id:\.self){Text($0.capitalized)}};if profile != "discovery"{TextField("TCP ports",text:$ports).wixalField()};Button("Review and start scan"){run("network_scan",["target":target,"profile":profile,"ports":ports,"timeout_seconds":180])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(nmap != true || !enabled("network_scan") || !engine.connected || target.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || engine.project==nil || engine.busy)}.wixalFont(size:11)
    }
    private var websiteForm:some View {
        VStack(alignment:.leading,spacing:12){Text("Website assessment").wixalFont(size:14,weight:.medium);TextField("Authorised https:// website",text:$url).wixalField();Picker("Profile",selection:$websiteProfile){Text("Headers and protected paths").tag("baseline");Text("Bounded unauthenticated probes").tag("probes")};TextField("Protected paths, comma separated",text:$paths).wixalField();TextField("Unused report prefix",text:$prefix).wixalField();Button("Review and assess website"){run("website_assess",["url":url,"profile":websiteProfile,"protected_paths":paths.split(separator:",").map{String($0).trimmingCharacters(in:.whitespaces)},"report_prefix":prefix,"max_pages":12])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!enabled("website_assess") || !engine.connected || url.isEmpty || prefix.isEmpty || engine.project==nil || engine.busy);Text("Local attack simulations").wixalFont(size:12,weight:.medium);Text("Checks vulnerable and hardened disposable loopback fixtures. Uses synthetic data.").wixalFont(size:10).foregroundStyle(theme.muted);Button("Review and run local simulations"){run("website_simulate",["report_prefix":prefix+"-simulation"])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!enabled("website_simulate") || !engine.connected || engine.project==nil || prefix.isEmpty || engine.busy)}.wixalFont(size:11)
    }
    private var results:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Recent results").wixalFont(size:14,weight:.medium)
            ForEach(Array(records(engine.state["assessmentResults"]).filter{textValue($0["projectId"])==textValue(engine.state["activeProject"])}.reversed().enumerated()),id:\.offset){_,item in
                let result=item["result"] as? [String:Any] ?? [:]
                let status=textValue(item["status"] ?? result["status"])
                let partial=result["partial"] as? Bool ?? false
                VStack(alignment:.leading,spacing:8){
                    Text(textValue(item["name"]).replacingOccurrences(of:"_",with:" ").capitalized).wixalFont(size:12,weight:.medium)
                    Label(partial ? "Partial result · " + (status.isEmpty ? "Interrupted" : status.capitalized) : (status.isEmpty ? "Completed" : status.capitalized),systemImage:partial ? "stop.circle" : "checkmark.circle").foregroundStyle(partial ? theme.muted : theme.accent)
                    if partial {
                        Text("Completed checks and captured evidence remain available below.").foregroundStyle(theme.muted)
                        if !textValue(result["interrupted"]).isEmpty{Text("Interrupted: " + textValue(result["interrupted"])).textSelection(.enabled)}
                    }
                    let cases=records(result["cases"])
                    if !cases.isEmpty {Text("\(cases.count) checks recorded");ForEach(Array(cases.enumerated()),id:\.offset){_,check in Text(textValue(check["title"] ?? check["name"] ?? check["path"] ?? check["id"])).textSelection(.enabled)}}
                    DisclosureGroup("Evidence and technical details"){Text(pretty(result)).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}
                    Button("Save output to project…"){
                        let panel=NSSavePanel();panel.directoryURL=URL(fileURLWithPath:engine.root);panel.nameFieldStringValue="assessment-output.json"
                        if panel.runModal() == .OK,let destination=panel.url,destination.path.hasPrefix(engine.root+"/"){engine.action("tool",["name":"write_file","arguments":["path":String(destination.path.dropFirst(engine.root.count+1)),"content":pretty(result)]])}
                    }.disabled(engine.busy)
                }.wixalFont(size:11).wixalCard()
            }
        }
    }
    private func run(_ name:String,_ arguments:[String:Any]){
        guard (engine.state["enabledTools"] as? [String] ?? []).contains(name) else{engine.error="Enable " + name.replacingOccurrences(of:"_",with:" ") + " in the tool list first.";return}
        engine.error="";engine.assessmentProgress=["state":"starting","name":name];engine.busy=true;engine.action("assessment-run",["name":name,"arguments":arguments])
    }
}
