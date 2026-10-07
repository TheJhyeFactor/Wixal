import SwiftUI

struct LegalView: View {
    @ObservedObject var engine: EngineClient
    let document: String
    @ViewState private var content: [String: Any] = [:]
    @ViewState private var error = ""
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        WixalPage(eyebrow: "WIXAL LEGAL · DRAFT", title: textValue(content["title"]).isEmpty ? (document == "terms" ? "Terms & Conditions" : "Privacy Policy") : textValue(content["title"]), subtitle: textValue(content["version"])) {
            if content.isEmpty && error.isEmpty { ProgressView() }
            MarkdownMessage(content: textValue(content["markdown"]))
            if !error.isEmpty { Text(error).foregroundStyle(theme.muted) }
        }.task(id: document) { content = [:]; error = ""; do { content = try await engine.call("legal-document", ["id": document]) as? [String: Any] ?? [:] } catch { self.error = error.localizedDescription } }
    }
}
