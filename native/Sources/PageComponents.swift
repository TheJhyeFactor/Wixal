import SwiftUI

struct WixalPage<Content:View>:View {
    let eyebrow:String
    let title:String
    let subtitle:String
    @ViewBuilder let content:()->Content
    @Environment(\.wixalTheme) private var theme
    var body:some View {
        ScrollView { VStack(alignment:.leading,spacing:26){
            VStack(alignment:.leading,spacing:10){Text(eyebrow).wixalFont(size:10,weight:.medium).tracking(1.5).foregroundStyle(theme.muted);Text(title).wixalFont(size:30,weight:.medium).tracking(-0.8);Text(subtitle).wixalFont(size:12).foregroundStyle(theme.muted).lineSpacing(4)}
            content()
        }.padding(32).frame(maxWidth:960,alignment:.leading).frame(maxWidth:.infinity) }.background(theme.background)
    }
}
struct WixalSection<Content:View>:View {
    let title:String
    var detail:String=""
    @ViewBuilder let content:()->Content
    @Environment(\.wixalTheme) private var theme
    var body:some View {
        VStack(alignment:.leading,spacing:14){Text(title).wixalFont(size:14,weight:.medium);if !detail.isEmpty{Text(detail).wixalFont(size:11).foregroundStyle(theme.muted).lineSpacing(4)};content()}.frame(maxWidth:.infinity,alignment:.leading)
    }
}
struct WixalCard:ViewModifier {
    @Environment(\.wixalTheme) private var theme
    func body(content:Content)->some View {content.padding(16).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel,in:RoundedRectangle(cornerRadius:9)).overlay(RoundedRectangle(cornerRadius:9).stroke(theme.line,lineWidth:1)).shadow(color:.black.opacity(theme.light ? 0.035 : 0.1),radius:4,x:0,y:2)}
}
struct WixalField:ViewModifier {
    @Environment(\.wixalTheme) private var theme
    func body(content:Content)->some View{content.textFieldStyle(.plain).wixalFont(size:12).padding(10).background(theme.raised,in:RoundedRectangle(cornerRadius:7)).overlay(RoundedRectangle(cornerRadius:7).stroke(theme.line,lineWidth:1))}
}
struct PreferenceRow<Content:View>:View {
    let title:String
    var detail:String=""
    @ViewBuilder let content:()->Content
    @Environment(\.wixalTheme) private var theme
    var body:some View {HStack(spacing:24){VStack(alignment:.leading,spacing:5){Text(title).wixalFont(size:12);if !detail.isEmpty{Text(detail).wixalFont(size:10).foregroundStyle(theme.muted).lineSpacing(3)}};Spacer(minLength:16);content()}.padding(.vertical,9)}
}
extension View {
    func wixalCard()->some View{modifier(WixalCard())}
    func wixalField()->some View{modifier(WixalField())}
}
private struct ConversationSizeKey:EnvironmentKey{static let defaultValue:CGFloat=13}
extension EnvironmentValues{var wixalTextSize:CGFloat{get{self[ConversationSizeKey.self]}set{self[ConversationSizeKey.self]=newValue}}}

private struct WixalScaledFont:ViewModifier {
    let size:CGFloat
    let weight:Font.Weight
    let design:Font.Design
    @Environment(\.wixalTextSize) private var textSize
    func body(content:Content)->some View{content.font(.system(size:max(10,size+textSize-13),weight:weight,design:design))}
}
extension View {
    func wixalFont(size:CGFloat,weight:Font.Weight = .regular,design:Font.Design = .default)->some View{modifier(WixalScaledFont(size:size,weight:weight,design:design))}
}
