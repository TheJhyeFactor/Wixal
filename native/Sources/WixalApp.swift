import SwiftUI
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    var engine: EngineClient?
    func applicationDidFinishLaunching(_ notification: Notification) { NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true) }
    func applicationWillTerminate(_ notification: Notification) { MainActor.assumeIsolated { engine?.close() } }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main struct WixalApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var engine = EngineClient()
    var body: some Scene {
        WindowGroup("Wixal Native") {
            WorkspaceView(engine: engine)
                .frame(minWidth: 920, minHeight: 640)
                .onAppear {
                    delegate.engine = engine; engine.start()
                    // A deterministic packaged acceptance window, with the same
                    // production minimum and no change to normal saved geometry.
                    if ProcessInfo.processInfo.environment["WIXAL_NATIVE_ACCEPTANCE"] == "1" {
                        DispatchQueue.main.async { NSApp.windows.first(where:{$0.title=="Wixal Native"})?.setContentSize(NSSize(width:920,height:640)) }
                    }
                }
        }
        .defaultSize(width: 1320, height: 880)
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(after:.appInfo){Button("Settings…"){NotificationCenter.default.post(name:.wixalOpenSettings,object:nil)}.keyboardShortcut(",");Divider()}

            CommandGroup(replacing: .newItem) {
                Button("New conversation") { navigate("New conversation") }.keyboardShortcut("n")
                Button("Open project…") { engine.pickProject() }.keyboardShortcut("o")
            }
            CommandMenu("Workspace"){
                Button("Project files"){navigate("Files")}.keyboardShortcut("f",modifiers:[.command,.shift])
                Button("Tool kit"){navigate("Tool kit")}.keyboardShortcut("t",modifiers:[.command,.shift])
                Button("Chat"){navigate("Chat")}
                Button("Agents"){navigate("Agents")}
                Button("Cybersecurity"){navigate("Cybersecurity")}
                Button("Projects"){navigate("Projects")}
                Button("Terminal"){navigate("Terminal")}.keyboardShortcut("j")
                Button("Models"){navigate("Models")}.keyboardShortcut("l")
                Button("Usage & performance"){navigate("Performance")}
                Button("Find a command"){navigate("Commands")}.keyboardShortcut("k")
                Divider()
                Button("Archived chats"){navigate("Archived chats")}
                Button("Task inbox"){navigate("Tasks")}
                Button("Connections"){navigate("Connections")}
                Button("Account"){navigate("Account")}
            }
        }
    }
    private func navigate(_ action:String){NotificationCenter.default.post(name:.wixalNavigate,object:action)}
}
