import SwiftUI
import AppKit

struct WorkspaceSyncView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState private var folder=""
    @ViewState private var passphrase=""
    @ViewState private var working=false
    private var state:[String:Any]{engine.state["syncState"] as? [String:Any] ?? [:]}
    private var enabled:Bool{state["enabled"] as? Bool ?? false}
    var body:some View {
        WixalSection(title:"Encrypted workspace sync",detail:"Sync saved notes, conversations and their images through a folder shared between your devices, such as iCloud Drive. Use the same passphrase and identity on both Macs. Project files, credentials, drafts, tool permissions and schedules stay local.") {
            if enabled {
                Text(textValue(state["folder"])).font(.system(size:11,design:.monospaced)).textSelection(.enabled)
                HStack{Button("Sync now"){run("sync-run")};Button("Disable sync"){run("sync-settings",["enabled":false])}}
                if let last=state["lastSync"] as? Double{Text("Last sync: \(Date(timeIntervalSince1970:last/1000).formatted())").font(.system(size:10)).foregroundStyle(theme.muted)}
            } else {
                HStack{TextField("Shared sync folder",text:$folder).wixalField();Button("Choose folder…",action:chooseFolder)}
                SecureField("Shared passphrase, at least 12 characters",text:$passphrase).wixalField().accessibilityLabel("Workspace sync passphrase")
                Button("Enable encrypted sync"){let secret=passphrase;passphrase="";run("sync-settings",["enabled":true,"folder":folder,"passphrase":secret])}.disabled(folder.isEmpty || passphrase.count<12)
            }
            ForEach(state["warnings"] as? [String] ?? [],id:\.self){Text($0).font(.system(size:11)).foregroundStyle(theme.muted)}
            ForEach(Array(records(state["conflicts"]).enumerated()),id:\.offset){_,conflict in
                VStack(alignment:.leading,spacing:8){
                    Text("Review incoming \(textValue(conflict["collection"])): \(textValue(conflict["title"]))").font(.system(size:12,weight:.medium))
                    DisclosureGroup("Incoming content"){Text(pretty(conflict["record"] ?? [:])).font(.system(size:11,design:.monospaced)).textSelection(.enabled)}
                    HStack{Button("Keep local"){run("sync-resolve",["id":textValue(conflict["id"]),"choice":"local"])};Button("Use incoming"){run("sync-resolve",["id":textValue(conflict["id"]),"choice":"remote"])}}
                }.wixalCard()
            }
            ForEach(Array(records(engine.state["projects"]).filter{$0["syncRootRequired"] as? Bool == true}.enumerated()),id:\.offset){_,project in
                HStack{Text("Choose the local folder for \(textValue(project["name"]))");Button("Locate project…"){locate(project)}}
            }
        }.font(.system(size:11)).buttonStyle(WixalButtonStyle(outlined:true)).disabled(working || engine.busy)
    }
    private func chooseFolder(){let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false;panel.begin{answer in if answer == .OK {folder=panel.url?.path ?? ""}}}
    private func locate(_ project:[String:Any]){let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.begin{answer in if answer == .OK,let url=panel.url{run("project-relocate",["id":textValue(project["id"]),"root":url.path])}}}
    private func run(_ method:String,_ params:[String:Any]=[:]){working=true;Task{defer{working=false};do{_=try await engine.call(method,params)}catch{engine.error=error.localizedDescription}}}
}
