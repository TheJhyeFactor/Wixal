import SwiftUI
import AppKit

struct AgentAvatar:View {
    let icon:String
    var size:CGFloat=38
    @Environment(\.wixalTheme) private var theme
    var body:some View {Image(systemName:icon).wixalFont(size:size*0.43).foregroundStyle(theme.accent).frame(width:size,height:size).background(theme.selected,in:RoundedRectangle(cornerRadius:10)).overlay(RoundedRectangle(cornerRadius:10).stroke(theme.line,lineWidth:1)).accessibilityHidden(true)}
}
struct AgentRuntimeBanner:View {
    @Environment(\.wixalTheme) private var theme
    var body:some View{HStack(alignment:.top,spacing:9){Image(systemName:"rectangle.dashed").foregroundStyle(theme.accent);Text("Agents run on your local engine. The model chooses tools; activity retains requests, results and review decisions.").wixalFont(size:11).foregroundStyle(theme.muted);Spacer(minLength:0)}.padding(12).background(theme.selected,in:RoundedRectangle(cornerRadius:8))}
}
struct AgentEmptyState:View {
    let icon:String
    let title:String
    let detail:String
    let action:String
    let perform:()->Void
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:16){AgentAvatar(icon:icon,size:48);Text(title).wixalFont(size:24,weight:.medium);Text(detail).wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(4).frame(maxWidth:520,alignment:.leading);Button(action,action:perform).buttonStyle(WixalButtonStyle(outlined:true))}.padding(28).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:12)).overlay(RoundedRectangle(cornerRadius:12).stroke(theme.line,lineWidth:1))}
}
struct AgentMetadata:View {
    let title:String
    let value:String
    @Environment(\.wixalTheme) private var theme
    var body:some View{HStack(alignment:.top){Text(title).foregroundStyle(theme.muted);Spacer();Text(value).multilineTextAlignment(.trailing)}.wixalFont(size:11).padding(.vertical,7)}
}
struct AgentDesignPage<Content:View>:View {
    let title:String
    let subtitle:String
    @ViewBuilder let content:()->Content
    @Environment(\.wixalTheme) private var theme
    var body:some View{ScrollView{VStack(alignment:.leading,spacing:24){VStack(alignment:.leading,spacing:8){Text(title).wixalFont(size:28,weight:.medium).tracking(-0.6);Text(subtitle).wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(4)};content()}.padding(26).frame(maxWidth:1060,alignment:.leading).frame(maxWidth:.infinity)}.background(theme.background)}
}
struct AgentEditorHeader:View {
    let title:String
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    var body:some View{HStack{VStack(alignment:.leading,spacing:5){Text("AGENTS").wixalFont(size:10,design:.monospaced).foregroundStyle(theme.muted);Text(title).wixalFont(size:21,weight:.medium)};Spacer();Button(action:close){Image(systemName:"xmark")}.buttonStyle(WixalButtonStyle()).accessibilityLabel("Close \(title)")}.padding(22)}
}

struct AgentTileButtonStyle:ButtonStyle {
    var reducedMotion=false
    func makeBody(configuration:Configuration)->some View{AgentTileBody(label:configuration.label,pressed:configuration.isPressed,reducedMotion:reducedMotion)}
}
private struct AgentTileBody<Label:View>:View {
    let label:Label
    let pressed:Bool
    let reducedMotion:Bool
    @Environment(\.wixalTheme) private var theme
    @ViewState private var hover=false
    var body:some View{label.overlay(RoundedRectangle(cornerRadius:9).stroke(hover ? theme.accent.opacity(0.5) : .clear,lineWidth:1)).scaleEffect(pressed && !reducedMotion ? 0.99 : 1).onHover{hover=$0}.animation(reducedMotion ? nil : .easeOut(duration:0.14),value:hover).animation(reducedMotion ? nil : .easeOut(duration:0.1),value:pressed)}
}

private struct AgentDesignReduceMotionKey:EnvironmentKey{static let defaultValue=false}
extension EnvironmentValues{var agentDesignReduceMotion:Bool{get{self[AgentDesignReduceMotionKey.self]}set{self[AgentDesignReduceMotionKey.self]=newValue}}}

// Capture the parent size once. Re-reading keyWindow while typing measures the
// sheet itself and creates a shrinking feedback loop.
struct AgentSheetSize {
    var width:CGFloat
    var height:CGFloat
    static func preferred(width:CGFloat,height:CGFloat)->Self {
        let key=NSApp.keyWindow
        let parent=key?.sheetParent ?? key
        let frame=parent?.contentLayoutRect.size ?? CGSize(width:920,height:740)
        return Self(width:min(width,max(500,frame.width-40)),height:min(height,max(450,frame.height-70)))
    }
}
