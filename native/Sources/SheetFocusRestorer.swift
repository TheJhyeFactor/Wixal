import SwiftUI
import AppKit

/// Retain the actual control that opened a sheet, including the AppKit composer.
struct SheetFocusRestorer: NSViewRepresentable {
    final class FocusView: NSView {
        private var observers:[NSObjectProtocol]=[]
        private weak var previous:NSResponder?
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            observers.forEach(NotificationCenter.default.removeObserver);observers=[]
            guard let window else{return}
            observers.append(NotificationCenter.default.addObserver(forName:NSWindow.willBeginSheetNotification,object:window,queue:.main){[weak self] _ in self?.previous=window.firstResponder})
            observers.append(NotificationCenter.default.addObserver(forName:NSWindow.didEndSheetNotification,object:window,queue:.main){[weak self] _ in
                DispatchQueue.main.async {guard window.attachedSheet==nil,let responder=self?.previous else{return};window.makeFirstResponder(responder);self?.previous=nil}
            })
        }
        deinit{observers.forEach(NotificationCenter.default.removeObserver)}
    }
    func makeNSView(context:Context)->FocusView{FocusView()}
    func updateNSView(_ view:FocusView,context:Context){}
}
