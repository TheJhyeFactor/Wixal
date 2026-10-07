import SwiftUI
import AppKit

private func modelNumber(_ value:Any?)->Double{(value as? NSNumber)?.doubleValue ?? 0}
private func modelBytes(_ value:Any?)->String{ByteCountFormatter.string(fromByteCount:Int64(modelNumber(value)),countStyle:.file)}

struct ModelsView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState<[String:Any]> private var manager=[:]
    @ViewState<String> private var search=""
    @ViewState<String> private var tab="Your models"
    @ViewState<String> private var capability="all"
    @ViewState<String> private var fit="all"
    @ViewState<String> private var size="all"
    @ViewState<String> private var sort="name"
    @ViewState<String> private var download=""
    @ViewState<String> private var deleting=""
    @ViewState<Bool> private var operation=false
    @ViewState<Bool> private var loading=true
    @ViewState<String> private var feedback=""
    @ViewState<Bool> private var filtersOpen=false
    private var installed:[[String:Any]]{records(manager["installed"])}
    private var jobs:[[String:Any]]{records(manager["downloads"])}
    private var benchmarks:[[String:Any]]{records(manager["benchmarks"])}
    private var runtime:[String:Any]{manager["runtime"] as? [String:Any] ?? [:]}
    private var library:[String:Any]{manager["library"] as? [String:Any] ?? [:]}
    private var hardware:[String:Any]{manager["hardware"] as? [String:Any] ?? [:]}
    private var benchmark:[String:Any]?{manager["benchmark"] as? [String:Any]}
    private var selected:String{textValue(engine.state["model"])}
    private var locked:Bool{engine.busy || operation || benchmark != nil || !textValue(manager["importing"]).isEmpty}
    private var hasDownload:Bool{jobs.contains{textValue($0["state"])=="downloading"}}
    private var current:[String:Any]?{installed.first{textValue($0["name"])==selected}}
    private var context:Int{engine.state["contextSize"] as? Int ?? 8192}
    private var filterCount:Int{[capability != "all",fit != "all",size != "all",sort != "name"].filter{$0}.count}
    var body:some View {
        WixalPage(eyebrow:"WIXAL LOCAL · ON THIS MAC",title:"Models",subtitle:"Choose a model, check its capabilities and manage your local library."){
            ViewThatFits(in:.horizontal){
                HStack(alignment:.top,spacing:24){summary.frame(width:224);modelLibrary.frame(minWidth:360,maxWidth:.infinity)}
                VStack(alignment:.leading,spacing:24){summary;modelLibrary}
            }
            performance
            Button("Conversation usage & performance ↗"){NotificationCenter.default.post(name:.wixalNavigate,object:"Performance")}.buttonStyle(WixalButtonStyle(outlined:true))
        }
        .task {
            await refresh()
            while !Task.isCancelled {
                do {try await Task.sleep(nanoseconds:1_000_000_000)}catch{break}
                guard !Task.isCancelled else{break}
                if let result=try? await engine.call("model-status") as? [String:Any]{manager=result}
            }
        }
        .alert("Delete this model?",isPresented:Binding(get:{!deleting.isEmpty},set:{if !$0{deleting=""}})){
            Button("Cancel",role:.cancel){deleting=""}
            Button("Delete model",role:.destructive){let name=deleting;deleting="";run("model-delete",["name":name],success:"Model deleted from the native library.")}
        }message:{Text("\(deleting) will be removed from Wixal’s model library. Conversations are kept.")}
    }
    private var summary:some View {
        VStack(alignment:.leading,spacing:20){
            WixalSection(title:"Current model"){
                Text(selected.isEmpty ? "No model selected" : selected).font(.system(size:13,weight:.medium)).textSelection(.enabled)
                Text(selected.isEmpty ? "Choose from your library" : "Wixal Local · On this Mac").font(.system(size:10)).foregroundStyle(theme.muted)
            }
            Divider().overlay(theme.line)
            WixalSection(title:"Context window",detail:"More context needs more memory. Fit estimates use this setting."){
                Picker("Context window",selection:Binding(get:{context},set:{run("model-context",["contextSize":$0])})){
                    if ![4096,8192,16384,32768].contains(context){Text("\(context) tokens · model limit").tag(context)}
                    ForEach([4096,8192,16384,32768],id:\.self){value in Text("\(value/1024)k tokens").tag(value)}
                }.labelsHidden().disabled(locked)
                if let suggested=current?["suggestedContext"] as? Int {
                    Text("Suggested: \(suggested/1024)k for this model.").font(.system(size:10)).foregroundStyle(theme.muted)
                    Button("Use suggested context"){run("model-context",["contextSize":suggested])}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:10)).disabled(locked || suggested==context)
                }else if current != nil{Text("This model may exceed the memory budget. Try a smaller model or measure a benchmark.").font(.system(size:10)).foregroundStyle(theme.muted).lineSpacing(3)}
            }
            Divider().overlay(theme.line)
            WixalSection(title:"On this Mac"){
                Text(textValue(hardware["cpu"]).isEmpty ? "Checking hardware…" : textValue(hardware["cpu"])).font(.system(size:12))
                Text("\(modelBytes(hardware["totalMemory"])) memory · \(Int(modelNumber(hardware["cores"]))) cores").font(.system(size:10)).foregroundStyle(theme.muted)
                Text("Fit estimates reserve 25% for macOS. Benchmarks measure generation speed, not answer quality.").font(.system(size:10)).foregroundStyle(theme.muted).lineSpacing(3)
            }
            Divider().overlay(theme.line)
            engineControls
        }.wixalCard()
    }
    private var engineControls:some View {
        VStack(alignment:.leading,spacing:11){
            HStack{Text("Local engine").font(.system(size:12,weight:.medium));Spacer();Circle().fill(textValue(runtime["status"])=="ready" || textValue(runtime["status"])=="external" ? theme.accent : theme.muted).frame(width:6,height:6)}
            Text("\(textValue(runtime["status"]).capitalized) · \(textValue(runtime["version"]))").font(.system(size:10)).foregroundStyle(theme.muted)
            if !textValue(runtime["error"]).isEmpty{Text(textValue(runtime["error"])).font(.system(size:10)).foregroundStyle(.red).textSelection(.enabled)}
            HStack(spacing:8){
                Button("Start"){run("runtime-start")}.disabled(locked || textValue(runtime["status"])=="ready")
                Button("Stop"){run("runtime-stop")}.disabled(locked || hasDownload || textValue(runtime["status"]) != "ready")
            }.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:10))
            Button("Open model folder ↗"){
                let path=textValue(runtime["library"])
                if !path.isEmpty{NSWorkspace.shared.open(URL(fileURLWithPath:path))}
            }.buttonStyle(.plain).font(.system(size:10)).foregroundStyle(theme.accent).disabled(textValue(runtime["library"]).isEmpty)
            Text("\(modelBytes(library["diskFree"])) available on the model drive").font(.system(size:10)).foregroundStyle(theme.muted)
            if library["loadedAvailable"] as? Bool ?? false {
                let loaded=records(library["loaded"])
                Text(loaded.isEmpty ? "No models loaded in memory" : "\(loaded.count) loaded · \(modelBytes(loaded.reduce(0.0){$0+modelNumber($1["size"])})) model memory").font(.system(size:10)).foregroundStyle(theme.muted)
                Button("Free model memory"){run("model-unload")}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:10)).disabled(locked || loaded.isEmpty)
            }else{Text("Loaded memory unavailable").font(.system(size:10)).foregroundStyle(theme.muted)}
            Text("One loaded model, one request at a time, Flash Attention and an 8-bit context cache.").font(.system(size:10)).foregroundStyle(theme.muted).lineSpacing(3)
        }
    }
    private var modelLibrary:some View {
        VStack(alignment:.leading,spacing:16){
            HStack{Text("Model library").font(.system(size:18,weight:.medium));Spacer();if loading{ProgressView().controlSize(.small)};Button("Refresh"){Task{await refresh()}}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11)).disabled(operation)}
            TextField(tab=="Downloads" ? "Search downloads…" : "Search installed models…",text:$search).wixalField()
            HStack(spacing:7){ForEach(["Your models","Downloads","Import"],id:\.self){name in
                Button{tab=name}label:{HStack(spacing:5){Text(name);if name=="Your models"{Text("\(installed.count)").foregroundStyle(theme.muted)};if name=="Downloads" && jobs.contains(where:{["queued","downloading"].contains(textValue($0["state"]))}){Text("\(jobs.filter{["queued","downloading"].contains(textValue($0["state"]))}.count)").foregroundStyle(theme.accent)}}.font(.system(size:11)).padding(.horizontal,10).padding(.vertical,8).background(tab==name ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6)).overlay(RoundedRectangle(cornerRadius:6).stroke(tab==name ? theme.accent.opacity(0.4) : theme.line,lineWidth:1))}.buttonStyle(.plain).accessibilityAddTraits(tab==name ? .isSelected : [])
            };Spacer(minLength:0)}
            if tab != "Import"{filters}
            if tab=="Your models"{installedList}else if tab=="Import"{imports}else{downloads}
            if !feedback.isEmpty{Text(feedback).font(.system(size:11)).foregroundStyle(theme.muted).textSelection(.enabled).accessibilityAddTraits(.updatesFrequently)}
            if let benchmark{HStack{ProgressView().controlSize(.small);VStack(alignment:.leading,spacing:4){Text(textValue(benchmark["name"]));Text("\(textValue(benchmark["phase"])) · run \(Int(modelNumber(benchmark["sample"])))/2").foregroundStyle(theme.muted)};Spacer();Button("Stop benchmark"){run("benchmark-cancel")}.buttonStyle(WixalButtonStyle(outlined:true))}.font(.system(size:11)).wixalCard()}
        }
    }
    private var filters:some View {
        DisclosureGroup(isExpanded:$filtersOpen){
            VStack(alignment:.leading,spacing:10){
                HStack(spacing:12){filterPicker("Capability",value:$capability,options:[("all","All capabilities"),("tools","Tools"),("vision","Images"),("thinking","Thinking")]);filterPicker("Fit",value:$fit,options:tab=="Downloads" ? [("all","All models"),("estimated","Estimated fit")] : [("all","All models"),("estimated","Estimated fit"),("tested","Benchmarked"),("fast","Tested ≥20 tok/s")])}
                HStack(spacing:12){filterPicker("Size",value:$size,options:[("all","Any size"),("2","Under 2 GB"),("5","Under 5 GB"),("10","Under 10 GB"),("20","Under 20 GB")]);filterPicker("Sort",value:$sort,options:tab=="Downloads" ? [("name","Name"),("size","Size")] : [("name","Name"),("size","Size"),("speed","Benchmark speed")]);Button("Reset"){capability="all";fit="all";size="all";sort="name";search=""}.buttonStyle(.plain).foregroundStyle(theme.accent).font(.system(size:10))}
            }.padding(.top,12)
        }label:{Text(filterCount>0 ? "Filters · \(filterCount)" : "Filters").font(.system(size:11)).foregroundStyle(theme.muted)}.padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:7))
    }
    private func filterPicker(_ title:String,value:Binding<String>,options:[(String,String)])->some View {
        VStack(alignment:.leading,spacing:5){Text(title).font(.system(size:9)).foregroundStyle(theme.muted);Picker(title,selection:value){ForEach(options,id:\.0){option in Text(option.1).tag(option.0)}}.labelsHidden().font(.system(size:11))}.frame(maxWidth:.infinity,alignment:.leading)
    }
    private var installedList:some View {
        VStack(alignment:.leading,spacing:12){
            let rows=filtered(installed)
            Text("\(rows.count) installed models\(rows.count==installed.count ? "" : " of \(installed.count)") · select a model to use it").font(.system(size:10)).foregroundStyle(theme.muted)
            if rows.isEmpty{empty(installed.isEmpty ? "Your library is empty" : "No matching models",detail:installed.isEmpty ? "Download a model or import one from your existing Wixal or Ollama library." : "Try another search or reset the filters.")}
            ForEach(Array(rows.enumerated()),id:\.offset){_,model in modelCard(model)}
        }
    }
    private func modelCard(_ model:[String:Any])->some View {
        let name=textValue(model["name"]),details=model["details"] as? [String:Any] ?? [:],caps=model["capabilities"] as? [String] ?? [],fitInfo=model["fit"] as? [String:Any] ?? [:]
        let saved=score(model)
        return VStack(alignment:.leading,spacing:13){
            HStack(alignment:.top){VStack(alignment:.leading,spacing:6){HStack{Text(name).font(.system(size:13,weight:.medium));if selected==name{Text("✓ CURRENT").font(.system(size:9,design:.monospaced)).foregroundStyle(theme.accent)}};Text([textValue(details["parameter_size"]),textValue(details["quantization_level"]),"\(Int(modelNumber(model["contextLength"]))/1024)k max context"].filter{!$0.isEmpty}.joined(separator:" · ")).font(.system(size:10)).foregroundStyle(theme.muted)};Spacer();VStack(alignment:.trailing,spacing:3){Text(modelBytes(model["size"]));Text("on disk").font(.system(size:9))}.font(.system(size:11)).foregroundStyle(theme.muted)}
            HStack(spacing:6){if caps.contains("completion"){badge("Chat")};ForEach(caps.filter{$0 != "completion"},id:\.self){badge($0=="vision" ? "Images" : $0.capitalized)};Spacer()}
            Divider().overlay(theme.line)
            Text(saved != nil ? "\(String(format:"%.1f",modelNumber(saved?["tokensPerSecond"]))) tok/s · tested at \(Int(modelNumber(saved?["context"]))/1024)k" : "\((fitInfo["fits"] as? Bool ?? false) ? "Estimated fit" : "May exceed RAM") · \(modelBytes(fitInfo["required"])) estimate").font(.system(size:10)).foregroundStyle(theme.muted)
            HStack(spacing:12){Button("Benchmark"){run("benchmark-start",["name":name])}.buttonStyle(.plain).foregroundStyle(theme.accent).disabled(locked || hasDownload || !caps.contains("completion"));Menu{Button("Free model memory"){run("model-unload",["name":name])};Button("Delete model…",role:.destructive){deleting=name}}label:{Image(systemName:"ellipsis")}.menuStyle(.borderlessButton).frame(width:24).disabled(locked || hasDownload).accessibilityLabel("Manage \(name)");Spacer();if caps.contains("embedding") && !caps.contains("completion"){Button("Use for memory"){run("memory-semantic",["model":name],success:"Using \(name) for memory retrieval.")}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked)}else{Button(selected==name ? "Selected" : "Use model →"){run("model-use",["name":name],success:"Using \(name).")}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(locked || selected==name)}}.font(.system(size:11))
        }.wixalCard().overlay(RoundedRectangle(cornerRadius:9).stroke(selected==name ? theme.accent.opacity(0.6) : .clear,lineWidth:1))
    }
    private func badge(_ text:String)->some View{Text(text).font(.system(size:9)).padding(.horizontal,7).padding(.vertical,4).background(theme.selected,in:RoundedRectangle(cornerRadius:4))}
    private var imports:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Import an existing model. Wixal verifies the model files, copies them into this library and selects chat models when ready. Embedding models can be selected for memory retrieval.").font(.system(size:11)).foregroundStyle(theme.muted).lineSpacing(4)
            let rows=engine.imports.filter{search.isEmpty || textValue($0["name"]).localizedCaseInsensitiveContains(search)}
            if rows.isEmpty{empty("No models available to import",detail:"Wixal checks your original Wixal and Ollama model folders.")}
            ForEach(Array(rows.enumerated()),id:\.offset){_,item in HStack{VStack(alignment:.leading,spacing:6){Text(textValue(item["name"])).font(.system(size:12,weight:.medium));Text(textValue(item["source"])).font(.system(size:9)).foregroundStyle(theme.muted).lineLimit(2)};Spacer();Button("Import & use →"){run("model-import",item,success:"Imported and selected \(textValue(item["name"])).")}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11)).disabled(locked || hasDownload)}.wixalCard()}
        }
    }
    private var downloads:some View {
        VStack(alignment:.leading,spacing:16){
            VStack(alignment:.leading,spacing:12){Text("Download a model").font(.system(size:14,weight:.medium));Text("Downloads use the Ollama registry and run one at a time. Paused transfers can resume.").font(.system(size:11)).foregroundStyle(theme.muted);HStack{TextField("For example, qwen3:4b",text:$download).wixalField();Button(hasDownload ? "Queue download" : "Download"){let tag=download.trimmingCharacters(in:.whitespacesAndNewlines);download="";run("model-pull",["name":tag],success:"Queued \(tag).")}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:11)).disabled(locked || download.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)}}.wixalCard()
            if !jobs.isEmpty{WixalSection(title:"Download queue",detail:"\(jobs.filter{["queued","downloading"].contains(textValue($0["state"]))}.count) pending"){ForEach(Array(jobs.reversed().enumerated()),id:\.offset){_,job in downloadCard(job)}}}
            WixalSection(title:"Models for this Mac",detail:"Local catalog · checked \(textValue(manager["catalogChecked"])) · sizes and memory fit are estimates."){
                let rows=filtered(records(manager["catalog"]),catalog:true)
                if rows.isEmpty{empty("No matching downloads",detail:"Try another search or reset the filters.")}
                ForEach(Array(rows.enumerated()),id:\.offset){_,model in catalogCard(model)}
            }
        }
    }
    private func catalogCard(_ model:[String:Any])->some View {
        let name=textValue(model["name"]),present=installed.contains{textValue($0["name"])==name},fitInfo=model["fit"] as? [String:Any] ?? [:]
        let queued=jobs.last{ textValue($0["name"])==name && ["queued","downloading","paused"].contains(textValue($0["state"])) }
        return HStack(spacing:14){VStack(alignment:.leading,spacing:6){Button(name){download=name}.buttonStyle(.plain).font(.system(size:12,weight:.medium)).accessibilityLabel("Choose download tag \(name)");Text((model["capabilities"] as? [String] ?? []).map{$0=="vision" ? "Images" : $0.capitalized}.joined(separator:" · ")).font(.system(size:10)).foregroundStyle(theme.muted);Text((fitInfo["fits"] as? Bool ?? false) ? "Estimated fit" : "May exceed RAM").font(.system(size:10)).foregroundStyle(theme.muted)};Spacer();Text(modelBytes(model["size"])).font(.system(size:11)).foregroundStyle(theme.muted);Button(present ? "Use model" : queued != nil ? textValue(queued?["state"]).capitalized : "Download"){run(present ? "model-use" : "model-pull",["name":name])}.buttonStyle(WixalButtonStyle(outlined:true)).font(.system(size:10)).disabled(locked || (!present && queued != nil))}.wixalCard()
    }
    private func embeddingOnly(_ name:String)->Bool {let caps=installed.first{textValue($0["name"])==name}?["capabilities"] as? [String] ?? [];return caps.contains("embedding") && !caps.contains("completion")}
    private func downloadCard(_ job:[String:Any])->some View {
        let state=textValue(job["state"]),id=textValue(job["id"]),total=modelNumber(job["total"]),completed=modelNumber(job["completed"])
        return VStack(alignment:.leading,spacing:10){HStack{Text(textValue(job["name"])).font(.system(size:12,weight:.medium));Spacer();Text(state.capitalized).font(.system(size:10)).foregroundStyle(theme.muted)};Text(textValue(job["status"])).font(.system(size:11)).foregroundStyle(theme.muted)
            if ["downloading","paused"].contains(state){if total>0{ProgressView(value:min(completed,total),total:total).tint(theme.accent).accessibilityLabel("Download progress for \(textValue(job["name"]))")}else if state=="downloading"{ProgressView().controlSize(.small)}}
            if total>0{Text("\(modelBytes(completed)) / \(modelBytes(total)) reported\(modelNumber(job["rate"])>0 ? " · \(modelBytes(job["rate"]))/s" : "")\(modelNumber(job["eta"])>0 ? " · about \(Int(modelNumber(job["eta"])))s remaining" : "")").font(.system(size:10)).foregroundStyle(theme.muted)}
            if !textValue(job["error"]).isEmpty{Text(textValue(job["error"])).font(.system(size:10)).foregroundStyle(.red).textSelection(.enabled)}
            HStack(spacing:14){
                if ["queued","downloading"].contains(state){downloadAction("Pause",id:id,action:"pause");downloadAction("Cancel",id:id,action:"cancel")}
                else if ["paused","failed","cancelled"].contains(state){downloadAction(state=="paused" ? "Resume" : "Retry",id:id,action:state=="paused" ? "resume" : "retry");downloadAction("Remove",id:id,action:"remove")}
                else{Button(embeddingOnly(textValue(job["name"])) ? "Use for memory" : "Use model →"){run(embeddingOnly(textValue(job["name"])) ? "memory-semantic" : "model-use",["name":textValue(job["name"]),"model":textValue(job["name"])])}.disabled(locked);downloadAction("Dismiss",id:id,action:"remove")}
                Spacer()
            }.buttonStyle(.plain).font(.system(size:11)).foregroundStyle(theme.accent)
        }.wixalCard()
    }
    private func downloadAction(_ title:String,id:String,action:String)->some View{Button(title){run("model-download-action",["id":id,"action":action])}.disabled(operation || (engine.busy && ["resume","retry"].contains(action)) || benchmark != nil)}
    private var performance:some View {
        WixalSection(title:"Performance",detail:"Saved benchmarks use the engine’s reported generation counters. The first run includes model loading; the second measures warm generation."){
            let rows=benchmarks.filter{textValue($0["hardwareId"])==textValue(hardware["id"])}
            if rows.isEmpty{Text("Benchmark an installed model to measure speed on this Mac.").font(.system(size:11)).foregroundStyle(theme.muted)}
            ForEach(Array(rows.reversed().enumerated()),id:\.offset){_,row in HStack(alignment:.top){VStack(alignment:.leading,spacing:6){Text(textValue(row["name"])).font(.system(size:12,weight:.medium));Text("\(String(format:"%.1f",modelNumber(row["tokensPerSecond"]))) tok/s · \(Int(modelNumber(row["context"]))/1024)k context").font(.system(size:11));Text("First output \(String(format:"%.2f",modelNumber(row["timeToFirstToken"])))s\(modelNumber(row["loadedBytes"])>0 ? " · \(modelBytes(row["loadedBytes"])) loaded" : "")").font(.system(size:10)).foregroundStyle(theme.muted);if row["fixture"] as? Bool ?? false{Text("Test fixture · not a real model benchmark").font(.system(size:10)).foregroundStyle(theme.muted)}};Spacer();Text(Date(timeIntervalSince1970:modelNumber(row["created"])/1000),style:.date).font(.system(size:10)).foregroundStyle(theme.muted)}.wixalCard()}
        }
    }
    private func filtered(_ rows:[[String:Any]],catalog:Bool=false)->[[String:Any]] {
        rows.filter {model in
            let modelFit=model["fit"] as? [String:Any] ?? [:],saved=score(model)
            return (search.isEmpty || textValue(model["name"]).localizedCaseInsensitiveContains(search)) && (capability=="all" || (model["capabilities"] as? [String] ?? []).contains(capability)) && (size=="all" || modelNumber(model["size"])<((Double(size) ?? 0)*1e9)) && (fit=="all" || fit=="estimated" && (modelFit["fits"] as? Bool ?? false) || !catalog && fit=="tested" && saved != nil || !catalog && fit=="fast" && modelNumber(saved?["tokensPerSecond"])>=20)
        }.sorted{a,b in if sort=="size"{return modelNumber(a["size"])<modelNumber(b["size"])};if sort=="speed" && !catalog{return modelNumber(score(a)?["tokensPerSecond"])>modelNumber(score(b)?["tokensPerSecond"])};return textValue(a["name"]).localizedStandardCompare(textValue(b["name"])) == .orderedAscending}
    }
    private func score(_ model:[String:Any])->[String:Any]? {benchmarks.last{textValue($0["name"])==textValue(model["name"]) && textValue($0["digest"])==textValue(model["digest"]) && textValue($0["hardwareId"])==textValue(hardware["id"]) && textValue($0["status"])=="completed" && !($0["fixture"] as? Bool ?? false)}}
    private func empty(_ title:String,detail:String)->some View{VStack(alignment:.leading,spacing:8){Text(title).font(.system(size:13,weight:.medium));Text(detail).font(.system(size:11)).foregroundStyle(theme.muted).lineSpacing(4)}.wixalCard()}
    @MainActor private func refresh() async {
        loading=true;defer{loading=false}
        do {manager=try await engine.call("model-status",["refresh":true]) as? [String:Any] ?? [:];engine.models=installed;engine.imports=records(try await engine.call("model-imports"))}catch{engine.error=error.localizedDescription;feedback=error.localizedDescription;manager=(try? await engine.call("model-status") as? [String:Any]) ?? manager}
    }
    private func run(_ method:String,_ params:[String:Any]=[:],success:String=""){
        operation=true
        Task{defer{operation=false};do{let result=try await engine.call(method,params);if let snapshot=result as? [String:Any]{manager=snapshot};if let imported=result as? [[String:Any]]{engine.models=imported};manager=try await engine.call("model-status") as? [String:Any] ?? manager;engine.models=installed;feedback=success}catch{engine.error=error.localizedDescription;feedback=error.localizedDescription}}
    }
}
