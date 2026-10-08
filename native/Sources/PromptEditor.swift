import SwiftUI
import AppKit

final class WixalPromptTextView: NSTextView {
    var submit: (() -> Void)?
    var mentionKey: ((UInt16) -> Bool)?
    override func keyDown(with event:NSEvent) {
        if !hasMarkedText(), mentionKey?(event.keyCode) == true { return }
        if event.keyCode == 36 && !event.modifierFlags.contains(.shift) && !hasMarkedText() {submit?();return}
        super.keyDown(with:event)
    }
}
struct PromptEditor:NSViewRepresentable {
    @Binding var text:String
    @Environment(\.wixalTextSize) private var textSize
    var theme:WixalTheme
    var send:()->Void
    var selection: NSRange = NSRange(location:0,length:0)
    var onSelection: (NSRange)->Void = {_ in}
    var mentionKey: (UInt16)->Bool = {_ in false}
    var onHeight:(CGFloat)->Void = {_ in}
    final class Coordinator:NSObject,NSTextViewDelegate {
        var parent:PromptEditor
        var lastHeight:CGFloat=0
        init(_ parent:PromptEditor){self.parent=parent}
        func textDidChange(_ notification:Notification){guard let view=notification.object as? NSTextView else{return};if view.string.count>16000{view.string=String(view.string.prefix(16000))};parent.text=view.string; measure(view)}
        func textViewDidChangeSelection(_ notification:Notification) { guard let view=notification.object as? NSTextView else{return};let range=view.selectedRange();DispatchQueue.main.async{self.parent.onSelection(range)} }
        func measure(_ view:NSTextView){guard let container=view.textContainer,let layout=view.layoutManager else{return};layout.ensureLayout(for:container);let height=min(180,max(58,layout.usedRect(for:container).height+12));guard abs(height-lastHeight)>0.5 else{return};lastHeight=height;DispatchQueue.main.async{self.parent.onHeight(height)}}
    }
    func makeCoordinator()->Coordinator{Coordinator(self)}
    func makeNSView(context:Context)->NSScrollView {
        let scroll=NSScrollView();scroll.drawsBackground=false;scroll.hasVerticalScroller=true;scroll.autohidesScrollers=true;scroll.borderType = .noBorder
        let view=WixalPromptTextView();view.isRichText=false;view.drawsBackground=false;view.isHorizontallyResizable=false;view.isVerticallyResizable=true;view.autoresizingMask=[.width];view.textContainer?.widthTracksTextView=true;view.textContainer?.containerSize=NSSize(width:0,height:CGFloat.greatestFiniteMagnitude);view.textContainer?.lineFragmentPadding=0;view.textContainerInset=NSSize(width:0,height:4);view.font=NSFont.systemFont(ofSize:max(13,textSize+1));view.isAutomaticQuoteSubstitutionEnabled=false;view.isAutomaticDashSubstitutionEnabled=false;view.isAutomaticTextReplacementEnabled=false;view.delegate=context.coordinator;view.submit=send;view.setAccessibilityLabel("Message Wixal");scroll.documentView=view
        return scroll
    }
    func updateNSView(_ scroll:NSScrollView,context:Context){
        context.coordinator.parent=self
        guard let view=scroll.documentView as? WixalPromptTextView else{return}
        if view.string != text{view.string=text;view.setSelectedRange(NSRange(location:min(selection.location,(text as NSString).length),length:0))}
        view.font=NSFont.systemFont(ofSize:max(13,textSize+1))
        view.mentionKey=mentionKey
        context.coordinator.measure(view)
        view.textColor=NSColor(theme.text);view.insertionPointColor=NSColor(theme.accent);view.submit=send
    }
}
