import SwiftUI
import AppKit
import SwiftTerm

/// SwiftTerm's macOS accessibility service is currently empty. Expose the real
/// visible terminal buffer and a focus action without pretending it is an editor.
@MainActor final class AccessibleTerminalView:LocalProcessTerminalView {
    var projectDirectory=""
    private var accessibilityUpdate:DispatchWorkItem?
    override func isAccessibilityElement()->Bool { true }
    override func accessibilityRole()->NSAccessibility.Role? { .textArea }
    override func accessibilityLabel()->String? { "Terminal · "+projectDirectory }
    override func accessibilityHelp()->String? { "Host shell. Interact to type commands. Visible output follows terminal scrolling." }
    override func accessibilityValue()->Any? {
        guard let terminal else{return ""}
        return (0..<min(terminal.rows,80)).compactMap{terminal.getLine(row:$0)?.translateToString(trimRight:true)}.joined(separator:"\n").trimmingCharacters(in:.whitespacesAndNewlines)
    }
    override func accessibilityPerformPress()->Bool { window?.makeFirstResponder(self) ?? false }
    override func dataReceived(slice:ArraySlice<UInt8>) {
        super.dataReceived(slice:slice)
        accessibilityUpdate?.cancel()
        let update=DispatchWorkItem{[weak self] in guard let self else{return};NSAccessibility.post(element:self,notification:.valueChanged)}
        accessibilityUpdate=update
        DispatchQueue.main.asyncAfter(deadline:.now()+0.3,execute:update)
    }
}

@MainActor final class TerminalSession:ObservableObject {
    private var views: [String: LocalProcessTerminalView] = [:]
    private var view:LocalProcessTerminalView?
    private var directory=""
    func terminal(root:String)->LocalProcessTerminalView {
        let next=root.isEmpty ? NSHomeDirectory() : root
        if let retained=views[next] { directory=next; view=retained; return retained }
        let terminal=AccessibleTerminalView(frame:.zero)
        terminal.projectDirectory=next
        directory=next;view=terminal;views[next]=terminal
        terminal.startProcess(executable:"/bin/zsh",args:ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil ? ["-l","-c","printf native-terminal-ok; sleep 120"] : ["-l"],currentDirectory:next)
        return terminal
    }
    func close(){views.values.forEach{$0.process.terminate()};views.removeAll();view=nil;directory=""}
    func clear(){view?.feed(text:"\u{1B}[2J\u{1B}[H")}
}

struct TerminalPanel: NSViewRepresentable {
    let session:TerminalSession
    let root: String
    let theme:WixalTheme
    let textSize:CGFloat
    func makeNSView(context: Context) -> LocalProcessTerminalView {
        let view = session.terminal(root:root)
        apply(view)
        return view
    }
    func updateNSView(_ view: LocalProcessTerminalView, context: Context) {apply(view)}
    private func apply(_ view:LocalProcessTerminalView){view.font=NSFont.monospacedSystemFont(ofSize:textSize,weight:.regular);view.nativeForegroundColor=NSColor(theme.text);view.nativeBackgroundColor=NSColor(theme.background)}
    // The scene owns the shell. Hiding the panel only detaches its view.
    static func dismantleNSView(_ view: LocalProcessTerminalView, coordinator: ()) {}
}
