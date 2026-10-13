import SwiftUI

struct WorkspaceDrawer:View{
    @ObservedObject var engine:EngineClient
    let kind:String
    var close:()->Void
    var body:some View{Group{if kind=="Tools"{ToolsDrawer(engine:engine,close:close)}else{MemoryDrawer(engine:engine,close:close).id(textValue(engine.state["activeProject"]))}}.onExitCommand(perform:close)}
}
struct CommandPalette:View{
    var projects:[[String:Any]]=[]
    var sessions:[[String:Any]]=[]
    let action:(String)->Void
    @Environment(\.wixalTheme) private var theme
    @Environment(\.dismiss) private var dismiss
    @FocusState private var searchFocused:Bool
    @ViewState<String> private var query=""
    @ViewState<Int> private var selection=0
    let commands=["New conversation","Open project","Chat","Agents","Cybersecurity","Tools","Projects","Recents","Toggle sidebar","Models","Performance","Files","Tool kit","Project memory","Terminal","Tasks","Archived chats","Settings","Account","Connections","Setup","Terms","Privacy"]
    private struct Result:Identifiable {
        let id:String
        let title:String
        let detail:String
        let route:String
    }
    private var matches:[Result] {
        let commandRows=commands.map{Result(id:"command:"+$0,title:$0,detail:"Command",route:$0)}
        let projectRows=projects.map{Result(id:"project:"+textValue($0["id"]),title:textValue($0["name"]),detail:"Project · "+textValue($0["root"]),route:"Project:"+textValue($0["id"]))}
        let conversationRows=sessions.filter{$0["archivedAt"] == nil || $0["archivedAt"] is NSNull}.reversed().map { session in
            let project=projects.first{textValue($0["id"])==textValue(session["projectId"])}
            return Result(id:"conversation:"+textValue(session["id"]),title:textValue(session["title"]),detail:(project.map{textValue($0["name"])} ?? "Personal") + (textValue(session["mode"])=="agent" ? " · Agent conversation" : " · Chat"),route:"Conversation:"+textValue(session["id"]))
        }
        return (commandRows+projectRows+conversationRows).filter{query.isEmpty || ($0.title+" "+$0.detail).localizedCaseInsensitiveContains(query)}
    }
    var body:some View{
        VStack(alignment:.leading,spacing:16){
            HStack{Text("Search & commands").font(.system(size:13,weight:.medium));Spacer();Text("ESC").font(.system(size:10,design:.monospaced)).foregroundStyle(theme.muted)}
            TextField("Search commands, projects and conversations…",text:$query).wixalField().focused($searchFocused).onSubmit(activate)
            ScrollViewReader{proxy in
                ScrollView{VStack(spacing:4){
                    if matches.isEmpty{Text("No results match “\(query)”").font(.system(size:11)).foregroundStyle(theme.muted).frame(maxWidth:.infinity,alignment:.leading).padding(10)}
                    ForEach(Array(matches.enumerated()),id:\.element.id){index,result in
                        Button{action(result.route)}label:{HStack{VStack(alignment:.leading,spacing:3){Text(result.title).font(.system(size:12)).lineLimit(1);Text(result.detail).font(.system(size:10)).foregroundStyle(theme.muted).lineLimit(1)};Spacer();Image(systemName:"arrow.up.right").font(.system(size:9))}.padding(.horizontal,10).frame(height:44).frame(maxWidth:.infinity).contentShape(Rectangle()).background(selection==index ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:7))}.buttonStyle(WixalNavigationButtonStyle(selected:selection==index)).id(index).onHover{if $0{selection=index}}.accessibilityLabel(result.title+", "+result.detail).accessibilityValue(selection==index ? "Selected" : "")
                    }
                }}.frame(maxHeight:430)
                .onChange(of:selection){_,index in proxy.scrollTo(index,anchor:.center)}
            }
            Text("↑ ↓ select · Return run · Escape close").font(.system(size:10,design:.monospaced)).foregroundStyle(theme.muted)
        }.padding(20).frame(width:460).background(theme.panel).foregroundStyle(theme.text)
        .onAppear{searchFocused=true}
        .onChange(of:query){_,_ in selection=0}
        .onKeyPress(keys:[.downArrow,.upArrow,.home,.end,.return,.escape]){press in
            switch press.key{
            case .downArrow:if !matches.isEmpty{selection=(selection+1)%matches.count}
            case .upArrow:if !matches.isEmpty{selection=(selection+matches.count-1)%matches.count}
            case .home:selection=0
            case .end:selection=max(0,matches.count-1)
            case .return:activate()
            case .escape:dismiss()
            default:return .ignored
            }
            return .handled
        }
    }
    private func activate(){guard !matches.isEmpty else{return};action(matches[min(selection,matches.count-1)].route)}
}
