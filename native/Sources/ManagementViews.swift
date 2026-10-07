import SwiftUI

struct FilesView:View {
    @ObservedObject var engine:EngineClient
    var onUse:([String:Any])->Void = {_ in}
    @Environment(\.wixalTheme) private var theme
    @ViewState<[String]> private var files=[]
    @ViewState<String> private var query=""
    @ViewState<String> private var selected=""
    @ViewState<String> private var content=""
    @ViewState<Bool> private var loading=false
    @ViewState<String> private var readError=""
    var body:some View {
        HSplitView {
            VStack(alignment:.leading,spacing:16){
                HStack{Text("PROJECT FILES").font(.system(size:10,weight:.medium)).tracking(1);Spacer();Button(action:load){Image(systemName:"arrow.clockwise")}.buttonStyle(.plain).accessibilityLabel("Refresh project files")}
                TextField("Find a file…",text:$query).wixalField()
                if loading{ProgressView().controlSize(.small)}
                if !readError.isEmpty{Text(readError).font(.system(size:11)).foregroundStyle(.red)}
                if !loading && files.isEmpty{Text("No project files found.").font(.system(size:11)).foregroundStyle(theme.muted)}
                ScrollView{LazyVStack(alignment:.leading,spacing:2){ForEach(files.filter{query.isEmpty || $0.localizedCaseInsensitiveContains(query)},id:\.self){file in Button{selected=file;read(file)}label:{HStack(spacing:8){Image(systemName:"doc.text").foregroundStyle(theme.muted);Text(file).lineLimit(1).truncationMode(.middle);Spacer(minLength:0)}.font(.system(size:11,design:.monospaced)).padding(9).frame(maxWidth:.infinity,alignment:.leading).background(selected==file ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6))}.buttonStyle(.plain)}}}
                Text("\(files.count) files").font(.system(size:10)).foregroundStyle(theme.muted)
            }.padding(20).frame(minWidth:220,idealWidth:270,maxWidth:340).background(theme.panel)
            ScrollView{VStack(alignment:.leading,spacing:18){
                if selected.isEmpty{Image(systemName:"doc.text.magnifyingglass").font(.system(size:28)).foregroundStyle(theme.muted).padding(.top,50);Text("Select a file").font(.system(size:23,weight:.medium));Text(engine.project==nil ? "Open a project folder to browse its files." : "Browse your project and preview a file here.").font(.system(size:12)).foregroundStyle(theme.muted);if engine.project==nil{Button("Open project folder ↗",action:engine.pickProject).buttonStyle(WixalButtonStyle(outlined:true))}}
                else{HStack{Text(selected).font(.system(size:12,weight:.medium,design:.monospaced));Spacer();Button("Add to message ↗"){onUse(["type":"file","name":URL(fileURLWithPath:selected).lastPathComponent,"path":selected,"content":String(content.prefix(8000))])}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(content.isEmpty || !readError.isEmpty || engine.busy);Text("READ ONLY").font(.system(size:9)).tracking(1).foregroundStyle(theme.muted)};Divider().overlay(theme.line);Text(content).font(.system(size:12,design:.monospaced)).lineSpacing(5).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}
            }.padding(28).frame(maxWidth:.infinity,alignment:.leading)}.background(theme.background)
        }.onAppear(perform:load).onChange(of:engine.root){_,_ in selected="";content="";load()}
    }
    private func load(){let root=engine.root;files=[];readError="";guard engine.project != nil else{loading=false;return};loading=true;Task{defer{loading=false};do{let result=try await engine.call("tool",["name":"list_files","arguments":[:]]) as? [String] ?? [];guard engine.root==root else{return};files=result}catch{if engine.root==root{readError="Could not list these files: \(error.localizedDescription)"}}}}
    private func read(_ path:String){content="";readError="";Task{do{let result=try await engine.call("tool",["name":"read_file","arguments":["path":path]]) as? [String:Any] ?? [:];guard selected==path else{return};content=textValue(result["content"])+((result["more"] as? Bool ?? false) ? "\n\n[Preview limited to 24,000 characters]" : "")}catch{readError="Could not preview this file: \(error.localizedDescription)"}}}
}
