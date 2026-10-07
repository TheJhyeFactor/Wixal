import SwiftUI

struct AccountView: View {
    @ObservedObject var engine: EngineClient
    var navigate: (String) -> Void = { _ in }
    @Environment(\.wixalTheme) private var theme
    @ViewState private var create = false
    @ViewState private var name = ""
    @ViewState private var email = ""
    @ViewState private var password = ""
    @ViewState private var presetName = ""
    @ViewState private var memory = ""
    @ViewState private var working = false
    @ViewState private var status = ""
    @ViewState private var pendingDelete: String?
    @ViewState private var accountDelete=false
    @ViewState private var confirmDelete=""
    @ViewState private var currentPassword=""
    @ViewState private var newPassword=""
    private var account: [String: Any] { engine.state["account"] as? [String: Any] ?? [:] }
    private var profile: [String: Any] { account["profile"] as? [String: Any] ?? [:] }
    private var signedIn: Bool { account["signedIn"] as? Bool ?? false }
    private var verified: Bool { profile["verified"] as? Bool ?? false }
    var body: some View {
        WixalPage(eyebrow: "WIXAL ACCOUNT", title: "Your workspace, wherever you work", subtitle: "Sign in to save workspace presets on another Mac. Local chat, projects, memory and tools are available as a guest.") {
            if signedIn {
                HStack(spacing: 16) {
                    Text("◎").font(.system(size: 32)).foregroundStyle(theme.accent)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(textValue(profile["name"])).font(.system(size: 18, weight: .medium))
                        Text(textValue(profile["email"])).foregroundStyle(theme.muted)
                        Text(verified ? "Email verified" : "Verification needed").font(.system(size: 11)).foregroundStyle(verified ? theme.accent : theme.muted)
                    }
                }.wixalCard()
                if !verified {
                    HStack {
                        Button("I’ve verified my email") { run("account-refresh") }
                        Button("Resend verification") { run("account-resend") }
                    }.buttonStyle(WixalButtonStyle(outlined: true))
                }
                WixalSection(title: "Cloud workspace presets", detail: "Save your theme, text size, sidebar, motion, conversation mode and context preferences. Project tools and approval rules stay as they are.") {
                    HStack {
                        TextField("e.g. Focus, Coding, Reading", text: $presetName).wixalField()
                        Button("Save current setup") { run("account-preset-save", ["name": presetName]); presetName = "" }.disabled(presetName.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                    ForEach(Array(records(account["presets"]).enumerated()), id: \.offset) { _, preset in
                        HStack {
                            Text(textValue(preset["name"])); Spacer()
                            Button("Apply") { run("account-preset-apply", ["id": textValue(preset["id"])]) }
                            Button("Delete") { pendingDelete = textValue(preset["id"]) }
                        }.wixalCard()
                    }
                    Button("Refresh cloud presets") { run("account-sync") }
                }.disabled(!verified)
                WixalSection(title: "Global preferences", detail: "Keep short personal instructions in your account. Up to 1,200 characters. Project memory stays local unless you enable sharing separately.") {
                    TextEditor(text: $memory).scrollContentBackground(.hidden).frame(height: 100).wixalField()
                    HStack { Text("\(memory.count) / 1,200").font(.system(size: 10)).foregroundStyle(theme.muted); Spacer(); Button("Save preferences") { run("global-memory-save", ["content": memory]) }.disabled(memory.count > 1200) }
                }.disabled(!verified)
                WixalSection(title:"Password & account") {
                    SecureField("Current password",text:$currentPassword).textContentType(.password).wixalField().accessibilityLabel("Current password for account changes")
                    SecureField("New password, at least 10 characters",text:$newPassword).textContentType(.newPassword).wixalField().accessibilityLabel("New account password")
                    Button("Change password") { run("account-password-change",["password":currentPassword,"newPassword":newPassword]);currentPassword="";newPassword="" }.disabled(currentPassword.isEmpty || newPassword.count<10)
                    Button("Delete online account…",role:.destructive) { accountDelete=true }.disabled(currentPassword.isEmpty)
                    Text("Deletion removes the online identity and cloud presets/preferences. Local projects and chats stay on this Mac.").font(.system(size:10)).foregroundStyle(theme.muted)
                }
                Button("Sign out & use guest workspace") { run("account-sign-out") }
            } else {
                HStack {
                    Button("Sign in") { create = false }.buttonStyle(WixalButtonStyle(outlined: !create))
                    Button("Create account") { create = true }.buttonStyle(WixalButtonStyle(outlined: create))
                }
                VStack(alignment: .leading, spacing: 14) {
                    if create { labeled("Display name") { TextField("Your name", text: $name).wixalField() } }
                    labeled("Email") { TextField("you@example.com", text: $email).textContentType(.emailAddress).wixalField() }
                    labeled("Password") { SecureField(create ? "At least 10 characters" : "Password", text: $password).textContentType(create ? .newPassword : .password).wixalField().onSubmit(authenticate) }
                    Button(create ? "Create account" : "Sign in", action: authenticate).buttonStyle(WixalButtonStyle(outlined: false)).disabled(email.isEmpty || password.isEmpty || (create && name.isEmpty))
                    Button("Forgot password? Send reset email") { run("account-reset", ["email": email]) }.buttonStyle(.plain).foregroundStyle(theme.muted)
                    Button("Restore saved sign-in from Keychain") { run("account-restore") }.buttonStyle(.plain).foregroundStyle(theme.muted)
                }.wixalCard()
            }
            HStack {
                Button("Terms & Conditions") { navigate("Terms") }
                Text("·").foregroundStyle(theme.muted)
                Button("Privacy Policy") { navigate("Privacy") }
            }.buttonStyle(.plain).font(.system(size: 11))
            if working { HStack { ProgressView().controlSize(.small); Text("Contacting account service…") } }
            Text(status.isEmpty ? textValue(account["message"]) : status).font(.system(size: 11)).foregroundStyle(theme.muted).textSelection(.enabled).id(status.isEmpty ? textValue(account["message"]) : status)
        }.font(.system(size: 12)).disabled(working).onAppear { memory = textValue(account["globalMemory"]) }
        .alert("Delete your online Wixal account?",isPresented:$accountDelete) {
            TextField("Type DELETE",text:$confirmDelete)
            Button("Cancel",role:.cancel){confirmDelete=""}
            Button("Delete online account",role:.destructive){run("account-delete",["password":currentPassword,"confirmation":confirmDelete]);currentPassword="";confirmDelete=""}.disabled(confirmDelete != "DELETE")
        } message: { Text("This permanently deletes the signed-in online account. Local data remains available.") }
        .alert("Delete this cloud preset?", isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } })) {
            Button("Cancel", role: .cancel) { pendingDelete = nil }
            Button("Delete", role: .destructive) { if let id = pendingDelete { run("account-preset-delete", ["id": id]) }; pendingDelete = nil }
        }
    }
    private func authenticate() { run(create ? "account-create" : "account-sign-in", ["email": email, "password": password, "name": name]); password = "" }
    private func run(_ method: String, _ params: [String: Any] = [:]) {
        guard !working else { return }; working = true; status = ""
        Task { defer { working = false }; do { let value = try await engine.call(method, params) as? [String: Any] ?? [:]; status = textValue(value["message"]); if signedIn { memory = textValue(value["globalMemory"]) } } catch { status = error.localizedDescription } }
    }
    private func labeled<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View { VStack(alignment: .leading, spacing: 7) { Text(title).font(.system(size: 11)); content() } }
}
