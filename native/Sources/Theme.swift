import SwiftUI

extension Color {
    init(wixal hex: UInt32) { self.init(red: Double((hex >> 16) & 255)/255,green:Double((hex >> 8) & 255)/255,blue:Double(hex & 255)/255) }
}
struct WixalTheme {
    let name: String
    var light: Bool { name == "Paper" }
    private func colour(_ sakura:UInt32,_ paper:UInt32,_ midnight:UInt32,_ forest:UInt32)->Color { Color(wixal: name == "Paper" ? paper : name == "Midnight" ? midnight : name == "Forest" ? forest : sakura) }
    var background: Color { colour(0x17181b,0xf3f2ef,0x17181b,0x171b19) }
    var sidebar: Color { colour(0x1b1c20,0xebe9e4,0x1b1d20,0x1b201e) }
    var panel: Color { colour(0x1d1e22,0xfaf9f6,0x1d1f22,0x1d2220) }
    var raised: Color { colour(0x232428,0xfffefa,0x232528,0x232926) }
    var inset: Color { colour(0x111215,0xf0eee9,0x111215,0x111613) }
    var line: Color { colour(0x303136,0xdcd9d2,0x303236,0x303633) }
    var text: Color { colour(0xe8e7e5,0x2f2d2a,0xe5e6e8,0xe5e8e7) }
    var muted: Color { colour(0x96979e,0x4b4945,0x96999e,0x969e9a) }
    var accent: Color { colour(0xe9a5bd,0x423a2e,0xafbcdf,0xafdfcb) }
    var selected: Color { accent.opacity(light ? 0.055 : 0.09) }
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
