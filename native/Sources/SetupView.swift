import SwiftUI
import AppKit

struct SetupView: View {
    @ObservedObject var engine: EngineClient
    var navigate: (String) -> Void = { _ in }
    var complete: () -> Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var accepted = false
    @ViewState private var accountPresented = false
    @ViewState private var legalDocument: String?
    @ViewState private var working = false
    @ViewState private var status = ""
    private var setup: [String: Any] { engine.state["setup"] as? [String: Any] ?? [:] }
    private var entryCompleted: Bool { setup["entryCompleted"] as? Bool ?? false }
    private var account: [String: Any] { engine.state["account"] as? [String: Any] ?? [:] }
    private var signedIn: Bool { account["signedIn"] as? Bool ?? false }
    var body: some View {
        WixalPage(eyebrow: "WELCOME TO WIXAL", title: entryCompleted ? "Set up your workspace" : "Welcome to Wixal", subtitle: entryCompleted ? "Choose your theme and get ready to work." : "Sign in or continue as a guest.") {
            if !entryCompleted {
                Text("wixal_").font(.system(size: 48, weight: .medium, design: .monospaced)).tracking(-3).padding(.vertical, 12)
                Button("Sign in / Create account") { accountPresented = true }.buttonStyle(WixalButtonStyle(outlined: false))
                if signedIn { Text("Signed in as \(textValue((account["profile"] as? [String: Any])?["name"]))").foregroundStyle(theme.muted) }
                HStack { Button("Terms & Conditions") { legalDocument = "terms" }; Text("·"); Button("Privacy Policy") { legalDocument = "privacy" } }.buttonStyle(.plain).font(.system(size: 11))
                Toggle("I have reviewed and accept the Terms & Conditions and Privacy Policy", isOn: $accepted).toggleStyle(.checkbox).font(.system(size: 11))
                HStack { Button(signedIn ? "Continue to Wixal →" : "Continue as guest →") { enter(signedIn ? "account" : "guest") }.buttonStyle(WixalButtonStyle(outlined: false)).disabled(!accepted); if signedIn { Button("Use guest workspace") { enter("guest") }.disabled(!accepted) } }
            } else {
                step("01", "Your workspace") {
                    Text("Guests can use local chat, models, projects, memory and tools. An account adds presets you can use on another Mac.").foregroundStyle(theme.muted)
                    HStack { Button("Create account / sign in") { accountPresented = true }; Text(signedIn ? "Signed in" : "Guest workspace").foregroundStyle(theme.muted) }
                }
                step("02", "Choose your theme") {
                    HStack(spacing: 10) { ForEach(["sakura", "midnight", "forest", "paper"], id: \.self) { name in Button { engine.action("settings", ["ui": ["theme": name]]) } label: { VStack(spacing: 8) { RoundedRectangle(cornerRadius: 6).fill(WixalTheme(name: name.capitalized).background).overlay(RoundedRectangle(cornerRadius: 6).stroke(WixalTheme(name: name.capitalized).accent, lineWidth: 2)).frame(height: 50); Text(name.capitalized) }.padding(10).frame(maxWidth: .infinity).background(theme.panel, in: RoundedRectangle(cornerRadius: 8)) }.buttonStyle(.plain) } }
                }
                step("03", "Get ready to work") {
                    Text(engine.modelConnectionLabel).foregroundStyle(theme.muted)
                    Text(textValue(engine.state["model"]).isEmpty ? "Choose a model before your first conversation." : "Selected model: \(textValue(engine.state["model"]))").foregroundStyle(theme.muted)
                    Text(engine.project == nil ? "Choose a project folder, or start in your personal workspace." : "Project: \(textValue(engine.project?["name"]))").foregroundStyle(theme.muted)
                    HStack { Button("Choose / download a model ↗") { navigate("Models") }; Button("Open project folder ↗", action: engine.pickProject) }
                }
                HStack { Button(signedIn ? "Continue to Wixal →" : "Continue as guest →") { finish() }.buttonStyle(WixalButtonStyle(outlined: false)); Text("You can run setup again from Settings.").font(.system(size: 10)).foregroundStyle(theme.muted) }
            }
            if working { ProgressView().controlSize(.small) }; if !status.isEmpty { Text(status).foregroundStyle(theme.muted).font(.system(size: 11)) }
        }.font(.system(size: 12)).disabled(working)
        .sheet(isPresented: $accountPresented) { VStack(spacing: 0) { closeBar { accountPresented = false }; AccountView(engine: engine, navigate: { route in accountPresented = false; Task { try? await Task.sleep(nanoseconds: 200_000_000); legalDocument = route == "Terms" ? "terms" : "privacy" } }) }.frame(width:min(680, (NSApp.keyWindow?.frame.width ?? 1000)-60),height:min(600, (NSApp.keyWindow?.frame.height ?? 680)-80)).environment(\.wixalTheme, theme) }
        .sheet(isPresented: Binding(get: { legalDocument != nil }, set: { if !$0 { legalDocument = nil } })) { VStack(spacing: 0) { closeBar { legalDocument = nil }; LegalView(engine: engine, document: legalDocument ?? "terms") }.frame(width:min(720, (NSApp.keyWindow?.frame.width ?? 1000)-60),height:min(600, (NSApp.keyWindow?.frame.height ?? 680)-80)).environment(\.wixalTheme, theme) }
    }
    private func step<Content: View>(_ number: String, _ title: String, @ViewBuilder content: () -> Content) -> some View { HStack(alignment: .top, spacing: 18) { Text(number).font(.system(size: 11, design: .monospaced)).foregroundStyle(theme.accent).padding(.top, 3); VStack(alignment: .leading, spacing: 14) { Text(title).font(.system(size: 16, weight: .medium)); content() }.frame(maxWidth: .infinity, alignment: .leading) }.wixalCard() }
    private func closeBar(_ close: @escaping () -> Void) -> some View { HStack { Spacer(); Button("Close", action: close).buttonStyle(.plain).padding(16) }.background(theme.background) }
    private func enter(_ choice: String) { working = true; Task { defer { working = false }; do { _ = try await engine.call("entry-complete", ["choice": choice, "legalAccepted": accepted]) } catch { status = error.localizedDescription } } }
    private func finish() { working = true; Task { defer { working = false }; do { _ = try await engine.call("setup-complete"); complete() } catch { status = error.localizedDescription } } }
}
