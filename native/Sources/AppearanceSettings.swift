import SwiftUI
import AppKit

/// Uses acknowledged engine preferences; preview content never creates a conversation.
struct QuietAppearanceSettings: View {
    let ui: [String:Any]
    let locked: Bool
    let systemReduceMotion: Bool
    let save: ([String:Any]) -> Void
    let previewLaunch: () -> Void
    let reset: () -> Void
    @Environment(\.wixalTheme) private var colours
    @ViewState private var themePicker = false
    @ViewState private var iconPicker = false
    @FocusState private var focusedTheme: String?
    private var palette: WixalPalette { WixalPalette.resolve(textValue(ui["theme"])) }
    private var matching: Bool { textValue(ui["appIcon"]).isEmpty || textValue(ui["appIcon"]) == "theme" }
    private var icon: String { let value=textValue(ui["appIcon"]); return WixalPalette.iconVariants.contains(value) ? value : palette.icon }
    private var textSize: Int { ui["textSize"] as? Int ?? 13 }
    private func toggle(_ key: String, default fallback: Bool = false) -> Binding<Bool> {
        Binding(get:{ui[key] as? Bool ?? fallback},set:{save([key:$0])})
    }
    var body: some View {
        VStack(alignment:.leading,spacing:0) {
            workspacePreview.padding(.bottom,20)
            Divider()
            ViewThatFits(in:.horizontal) {
                HStack(alignment:.top,spacing:20) { themeControl.frame(minWidth:170,maxWidth:.infinity); iconControl.frame(minWidth:180,maxWidth:.infinity) }
                VStack(alignment:.leading,spacing:18) { themeControl; iconControl }
            }.padding(.vertical,16)
            Divider()
            quietRow("Text size",detail:"\(textSize) pt · \(sizeName)") {
                Picker("Text size",selection:Binding(get:{textSize},set:{save(["textSize":$0])})) {
                    Text("Small").tag(11); Text("Default").tag(13); Text("Large").tag(15); Text("Extra large").tag(17)
                }.pickerStyle(.segmented).labelsHidden().frame(width:270)
            }
            Divider()
            quietRow("Reduce motion",detail:systemReduceMotion ? "Your Mac’s reduced motion setting is active." : "Also respects your Mac’s setting.") {
                Toggle("Reduce motion",isOn:toggle("reduceMotion")).labelsHidden().toggleStyle(.switch).controlSize(.small)
            }
            Divider()
            quietRow("When Wixal opens",detail:"Choose your launch effects.") {
                HStack(spacing:16) {
                    Toggle("Animation",isOn:toggle("launchAnimation",default:true)).toggleStyle(.checkbox)
                    Toggle("Sound",isOn:toggle("launchSound",default:true)).toggleStyle(.checkbox)
                }.wixalFont(size:11)
            }
            Divider()
            ViewThatFits(in:.horizontal) {
                HStack(spacing:20) { footer }
                VStack(alignment:.leading,spacing:12) { footer }
            }.padding(.top,18)
        }.disabled(locked)
    }
    private var sizeName: String { [11:"Small",13:"Default",15:"Large",17:"Extra large"][textSize] ?? "Default" }
    @ViewBuilder private var footer: some View {
        Button("Reset appearance…",action:reset).buttonStyle(.plain).foregroundStyle(colours.muted)
        Button("Preview launch intro",action:previewLaunch).buttonStyle(.plain).foregroundStyle(colours.muted)
    }
    private func quietRow<Control:View>(_ title:String,detail:String,@ViewBuilder control:()->Control)->some View {
        ViewThatFits(in:.horizontal) {
            HStack(spacing:18) { rowLabel(title,detail:detail).frame(minWidth:150,maxWidth:.infinity,alignment:.leading); control().fixedSize() }
            VStack(alignment:.leading,spacing:12) { rowLabel(title,detail:detail); control() }
        }.padding(.vertical,15)
    }
    private func rowLabel(_ title:String,detail:String)->some View {
        VStack(alignment:.leading,spacing:5) { Text(title).wixalFont(size:12,weight:.medium); Text(detail).wixalFont(size:11).foregroundStyle(colours.muted).fixedSize(horizontal:false,vertical:true) }
    }
    private var themeControl: some View {
        VStack(alignment:.leading,spacing:9) {
            Text("Theme").wixalFont(size:12,weight:.medium)
            Button { themePicker.toggle() } label: {
                HStack(spacing:9) { AppearanceIcon(variant:palette.icon,size:26); Text(palette.name).wixalFont(size:12); Spacer(minLength:8); AppearancePalettePreview(palette:palette); Image(systemName:"chevron.down").wixalFont(size:9).foregroundStyle(colours.muted) }
                    .padding(8).background(colours.panel,in:RoundedRectangle(cornerRadius:5)).overlay(RoundedRectangle(cornerRadius:5).stroke(colours.line,lineWidth:1))
            }.buttonStyle(.plain).accessibilityLabel("Theme: \(palette.name)").accessibilityValue(themePicker ? "Expanded" : "Collapsed")
                .popover(isPresented:$themePicker,arrowEdge:.bottom) {
                    ScrollViewReader { scroll in
                    ScrollView {
                        VStack(spacing:2) {
                            ForEach(WixalPalette.all,id:\.id) { option in
                                Button { themePicker=false;save(["theme":option.id]) } label: {
                                    HStack(spacing:10) {
                                        AppearanceIcon(variant:option.icon,size:28)
                                        Text(option.name).wixalFont(size:12)
                                        Spacer(minLength:10)
                                        AppearancePalettePreview(palette:option)
                                        Image(systemName:option.id == palette.id ? "checkmark" : "").wixalFont(size:11).foregroundStyle(colours.accent).frame(width:12)
                                    }.padding(.horizontal,9).padding(.vertical,6).contentShape(Rectangle())
                                        .background(option.id == palette.id ? colours.selected : .clear,in:RoundedRectangle(cornerRadius:4))
                                }.buttonStyle(WixalButtonStyle()).focused($focusedTheme,equals:option.id)
                                    .accessibilityLabel("\(option.name) theme, \(option.light ? "light" : "dark") palette and matching icon")
                                    .accessibilityAddTraits(option.id == palette.id ? [.isSelected] : []).id(option.id)
                            }
                        }.padding(6)
                    }.frame(width:300,height:420).background(colours.panel).foregroundStyle(colours.text)
                        .onAppear { focusedTheme=palette.id; scroll.scrollTo(palette.id) }
                        .onChange(of:focusedTheme) { _,id in if let id { scroll.scrollTo(id) } }
                        .onExitCommand { themePicker=false }
                        .onKeyPress(keys:[.upArrow,.downArrow]) { press in
                            let ids=WixalPalette.all.map(\.id), index=ids.firstIndex(of:focusedTheme ?? palette.id) ?? 0
                            focusedTheme=ids[(index+(press.key == .downArrow ? 1 : ids.count-1))%ids.count]
                            return .handled
                        }
                    }
                }
            Text("Ten palettes · light to dark").wixalFont(size:11).foregroundStyle(colours.muted)
        }
    }
    private var iconControl: some View {
        VStack(alignment:.leading,spacing:9) {
            Text("Dock icon").wixalFont(size:12,weight:.medium)
            HStack(spacing:9) {
                AppearanceIcon(variant:icon,size:32).accessibilityLabel("\(icon.capitalized) Dock icon")
                Button("Choose icon…") { iconPicker.toggle() }.buttonStyle(WixalButtonStyle(outlined:true)).wixalFont(size:11)
                    .popover(isPresented:$iconPicker,arrowEdge:.bottom) {
                        VStack(alignment:.leading,spacing:12) {
                            Text("Dock icon").wixalFont(size:13,weight:.medium)
                            LazyVGrid(columns:[GridItem(.adaptive(minimum:72),spacing:8)],spacing:8) {
                                ForEach(WixalPalette.iconVariants,id:\.self) { variant in
                                    Button { iconPicker=false;save(["appIcon":variant]) } label: {
                                        VStack(spacing:5) { AppearanceIcon(variant:variant,size:38); Text(variant.capitalized).wixalFont(size:11) }.padding(8).frame(maxWidth:.infinity)
                                            .background(icon == variant ? colours.selected : .clear,in:RoundedRectangle(cornerRadius:5))
                                            .overlay(RoundedRectangle(cornerRadius:5).stroke(icon == variant ? colours.accent : colours.line,lineWidth:1))
                                    }.buttonStyle(.plain).accessibilityLabel("\(variant.capitalized) Dock icon").accessibilityAddTraits(icon == variant ? [.isSelected] : [])
                                }
                            }
                            Text("Changes the running Dock icon.").wixalFont(size:11).foregroundStyle(colours.muted)
                        }.padding(14).frame(width:300).background(colours.panel).foregroundStyle(colours.text).onExitCommand { iconPicker=false }
                    }
            }.frame(minHeight:42)
            Toggle("Follow selected theme",isOn:Binding(get:{matching},set:{save(["appIcon":$0 ? "theme" : icon])})).toggleStyle(.checkbox).wixalFont(size:11)
        }
    }
    private var workspacePreview: some View {
        VStack(spacing:0) {
            HStack { Text("wixal_").wixalFont(size:11,design:.monospaced); Spacer(); Text("Preview").wixalFont(size:11).foregroundStyle(colours.muted) }.padding(.horizontal,12).frame(height:32)
            Divider()
            HStack(spacing:0) {
                VStack(alignment:.leading,spacing:12) {
                    Text("Chats").wixalFont(size:11,weight:.medium)
                    ForEach(["New chat","Projects","Recents"],id:\.self) { Text($0).wixalFont(size:11).foregroundStyle(colours.muted) }
                    Spacer(minLength:0)
                }.padding(12).frame(width:100,alignment:.leading).frame(maxHeight:.infinity).background(colours.sidebar)
                Divider()
                VStack(alignment:.leading,spacing:10) {
                    Text("A workspace that feels like yours.").wixalFont(size:13,weight:.medium)
                    Text("Your theme and text size, together.").wixalFont(size:13).foregroundStyle(colours.muted)
                    Spacer(minLength:0)
                    HStack { Text("Message Wixal…"); Spacer(); Image(systemName:"arrow.up").foregroundStyle(colours.accent) }.wixalFont(size:11).padding(9).background(colours.panel,in:RoundedRectangle(cornerRadius:4)).overlay(RoundedRectangle(cornerRadius:4).stroke(colours.line,lineWidth:1))
                }.padding(16).frame(maxWidth:.infinity,alignment:.leading)
            }.frame(height:150)
        }.background(colours.background).clipShape(RoundedRectangle(cornerRadius:6)).overlay(RoundedRectangle(cornerRadius:6).stroke(colours.line,lineWidth:1)).accessibilityHidden(true)
    }
}

private struct AppearanceIcon: View {
    let variant: String
    let size: CGFloat
    var body: some View {
        Group {
            if let url=Bundle.main.url(forResource:variant,withExtension:"png",subdirectory:"icon-variants"),let image=NSImage(contentsOf:url) {
                Image(nsImage:image).resizable().scaledToFit()
            } else { Image(systemName:"app").resizable().scaledToFit() }
        }.frame(width:size,height:size).accessibilityHidden(true)
    }
}

private struct AppearancePalettePreview: View {
    let palette: WixalPalette
    private var preview: WixalTheme { WixalTheme(name:palette.name) }
    var body: some View {
        HStack(spacing:0) {
            preview.sidebar.frame(width:14)
            VStack(alignment:.leading,spacing:4) {
                RoundedRectangle(cornerRadius:1).fill(preview.text).frame(height:2)
                RoundedRectangle(cornerRadius:1).fill(preview.accent).frame(height:3)
            }.padding(5).frame(maxWidth:.infinity).background(preview.background)
        }.frame(width:58,height:25).clipShape(RoundedRectangle(cornerRadius:3)).overlay(RoundedRectangle(cornerRadius:3).stroke(preview.line,lineWidth:1)).accessibilityHidden(true)
    }
}
