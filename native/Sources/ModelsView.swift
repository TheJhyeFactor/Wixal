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
    @ViewState<String> private var tab="Library"
    @ViewState<String> private var capability="all"
    @ViewState<String> private var publisher="all"
    @ViewState<[String:Any]> private var filterData=[:]
    @ViewState<Bool> private var typeOpen=false
    @ViewState<Bool> private var providerOpen=false
    @ViewState<Bool> private var moreFiltersOpen=false
    @ViewState<String> private var typeSearch=""
    @ViewState<String> private var providerSearch=""
    @ViewState<[[String:Any]]> private var providerMatches=[]
    @ViewState<Bool> private var findingProviders=false
    @ViewState<String> private var filterError=""
    @ViewState<String> private var providerError=""
    @ViewState<Task<Void,Never>?> private var hubTask=nil
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
    @ViewState<Bool> private var engineOpen=false
    @ViewState<String> private var performanceTab="Benchmarks"
    @ViewState<String> private var inspected=""
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
    private var providerValue:String{publisher=="all" ? "" : publisher}
    private var typeName:String{records(filterData["tasks"]).first{textValue($0["id"])==capability}.map{textValue($0["label"])} ?? capability}
    private var extraFilterCount:Int{[parameters != "all",size != "all",fit != "all"].filter{$0}.count}
    private var catalog:[[String:Any]]{
        if searchedHub{return hubRows}
        let groups=Dictionary(grouping:records(manager["catalog"])){textValue($0["repo"])}
        return groups.values.compactMap{files in guard var row=files.first else{return nil};row["files"]=files.sorted{modelNumber($0["size"])<modelNumber($1["size"])};return row}
    }
    var body:some View {
        WixalPage(eyebrow:"LOCAL AI",title:"Models & performance",subtitle:"Your models, downloads and measured performance in one place."){
            HStack(spacing:16){Text("This Mac · \(modelRAM(hardware["totalMemory"])) RAM");Text("\(modelBytes(library["diskFree"])) disk available");Spacer()}.wixalFont(size:11).foregroundStyle(theme.muted)
            modelLibrary
        }
        .task {
            await refresh()
            await loadFilterOptions()
            while !Task.isCancelled {
                do {try await Task.sleep(nanoseconds:1_000_000_000)}catch{break}
                guard !Task.isCancelled else{break}
                if let result=try? await engine.call("model-status") as? [String:Any]{manager=result;engine.models=installed}
            }
        }
        .onChange(of:publisher){_,_ in invalidateSearch();if tab=="Discover"{searchHub()}}
        .onChange(of:parameters){_,_ in invalidateSearch()}
        .onChange(of:capability){_,_ in invalidateSearch();if tab=="Discover"{searchHub()}}
        .onChange(of:search){_,_ in invalidateSearch()}
        .onDisappear{searchRevision+=1;hubTask?.cancel()}
        .alert("Delete this model?",isPresented:Binding(get:{!deleting.isEmpty},set:{if !$0{deleting=""}})){
            Button("Cancel",role:.cancel){deleting=""}
            Button("Delete model",role:.destructive){let name=deleting;deleting="";run("model-delete",["name":name],success:"Model removed. Conversations are kept.")}
        }message:{Text("\(deleting) will be removed from the local library. Its unused Hugging Face cache is also removed. Conversations are kept.")}
    }
    private var modelLibrary:some View {
        VStack(alignment:.leading,spacing:18){
            SettingsCard {
                SettingsRow(title:selected.isEmpty ? "Choose a model" : modelTitle(current ?? ["name":selected]),detail:engine.modelConnectionLabel,scope:"All workspaces") {
                    Button("Adjust context →"){NotificationCenter.default.post(name:.wixalNavigate,object:"Settings:Context & memory")}.buttonStyle(WixalButtonStyle(inline:true))
                }
            }
            QuietSettingsTabs(items:["Library","Discover","Downloads","Performance"],selection:$tab)
            HStack { Text(tab=="Library" ? "\(installed.count) installed models" : tab=="Downloads" ? "\(jobs.count) download jobs" : tab=="Performance" ? "Measurements on this Mac" : "Public GGUF models").wixalFont(size:11).foregroundStyle(theme.muted);Spacer();Button("Refresh"){Task{await refresh()}}.disabled(operation);if loading{ProgressView().controlSize(.small)} }.wixalFont(size:11)
            if tab=="Library" || tab=="Discover" {
                HStack{TextField(tab=="Discover" ? "Search models or providers…" : "Search your models…",text:$search).wixalField().onSubmit{if tab=="Discover"{searchHub()}};if tab=="Discover"{Button(searchingHub ? "Searching…" : "Search"){searchHub()}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(searchingHub)}}
                filters
                if tab=="Discover"{browseList}else{yourModels;DisclosureGroup("Import existing models"){imports.padding(.top,12)}.wixalFont(size:12)}
            } else if tab=="Downloads" {
                if jobs.isEmpty{empty("No downloads",detail:"Find a model in Discover. Transfers stay available here while you use other pages.")}
                ForEach(Array(jobs.enumerated()),id:\.offset){_,job in downloadCard(job)}
            } else {
                QuietSettingsTabs(items:["Benchmarks","Request usage"],selection:$performanceTab)
                if performanceTab=="Benchmarks"{benchmarkControls;performance}else{PerformanceView(engine:engine,embedded:true)}
            }
            if !feedback.isEmpty{Text(feedback).wixalFont(size:11).foregroundStyle(theme.muted).textSelection(.enabled).accessibilityAddTraits(.updatesFrequently)}
            if let benchmark{HStack{ProgressView().controlSize(.small);Text("\(textValue(benchmark["name"])) · \(textValue(benchmark["phase"]))");Spacer();Button("Stop benchmark"){run("benchmark-cancel")}}.wixalFont(size:11).wixalCard()}
            if tab != "Downloads", let job=jobs.first(where:{["queued","downloading","paused","failed"].contains(textValue($0["state"]))}) {
                Button{tab="Downloads"}label:{HStack{Image(systemName:"arrow.down.circle");Text(textValue(job["name"])).lineLimit(1);Spacer();Text(textValue(job["state"]).capitalized);Image(systemName:"chevron.right")}.wixalFont(size:11).wixalCard()}.buttonStyle(WixalButtonStyle(inline:true)).accessibilityLabel("Open downloads")
            }
            DisclosureGroup("Local engine & hardware",isExpanded:$engineOpen){summary.padding(.top,12)}.wixalFont(size:12)
        }
    }
    private var benchmarkControls:some View {
        VStack(alignment:.leading,spacing:10){
            Text("Measure generation speed").wixalFont(size:13,weight:.medium)
            Text("Choose Benchmark beside a model below. The first run includes loading; the second measures warm generation. This does not measure answer quality.").wixalFont(size:11).foregroundStyle(theme.muted)
            ForEach(Array(installed.filter{($0["capabilities"] as? [String] ?? []).contains("completion")}.enumerated()),id:\.offset){_,model in
                HStack{Text(modelTitle(model)).wixalFont(size:12);Spacer();Button("Benchmark"){run("benchmark-start",["name":textValue(model["name"])])}.disabled(locked || hasDownload).buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11)}
            }
        }.wixalCard()
    }
    private var filters:some View {
        VStack(alignment:.leading,spacing:10){
            HStack(spacing:10){
                Button(capability=="all" ? "Model type" : typeName){typeOpen=true}.popover(isPresented:$typeOpen){typePopover}
                Button(publisher=="all" ? "Provider" : publisher){providerOpen=true}.popover(isPresented:$providerOpen){providerPopover}
                Button(extraFilterCount==0 ? "Filters" : "Filters · \(extraFilterCount)"){moreFiltersOpen=true}.popover(isPresented:$moreFiltersOpen){additionalFilters}
                Spacer(minLength:0)
                Menu{Button("Name"){sort="name"};Button("Smallest file"){sort="size"};Button("Parameter count"){sort="parameters"}}label:{Image(systemName:"arrow.up.arrow.down");Text("Sort")}.menuStyle(.borderlessButton).fixedSize().accessibilityLabel("Sort models")
            }.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:12)
            if capability != "all" || publisher != "all" || extraFilterCount>0 {
                HStack(spacing:10){Text(activeFilterSummary).wixalFont(size:11).foregroundStyle(theme.muted);Spacer(minLength:0);Button("Clear filters"){resetFilters()}.buttonStyle(WixalButtonStyle(inline:true)).wixalFont(size:11)}
            }
        }
    }
    private var activeFilterSummary:String{
        var labels:[String]=[]
        if capability != "all"{labels.append(typeName)}
        if publisher != "all"{labels.append(publisher)}
        if parameters != "all"{labels.append(parameters=="2" ? "Under 2B" : parameters=="8" ? "2B–8B" : "Over 8B")}
        if size != "all"{labels.append("Under \(size) GB")}
        if fit != "all"{labels.append("Estimated RAM fit")}
        return labels.joined(separator:" · ")
    }
    private var typeChoices:[[String:Any]]{
        typeSearch.isEmpty ? records(filterData["popularTypes"]).prefix(5).map{$0} : records(filterData["tasks"]).filter{(textValue($0["label"])+" "+textValue($0["id"])).localizedCaseInsensitiveContains(typeSearch)}
    }
    private var typePopover:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Model type").wixalFont(size:14,weight:.medium)
            TextField("Search Hugging Face types…",text:$typeSearch).wixalField()
            Button("All model types"){chooseType("all")}.buttonStyle(WixalButtonStyle(inline:true))
            Text(typeSearch.isEmpty ? "Popular GGUF types" : "Search results").wixalFont(size:11).foregroundStyle(theme.muted)
            ScrollView{VStack(alignment:.leading,spacing:4){ForEach(Array(typeChoices.enumerated()),id:\.offset){_,row in choiceButton(row,selected:capability){chooseType(textValue(row["id"]))}}}}.frame(maxHeight:230)
            if typeChoices.isEmpty{Text(filterError.isEmpty ? "No matching types" : filterError).wixalFont(size:11).foregroundStyle(theme.muted)}
            filterSourceNote
        }.padding(16).frame(width:300).background(theme.panel)
    }
    private var providerPopover:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Provider").wixalFont(size:14,weight:.medium)
            TextField("Search Hugging Face providers…",text:$providerSearch).wixalField()
            Button("All providers"){chooseProvider("all")}.buttonStyle(WixalButtonStyle(inline:true))
            Text(providerSearch.isEmpty ? "Popular GGUF providers" : "Search results").wixalFont(size:11).foregroundStyle(theme.muted)
            if findingProviders{ProgressView().controlSize(.small)}
            let choices=providerSearch.isEmpty ? records(filterData["providers"]).prefix(5).map{$0} : providerMatches
            ScrollView{VStack(alignment:.leading,spacing:4){ForEach(Array(choices.enumerated()),id:\.offset){_,row in choiceButton(row,selected:publisher){chooseProvider(textValue(row["id"]))}}}}.frame(maxHeight:230)
            if choices.isEmpty && !findingProviders{Text(providerError.isEmpty ? filterError.isEmpty ? "No matching providers" : filterError : providerError).wixalFont(size:11).foregroundStyle(theme.muted)}
            filterSourceNote
        }.padding(16).frame(width:300).background(theme.panel)
        .task(id:providerSearch){
            providerMatches=[];providerError="";findingProviders=false
            let query=providerSearch.trimmingCharacters(in:.whitespacesAndNewlines)
            guard !query.isEmpty else{return}
            do {try await Task.sleep(nanoseconds:300_000_000);findingProviders=true
                let result=try await engine.call("model-hf-filters",["kind":"provider","search":query]) as? [String:Any] ?? [:]
                guard !Task.isCancelled,query==providerSearch.trimmingCharacters(in:.whitespacesAndNewlines) else{return}
                providerMatches=records(result["providers"]);findingProviders=false
            }catch{if !Task.isCancelled{providerError=error.localizedDescription;findingProviders=false}}
        }
    }
    private var filterSourceNote:some View {
        Text("From Hugging Face\(filterData["stale"] as? Bool == true ? " · saved metadata" : "")").wixalFont(size:11).foregroundStyle(theme.muted).help("Popular choices are ranked by model count in Hugging Face’s 100 most-downloaded GGUF repositories.")
    }
    private func choiceButton(_ row:[String:Any],selected:String,choose:@escaping ()->Void)->some View {
        Button(action:choose){HStack{VStack(alignment:.leading,spacing:2){Text(textValue(row["label"]));if textValue(row["label"]).replacingOccurrences(of:"-",with:" ").lowercased() != textValue(row["id"]).replacingOccurrences(of:"-",with:" ").lowercased(){Text(textValue(row["id"])).wixalFont(size:11).foregroundStyle(theme.muted)}};Spacer();if textValue(row["id"])==selected{Image(systemName:"checkmark")}}.padding(.vertical,6).frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(WixalButtonStyle(inline:true)).wixalFont(size:12)
    }
    private func chooseType(_ value:String){capability=value;typeOpen=false}
    private func chooseProvider(_ value:String){publisher=value;providerOpen=false}
    private func loadFilterOptions() async {
        do{filterData=try await engine.call("model-hf-filters") as? [String:Any] ?? [:];filterError=""}catch{filterError=error.localizedDescription}
    }
    private var additionalFilters:some View {
        VStack(alignment:.leading,spacing:16){Text("More filters").wixalFont(size:14,weight:.medium);parameterPicker;sizePicker;fitPicker;HStack{Button("Reset"){parameters="all";size="all";fit="all"};Spacer();Button("Done"){moreFiltersOpen=false;if tab=="Discover"{searchHub()}}}}.padding(16).frame(width:300).background(theme.panel)
    }
    private var parameterPicker:some View{filterPicker("Parameters",value:$parameters,options:[("all","Any model size"),("2","Under 2B"),("8","2B–8B"),("large","Over 8B")])}
    private var sizePicker:some View{filterPicker("Download / disk size",value:$size,options:[("all","Any file size"),("2","Under 2 GB"),("5","Under 5 GB"),("10","Under 10 GB"),("20","Under 20 GB")])}
    private var fitPicker:some View{filterPicker("Memory",value:$fit,options:[("all","Any RAM estimate"),("estimated","Estimated fit on this Mac")])}
    private var sortPicker:some View{filterPicker("Sort",value:$sort,options:[("name","Name"),("size","Smallest file"),("parameters","Parameter count")])}
    private func filterPicker(_ title:String,value:Binding<String>,options:[(String,String)])->some View {
        VStack(alignment:.leading,spacing:5){Text(title).wixalFont(size:11).foregroundStyle(theme.muted);Picker(title,selection:value){ForEach(options,id:\.0){option in Text(option.1).tag(option.0)}}.labelsHidden().wixalFont(size:12)}.frame(minWidth:130,maxWidth:.infinity,alignment:.leading)
    }
    private func resetFilters(){capability="all";publisher="all";parameters="all";fit="all";size="all";sort="name";search="";invalidateSearch()}
    private func invalidateSearch(){searchRevision+=1;hubTask?.cancel();searchedHub=false;hubRows=[];nextPage="";hubError="";expanded="";searchingHub=false}
    private func searchHub(more:Bool=false){
        let revision=searchRevision
        let query:[String:Any]=["search":search.trimmingCharacters(in:.whitespacesAndNewlines),"publisher":providerValue,"parameters":parameters,"task":capability=="all" ? "" : capability,"page":more ? nextPage : ""]
        searchingHub=true;hubError=""
        hubTask=Task {
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
                if queued{tab="Downloads"}else{tab="Downloads";run("model-pull",["repo":textValue(file["repo"]),"file":textValue(file["file"]),"revision":textValue(file["revision"])])}
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(present || (!queued && locked))}
            memoryLine(file)
        }.padding(.vertical,6)
    }
    private func compactHeader(_ model:[String:Any],sizeValue:Any?,sizeLabel:String,action:@escaping ()->Void,actionTitle:String)->some View {
        HStack(alignment:.center,spacing:14){
            VStack(alignment:.leading,spacing:5){Text(textValue(model["displayName"]).isEmpty ? textValue(model["name"]) : textValue(model["displayName"])).wixalFont(size:13,weight:.medium).textSelection(.enabled);Text("\(textValue(model["publisher"]).isEmpty ? "Unknown provider" : textValue(model["publisher"])) · \(parameterLabel(model)) · \(typeLabel(model))").wixalFont(size:11).foregroundStyle(theme.muted)}.frame(maxWidth:.infinity,alignment:.leading)
            VStack(alignment:.trailing,spacing:3){Text(modelBytes(sizeValue)).wixalFont(size:12);Text(sizeLabel).wixalFont(size:11).foregroundStyle(theme.muted)}
            Button(actionTitle,action:action).buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:12).disabled(tab=="Library" && (locked || textValue(model["name"])==selected))
        }
    }
    private func memoryLine(_ model:[String:Any])->some View {
        let info=model["fit"] as? [String:Any] ?? [:]
        return Text(modelNumber(info["required"])>0 ? "Estimated model RAM \(modelRAM(info["required"])) · Recommended Mac RAM \(modelRAM(info["recommended"])) · \(Int(modelNumber(info["context"]))/1024)k context · \((info["fits"] as? Bool ?? false) ? "Estimated fit" : "May exceed this Mac’s budget")" : "RAM requirement unknown until file metadata is available").wixalFont(size:11).foregroundStyle(theme.muted).help("Estimate includes weights, context cache and overhead; recommended total RAM reserves 25% for macOS. Actual memory depends on the model and runtime.")
    }
    private func modelTitle(_ model:[String:Any])->String{textValue(model["displayName"]).isEmpty ? textValue(model["name"]) : textValue(model["displayName"])}
    private func parameterLabel(_ model:[String:Any])->String{let count=modelNumber(model["parameters"]);return count>0 ? String(format:"%.1fB parameters",count/1e9) : "Parameters unknown"}
    private func typeLabel(_ model:[String:Any])->String{let task=textValue(model["pipelineTag"]);return records(filterData["tasks"]).first{textValue($0["id"])==task}.map{textValue($0["label"])} ?? (task.isEmpty ? "Type not listed" : task)}
    private var yourModels:some View {
        VStack(alignment:.leading,spacing:0){
            let models=filtered(installed)
            if models.isEmpty{empty("No matching models",detail:"Find a model in Discover, import an existing model below, or clear the filters.")}
            ForEach(Array(models.enumerated()),id:\.offset){_,model in modelCard(model);Divider().overlay(theme.line)}
        }
    }
    private func modelCard(_ model:[String:Any])->some View {
        let name=textValue(model["name"]),caps=model["capabilities"] as? [String] ?? [],saved=score(model)
        return VStack(alignment:.leading,spacing:10){
            compactHeader(model,sizeValue:model["size"],sizeLabel:"on disk",action:{run(embeddingOnly(name) ? "memory-semantic" : "model-use",["name":name,"model":name])},actionTitle:selected==name ? "Selected" : embeddingOnly(name) ? "Use for memory" : "Use model")
            HStack{if let saved{Text("\(String(format:"%.1f",modelNumber(saved["tokensPerSecond"]))) tok/s measured").foregroundStyle(theme.muted)};Spacer();Button(inspected==name ? "Hide details" : "Details"){inspected=inspected==name ? "" : name}.buttonStyle(WixalButtonStyle(inline:true)).accessibilityLabel("Details for \(name)")}.wixalFont(size:11)
            if inspected==name {
                memoryLine(model)
                Text(name).wixalFont(size:10).foregroundStyle(theme.muted).textSelection(.enabled)
                HStack(spacing:14){Button("Benchmark"){performanceTab="Benchmarks";tab="Performance";run("benchmark-start",["name":name])}.disabled(locked || hasDownload || !caps.contains("completion"));Spacer();Button("Delete model…",role:.destructive){deleting=name}.disabled(locked || hasDownload).accessibilityLabel("Delete model \(name)")}.buttonStyle(WixalButtonStyle(inline:true)).wixalFont(size:11)
            }
        }.padding(.vertical,14)
    }
    private func filtered(_ rows:[[String:Any]],catalog:Bool=false)->[[String:Any]] {
        rows.filter {model in
            let count=modelNumber(model["parameters"]),task=textValue(model["pipelineTag"]),provider=textValue(model["publisher"])
            let needle=[textValue(model["name"]),textValue(model["displayName"]),textValue(model["repo"]),provider].joined(separator:" ")
            let parameterMatch=parameters=="all" || count>0 && (parameters=="2" && count<2e9 || parameters=="8" && count>=2e9 && count<=8e9 || parameters=="large" && count>8e9)
            let bytes=modelNumber(model["size"]),info=model["fit"] as? [String:Any] ?? [:]
            let fileMatch=catalog ? (size=="all" && fit=="all" || !matchingFiles(model).isEmpty) : (size=="all" || bytes>0 && bytes<(Double(size) ?? 0)*1e9) && (fit=="all" || info["fits"] as? Bool == true)
            return (search.isEmpty || needle.localizedCaseInsensitiveContains(search)) && (providerValue.isEmpty || provider.localizedCaseInsensitiveCompare(providerValue) == .orderedSame) && (capability=="all" || task==capability) && parameterMatch && fileMatch
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
            }.buttonStyle(WixalButtonStyle(inline:true)).wixalFont(size:10).foregroundStyle(theme.accent).disabled(textValue(runtime["library"]).isEmpty)
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
            let rows=engine.imports
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
            }.buttonStyle(WixalButtonStyle(inline:true)).wixalFont(size:11).foregroundStyle(theme.accent)
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
