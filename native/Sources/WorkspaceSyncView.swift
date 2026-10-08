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
                Text(textValue(state["folder"])).wixalFont(size:11,design:.monospaced).textSelection(.enabled)
                HStack{Button("Sync now"){run("sync-run")};Button("Disable sync"){run("sync-settings",["enabled":false])}}
                if let last=state["lastSync"] as? Double{Text("Last sync: \(Date(timeIntervalSince1970:last/1000).formatted())").wixalFont(size:10).foregroundStyle(theme.muted)}
            } else {
                HStack{TextField("Shared sync folder",text:$folder).wixalField();Button("Choose folder…",action:chooseFolder)}
                SecureField("Shared passphrase, at least 12 characters",text:$passphrase).wixalField().accessibilityLabel("Workspace sync passphrase")
                Button("Enable encrypted sync"){let secret=passphrase;passphrase="";run("sync-settings",["enabled":true,"folder":folder,"passphrase":secret])}.disabled(folder.isEmpty || passphrase.count<12)
            }
            ForEach(state["warnings"] as? [String] ?? [],id:\.self){Text($0).wixalFont(size:11).foregroundStyle(theme.muted)}
            ForEach(Array(records(state["conflicts"]).enumerated()),id:\.offset){_,conflict in
                conflictCard(conflict)
            }
            ForEach(Array(records(engine.state["projects"]).filter{$0["syncRootRequired"] as? Bool == true}.enumerated()),id:\.offset){_,project in
                HStack{Text("Choose the local folder for \(textValue(project["name"]))");Button("Locate project…"){locate(project)}}
            }
        }.wixalFont(size:11).buttonStyle(WixalButtonStyle(outlined:true)).disabled(working || engine.busy)
    }
    private func conflictCard(_ conflict:[String:Any])->some View {
        let local=conflict["localRecord"] as? [String:Any] ?? [:],incoming=conflict["record"] as? [String:Any] ?? [:]
        let stale=conflict["localChanged"] as? Bool ?? false
        return VStack(alignment:.leading,spacing:12) {
            Text("Review \(textValue(conflict["collection"])): \(textValue(conflict["title"]))").wixalFont(size:12,weight:.medium)
            ViewThatFits(in:.horizontal) {
                HStack(alignment:.top,spacing:16){version("Local version",record:local,device:textValue(conflict["localDevice"]));version("Incoming version",record:incoming,device:textValue(conflict["device"]))}
                VStack(alignment:.leading,spacing:16){version("Local version",record:local,device:textValue(conflict["localDevice"]));version("Incoming version",record:incoming,device:textValue(conflict["device"]))}
            }
            Text("Keep local retains this Mac’s saved version. Use incoming replaces it with the incoming version. Project folders and action permissions stay local.").foregroundStyle(theme.muted)
            if stale {Text("Local content changed after this conflict was detected. Sync again before choosing a version.").foregroundStyle(.red)}
            DisclosureGroup("Technical details"){Text(pretty(conflict)).wixalFont(size:10,design:.monospaced).textSelection(.enabled)}
            HStack{Button("Keep local"){run("sync-resolve",["id":textValue(conflict["id"]),"choice":"local"])};Button("Use incoming"){run("sync-resolve",["id":textValue(conflict["id"]),"choice":"remote"])}}.disabled(stale)
        }.wixalCard()
    }
    private func version(_ title:String,record:[String:Any],device:String)->some View {
        VStack(alignment:.leading,spacing:7) {
            Text(title).fontWeight(.medium)
            Text("Device: \(device.isEmpty ? "Not recorded" : device)").wixalFont(size:10).foregroundStyle(theme.muted)
            if let stamp=(record["updated"] ?? record["created"]) as? NSNumber {Text("Saved: \(Date(timeIntervalSince1970:stamp.doubleValue/1000).formatted())").wixalFont(size:10).foregroundStyle(theme.muted)}
            if !textValue(record["content"]).isEmpty {Text(textValue(record["content"])).textSelection(.enabled)}
            else if record["messages"] != nil {
                Text(textValue(record["title"])).fontWeight(.medium)
                Text("\(records(record["messages"]).count) messages").foregroundStyle(theme.muted)
                ScrollView{VStack(alignment:.leading,spacing:8){ForEach(Array(records(record["messages"]).enumerated()),id:\.offset){_,message in
                    Text(textValue(message["role"]).capitalized).fontWeight(.medium)
                    Text(textValue(message["content"])).textSelection(.enabled)
                }}}.frame(maxHeight:200)
            } else {Text(textValue(record["name"])).textSelection(.enabled);Text("Memory scope: \(textValue(record["memoryMode"])) · Note budget: \(record["memorySize"] as? Int ?? 24000) characters").foregroundStyle(theme.muted)}
        }.frame(minWidth:150,maxWidth:.infinity,alignment:.leading)
    }
    private func chooseFolder(){let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false;panel.begin{answer in if answer == .OK {folder=panel.url?.path ?? ""}}}
    private func locate(_ project:[String:Any]){let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.begin{answer in if answer == .OK,let url=panel.url{run("project-relocate",["id":textValue(project["id"]),"root":url.path])}}}
    private func run(_ method:String,_ params:[String:Any]=[:]){working=true;Task{defer{working=false};do{_=try await engine.call(method,params)}catch{engine.error=error.localizedDescription}}}
}
