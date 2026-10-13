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
struct WixalButtonStyle: ButtonStyle {
    @Environment(\.wixalTheme) private var theme
    var outlined = false
    func makeBody(configuration:Configuration) -> some View {
        WixalButtonBody(label:configuration.label,pressed:configuration.isPressed,outlined:outlined)
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
    @Environment(\.wixalTheme) private var theme
    @Environment(\.isEnabled) private var enabled
    @ViewState<Bool> private var hover=false
    var body:some View{label.foregroundStyle(theme.text).padding(.horizontal,10).padding(.vertical,8).background(pressed || hover && enabled ? theme.selected : outlined ? theme.panel : .clear,in:RoundedRectangle(cornerRadius:7)).overlay(RoundedRectangle(cornerRadius:7).stroke(outlined ? hover && enabled ? theme.accent.opacity(0.45) : theme.line : .clear,lineWidth:1)).opacity(enabled ? 1 : 0.45).onHover{hover=$0}}
}
