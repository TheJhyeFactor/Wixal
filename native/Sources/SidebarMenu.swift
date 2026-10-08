import SwiftUI

struct SidebarRailButton:View {
    let title:String
    let symbol:String
    let collapsed:Bool
    var selected=false
    let action:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState<Bool> private var hover=false
    var body:some View {
        Button(action:action){HStack(spacing:10){Text(symbol).wixalFont(size:16,design:.monospaced).frame(width:20,height:20);if !collapsed{Text(title).wixalFont(size:11);Spacer();if title=="Workspace"{Image(systemName:selected ? "chevron.down" : "chevron.up").wixalFont(size:9)}}}.padding(.horizontal,collapsed ? 0 : 10).frame(maxWidth:.infinity,alignment:collapsed ? .center : .leading).frame(height:40).contentShape(Rectangle()).background(selected || hover ? theme.panel : .clear,in:RoundedRectangle(cornerRadius:8))}.buttonStyle(.plain).foregroundStyle(selected ? theme.text : theme.muted).accessibilityAddTraits(selected ? [.isSelected] : []).onHover{hover=$0}.accessibilityLabel(title=="Workspace" ? "Workspace menu" : title).help(title=="Settings" ? "Settings · ⌘ ," : title)
    }
}
struct SidebarWorkspaceMenu:View {
    @ObservedObject var engine:EngineClient
    let action:(String)->Void
    var dismissMenu:(()->Void)? = nil
    @ViewState<Int?> private var focusedRow:Int?
    @FocusState private var menuFocused:Bool
    @Environment(\.wixalTheme) private var theme
    private var archives:Int{records(engine.state["sessions"]).filter{ $0["archivedAt"] != nil && !($0["archivedAt"] is NSNull)}.count}
    private var notes:Int{records(engine.state["memories"]).filter{textValue($0["projectId"])==textValue(engine.state["activeProject"])}.count}
    var body:some View {
        VStack(alignment:.leading,spacing:2){
            Text("WORKSPACE").wixalFont(size:9,design:.monospaced).tracking(1).foregroundStyle(theme.muted).padding(.horizontal,9).padding(.top,7).padding(.bottom,9)
            row("Archived chats",symbol:"▤",count:archives,route:"Archived chats")
            row("Task inbox",symbol:"↳",count:records(engine.state["tasks"]).filter{["queued","running","waiting_review","paused","interrupted","failed"].contains(textValue($0["status"]))}.count,route:"Tasks")
            row("Connections",symbol:"⇄",route:"Connections")
            row("Project files",icon:"folder",shortcut:"⌘ ⇧ F",route:"Files")
            row("Tool kit",icon:"wrench",count:(engine.state["enabledTools"] as? [String] ?? []).count,route:"Tool kit")
            row("Project memory",icon:"diamond",count:notes,route:"Project memory")
            row("Terminal",icon:"terminal",shortcut:"⌘ J",route:"Terminal")
            Rectangle().fill(theme.line).frame(height:1).padding(.top,8)
            HStack(spacing:9){Circle().fill(engine.modelReady ? theme.accent : theme.muted).frame(width:5,height:5);VStack(alignment:.leading,spacing:4){Text(engine.modelConnectionLabel).wixalFont(size:10);Text("On this Mac · 127.0.0.1").wixalFont(size:9,design:.monospaced).foregroundStyle(theme.muted)};Spacer(minLength:0);Button(action:engine.loadModels){Image(systemName:"arrow.clockwise").wixalFont(size:16).frame(width:24,height:30)}.buttonStyle(.plain).accessibilityLabel("Refresh models")}.padding(.horizontal,4).padding(.top,10).padding(.bottom,4)
        }.padding(9).frame(width:220).background(theme.raised,in:RoundedRectangle(cornerRadius:12)).overlay(RoundedRectangle(cornerRadius:12).stroke(theme.line,lineWidth:1)).shadow(color:.black.opacity(theme.light ? 0.18 : 0.45),radius:19,x:0,y:12).foregroundStyle(theme.text).accessibilityElement(children:.contain).accessibilityLabel("Workspace controls")
        .focusable().focusEffectDisabled().focused($menuFocused)
        .task{await Task.yield();focusedRow=0;menuFocused=true}
        .onKeyPress(keys:[.downArrow,.upArrow,.home,.end,.return,.escape]){press in
            switch press.key {
            case .downArrow:focusedRow=((focusedRow ?? -1)+1)%8
            case .upArrow:focusedRow=((focusedRow ?? 1)+7)%8
            case .home:focusedRow=0
            case .end:focusedRow=7
            case .return:if focusedRow==7{engine.loadModels()}else{action(routes[min(6,max(0,focusedRow ?? 0))])}
            case .escape:guard let dismissMenu else{return .ignored};dismissMenu()
            default:return .ignored
            }
            return .handled
        }
    }
    private let routes=["Archived chats","Tasks","Connections","Files","Tool kit","Project memory","Terminal"]
    private func index(_ route:String)->Int{routes.firstIndex(of:route) ?? 0}
    private func row(_ title:String,symbol:String="",icon:String="",count:Int?=nil,shortcut:String="",route:String)->some View {
        WorkspaceMenuRow(title:title,symbol:symbol,icon:icon,count:count,shortcut:shortcut,focused:focusedRow == index(route),action:{action(route)})

    }
}
private struct WorkspaceMenuRow:View {
    let title:String
    let symbol:String
    let icon:String
    let count:Int?
    let shortcut:String
    var focused:Bool=false
    let action:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState<Bool> private var hover=false
    var body:some View {
        Button(action:action){HStack(spacing:10){Group{if icon.isEmpty{Text(symbol).wixalFont(size:16,design:.monospaced)}else{Image(systemName:icon).wixalFont(size:15)}}.foregroundStyle(theme.muted).frame(width:20,height:20);Text(title).wixalFont(size:11).lineLimit(1);Spacer(minLength:0);if let count{Text("\(count)").wixalFont(size:10,design:.monospaced).padding(.horizontal,6).padding(.vertical,3).background(theme.line.opacity(0.7),in:RoundedRectangle(cornerRadius:4))};if !shortcut.isEmpty{Text(shortcut).wixalFont(size:9,design:.monospaced).foregroundStyle(theme.muted)}}.padding(.horizontal,8).frame(height:40).frame(maxWidth:.infinity).contentShape(Rectangle()).background(hover || focused ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:8))}.buttonStyle(.plain).onHover{hover=$0}.accessibilityLabel(title).accessibilityValue(count.map{"\($0) items"} ?? shortcut).help(shortcut.isEmpty ? title : "\(title) · \(shortcut)")
    }
}
extension Notification.Name { static let wixalOpenSettings=Notification.Name("WixalOpenSettings");static let wixalNavigate=Notification.Name("WixalNavigate") }
