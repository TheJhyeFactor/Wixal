import SwiftUI
import AppKit

private func modelNumber(_ value:Any?)->Double{(value as? NSNumber)?.doubleValue ?? 0}
private func modelBytes(_ value:Any?)->String{value == nil || modelNumber(value)<=0 ? "Unknown" : ByteCountFormatter.string(fromByteCount:Int64(modelNumber(value)),countStyle:.file)}

private func modelRAM(_ value:Any?)->String{value == nil || modelNumber(value)<=0 ? "Unknown" : ByteCountFormatter.string(fromByteCount:Int64(modelNumber(value)),countStyle:.memory)}

struct ModelsView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState<[String:Any]> private var manager=[:]
    @ViewState<String> private var search=""
    @ViewState<String> private var tab="Browse"
    @ViewState<String> private var capability="all"
    @ViewState<String> private var publisher="all"
    @ViewState<String> private var customPublisher=""
    @ViewState<String> private var parameters="all"
    @ViewState<String> private var fit="all"
    @ViewState<String> private var size="all"
    @ViewState<String> private var sort="name"
    @ViewState<String> private var deleting=""
    @ViewState<Bool> private var operation=false
    @ViewState<Bool> private var loading=true
    @ViewState<String> private var feedback=""
    @ViewState<[[String:Any]]> private var hubRows=[]
    @ViewState<String> private var nextPage=""
    @ViewState<Bool> private var searchedHub=false
    @ViewState<Bool> private var searchingHub=false
    @ViewState<Int> private var searchRevision=0
    @ViewState<String> private var hubError=""
    @ViewState<String> private var expanded=""
    @ViewState<Bool> private var importsOpen=false
    @ViewState<Bool> private var controlsOpen=false
    @ViewState<Bool> private var performanceOpen=false
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
    private var providerValue:String{publisher=="custom" ? customPublisher.trimmingCharacters(in:.whitespacesAndNewlines) : publisher=="all" ? "" : publisher}
    private var providerOptions:[(String,String)]{
        var values=Set((records(manager["catalog"])+hubRows+installed).map{textValue($0["publisher"])}.filter{!$0.isEmpty && $0 != "Unknown"})
        if !["all","custom"].contains(publisher){values.insert(publisher)}
        return [("all","All providers")]+values.sorted().map{($0,$0)}+[("custom","Other provider…")]
    }
    private var catalog:[[String:Any]]{
        if searchedHub{return hubRows}
        let groups=Dictionary(grouping:records(manager["catalog"])){textValue($0["repo"])}
        return groups.values.compactMap{files in guard var row=files.first else{return nil};row["files"]=files.sorted{modelNumber($0["size"])<modelNumber($1["size"])};return row}
    }
    var body:some View {
        WixalPage(eyebrow:"MODEL LIBRARY",title:"Models",subtitle:"Discover models on Hugging Face and manage your local library."){
            HStack(spacing:16){Text("This Mac · \(modelRAM(hardware["totalMemory"])) RAM");Text("\(modelBytes(library["diskFree"])) disk available");Spacer()}.wixalFont(size:11).foregroundStyle(theme.muted)
            modelLibrary
            DisclosureGroup("Model & engine settings",isExpanded:$controlsOpen){summary.padding(.top,12)}.wixalFont(size:12)
            DisclosureGroup("Saved benchmarks",isExpanded:$performanceOpen){performance.padding(.top,12)}.wixalFont(size:12)
        }
        .task {
            await refresh()
            while !Task.isCancelled {
                do {try await Task.sleep(nanoseconds:1_000_000_000)}catch{break}
                guard !Task.isCancelled else{break}
                if let result=try? await engine.call("model-status") as? [String:Any]{manager=result;engine.models=installed}
            }
        }
        .onChange(of:publisher){_,_ in invalidateSearch()}
        .onChange(of:parameters){_,_ in invalidateSearch()}
        .onChange(of:capability){_,_ in invalidateSearch()}
        .onChange(of:customPublisher){_,_ in invalidateSearch()}
        .onChange(of:search){_,_ in invalidateSearch()}
        .onDisappear{searchRevision+=1}
        .alert("Delete this model?",isPresented:Binding(get:{!deleting.isEmpty},set:{if !$0{deleting=""}})){
            Button("Cancel",role:.cancel){deleting=""}
            Button("Delete model",role:.destructive){let name=deleting;deleting="";run("model-delete",["name":name],success:"Model removed. Conversations are kept.")}
        }message:{Text("\(deleting) will be removed from the local library. Its unused Hugging Face cache is also removed. Conversations are kept.")}
    }
    private var modelLibrary:some View {
        VStack(alignment:.leading,spacing:16){
            HStack(spacing:16){ForEach(["Browse","Your models"],id:\.self){name in
                Button{tab=name;expanded=""}label:{Text(name + (name=="Your models" ? " · \(installed.count)" : "")).wixalFont(size:13,weight:.medium).padding(.vertical,9).padding(.horizontal,12).background(tab==name ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6))}.buttonStyle(.plain).accessibilityAddTraits(tab==name ? .isSelected : [])
            };Spacer();Button("Refresh library"){Task{await refresh()}}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(operation);if loading{ProgressView().controlSize(.small)}}
            HStack{TextField(tab=="Browse" ? "Search models or providers…" : "Search your models…",text:$search).wixalField().onSubmit{if tab=="Browse"{searchHub()}};if tab=="Browse"{Button(searchingHub ? "Searching…" : "Search Hugging Face"){searchHub()}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(searchingHub)}}
            filters
            if publisher=="custom"{TextField("Hugging Face provider, for example bartowski",text:$customPublisher).wixalField().onSubmit{searchHub()}}
            if tab=="Browse"{browseList}else{yourModels}
            if !feedback.isEmpty{Text(feedback).wixalFont(size:11).foregroundStyle(theme.muted).textSelection(.enabled).accessibilityAddTraits(.updatesFrequently)}
            if let benchmark{HStack{ProgressView().controlSize(.small);Text("\(textValue(benchmark["name"])) · \(textValue(benchmark["phase"]))");Spacer();Button("Stop benchmark"){run("benchmark-cancel")}}.wixalFont(size:11).wixalCard()}
        }
    }
    private var filters:some View {
        VStack(alignment:.leading,spacing:12){
            ViewThatFits(in:.horizontal){
                HStack(spacing:12){typePicker;providerPicker;parameterPicker}
                VStack(alignment:.leading,spacing:10){typePicker;providerPicker;parameterPicker}
            }
            ViewThatFits(in:.horizontal){
                HStack(spacing:12){sizePicker;fitPicker;sortPicker;Button("Clear"){resetFilters()}.buttonStyle(.plain).wixalFont(size:11)}
                VStack(alignment:.leading,spacing:10){sizePicker;fitPicker;sortPicker;Button("Clear filters"){resetFilters()}.buttonStyle(.plain)}
            }
        }
    }
    private var typePicker:some View{filterPicker("Model type",value:$capability,options:[("all","All types"),("chat","Chat"),("coding","Coding"),("reasoning","Reasoning"),("embedding","Embeddings"),("vision","Images + text")])}
    private var providerPicker:some View{filterPicker("Provider / publisher",value:$publisher,options:providerOptions)}
    private var parameterPicker:some View{filterPicker("Parameters",value:$parameters,options:[("all","Any model size"),("2","Under 2B"),("8","2B–8B"),("large","Over 8B")])}
    private var sizePicker:some View{filterPicker("Download / disk size",value:$size,options:[("all","Any file size"),("2","Under 2 GB"),("5","Under 5 GB"),("10","Under 10 GB"),("20","Under 20 GB")])}
    private var fitPicker:some View{filterPicker("Memory",value:$fit,options:[("all","Any RAM estimate"),("estimated","Estimated fit on this Mac")])}
    private var sortPicker:some View{filterPicker("Sort",value:$sort,options:[("name","Name"),("size","Smallest file"),("parameters","Parameter count")])}
    private func filterPicker(_ title:String,value:Binding<String>,options:[(String,String)])->some View {
        VStack(alignment:.leading,spacing:5){Text(title).wixalFont(size:11).foregroundStyle(theme.muted);Picker(title,selection:value){ForEach(options,id:\.0){option in Text(option.1).tag(option.0)}}.labelsHidden().wixalFont(size:12)}.frame(minWidth:130,maxWidth:.infinity,alignment:.leading)
    }
    private func resetFilters(){capability="all";publisher="all";customPublisher="";parameters="all";fit="all";size="all";sort="name";search="";invalidateSearch()}
    private func invalidateSearch(){searchRevision+=1;searchedHub=false;hubRows=[];nextPage="";hubError="";expanded="";searchingHub=false}
    private func searchHub(more:Bool=false){
        let revision=searchRevision
        let query:[String:Any]=["search":search.trimmingCharacters(in:.whitespacesAndNewlines),"publisher":providerValue,"parameters":parameters,"type":capability,"page":more ? nextPage : ""]
        searchingHub=true;hubError=""
        Task {
            do {let result=try await engine.call("model-hf-search",query) as? [String:Any] ?? [:]
                guard revision==searchRevision else{return}
                let rows=records(result["models"])
                hubRows=more ? hubRows+rows.filter{row in !hubRows.contains{textValue($0["repo"])==textValue(row["repo"])}} : rows
                nextPage=textValue(result["nextPage"]);searchedHub=true
            }catch{if revision==searchRevision{hubError=error.localizedDescription}}
            if revision==searchRevision{searchingHub=false}
        }
    }
    private var browseList:some View {
        VStack(alignment:.leading,spacing:10){
            let rows=filtered(catalog,catalog:true)
            HStack{Text("\(rows.count) models · \(searchedHub ? "Hugging Face results" : "Saved catalog")").wixalFont(size:11).foregroundStyle(theme.muted);Spacer();if !searchedHub{Text("Checked \(textValue(manager["catalogChecked"]))").wixalFont(size:11).foregroundStyle(theme.muted)}}
            if searchingHub{HStack{ProgressView().controlSize(.small);Text("Inspecting public model files…").wixalFont(size:12)}}
            if !hubError.isEmpty{Text(hubError).wixalFont(size:12).foregroundStyle(.red).textSelection(.enabled)}
            if rows.isEmpty && !searchingHub{empty("No matching models",detail:searchedHub ? "Try another filter or load the next page. Unknown sizes and memory estimates are excluded by size and fit filters." : "Search Hugging Face for more providers and model types, or clear the filters.")}
            ForEach(Array(rows.enumerated()),id:\.offset){_,model in browseRow(model)}
            if searchedHub && !nextPage.isEmpty{Button("Load more models"){searchHub(more:true)}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(searchingHub || hubRows.count>=120)}
            Text("Provider means the Hugging Face repository publisher. Model type is metadata, not a verified capability. Public single-file GGUFs are supported; compatibility is checked after import.").wixalFont(size:11).foregroundStyle(theme.muted)
        }
    }
    private func matchingFiles(_ model:[String:Any])->[[String:Any]]{records(model["files"]).filter{file in (size=="all" || modelNumber(file["size"])>0 && modelNumber(file["size"])<(Double(size) ?? 0)*1e9) && (fit=="all" || (file["fit"] as? [String:Any])?["fits"] as? Bool == true)}.sorted{modelNumber($0["size"])<modelNumber($1["size"])}}
    private func browseRow(_ model:[String:Any])->some View {
        let repo=textValue(model["repo"]),files=matchingFiles(model),representative=files.first ?? model
        return VStack(alignment:.leading,spacing:12){
            compactHeader(model,sizeValue:representative["size"],sizeLabel:"download",action:{expanded=expanded==repo ? "" : repo},actionTitle:expanded==repo ? "Close" : "View files")
            memoryLine(representative)
            if expanded==repo {
                Divider().overlay(theme.line)
                Text(repo).wixalFont(size:11).foregroundStyle(theme.muted).textSelection(.enabled)
                if files.isEmpty{Text(textValue(model["unavailable"]).isEmpty ? "No supported files match these filters." : textValue(model["unavailable"])).wixalFont(size:12).foregroundStyle(theme.muted)}
                ForEach(Array(files.enumerated()),id:\.offset){_,file in fileRow(file)}
            }
        }.wixalCard()
    }
    private func fileRow(_ file:[String:Any])->some View {
        let name=textValue(file["name"]),present=installed.contains{textValue($0["name"])==name},queued=jobs.contains{textValue($0["name"])==name && ["queued","downloading","paused","failed"].contains(textValue($0["state"]))}
        return VStack(alignment:.leading,spacing:7){
            HStack{VStack(alignment:.leading,spacing:4){Text(textValue(file["file"])).wixalFont(size:12).textSelection(.enabled);Text("\(modelBytes(file["size"])) · \(textValue(file["license"]))").wixalFont(size:11).foregroundStyle(theme.muted)};Spacer();Button(present ? "Installed" : queued ? "In your models" : "Download"){
                if queued{tab="Your models"}else{tab="Your models";run("model-pull",["repo":textValue(file["repo"]),"file":textValue(file["file"]),"revision":textValue(file["revision"])])}
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(present || (!queued && locked))}
            memoryLine(file)
        }.padding(.vertical,6)
    }
    private func compactHeader(_ model:[String:Any],sizeValue:Any?,sizeLabel:String,action:@escaping ()->Void,actionTitle:String)->some View {
        HStack(alignment:.center,spacing:14){
            VStack(alignment:.leading,spacing:5){Text(textValue(model["displayName"]).isEmpty ? textValue(model["name"]) : textValue(model["displayName"])).wixalFont(size:13,weight:.medium).textSelection(.enabled);Text("\(textValue(model["publisher"]).isEmpty ? "Unknown provider" : textValue(model["publisher"])) · \(parameterLabel(model)) · \(typeLabel(model))").wixalFont(size:11).foregroundStyle(theme.muted)}.frame(maxWidth:.infinity,alignment:.leading)
            VStack(alignment:.trailing,spacing:3){Text(modelBytes(sizeValue)).wixalFont(size:12);Text(sizeLabel).wixalFont(size:11).foregroundStyle(theme.muted)}
            Button(actionTitle,action:action).buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:12)
        }
    }
    private func memoryLine(_ model:[String:Any])->some View {
        let info=model["fit"] as? [String:Any] ?? [:]
        return Text(modelNumber(info["required"])>0 ? "Estimated model RAM \(modelRAM(info["required"])) · Recommended Mac RAM \(modelRAM(info["recommended"])) · \(Int(modelNumber(info["context"]))/1024)k context · \((info["fits"] as? Bool ?? false) ? "Estimated fit" : "May exceed this Mac’s budget")" : "RAM requirement unknown until file metadata is available").wixalFont(size:11).foregroundStyle(theme.muted).help("Estimate includes weights, context cache and overhead; recommended total RAM reserves 25% for macOS. Actual memory depends on the model and runtime.")
    }
    private func parameterLabel(_ model:[String:Any])->String{let count=modelNumber(model["parameters"]);return count>0 ? String(format:"%.1fB parameters",count/1e9) : "Parameters unknown"}
    private func typeLabel(_ model:[String:Any])->String{let types=model["types"] as? [String] ?? [];return types.isEmpty ? "Type unknown" : types.map{$0=="embedding" ? "Embeddings" : $0=="vision" ? "Images + text" : $0.capitalized}.joined(separator:" / ")}
    private var yourModels:some View {
        VStack(alignment:.leading,spacing:12){
            let pending=jobs.filter{job in textValue(job["state"]) != "completed" && !installed.contains{model in textValue(model["name"])==textValue(job["name"])}}
            // Keep transfers visible even when an installed-model filter excludes their metadata.
            let downloads=pending,models=filtered(installed)
            Text("\(models.count) installed · \(downloads.count) download jobs").wixalFont(size:11).foregroundStyle(theme.muted)
            if models.isEmpty && downloads.isEmpty{empty("No matching models",detail:"Browse Hugging Face to download a model, import an existing model, or clear the filters.")}
            ForEach(Array(downloads.enumerated()),id:\.offset){_,job in downloadCard(job)}
            ForEach(Array(models.enumerated()),id:\.offset){_,model in modelCard(model)}
            DisclosureGroup("Import existing models",isExpanded:$importsOpen){imports.padding(.top,10)}.wixalFont(size:12)
        }
    }
    private func modelCard(_ model:[String:Any])->some View {
        let name=textValue(model["name"]),caps=model["capabilities"] as? [String] ?? [],saved=score(model)
        return VStack(alignment:.leading,spacing:10){
            compactHeader(model,sizeValue:model["size"],sizeLabel:"on disk",action:{run(embeddingOnly(name) ? "memory-semantic" : "model-use",["name":name,"model":name])},actionTitle:selected==name ? "Selected" : embeddingOnly(name) ? "Use for memory" : "Use model").disabled(locked || selected==name)
            memoryLine(model)
            HStack(spacing:14){
                if let saved{Text("\(String(format:"%.1f",modelNumber(saved["tokensPerSecond"]))) tok/s measured").foregroundStyle(theme.muted)}
                Button("Benchmark"){run("benchmark-start",["name":name])}.disabled(locked || hasDownload || !caps.contains("completion"))
                Spacer();Button("Delete model…",role:.destructive){deleting=name}.disabled(locked || hasDownload).accessibilityLabel("Delete model \(name)")
            }.buttonStyle(.plain).wixalFont(size:11)
        }.wixalCard()
    }
    private func filtered(_ rows:[[String:Any]],catalog:Bool=false)->[[String:Any]] {
        rows.filter {model in
            let count=modelNumber(model["parameters"]),types=model["types"] as? [String] ?? [],provider=textValue(model["publisher"])
            let needle=[textValue(model["name"]),textValue(model["displayName"]),textValue(model["repo"]),provider].joined(separator:" ")
            let parameterMatch=parameters=="all" || count>0 && (parameters=="2" && count<2e9 || parameters=="8" && count>=2e9 && count<=8e9 || parameters=="large" && count>8e9)
            let bytes=modelNumber(model["size"]),info=model["fit"] as? [String:Any] ?? [:]
            let fileMatch=catalog ? (size=="all" && fit=="all" || !matchingFiles(model).isEmpty) : (size=="all" || bytes>0 && bytes<(Double(size) ?? 0)*1e9) && (fit=="all" || info["fits"] as? Bool == true)
            return (search.isEmpty || needle.localizedCaseInsensitiveContains(search)) && (providerValue.isEmpty || provider.localizedCaseInsensitiveCompare(providerValue) == .orderedSame) && (capability=="all" || types.contains(capability)) && parameterMatch && fileMatch
        }.sorted{a,b in if sort=="size"{return modelNumber(a["size"])<modelNumber(b["size"])};if sort=="parameters"{return modelNumber(a["parameters"])<modelNumber(b["parameters"])};return textValue(a["displayName"]).localizedStandardCompare(textValue(b["displayName"])) == .orderedAscending}
    }
    private var summary:some View {
        VStack(alignment:.leading,spacing:20){
            WixalSection(title:"Current model"){
                Text(selected.isEmpty ? "No model selected" : selected).wixalFont(size:13,weight:.medium).textSelection(.enabled)
                Text(selected.isEmpty ? "Choose from your library" : "Wixal Local · On this Mac").wixalFont(size:10).foregroundStyle(theme.muted)
            }
            Divider().overlay(theme.line)
            WixalSection(title:"Context window",detail:"More context needs more memory. Fit estimates use this setting."){
                Picker("Context window",selection:Binding(get:{context},set:{run("model-context",["contextSize":$0])})){
                    if ![4096,8192,16384,32768].contains(context){Text("\(context) tokens · model limit").tag(context)}
                    ForEach([4096,8192,16384,32768],id:\.self){value in Text("\(value/1024)k tokens").tag(value)}
                }.labelsHidden().disabled(locked)
                if let suggested=current?["suggestedContext"] as? Int {
                    Text("Suggested: \(suggested/1024)k for this model.").wixalFont(size:10).foregroundStyle(theme.muted)
                    Button("Use suggested context"){run("model-context",["contextSize":suggested])}.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:10).disabled(locked || suggested==context)
                }else if current != nil{Text("This model may exceed the memory budget. Try a smaller model or measure a benchmark.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)}
            }
            Divider().overlay(theme.line)
            WixalSection(title:"On this Mac"){
                Text(textValue(hardware["cpu"]).isEmpty ? "Checking hardware…" : textValue(hardware["cpu"])).wixalFont(size:12)
                Text("\(modelRAM(hardware["totalMemory"])) memory · \(Int(modelNumber(hardware["cores"]))) cores").wixalFont(size:10).foregroundStyle(theme.muted)
                Text("Fit estimates reserve 25% for macOS. Benchmarks measure generation speed, not answer quality.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
            }
            Divider().overlay(theme.line)
            engineControls
        }.wixalCard()
    }
    private var engineControls:some View {
        VStack(alignment:.leading,spacing:11){
            HStack{Text("Local engine").wixalFont(size:12,weight:.medium);Spacer();Circle().fill(textValue(runtime["status"])=="ready" || textValue(runtime["status"])=="external" ? theme.accent : theme.muted).frame(width:6,height:6)}
            Text("\(textValue(runtime["status"]).capitalized) · \(textValue(runtime["version"]))").wixalFont(size:10).foregroundStyle(theme.muted)
            if !textValue(runtime["error"]).isEmpty{Text(textValue(runtime["error"])).wixalFont(size:10).foregroundStyle(.red).textSelection(.enabled)}
            HStack(spacing:8){
                Button("Start"){run("runtime-start")}.disabled(locked || textValue(runtime["status"])=="ready")
                Button("Stop"){run("runtime-stop")}.disabled(locked || hasDownload || textValue(runtime["status"]) != "ready")
            }.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:10)
            Button("Open model folder ↗"){
                let path=textValue(runtime["library"])
                if !path.isEmpty{NSWorkspace.shared.open(URL(fileURLWithPath:path))}
            }.buttonStyle(.plain).wixalFont(size:10).foregroundStyle(theme.accent).disabled(textValue(runtime["library"]).isEmpty)
            Text("\(modelBytes(library["diskFree"])) available on the model drive").wixalFont(size:10).foregroundStyle(theme.muted)
            if library["loadedAvailable"] as? Bool ?? false {
                let loaded=records(library["loaded"])
                Text(loaded.isEmpty ? "No models loaded in memory" : "\(loaded.count) loaded · \(modelBytes(loaded.reduce(0.0){$0+modelNumber($1["size"])})) model memory").wixalFont(size:10).foregroundStyle(theme.muted)
                Button("Free model memory"){run("model-unload")}.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:10).disabled(locked || loaded.isEmpty)
            }else{Text("Loaded memory unavailable").wixalFont(size:10).foregroundStyle(theme.muted)}
            Text("One loaded model, one request at a time, Flash Attention and an 8-bit context cache.").wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)
        }
    }
    private var imports:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Import an existing model. Wixal verifies the model files, copies them into this library and selects chat models when ready. Embedding models can be selected for memory retrieval.").wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)
            let rows=engine.imports.filter{search.isEmpty || textValue($0["name"]).localizedCaseInsensitiveContains(search)}
            if rows.isEmpty{empty("No models available to import",detail:"Wixal checks your original Wixal and Ollama model folders.")}
            ForEach(Array(rows.enumerated()),id:\.offset){_,item in HStack{VStack(alignment:.leading,spacing:6){Text(textValue(item["name"])).wixalFont(size:12,weight:.medium);Text(textValue(item["source"])).wixalFont(size:9).foregroundStyle(theme.muted).lineLimit(2)};Spacer();Button("Import & use →"){run("model-import",item,success:"Imported and selected \(textValue(item["name"])).")}.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11).disabled(locked || hasDownload)}.wixalCard()}
        }
    }
    private func embeddingOnly(_ name:String)->Bool {let caps=installed.first{textValue($0["name"])==name}?["capabilities"] as? [String] ?? [];return caps.contains("embedding") && !caps.contains("completion")}
    private func downloadCard(_ job:[String:Any])->some View {
        let state=textValue(job["state"]),id=textValue(job["id"]),total=modelNumber(job["total"]),completed=modelNumber(job["completed"])
        return VStack(alignment:.leading,spacing:10){HStack{Text(textValue(job["displayName"]).isEmpty ? textValue(job["name"]) : textValue(job["displayName"])).wixalFont(size:12,weight:.medium);Spacer();Text(state.capitalized).wixalFont(size:10).foregroundStyle(theme.muted)};memoryLine(job);Text(textValue(job["status"])).wixalFont(size:11).foregroundStyle(theme.muted)
            if ["downloading","paused"].contains(state){if total>0{ProgressView(value:min(completed,total),total:total).tint(theme.accent).accessibilityLabel("Download progress for \(textValue(job["name"]))")}else if state=="downloading"{ProgressView().controlSize(.small)}}
            if total>0{Text("\(modelBytes(completed)) / \(modelBytes(total)) reported\(modelNumber(job["rate"])>0 ? " · \(modelBytes(job["rate"]))/s" : "")\(modelNumber(job["eta"])>0 ? " · about \(Int(modelNumber(job["eta"])))s remaining" : "")").wixalFont(size:10).foregroundStyle(theme.muted)}
            if !textValue(job["error"]).isEmpty{Text(textValue(job["error"])).wixalFont(size:10).foregroundStyle(.red).textSelection(.enabled)}
            HStack(spacing:14){
                if ["queued","downloading"].contains(state){downloadAction("Pause",id:id,action:"pause");downloadAction("Cancel",id:id,action:"cancel")}
                else if ["paused","failed","cancelled"].contains(state){downloadAction(state=="paused" ? "Resume" : "Retry",id:id,action:state=="paused" ? "resume" : "retry");downloadAction("Remove",id:id,action:"remove")}
                else {
                    if installed.contains(where:{textValue($0["name"]) == textValue(job["name"])}) {
                        Button(embeddingOnly(textValue(job["name"])) ? "Use for memory" : "Use model →"){run(embeddingOnly(textValue(job["name"])) ? "memory-semantic" : "model-use",["name":textValue(job["name"]),"model":textValue(job["name"])])}.disabled(locked)
                    }else if textValue(job["provider"]) == "huggingface" {
                        Button("Download again"){run("model-pull",["repo":textValue(job["repo"]),"file":textValue(job["file"]),"revision":textValue(job["revision"])])}.disabled(locked)
                    }
                    downloadAction("Dismiss",id:id,action:"remove")
                }
                Spacer()
            }.buttonStyle(.plain).wixalFont(size:11).foregroundStyle(theme.accent)
        }.wixalCard()
    }
    private func downloadAction(_ title:String,id:String,action:String)->some View{Button(title){run("model-download-action",["id":id,"action":action])}.disabled(operation || (engine.busy && ["resume","retry"].contains(action)) || benchmark != nil)}
    private var performance:some View {
        WixalSection(title:"Performance",detail:"Saved benchmarks use the engine’s reported generation counters. The first run includes model loading; the second measures warm generation."){
            let rows=benchmarks.filter{textValue($0["hardwareId"])==textValue(hardware["id"])}
            if rows.isEmpty{Text("Benchmark an installed model to measure speed on this Mac.").wixalFont(size:11).foregroundStyle(theme.muted)}
            ForEach(Array(rows.reversed().enumerated()),id:\.offset){_,row in HStack(alignment:.top){VStack(alignment:.leading,spacing:6){Text(textValue(row["name"])).wixalFont(size:12,weight:.medium);Text("\(String(format:"%.1f",modelNumber(row["tokensPerSecond"]))) tok/s · \(Int(modelNumber(row["context"]))/1024)k context").wixalFont(size:11);Text("First output \(String(format:"%.2f",modelNumber(row["timeToFirstToken"])))s\(modelNumber(row["loadedBytes"])>0 ? " · \(modelBytes(row["loadedBytes"])) loaded" : "")").wixalFont(size:10).foregroundStyle(theme.muted);if row["fixture"] as? Bool ?? false{Text("Test fixture · not a real model benchmark").wixalFont(size:10).foregroundStyle(theme.muted)}};Spacer();Text(Date(timeIntervalSince1970:modelNumber(row["created"])/1000),style:.date).wixalFont(size:10).foregroundStyle(theme.muted)}.wixalCard()}
        }
    }
    private func score(_ model:[String:Any])->[String:Any]? {benchmarks.last{textValue($0["name"])==textValue(model["name"]) && textValue($0["digest"])==textValue(model["digest"]) && textValue($0["hardwareId"])==textValue(hardware["id"]) && textValue($0["status"])=="completed" && !($0["fixture"] as? Bool ?? false)}}
    private func empty(_ title:String,detail:String)->some View{VStack(alignment:.leading,spacing:8){Text(title).wixalFont(size:13,weight:.medium);Text(detail).wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)}.wixalCard()}
    @MainActor private func refresh() async {
        loading=true;defer{loading=false}
        do {manager=try await engine.call("model-status",["refresh":true]) as? [String:Any] ?? [:];engine.models=installed;engine.imports=records(try await engine.call("model-imports"))}catch{engine.error=error.localizedDescription;feedback=error.localizedDescription;manager=(try? await engine.call("model-status") as? [String:Any]) ?? manager}
    }
    private func run(_ method:String,_ params:[String:Any]=[:],success:String=""){
        operation=true
        Task{defer{operation=false};do{let result=try await engine.call(method,params);if let snapshot=result as? [String:Any]{manager=snapshot};if let imported=result as? [[String:Any]]{engine.models=imported};manager=try await engine.call("model-status") as? [String:Any] ?? manager;engine.models=installed;feedback=success}catch{engine.error=error.localizedDescription;feedback=error.localizedDescription}}
    }
}
