import SwiftUI

struct SettingsCategory: Identifiable {
    let id: String
    let symbol: String
    let detail: String
    let terms: String
    static let all: [SettingsCategory] = [
        .init(id:"Appearance",symbol:"paintpalette",detail:"Make your workspace comfortable and familiar.",terms:"theme sakura midnight forest paper text font size motion animation icon launch sound"),
        .init(id:"Models & performance",symbol:"cpu",detail:"Manage local models and understand their resource use.",terms:"model library downloads import benchmark engine memory ram usage tokens speed"),
        .init(id:"Context & memory",symbol:"brain",detail:"Choose what Wixal includes when it responds.",terms:"context window summary summarise instructions global project recall history semantic indexing notes"),
        .init(id:"Tools & permissions",symbol:"checkmark.shield",detail:"Manage global installation and choose how actions are reviewed.",terms:"tools installation install automatic downloads global permissions review approval commands skills markdown"),
        .init(id:"Connections & sharing",symbol:"point.3.connected.trianglepath.dotted",detail:"Connect external tools and control project access.",terms:"mcp server executable arguments https oauth companion tunnel sharing"),
        .init(id:"Data & sync",symbol:"externaldrive",detail:"Manage saved data, recovery and device sync.",terms:"encrypted sync folder passphrase backup restore import migration storage"),
        .init(id:"Account",symbol:"person.crop.circle",detail:"Manage your identity and cloud presets.",terms:"account guest sign in email verification password cloud presets"),
        .init(id:"General & about",symbol:"gearshape",detail:"Control app behaviour and find help.",terms:"compact sidebar background schedules tasks diagnostics restart shortcuts setup version legal terms privacy")
    ]
}

@MainActor final class SettingsState: ObservableObject {
    struct Draft { var text: String; var baseline: String }
    @Published var category = "Appearance"
    @Published var search = ""
    @Published var detail: String?
    @Published var saving = false
    @Published var status = ""
    @Published var failure = ""
    @Published var drafts: [String: Draft] = [:]
    func open(_ category: String, detail: String? = nil) {
        self.category = category; self.detail = detail; search = ""
    }
    func syncDraft(_ owner: String, saved: String) {
        if let draft = drafts[owner], draft.text != draft.baseline { return }
        drafts[owner] = Draft(text:saved, baseline:saved)
    }
    func updateDraft(_ owner: String, text: String, saved: String) {
        let baseline = drafts[owner]?.baseline ?? saved
        drafts[owner] = Draft(text:text, baseline:baseline)
    }
    func dirty(_ owner: String) -> Bool {
        guard let draft = drafts[owner] else { return false }
        return draft.text != draft.baseline
    }
    func perform(_ engine: EngineClient, _ method: String, _ params: [String:Any] = [:], success: String = "Saved", completion: ((Any)->Void)? = nil) {
        guard !saving else { return }
        saving = true; failure = ""; status = "Saving…"
        Task {
            defer { saving = false }
            do { let result = try await engine.call(method,params); status = success; completion?(result) }
            catch { status = "Changes not saved"; failure = error.localizedDescription }
        }
    }
}

struct SettingsScope: View {
    let text: String
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        Text(text).wixalFont(size:10).foregroundStyle(theme.muted).padding(.horizontal,6).padding(.vertical,2)
            .overlay(RoundedRectangle(cornerRadius:4).stroke(theme.line,lineWidth:1))
    }
}

struct SettingsRow<Control: View>: View {
    let title: String
    let detail: String
    var scope = "This Mac"
    @ViewBuilder var control: () -> Control
    @Environment(\.wixalTheme) private var theme
    private var description: some View {
        VStack(alignment:.leading,spacing:5) {
            ViewThatFits(in:.horizontal) {
                HStack(spacing:8) { Text(title).wixalFont(size:12,weight:.medium); SettingsScope(text:scope) }
                VStack(alignment:.leading,spacing:5) { Text(title).wixalFont(size:12,weight:.medium); SettingsScope(text:scope) }
            }
            Text(detail).wixalFont(size:11).foregroundStyle(theme.muted).fixedSize(horizontal:false,vertical:true)
        }
    }
    var body: some View {
        ViewThatFits(in:.horizontal) {
            HStack(spacing:20) { description.frame(minWidth:190,maxWidth:.infinity,alignment:.leading); control().fixedSize(horizontal:true,vertical:false) }
            VStack(alignment:.leading,spacing:12) { description; control() }
        }.padding(.vertical,12)
    }
}

struct SettingsCard<Content: View>: View {
    @ViewBuilder var content: () -> Content
    var body: some View { VStack(alignment:.leading,spacing:0,content:content).wixalCard() }
}
