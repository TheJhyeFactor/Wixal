import SwiftUI
import AppKit
import OSLog
import CryptoKit

// Only appearance is cached here. Workspace data remains owned by the engine.
struct StartupPreferences {
    var theme = "sakura"
    var animation = true
    var sound = true
    var reducedMotion = false
    static var key: String {
        let workspace = ProcessInfo.processInfo.environment["WIXAL_NATIVE_DATA"]
            ?? Bundle.main.object(forInfoDictionaryKey:"WixalPreviewData") as? String ?? "default"
        let identity = SHA256.hash(data:Data(workspace.utf8)).map{String(format:"%02x",$0)}.joined()
        return "startup.appearance." + identity
    }
    static func load() -> Self {
        from(UserDefaults.standard.dictionary(forKey:key) ?? [:])
    }
    static func from(_ ui: [String:Any]) -> Self {
        let saved = textValue(ui["theme"])
        return Self(theme:["sakura","midnight","forest","paper"].contains(saved) ? saved : "sakura",
                    animation:ui["launchAnimation"] as? Bool ?? true,
                    sound:ui["launchSound"] as? Bool ?? true,
                    reducedMotion:ui["reduceMotion"] as? Bool ?? false)
    }
    static func save(_ ui: [String:Any]) {
        let value = from(ui)
        UserDefaults.standard.set(["theme":value.theme,"launchAnimation":value.animation,
                                   "launchSound":value.sound,"reduceMotion":value.reducedMotion],forKey:key)
    }
    var colours: WixalTheme {
        WixalTheme(name:["sakura":"Sakura","midnight":"Midnight","forest":"Forest","paper":"Paper"][theme] ?? "Sakura")
    }
}

enum StartupEvidence {
    private static let logger = Logger(subsystem:Bundle.main.bundleIdentifier ?? "app.wixal.native",category:"LaunchOrder")
    static func record(_ phase: String) {
        logger.info("Startup phase: \(phase, privacy:.public)")
        // Optional observation only; it does not alter production startup timing.
        guard ProcessInfo.processInfo.environment["WIXAL_NATIVE_ACCEPTANCE"] == "1",
              let path = ProcessInfo.processInfo.environment["WIXAL_NATIVE_STARTUP_TRACE"],
              let row = try? JSONSerialization.data(withJSONObject:["phase":phase,
                  "uptime":ProcessInfo.processInfo.systemUptime,"pid":ProcessInfo.processInfo.processIdentifier]) else{return}
        if !FileManager.default.fileExists(atPath:path){_ = FileManager.default.createFile(atPath:path,contents:nil)}
        guard let handle = FileHandle(forWritingAtPath:path) else{return}
        defer{try? handle.close()}
        _ = try? handle.seekToEnd();try? handle.write(contentsOf:row + Data([10]))
    }
}

// The engine starts after AppKit draws the first visible splash frame, rather
// than on the window's onAppear callback before rendering can complete.
private struct SplashPresentation: NSViewRepresentable {
    let presented: () -> Void
    final class Marker: NSView {
        var presented: (() -> Void)?
        private var reported = false
        override func hitTest(_ point:NSPoint) -> NSView? { nil }
        override func draw(_ dirtyRect:NSRect) {
            super.draw(dirtyRect)
            guard !reported,window?.isVisible == true else{return}
            reported = true
            DispatchQueue.main.async { [weak self] in self?.presented?() }
        }
        override func viewDidMoveToWindow(){super.viewDidMoveToWindow();needsDisplay=true}
    }
    func makeNSView(context:Context) -> Marker {
        let view = Marker();view.presented=presented;return view
    }
    func updateNSView(_ view:Marker,context:Context){view.presented=presented}
}

struct AppStartupView: View {
    @ObservedObject var engine: EngineClient
    @Environment(\.accessibilityReduceMotion) private var systemReducedMotion
    @ViewState<StartupPreferences> private var preferences = StartupPreferences.load()
    @ViewState<Bool> private var presented = false
    @ViewState<Bool> private var introFinished = false
    @ViewState<Bool> private var workspaceVisible = false
    private var canOpenWorkspace: Bool { presented && introFinished && (engine.connected || engine.startupFailed) }
    var body: some View {
        Group {
            if workspaceVisible {
                WorkspaceView(engine:engine)
            } else {
                LaunchView(theme:preferences.colours,
                           motion:preferences.animation && !preferences.reducedMotion && !systemReducedMotion,
                           sound:preferences.sound,dismissAutomatically:false,done:{
                    guard !introFinished else{return}
                    introFinished=true;StartupEvidence.record("reveal-finished")
                })
                .background(SplashPresentation(presented:{
                    guard !presented else{return}
                    presented=true;StartupEvidence.record("splash-presented");engine.start()
                }))
                .ignoresSafeArea(.container,edges:.top)
                .overlay(alignment:.bottom){
                    if introFinished && !engine.connected && !engine.startupFailed {
                        HStack(spacing:10){ProgressView().controlSize(.small);Text(engine.activity)}
                            .font(.system(size:12)).foregroundStyle(preferences.colours.muted).padding(.bottom,48)
                    }
                }
                .preferredColorScheme(preferences.colours.light ? .light : .dark)
            }
        }
        .onChange(of:canOpenWorkspace){_,ready in
            if ready && !workspaceVisible {workspaceVisible=true;StartupEvidence.record("workspace-released")}
        }
        .onChange(of:engine.connected,initial:true){_,ready in
            if ready {StartupPreferences.save(engine.state["ui"] as? [String:Any] ?? [:])}
        }
        .onChange(of:pretty(engine.state["ui"] as? [String:Any] ?? [:])){_,_ in
            if engine.connected {StartupPreferences.save(engine.state["ui"] as? [String:Any] ?? [:])}
        }
    }
}
