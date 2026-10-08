import SwiftUI
import AppKit

struct ProjectEntryView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState private var path:String
    @ViewState private var mode="project"
    @ViewState private var budget=24000
    @ViewState private var working=false
    @ViewState private var error=""
    init(engine:EngineClient,path:String){self.engine=engine;_path=ViewState(initialValue:path)}
    private var existing:Bool{records(engine.state["projects"]).contains{textValue($0["root"])==URL(fileURLWithPath:path).standardizedFileURL.path}}
    var body:some View {
        VStack(alignment:.leading,spacing:18){
            HStack{Text("Open project folder").font(.system(size:22,weight:.medium));Spacer();Button("Cancel"){engine.projectCandidate=nil}.keyboardShortcut(.cancelAction)}
            TextField("Folder path",text:$path).wixalField()
            HStack{Button("Browse or create a folder…"){
                let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=true;panel.directoryURL=URL(fileURLWithPath:path)
                if panel.runModal() == .OK,let url=panel.url{path=url.path}
            };Button("Show in Finder"){NSWorkspace.shared.selectFile(nil,inFileViewerRootedAtPath:path)}}.buttonStyle(WixalButtonStyle(outlined:true))
            if existing {Text("This project keeps its saved memory settings.").foregroundStyle(theme.muted)}else{
                Text("New project memory").font(.system(size:14,weight:.medium))
                Picker("Memory scope",selection:$mode){Text("Memory off").tag("off");Text("Project only").tag("project");Text("Global preferences only").tag("global");Text("Project + global preferences").tag("both")}
                Picker("Saved memory budget",selection:$budget){Text("Light · 8,000 characters").tag(8000);Text("Balanced · 24,000 characters").tag(24000);Text("Detailed · 48,000 characters").tag(48000)}
                Text("Project notes remain in this workspace. Global preferences use the active guest or account profile.").font(.system(size:11)).foregroundStyle(theme.muted)
            }
            if !error.isEmpty{Text(error).foregroundStyle(.red).textSelection(.enabled)}
            HStack{Spacer();if working{ProgressView().controlSize(.small)};Button("Use this folder"){
                working=true;Task{defer{working=false};do{_=try await engine.call("project-add",["root":path,"memoryMode":mode,"memorySize":budget]);engine.projectCandidate=nil}catch{self.error=error.localizedDescription}}
            }.buttonStyle(WixalButtonStyle(outlined:true)).keyboardShortcut(.defaultAction).disabled(working || engine.busy || path.isEmpty)}
        }.padding(24).frame(minWidth:420,idealWidth:560).background(theme.background)
    }
}

struct CreateProjectView:View {
    @ObservedObject var engine:EngineClient
    let close:()->Void
    @ViewState private var name=""
    @ViewState private var selectedFolder=""
    @ViewState private var working=false
    @ViewState private var error=""
    @FocusState private var focused:Bool
    @Environment(\.wixalTheme) private var theme
    var body:some View {
        VStack(alignment:.leading,spacing:18){
            Text("Create project").wixalFont(size:22,weight:.medium)
            TextField("Project name",text:$name).wixalField().focused($focused).onSubmit(create)
            Text(selectedFolder.isEmpty ? "Saved inside Wixal’s Projects folder, under the project name." : selectedFolder).wixalFont(size:11).foregroundStyle(theme.muted).textSelection(.enabled)
            HStack{
                Button("Select folder…"){
                    let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.prompt="Select folder"
                    if panel.runModal() == .OK,let url=panel.url{selectedFolder=url.path;if name.isEmpty{name=url.lastPathComponent}}
                }
                if !selectedFolder.isEmpty{Button("Use Wixal Projects"){selectedFolder=""}}
            }.buttonStyle(WixalButtonStyle(outlined:true)).disabled(working)
            if !error.isEmpty{Text(error).wixalFont(size:12).foregroundStyle(.red)}
            HStack{Button("Cancel",action:close).keyboardShortcut(.cancelAction).disabled(working);Spacer();if working{ProgressView().controlSize(.small)};Button(selectedFolder.isEmpty ? "Create project" : "Add project",action:create).keyboardShortcut(.defaultAction).disabled(working || engine.busy || name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)}.buttonStyle(WixalButtonStyle(outlined:true))
        }.padding(24).frame(width:480).background(theme.background).onAppear{focused=true}.interactiveDismissDisabled(working)
    }
    private func create(){
        guard !working && !engine.busy && !name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty else{return}
        working=true
        Task{defer{working=false};do{
            if selectedFolder.isEmpty{_=try await engine.call("project-create",["name":name])}
            else{_=try await engine.call("project-add",["root":selectedFolder,"name":name])}
            close()
        }catch{self.error=error.localizedDescription}}
    }
}
