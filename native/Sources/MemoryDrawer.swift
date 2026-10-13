import SwiftUI

struct MemoryDrawer:View {
    @ObservedObject var engine:EngineClient
    let close:()->Void
    var section:String?=nil
    var settings:SettingsState?=nil
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var note=""
    @ViewState<String?> private var editing=nil
    @ViewState<String> private var global=""
    @ViewState<String> private var scope="Project"
    @ViewState<String> private var query=""
    @ViewState<String> private var noteSearch=""
    @ViewState<[[String:Any]]> private var found=[]
    @ViewState<Bool> private var reviewing=false
    @ViewState<String> private var forgetting=""
    @ViewState<String> private var draftNamespace=""
    private var owner:String{let account=engine.state["account"] as? [String:Any] ?? [:];return account["signedIn"] as? Bool == true ? "account:"+textValue((account["profile"] as? [String:Any])?["id"]) : "guest"}
    // Capture identity on mount: disappearing after a workspace/account switch must
    // not move the old editor text into the newly active workspace's draft.
    private func draftKey(_ scope:String)->String{draftNamespace+":"+scope}
    private var policy:[String:Any]{engine.memoryStatus["policy"] as? [String:Any] ?? [:]}
    private var suggestions:[[String:Any]]{records(engine.memoryStatus["suggestions"]).filter{textValue($0["scope"]) == (scope=="Project" ? "project" : "global")}}
    private var sources:[[String:Any]]{records(engine.contextInfo["memorySources"])}
    private var globalNotes:[[String:Any]]{records(engine.memoryStatus["notes"]).filter{textValue($0["scope"])=="global"}}
    private var memories:[[String:Any]]{records(engine.state["memories"]).filter{textValue($0["projectId"])==textValue(engine.state["activeProject"])}}
    private var accountMemory:Bool{let account=engine.state["account"] as? [String:Any] ?? [:];return account["signedIn"] as? Bool ?? false}
    private var used:Int{memories.reduce(0){$0+textValue($1["content"]).count}}
    private var budget:Int{engine.project?["memorySize"] as? Int ?? 24000}
    private var mode:String{textValue(engine.project?["memoryMode"]).isEmpty ? "project" : textValue(engine.project?["memoryMode"])}
    private var globalEnabled:Bool{policy["global_"] as? Bool ?? false}
    private var projectEnabled:Bool{engine.project != nil && ["project","both"].contains(mode)}
    var body:some View {
        Group {
            if section != nil { content }
            else {
                VStack(alignment:.leading,spacing:16){
                    HStack{Text("Saved memory").wixalFont(size:21,weight:.medium);Spacer();Button(action:close){Image(systemName:"xmark")}.buttonStyle(WixalButtonStyle(inline:true)).accessibilityLabel("Close memory")}
                    ScrollView{content}
                }.padding(20)
            }
        }.foregroundStyle(theme.text)
        .onAppear{draftNamespace=owner+":"+textValue(engine.state["activeProject"]);global=engine.activeMemory;if engine.project==nil && scope != "Global"{scope="Global"}else{restoreDraft(scope)};engine.refreshMemory()}
        .onChange(of:engine.activeMemory){_,value in global=value}
        .onChange(of:scope){old,new in storeDraft(old);restoreDraft(new);found=[]}
        .onDisappear{storeDraft(scope)}
        .alert("Forget this saved memory?",isPresented:Binding(get:{!forgetting.isEmpty},set:{if !$0{forgetting=""}})){
            Button("Cancel",role:.cancel){forgetting=""}
            Button("Forget memory",role:.destructive){engine.action(scope=="Project" ? "memory-delete" : "memory-forget",["id":forgetting]);forgetting=""}
        }message:{Text("The saved note is removed. Its source conversation is kept.")}
    }
    private func storeDraft(_ value:String){settings?.memoryDrafts[draftKey(value)] = .init(text:note,editing:editing)}
    private func restoreDraft(_ value:String){let draft=settings?.memoryDrafts[draftKey(value)];note=draft?.text ?? "";editing=draft?.editing}
    private var content:some View {
        VStack(alignment:.leading,spacing:16){
            Picker("Memory scope",selection:$scope){Text("Project").tag("Project");Text("Global").tag("Global")}.pickerStyle(.segmented)
            Text(scope=="Project" ? (engine.project==nil ? "Open a project to manage its notes." : "Project: \(textValue(engine.project?["name"]))") : "Global notes · active guest or account identity").wixalFont(size:11).foregroundStyle(theme.muted)
            if section=="Suggestions" {
                if suggestions.isEmpty{Text("No suggestions to review. Lasting memories need your approval before saving.").wixalFont(size:12).foregroundStyle(theme.muted)}else{suggestedMemories}
                DisclosureGroup("Suggestion review settings"){suggestionControls.padding(.top,10)}.wixalFont(size:12)
            }else{
                TextField("Search saved notes…",text:$noteSearch).wixalField().accessibilityLabel("Search saved notes")
                if section==nil && !suggestions.isEmpty{suggestedMemories}
                if scope=="Project"{projectContent}else{globalContent}
                DisclosureGroup("Recall & indexing"){recallControls.padding(.top,10)}.wixalFont(size:12)
                if !sources.isEmpty{DisclosureGroup("Memory used for this conversation"){ForEach(Array(sources.enumerated()),id:\.offset){_,item in memorySource(item)}}.wixalFont(size:11).wixalCard()}
                if section==nil,let summary=engine.session?["summary"] as? [String:Any]{DisclosureGroup("Saved conversation summary"){Text(textValue(summary["content"])).wixalFont(size:11).textSelection(.enabled);Text("\(summary["messageCount"] as? Int ?? 0) messages · \(textValue(summary["method"]))").foregroundStyle(theme.muted);Button("Clear summary"){engine.action("summary-clear",["sessionId":textValue(engine.state["activeSession"])])}.disabled(engine.busy)}.wixalFont(size:11).wixalCard()}
            }
        }
    }
    private var projectContent:some View {
        VStack(alignment:.leading,spacing:14){
            Text(engine.project==nil ? "Open a project to save decisions and preferences." : "Save decisions and preferences for this project. Relevant notes and earlier chats are retrieved locally.").wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)
            if engine.project != nil {
                Picker("Recall scope",selection:Binding(get:{mode},set:{engine.action("memory-settings",["mode":$0])})){Text("Project only").tag("project");Text("Global only").tag("global");Text("Project + global").tag("both");Text("Off").tag("off")}.wixalFont(size:11).disabled(engine.busy)
                Picker("Saved note budget",selection:Binding(get:{budget},set:{engine.action("memory-settings",["size":$0])})){Text("Light · 8,000 characters").tag(8000);Text("Balanced · 24,000").tag(24000);Text("Detailed · 48,000").tag(48000)}.wixalFont(size:11).disabled(engine.busy)
                ProgressView(value:Double(used),total:Double(budget)).tint(theme.accent).accessibilityLabel("Saved project memory capacity")
                Text("\(used.formatted()) / \(budget.formatted()) saved characters").wixalFont(size:10).foregroundStyle(theme.muted)
                Text("Relevant notes and earlier chats are selected to fit the model’s context. Earlier chats do not consume the saved-note budget. Current corrections take precedence.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
                if memories.isEmpty{Text("No saved project notes yet.").wixalFont(size:11).foregroundStyle(theme.muted)}
                ForEach(Array(memories.filter{noteSearch.isEmpty || textValue($0["content"]).localizedCaseInsensitiveContains(noteSearch)}.enumerated()),id:\.offset){_,item in VStack(alignment:.leading,spacing:10){Text(textValue(item["content"])).wixalFont(size:12).textSelection(.enabled);HStack{Button("Edit"){editing=textValue(item["id"]);note=textValue(item["content"])}.disabled(!projectEnabled);Button("Delete",role:.destructive){forgetting=textValue(item["id"])};Spacer()}.wixalFont(size:10).buttonStyle(WixalButtonStyle(inline:true)).disabled(engine.busy)}.wixalCard()}
                Text(editing==nil ? "Add a note" : "Edit saved note").wixalFont(size:12,weight:.medium)
                TextEditor(text:$note).accessibilityLabel("New project memory").wixalFont(size:12).scrollContentBackground(.hidden).frame(height:120).wixalField().disabled(!projectEnabled || engine.busy)
                Text("\(note.count) / 4,000 characters").wixalFont(size:10).foregroundStyle(note.count>4000 ? .red : theme.muted)
                HStack{Button(editing==nil ? "Save memory" : "Save changes",action:saveNote).buttonStyle(WixalButtonStyle(outlined:true)).disabled(!projectEnabled || note.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || note.count>4000 || engine.busy);if editing != nil{Button("Cancel edit"){editing=nil;note=""}.buttonStyle(WixalButtonStyle(inline:true))};Spacer()}.wixalFont(size:11)
            }
        }
    }
    private var globalContent:some View {
        VStack(alignment:.leading,spacing:14){
            if section==nil {
            Toggle("Use global preferences",isOn:Binding(get:{engine.state["globalMemoryEnabled"] as? Bool ?? true},set:{engine.action("settings",["globalMemoryEnabled":$0])})).wixalFont(size:12).disabled(engine.busy)
            Text(accountMemory ? "This short profile belongs to your Wixal account. Project notes and chats stay on this Mac." : "Guest preferences stay on this Mac. Signing in uses that account’s separate profile.").wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)
            TextEditor(text:$global).accessibilityLabel("Global preferences").wixalFont(size:12).scrollContentBackground(.hidden).frame(height:160).wixalField()
            Text("\(global.count) / 1,200 characters").wixalFont(size:10).foregroundStyle(global.count>1200 ? .red : theme.muted)
            HStack{Button("Save global preferences"){engine.action("global-memory-save",["content":global])}.disabled(global.count>1200 || engine.busy);if accountMemory{Button("Refresh"){Task{do{_=try await engine.call("global-memory-refresh");global=engine.activeMemory}catch{engine.error=error.localizedDescription}}}}}.wixalFont(size:11).buttonStyle(WixalButtonStyle(outlined:true))
            }
            Text("Saved global memories on this Mac").wixalFont(size:12,weight:.medium)
            if !globalEnabled{Text("Global recall is disabled here. Enable global preferences and choose Both or Global in the project memory scope to save global notes.").wixalFont(size:11).foregroundStyle(theme.muted)}
            Text(section==nil ? "These notes belong to the active guest or account identity. Project-only chats exclude them. Notes stay local; the short profile retains its account sync." : "These notes belong to the active guest or account identity and stay on this Mac. Project-only chats exclude them. Edit the separate short profile in Instructions.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
            ForEach(Array(globalNotes.filter{noteSearch.isEmpty || textValue($0["content"]).localizedCaseInsensitiveContains(noteSearch)}.enumerated()),id:\.offset){_,item in VStack(alignment:.leading,spacing:8){Text(textValue(item["content"])).wixalFont(size:12).textSelection(.enabled);HStack{Button("Edit"){editing=textValue(item["id"]);note=textValue(item["content"])}.disabled(!globalEnabled);Button("Forget",role:.destructive){forgetting=textValue(item["id"])}}.wixalFont(size:10).buttonStyle(WixalButtonStyle(inline:true)).disabled(engine.busy)}.wixalCard()}
            TextEditor(text:$note).accessibilityLabel("New global memory").wixalFont(size:12).scrollContentBackground(.hidden).frame(height:100).wixalField().disabled(!globalEnabled || engine.busy)
            HStack{Button(editing==nil ? "Save global memory" : "Save changes"){saveGlobalNote()}.disabled(!globalEnabled || note.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || note.count>4000 || engine.busy);if editing != nil{Button("Cancel edit"){editing=nil;note=""}}}.wixalFont(size:11).buttonStyle(WixalButtonStyle(outlined:true))
            Text("\(note.count) / 4,000 characters").wixalFont(size:10).foregroundStyle(note.count>4000 ? .red : theme.muted)
            Text("\(engine.memoryStatus["globalUsed"] as? Int ?? 0) / 8,000 saved characters").wixalFont(size:10).foregroundStyle(theme.muted)
        }
    }
    private func saveGlobalNote(){saveMemory(globalScope:true)}
    private func saveNote(){saveMemory(globalScope:false)}
    private func saveMemory(globalScope:Bool){
        let key=draftKey(scope),content=note,id=editing
        Task{do{
            let method=globalScope ? "memory-save" : id==nil ? "memory-add" : "memory-update"
            var params:[String:Any]=["id":id ?? "","content":content]
            if globalScope{params["scope"]="global"}
            _=try await engine.call(method,params)
            settings?.memoryDrafts[key] = .init(text:"",editing:nil)
            if draftKey(scope)==key && note==content{editing=nil;note=""}
        }catch{engine.error=error.localizedDescription}}
    }
    private var recallControls:some View {
        VStack(alignment:.leading,spacing:12){
            Toggle("Reference earlier chats",isOn:Binding(get:{policy["history"] as? Bool ?? true},set:{engine.action("memory-policy",["referenceHistory":$0])})).disabled(engine.busy)
            if section==nil { suggestionControls }
            Text("Project recall stays within this project. Global recall can use personal chats from the active identity. Archived chats are excluded. Suggestions quote your preferences for review; they do not silently save inferred facts.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
            Picker("Local semantic retrieval",selection:Binding(get:{textValue(engine.memoryStatus["embeddingModel"])},set:{engine.action("memory-semantic",["model":$0]);engine.refreshMemory()})) {
                Text("Keyword search").tag("")
                ForEach(Array(engine.models.filter{($0["capabilities"] as? [String] ?? []).contains("embedding")}.enumerated()),id: \.offset) { _,model in Text(textValue(model["name"])).tag(textValue(model["name"])) }
            }.disabled(engine.busy)
            Text("Semantic retrieval uses an installed embedding model on this Mac. Download embeddinggemma in Models to enable it.").wixalFont(size:10).foregroundStyle(theme.muted)
            Button("Review duplicate or conflicting notes") { Task { do { engine.memoryStatus = try await engine.call("memory-consolidate",["scope":scope=="Project" ? "project" : "global"]) as? [String:Any] ?? [:] } catch { engine.error=error.localizedDescription } } }.disabled(engine.busy)
            Button("Index next memory batch") { Task { do { engine.memoryStatus = try await engine.call("memory-index") as? [String:Any] ?? [:] } catch { engine.error=error.localizedDescription } } }.disabled(engine.busy)
            if let retrieval=engine.memoryStatus["retrieval"] as? [String:Any] {
                Text("\(textValue(retrieval["mode"])) · \(retrieval["pending"] as? Int ?? 0) passages waiting · \(retrieval["milliseconds"] as? Int ?? 0) ms").wixalFont(size:10).foregroundStyle(theme.muted)
                if let error=retrieval["error"] as? String { Text(error).wixalFont(size:10).foregroundStyle(theme.muted) }
            }
            HStack{TextField("Find a decision or preference…",text:$query).wixalField().onSubmit(search);Button("Find",action:search).disabled(query.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)}
            ForEach(Array(found.enumerated()),id:\.offset){_,item in memorySource(item)}
        }.wixalFont(size:11).wixalCard()
    }
    private var suggestionControls:some View {
        VStack(alignment:.leading,spacing:12){
            Toggle("Suggest lasting memories",isOn:Binding(get:{policy["suggestions"] as? Bool ?? true},set:{engine.action("memory-policy",["memorySuggestions":$0])})).disabled(engine.busy)
            Toggle("Review lasting decisions with the local model",isOn:Binding(get:{policy["modelReview"] as? Bool ?? false},set:{engine.action("memory-policy",["memoryModelReview":$0])})).disabled(engine.busy || !(policy["suggestions"] as? Bool ?? true))
            Text("Optional: after a reply, the selected chat model reviews a small batch of your statements. Suggestions keep exact quotes and need your approval before saving. This adds a separate local request and its measured usage.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
            Button(reviewing ? "Reviewing conversation…" : "Review this conversation for lasting decisions") { Task { reviewing=true;engine.busy=true;defer{reviewing=false;engine.busy=false};do{engine.memoryStatus=try await engine.call("memory-review") as? [String:Any] ?? [:]}catch{engine.error=error.localizedDescription} } }.disabled(engine.busy || reviewing || engine.session==nil || !(policy["suggestions"] as? Bool ?? true))
            if let review=engine.memoryStatus["review"] as? [String:Any],!review.isEmpty {
                Text("Memory review: \(textValue(review["status"])) · \(review["suggested"] as? Int ?? 0) suggestions · \(review["milliseconds"] as? Int ?? 0) ms").wixalFont(size:10).foregroundStyle(theme.muted)
                if let error=review["error"] as? String{Text(error).wixalFont(size:10).foregroundStyle(theme.muted)}
            }
        }.wixalFont(size:11).wixalCard()
    }
    private var suggestedMemories:some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Review suggestions · \(suggestions.count)").wixalFont(size:12,weight:.medium)
            ForEach(Array(suggestions.enumerated()),id: \.offset) { _,item in
                VStack(alignment:.leading,spacing:8) {
                    Text(textValue(item["relatedId"]).isEmpty ? "Proposed note" : "Proposed correction").fontWeight(.medium)
                    Text("Scope: \(textValue(item["scope"]).capitalized)").foregroundStyle(theme.muted)
                    if !textValue(item["relatedId"]).isEmpty {
                        Text("Current note").fontWeight(.medium)
                        Text(textValue(item["previousContent"])).textSelection(.enabled)
                        Text("Proposed note").fontWeight(.medium)
                    }
                    Text(textValue(item["content"])).textSelection(.enabled)
                    if !textValue(item["sourceSession"]).isEmpty {
                        DisclosureGroup("Original conversation evidence") {
                            Text(sourceQuote(item)).textSelection(.enabled)
                            Button("Open source conversation ↗"){engine.openMemorySource(textValue(item["sourceSession"]))}
                        }
                    }
                    if item["quoteVerified"] as? Bool == true { Text("Exact user quote · \(textValue(item["classification"])) · \(textValue(item["reviewModel"]))").foregroundStyle(theme.muted) }
                    if !textValue(item["relatedId"]).isEmpty {
                        Text(textValue(item["reason"])).foregroundStyle(theme.muted)
                        Text("Replace updates the current note. Combine keeps both texts in one note. Saving separately keeps both notes.").foregroundStyle(theme.muted)
                        HStack {
                            Button("Replace earlier decision") { engine.action("memory-suggestion",["id":textValue(item["id"]),"accept":true,"consolidate":true,"operation":"replace"]) }
                            Button("Combine notes") { engine.action("memory-suggestion",["id":textValue(item["id"]),"accept":true,"consolidate":true,"operation":"merge"]) }
                        }.disabled(engine.busy || !(scope=="Project" ? projectEnabled : globalEnabled))
                    }
                    HStack {
                        Button("Save \(textValue(item["scope"])) memory") {
                            engine.action("memory-suggestion",["id":textValue(item["id"]),"accept":true])
                        }.disabled(!(scope=="Project" ? projectEnabled : globalEnabled))
                        Button("Dismiss") {
                            engine.action("memory-suggestion",["id":textValue(item["id"]),"accept":false])
                        }
                    }.disabled(engine.busy)
                }
            }
        }.wixalFont(size:11).wixalCard()
    }
    private func memorySource(_ item:[String:Any])->some View {
        VStack(alignment:.leading,spacing:7){Text(textValue(item["title"]).isEmpty ? "\(textValue(item["scope"]).capitalized) saved memory" : textValue(item["title"])).wixalFont(size:11,weight:.medium);Text("Source: \(textValue(item["sourceRole"]))").wixalFont(size:10).foregroundStyle(theme.muted);Text(textValue(item["excerpt"] ?? item["content"])).wixalFont(size:11).textSelection(.enabled);if !textValue(item["sourceSession"]).isEmpty{Button("Open source conversation ↗"){engine.openMemorySource(textValue(item["sourceSession"]))}.wixalFont(size:10).buttonStyle(WixalButtonStyle(inline:true))}}.padding(.vertical,6)
    }
    private func sourceQuote(_ item:[String:Any])->String {
        let session=records(engine.state["sessions"]).first{textValue($0["id"])==textValue(item["sourceSession"])}
        let message=records(session?["messages"]).first{textValue($0["id"])==textValue(item["sourceMessage"])}
        return textValue(message?["content"]).isEmpty ? "Original quote unavailable locally. Open the source conversation to inspect the evidence." : textValue(message?["content"])
    }
    private func search(){Task{do{found=records(try await engine.call("memory-recall",["query":query,"scope":scope=="Project" ? "project" : "global"]))}catch{engine.error=error.localizedDescription}}}
}
