import SwiftUI

struct AddonLibraryView: View {
    @ObservedObject var engine: EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState<[String:Any]> private var snapshot: [String:Any] = [:]
    @ViewState<String> private var page = "Browse"
    @ViewState<String> private var category = "All"
    @ViewState<String> private var kind = "All"
    @ViewState<String> private var query = ""
    @ViewState<String> private var expanded = ""
    @ViewState<String> private var error = ""
    @ViewState<String> private var status = ""
    @ViewState<Bool> private var loading = false
    @ViewState<[String:Any]?> private var detailItem = nil
    @ViewState<[String:Any]?> private var removal = nil
    private let categories = ["All","Web","Network","Traffic","Software","Validation","Discovered"]
    private var items: [[String:Any]] { records(snapshot["packages"]) + records(snapshot["workflows"]) }
    private var jobs: [[String:Any]] { records(engine.state["addonJobs"] ?? snapshot["jobs"]).filter { textValue($0["owner"]) == textValue(snapshot["owner"]) } }
    private var changes: String { jobs.map { textValue($0["id"])+textValue($0["status"]) }.joined(separator:"|") + pretty(engine.state["skills"] ?? []) }
    private func workflow(_ item:[String:Any])->Bool { textValue(item["kind"]) == "workflow" }
    private func installed(_ item:[String:Any])->Bool { item["installed"] as? Bool == true }
    private func pending(_ item:[String:Any])->Bool { jobs.contains { textValue($0["addon"]) == textValue(item["id"]) && ["queued","running","waiting_review"].contains(textValue($0["status"])) } }
    private func needsAttention(_ item:[String:Any])->Bool { let latest=jobs.last { textValue($0["addon"]) == textValue(item["id"]) }; return ["failed","interrupted","setup_required"].contains(textValue(latest?["status"])) }
    private var filtered: [[String:Any]] { items.filter { item in
        (category == "All" || textValue(item["category"]) == category) && (query.isEmpty || (textValue(item["name"])+" "+textValue(item["description"])).localizedCaseInsensitiveContains(query)) && (kind == "All" || workflow(item) == (kind == "Workflow packs")) && (page == "Browse" || installed(item) || pending(item) || needsAttention(item))
    } }
    private func categoryName(_ value:String)->String { ["All":"All tools","Web":"Web security","Network":"Network & TLS","Traffic":"Traffic analysis","Software":"Software security","Validation":"Validation","Discovered":"Discovered programs"][value] ?? value }
    private func symbol(_ value:String)->String { ["All":"square.grid.2x2","Web":"globe","Network":"network","Traffic":"waveform.path","Software":"shippingbox","Validation":"scope","Discovered":"magnifyingglass"][value] ?? "square.grid.2x2" }
    var body: some View {
        VStack(spacing:0) {
            header
            GeometryReader { geometry in
                HStack(alignment:.top,spacing:0) {
                    if geometry.size.width >= 760 { categorySidebar; Divider().overlay(theme.line) }
                    ScrollView {
                        VStack(alignment:.leading,spacing:18) {
                            if geometry.size.width < 760 { Picker("Category",selection:$category) { ForEach(categories,id:\.self) { Text(categoryName($0)).tag($0) } }.pickerStyle(.menu) }
                            HStack {
                                VStack(alignment:.leading,spacing:5) { Text(page == "Installed" && category == "All" ? "Installed tools" : categoryName(category)).wixalFont(size:18,weight:.medium); Text(page == "Installed" ? "Manage global installations and workflow packs." : "Programs and workflows for your AI workloads.").wixalFont(size:11).foregroundStyle(theme.muted) }
                                Spacer()
                                Button("Refresh") { Task { await refresh() } }.disabled(loading)
                            }
                            HStack {
                                TextField("Search tools and workflows…",text:$query).wixalField().accessibilityLabel("Search tools and workflows")
                                Picker("Tool type",selection:$kind) { Text("Programs & workflows").tag("All"); Text("Programs").tag("Programs"); Text("Workflow packs").tag("Workflow packs") }.labelsHidden().frame(maxWidth:185)
                            }
                            if !error.isEmpty { Text(error).foregroundStyle(.red).textSelection(.enabled) }
                            if filtered.isEmpty { Text(page == "Installed" ? "Nothing installed in this category. Browse to add tools." : "No matching tools.").foregroundStyle(theme.muted).padding(.vertical,24) }
                            if page == "Browse" {
                                ForEach(category == "All" ? categories.filter { $0 != "All" } : [category],id:\.self) { section in
                                    let rows=filtered.filter { textValue($0["category"]) == section }
                                    if !rows.isEmpty {
                                        if category == "All" { Text(categoryName(section)).wixalFont(size:13,weight:.medium) }
                                        LazyVGrid(columns:[GridItem(.adaptive(minimum:245),spacing:14)],alignment:.leading,spacing:14) { ForEach(rows,id:\.toolIdentity) { item in toolCard(item) } }
                                    }
                                }
                            } else { LazyVStack(alignment:.leading,spacing:0) { ForEach(filtered,id:\.toolIdentity) { item in installedRow(item) } } }
                        }.padding(24).frame(maxWidth:.infinity,alignment:.leading)
                    }
                }
            }
            Divider().overlay(theme.line)
            HStack { if loading { ProgressView().controlSize(.small) }; Text(status.isEmpty ? "Global library · " + ((engine.state["addonPolicy"] as? [String:Any])?["automaticInstall"] as? Bool == true ? "AI auto-install enabled" : "Ask before AI installs") : status); Spacer() }.wixalFont(size:11).foregroundStyle(theme.muted).padding(12).background(theme.panel)
        }.foregroundStyle(theme.text).background(theme.background)
        .task { await refresh() }
        .onChange(of:changes) { _,_ in Task { await refresh() } }
        .onChange(of:engine.connected) { _,ready in if ready { Task { await refresh() } } }
        .sheet(isPresented:Binding(get:{detailItem != nil},set:{if !$0 { detailItem=nil }})) {
            if let selected=detailItem { details(items.first { textValue($0["id"]) == textValue(selected["id"]) } ?? selected) }
        }
        .alert("Remove globally?",isPresented:Binding(get:{removal != nil},set:{if !$0 { removal=nil }})) {
            Button("Cancel",role:.cancel) { removal=nil }
            Button("Remove",role:.destructive) { if let item=removal { Task { await perform(workflow(item) ? "addon-workflow-remove" : "addon-manage",["id":textValue(item["id"]),"operation":"uninstall"]); removal=nil } } }
        } message: { Text("\(textValue(removal?["name"])) will no longer be available across Wixal projects. Removal affects the selected provider. Managed removal keeps historical evidence and requires active runs to finish. Homebrew removal also affects other applications using that installation.") }
    }
    private var header: some View {
        VStack(alignment:.leading,spacing:20) {
            HStack {
                VStack(alignment:.leading,spacing:5) { Text("Tools").wixalFont(size:23,weight:.medium); Text("Install once. Available throughout Wixal.").wixalFont(size:12).foregroundStyle(theme.muted) }
                Spacer()
                Button("Installation settings") { NotificationCenter.default.post(name:.wixalNavigate,object:"Settings:Tools") }.buttonStyle(WixalButtonStyle())
            }
            Picker("Tools view",selection:$page) { Text("Browse").tag("Browse"); Text("Installed · \(items.filter { installed($0) }.count)").tag("Installed") }.labelsHidden().pickerStyle(.segmented).frame(maxWidth:320)
        }.padding(24)
    }
    private var categorySidebar: some View {
        VStack(alignment:.leading,spacing:8) {
            Text("CATEGORIES").wixalFont(size:9,design:.monospaced).tracking(1).foregroundStyle(theme.muted).padding(.bottom,8)
            ForEach(categories.filter { $0 != "Discovered" || items.contains { textValue($0["category"]) == "Discovered" } },id:\.self) { value in
                Button { category=value } label: { HStack(spacing:8) { Image(systemName:symbol(value)); Text(categoryName(value)); Spacer(minLength:2); Text("\(items.filter { value == "All" || textValue($0["category"]) == value }.count)").foregroundStyle(theme.muted) }.wixalFont(size:11).padding(10).frame(maxWidth:.infinity,alignment:.leading).background(category == value ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7)) }.buttonStyle(.plain).accessibilityAddTraits(category == value ? .isSelected : [])
            }
            Spacer()
            Divider()
            Text("Global installation").wixalFont(size:11,weight:.medium)
            Text("Ready tools are available in Cybersecurity, Chat and Agents.").wixalFont(size:11).foregroundStyle(theme.muted)
        }.padding(16).frame(width:185).frame(maxHeight:.infinity,alignment:.top)
    }
    private func toolCard(_ item:[String:Any])->some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { Text(workflow(item) ? "WORKFLOW PACK" : "PROGRAM").foregroundStyle(theme.muted); Spacer(); Text(pending(item) ? "In progress" : installed(item) ? "Installed" : textValue(item["integration"]) == "setup_required" ? "Setup required" : "Available").foregroundStyle(installed(item) ? theme.accent : theme.muted) }.wixalFont(size:10)
            Text(textValue(item["name"])).wixalFont(size:14,weight:.medium)
            Text(textValue(item["description"])).wixalFont(size:12).foregroundStyle(theme.muted).fixedSize(horizontal:false,vertical:true)
            Spacer(minLength:8)
            Text(workflow(item) ? "Bundled Wixal workflow" : textValue(item["registry"])).wixalFont(size:10).foregroundStyle(theme.muted)
            HStack { Button("Details") { detailItem=item }.buttonStyle(.plain).foregroundStyle(theme.accent).accessibilityLabel("Details for " + textValue(item["name"])); Spacer(); Button(installed(item) || pending(item) ? "Manage" : item["installable"] as? Bool == true || workflow(item) ? "Install" : "View setup") { if installed(item) || pending(item) { page="Installed"; expanded=textValue(item["id"]) } else if item["installable"] as? Bool == true || workflow(item) { install(item) } else { detailItem=item } }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(!engine.connected).accessibilityIdentifier("tools.action." + textValue(item["id"])).accessibilityLabel((installed(item) || pending(item) ? "Manage " : item["installable"] as? Bool == true || workflow(item) ? "Install " : "View setup for ") + textValue(item["name"])) }.wixalFont(size:11)
        }.padding(18).frame(maxWidth:.infinity,minHeight:220,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:9)).overlay(RoundedRectangle(cornerRadius:9).stroke(theme.line,lineWidth:1))
    }
    private func installedRow(_ item:[String:Any])->some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { VStack(alignment:.leading,spacing:4) { Text(textValue(item["name"])).wixalFont(size:13,weight:.medium); Text(workflow(item) ? "Workflow pack" : textValue(item["registry"])).wixalFont(size:10).foregroundStyle(theme.muted) }; Spacer(); Text(pending(item) ? "In progress" : needsAttention(item) ? "Needs attention" : readinessLabel(item)).wixalFont(size:11).foregroundStyle(theme.accent); Button("Manage") { expanded=expanded == textValue(item["id"]) ? "" : textValue(item["id"]) }.buttonStyle(WixalButtonStyle(outlined:true)).accessibilityLabel("Manage " + textValue(item["name"])) }
            if expanded == textValue(item["id"]) { management(item) }
            Divider().overlay(theme.line)
        }.padding(.vertical,12)
    }
    private func management(_ item:[String:Any])->some View {
        VStack(alignment:.leading,spacing:14) {
            Text(textValue(item["description"])).wixalFont(size:12).foregroundStyle(theme.muted)
            if !textValue(item["path"]).isEmpty { Text(textValue(item["path"])).wixalFont(size:11,design:.monospaced).textSelection(.enabled) }
            if !textValue(item["version"]).isEmpty { Text(textValue(item["version"])).wixalFont(size:11).textSelection(.enabled) }
            if !workflow(item) {
                Text("Capability: " + readinessLabel(item) + " · Model: " + textValue(item["modelEvaluation"]).capitalized).wixalFont(size:11).foregroundStyle(theme.muted)
                if item["managed"] != nil { managedControls(item) }
            }
            HStack {
                Button("Details") { detailItem=item }
                if !workflow(item) {
                    Button("Verify") { Task { if await perform("addon-verify",["id":textValue(item["id"])]) { status="Executable verified" } } }
                    if item["installable"] as? Bool == true {
                        Button("Update") { Task { await perform("addon-manage",["id":textValue(item["id"]),"operation":"upgrade"]) } }
                        Button("Repair") { Task { await perform("addon-manage",["id":textValue(item["id"]),"operation":"reinstall"]) } }
                    }
                }
                if workflow(item) || item["installable"] as? Bool == true { Button("Remove…",role:.destructive) { removal=item } }
            }.disabled(pending(item) || !engine.connected).wixalFont(size:11)
            DisclosureGroup("Installation history") {
                let history=jobs.filter { textValue($0["addon"]) == textValue(item["id"]) }
                if history.isEmpty { Text("No Wixal installation receipt. This capability may have been installed outside Wixal.").wixalFont(size:11).foregroundStyle(theme.muted) }
                ForEach(history.reversed(),id:\.toolIdentity) { job in jobRow(job) }
            }.wixalFont(size:11)
            ForEach(jobs.filter { textValue($0["addon"]) == textValue(item["id"]) && ["queued","running","waiting_review"].contains(textValue($0["status"])) },id:\.toolIdentity) { job in jobRow(job) }
        }.padding(16).background(theme.panel,in:RoundedRectangle(cornerRadius:8))
    }
    private func readinessLabel(_ item:[String:Any])->String {
        if workflow(item) { return "Installed" }
        return textValue(item["readiness"]).replacingOccurrences(of:"_",with:" ").capitalized
    }
    private func managedControls(_ item:[String:Any])->some View {
        let managed=item["managed"] as? [String:Any] ?? [:]
        let active=managed["active"] as? [String:Any] ?? [:]
        let recovery=active["recovery"] as? [String] ?? []
        return VStack(alignment:.leading,spacing:10) {
            Text("Provider: " + textValue(item["provider"]).replacingOccurrences(of:"_",with:" ")).wixalFont(size:11)
            HStack {
                Button("Use external installation") { Task { await perform("addon-provider",["id":textValue(item["id"]),"provider":"external_homebrew"]) } }
                if managed["installed"] as? Bool == true {
                    Button("Use managed package") { Task { await perform("addon-provider",["id":textValue(item["id"]),"provider":"managed"]) } }
                }
                if managed["configured"] as? Bool == true {
                    Button("Install managed") { Task { await perform("addon-install",["id":textValue(item["id"]),"provider":"managed","reason":"Use a verified Wixal managed package"]) } }
                    Button("Check catalogue") { Task { await perform("addon-managed-refresh",[:]) } }
                }
            }.wixalFont(size:11).disabled(pending(item))
            if managed["configured"] as? Bool != true { Text("Managed downloads are unavailable in this build. A trusted repository must be supplied when packaging.").wixalFont(size:11).foregroundStyle(theme.muted) }
            Text("Package verified: " + ((item["packageVerified"] as? Bool == true) ? "Yes" : "No managed receipt") + " · AI utilisation: Unevaluated").wixalFont(size:11).foregroundStyle(theme.muted)
            if let stamp=managed["lastCatalogueCheck"] as? Double { Text("Catalogue checked " + Date(timeIntervalSince1970:stamp).formatted()).wixalFont(size:10).foregroundStyle(theme.muted) }
            ForEach(recovery,id:\.self) { artifact in
                Button("Roll back to " + String(artifact.prefix(12))) { Task { await perform("addon-rollback",["id":textValue(item["id"]),"artifact":artifact]) } }.wixalFont(size:11)
            }
            DisclosureGroup("Package identity") { Text(pretty(active)).wixalFont(size:10,design:.monospaced).textSelection(.enabled) }
        }
    }
    private func jobRow(_ job:[String:Any])->some View {
        VStack(alignment:.leading,spacing:8) {
            HStack {
                Text(textValue(job["reason"]))
                Spacer()
                Text((textValue(job["stage"]).isEmpty ? textValue(job["status"]) : textValue(job["stage"])).replacingOccurrences(of:"_",with:" ").capitalized)
                if ["queued","running","waiting_review"].contains(textValue(job["status"])) {
                    Button("Stop") { Task { await perform("addon-job",["id":textValue(job["id"]),"action":"stop"]) } }
                }
            }
            Text(textValue(job["registry"])).foregroundStyle(theme.muted).textSelection(.enabled)
            if !textValue(job["error"]).isEmpty { Text(textValue(job["error"])).foregroundStyle(.red) }
            DisclosureGroup("Output") { Text(textValue(job["output"])).wixalFont(size:10,design:.monospaced).textSelection(.enabled) }
        }.wixalFont(size:11).padding(.vertical,8)
    }
    private func details(_ item:[String:Any])->some View {
        VStack(alignment:.leading,spacing:18) {
            HStack { Text(textValue(item["name"])).wixalFont(size:22,weight:.medium); Spacer(); Button("Done") { detailItem=nil } }
            ScrollView { VStack(alignment:.leading,spacing:16) {
                Text(textValue(item["description"])).wixalFont(size:13)
                Text("Global installation · Shared across all projects").wixalFont(size:12).foregroundStyle(theme.muted)
                if !error.isEmpty { Text(error).foregroundStyle(.red).textSelection(.enabled) }
                ForEach(jobs.filter { textValue($0["addon"]) == textValue(item["id"]) && ["queued","running","waiting_review","failed","cancelled"].contains(textValue($0["status"])) },id:\.toolIdentity) { job in jobRow(job) }
                if workflow(item) { Text("Required programs: " + (item["tools"] as? [String] ?? []).joined(separator:", ")).wixalFont(size:12); Text(textValue(item["content"])).wixalFont(size:12).textSelection(.enabled) }
                else { if item["managed"] != nil { managedControls(item) }; Text(textValue(item["integration"]) == "setup_required" ? "Specialist setup and a usable AI adapter are still required. Installation alone does not make this tool ready." : "Structured AI adapter available. Execution follows the task's scope and permissions.").wixalFont(size:12); if let url=URL(string:textValue(item["source"])) { Link("Official documentation",destination:url) }; if let url=URL(string:textValue(item["registryURL"])) { Link("Installation source",destination:url) } }
            }.frame(maxWidth:.infinity,alignment:.leading) }
        }.padding(24).frame(width:560,height:480).foregroundStyle(theme.text).background(theme.background)
    }
    private func install(_ item:[String:Any]) {
        Task { await perform(workflow(item) ? "addon-workflow" : "addon-install",["id":textValue(item["id"]),"reason":"User selected this capability in Tools"]); page="Installed"; expanded=textValue(item["id"]) }
    }
    private func refresh() async {
        guard engine.connected else { return }; loading=true; defer { loading=false }
        do { snapshot=try await engine.call("addon-catalog") as? [String:Any] ?? [:] }
        catch { self.error=error.localizedDescription }
    }
    @discardableResult private func perform(_ method:String,_ arguments:[String:Any]) async -> Bool {
        error="";status=""
        do { let result=try await engine.call(method,arguments) as? [String:Any] ?? [:]; status=textValue(result["status"]).capitalized; await refresh(); return true }
        catch { self.error=error.localizedDescription; return false }
    }
}
private extension Dictionary where Key == String, Value == Any { var toolIdentity: String { textValue(self["id"]) } }
