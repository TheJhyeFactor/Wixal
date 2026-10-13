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
    var outlined = false
    var prominent = false
    var compact = false
    func makeBody(configuration:Configuration) -> some View {
        WixalButtonBody(label:configuration.label,pressed:configuration.isPressed,outlined:outlined,prominent:prominent,compact:compact)
    }
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
            .buttonStyle(WixalButtonStyle(outlined:outlined)).fixedSize()
            .popover(isPresented:$presented,arrowEdge:.bottom){VStack(alignment:.leading,spacing:2){ForEach(choices.indices,id:\.self){index in Button{presented=false;choices[index].1()}label:{Text(choices[index].0).frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(WixalButtonStyle())}}.padding(6).frame(width:180).foregroundStyle(theme.text).background(theme.panel).environment(\.wixalTheme,theme)}
    }
}

private struct WixalButtonBody<Label:View>:View {
    let label:Label
    let pressed:Bool
    let outlined:Bool
    let prominent:Bool
    let compact:Bool
    @Environment(\.wixalTheme) private var theme
    @Environment(\.isEnabled) private var enabled
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @Environment(\.wixalReducedMotion) private var appReduceMotion
    @ViewState<Bool> private var hover=false
    private var elevated:Bool { outlined || prominent }
    private var active:Bool { enabled && (hover || pressed) }
    private var depressed:Bool { enabled && pressed }
    private var reduceMotion:Bool { systemReduceMotion || appReduceMotion }
    private var shape:RoundedRectangle { RoundedRectangle(cornerRadius:7) }
    private var foreground:Color { prominent ? theme.light ? theme.raised : theme.background : theme.text }
    private var fill:Color { prominent ? theme.accent : elevated ? active ? theme.raised : theme.panel : active ? theme.selected : .clear }
    var body:some View {
        label.foregroundStyle(foreground)
            .padding(.horizontal,compact ? 0 : 10).padding(.vertical,compact ? 0 : 8)
            .background(fill,in:shape)
            .overlay(shape.stroke(elevated ? active ? theme.accent.opacity(0.45) : theme.line : .clear,lineWidth:1))
            .overlay(shape.stroke(.white.opacity(elevated && !depressed ? theme.light ? 0.7 : 0.12 : 0),lineWidth:1).mask(LinearGradient(colors:[.white,.clear],startPoint:.top,endPoint:.center)).allowsHitTesting(false))
            .overlay(shape.fill(.black.opacity(depressed && elevated ? 0.08 : 0)).allowsHitTesting(false))
            .compositingGroup()
            .shadow(color:.black.opacity(enabled && elevated && !depressed ? theme.light ? 0.10 : 0.24 : 0),radius:1,x:0,y:1)
            .shadow(color:.black.opacity(enabled && elevated && !depressed ? theme.light ? 0.06 : 0.18 : 0),radius:hover ? 4 : 2,x:0,y:hover ? 2 : 1)
            .offset(y:reduceMotion || !enabled || !elevated ? 0 : depressed ? 0.5 : hover ? -0.5 : 0)
            .opacity(enabled ? 1 : 0.45)
            .animation(reduceMotion ? nil : .easeOut(duration:0.12),value:active)
            .animation(reduceMotion ? nil : .easeOut(duration:0.08),value:depressed)
            .onHover{hover=$0}
    }
}
