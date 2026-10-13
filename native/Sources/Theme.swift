import SwiftUI

extension Color {
    init(wixal hex: UInt32) { self.init(red: Double((hex >> 16) & 255)/255,green:Double((hex >> 8) & 255)/255,blue:Double(hex & 255)/255) }
}
struct WixalTheme {
    let palette: WixalPalette
    init(name: String) { palette = WixalPalette.resolve(name) }
    var name: String { palette.name }
    var light: Bool { palette.light }
    var icon: String { palette.icon }
    var background: Color { Color(wixal:palette.background) }
    var sidebar: Color { Color(wixal:palette.sidebar) }
    var panel: Color { Color(wixal:palette.panel) }
    var raised: Color { Color(wixal:palette.raised) }
    var inset: Color { Color(wixal:palette.inset) }
    var line: Color { Color(wixal:palette.line) }
    var text: Color { Color(wixal:palette.text) }
    var muted: Color { Color(wixal:palette.muted) }
    var accent: Color { Color(wixal:palette.accent) }
    var secondaryAccent: Color { Color(wixal:palette.secondary) }
    var selected: Color { accent.opacity(light ? 0.08 : 0.11) }
}
private struct WixalThemeKey: EnvironmentKey { static let defaultValue = WixalTheme(name:"Sakura") }
extension EnvironmentValues { var wixalTheme: WixalTheme { get {self[WixalThemeKey.self]} set {self[WixalThemeKey.self]=newValue} } }
private struct WixalReducedMotionKey: EnvironmentKey { static let defaultValue = false }
extension EnvironmentValues { var wixalReducedMotion: Bool { get {self[WixalReducedMotionKey.self]} set {self[WixalReducedMotionKey.self]=newValue} } }
struct WixalButtonStyle: ButtonStyle {
    var outlined = true
    var prominent = false
    var compact = false
    var inline = false
    func makeBody(configuration:Configuration) -> some View {
        WixalButtonBody(label:configuration.label,pressed:configuration.isPressed,outlined:outlined,prominent:prominent,compact:compact,inline:inline,destructive:configuration.role == .destructive)
    }
}
/// Navigation keeps its existing label geometry and gains depth only on selection or hover.
struct WixalNavigationButtonStyle: ButtonStyle {
    var selected = false
    func makeBody(configuration:Configuration) -> some View {
        WixalButtonBody(label:configuration.label,pressed:configuration.isPressed,outlined:selected,prominent:false,compact:true,inline:false,destructive:configuration.role == .destructive,hoverElevation:true)
    }
}

struct WixalSoftDepth: ViewModifier {
    var cornerRadius:CGFloat = 7
    var elevated = true
    var pressed = false
    var hovered = false
    var enabled = true
    @Environment(\.wixalTheme) private var theme
    func body(content:Content)->some View {
        content
            .overlay(RoundedRectangle(cornerRadius:cornerRadius).stroke(.white.opacity(elevated && !pressed ? theme.light ? 0.7 : 0.12 : 0),lineWidth:1).mask(LinearGradient(colors:[.white,.clear],startPoint:.top,endPoint:.center)).allowsHitTesting(false))
            .compositingGroup()
            .shadow(color:.black.opacity(enabled && elevated && !pressed ? theme.light ? 0.10 : 0.24 : 0),radius:1,x:0,y:1)
            .shadow(color:.black.opacity(enabled && elevated && !pressed ? theme.light ? 0.06 : 0.18 : 0),radius:hovered ? 4 : 2,x:0,y:hovered ? 2 : 1)
    }
}
extension View {
    func wixalSoftDepth(cornerRadius:CGFloat = 7)->some View { modifier(WixalSoftDepth(cornerRadius:cornerRadius)) }
}
struct Wordmark: View {
    @Environment(\.wixalTheme) private var theme
    var size: CGFloat = 26
    var body: some View { (Text("wixal").foregroundColor(theme.text)+Text("_").foregroundColor(theme.accent)).font(.system(size:size,weight:.semibold,design:.monospaced)).tracking(-size/13) }
}

struct WixalChoiceMenu: View {
    let title:String
    let outlined:Bool
    let choices:[(String,()->Void)]
    @Environment(\.wixalTheme) private var theme
    @ViewState<Bool> private var presented=false
    var body:some View {
        Button{presented.toggle()}label:{HStack(spacing:8){Text(title);Image(systemName:"chevron.down").font(.system(size:8))}.font(.system(size:outlined ? 11 : 10))}
            .buttonStyle(WixalButtonStyle()).fixedSize()
            .popover(isPresented:$presented,arrowEdge:.bottom){VStack(alignment:.leading,spacing:2){ForEach(choices.indices,id:\.self){index in Button{presented=false;choices[index].1()}label:{Text(choices[index].0).frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(WixalButtonStyle())}}.padding(6).frame(width:180).foregroundStyle(theme.text).background(theme.panel).environment(\.wixalTheme,theme)}
    }
}

private struct WixalButtonBody<Label:View>:View {
    let label:Label
    let pressed:Bool
    let outlined:Bool
    let prominent:Bool
    let compact:Bool
    let inline:Bool
    let destructive:Bool
    var hoverElevation=false
    @Environment(\.wixalTheme) private var theme
    @Environment(\.isEnabled) private var enabled
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @Environment(\.wixalReducedMotion) private var appReduceMotion
    @ViewState<Bool> private var hover=false
    private var elevated:Bool { outlined || prominent || hoverElevation && active }
    private var active:Bool { enabled && (hover || pressed) }
    private var depressed:Bool { enabled && pressed }
    private var reduceMotion:Bool { systemReduceMotion || appReduceMotion }
    private var shape:RoundedRectangle { RoundedRectangle(cornerRadius:7) }
    private var foreground:Color { prominent ? destructive ? .white : theme.light ? theme.raised : theme.background : destructive ? .red : theme.text }
    private var fill:Color { prominent ? destructive ? .red : theme.accent : elevated ? active ? theme.raised : theme.panel : active ? theme.selected : .clear }
    var body:some View {
        label.foregroundStyle(foreground)
            .padding(.horizontal,compact ? 0 : inline ? 6 : 10).padding(.vertical,compact ? 0 : inline ? 3 : 8)
            .background(fill,in:shape)
            .overlay(shape.stroke(elevated ? active ? theme.accent.opacity(0.45) : theme.line : .clear,lineWidth:1))
            .overlay(shape.fill(.black.opacity(depressed && elevated ? 0.08 : 0)).allowsHitTesting(false))
            .modifier(WixalSoftDepth(elevated:elevated,pressed:depressed,hovered:hover,enabled:enabled))
            .offset(y:reduceMotion || !enabled || !elevated ? 0 : depressed ? 0.5 : hover ? -0.5 : 0)
            .opacity(enabled ? 1 : 0.45)
            .animation(reduceMotion ? nil : .easeOut(duration:0.12),value:active)
            .animation(reduceMotion ? nil : .easeOut(duration:0.08),value:depressed)
            .onHover{hover=$0}
    }
}
