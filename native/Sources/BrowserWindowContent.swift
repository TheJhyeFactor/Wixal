import AppKit
import SwiftUI
import WebKit


private struct BrowserWebContent: NSViewRepresentable {
    let view: WKWebView
    func makeNSView(context: Context) -> WKWebView { view }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
}

struct BrowserWindowContent: View {
    @ObservedObject var controller: BrowserController
    let webView: WKWebView
    let interactive: Bool
    var body: some View {
        VStack(spacing:0) {
            VStack(alignment:.leading,spacing:5) {
                Text(interactive ? "Interactive browser · manual sign-in" : "Public read browser").font(.headline)
                Text(interactive ? "Enter credentials yourself. Closing this window discards the session and cancels active downloads. New-window links stay here; providers requiring script popups or a system browser are unsupported." : "Public page reads only. Sign-in, submissions and downloads require a reviewed interactive page.").font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth:.infinity,alignment:.leading).padding(10)
            Divider()
            BrowserWebContent(view:webView)
            if !controller.records(for:webView).isEmpty {
                Divider()
                ScrollView {
                    VStack(alignment:.leading,spacing:10) {
                        ForEach(controller.records(for:webView)) { record in
                            VStack(alignment:.leading,spacing:4) {
                                HStack {
                                    Text(record.name).lineLimit(1); Spacer(); Text(record.status)
                                    if record.status == "Downloading" || record.status == "Choosing destination" {
                                        Button("Cancel") { controller.cancelDownload(record.id) }.accessibilityLabel("Cancel download \(record.name)")
                                    }
                                    if record.status == "Completed",let destination = record.destination {
                                        Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([destination]) }
                                    }
                                }
                                if let destination = record.destination { Text(destination.path).textSelection(.enabled).foregroundStyle(.secondary) }
                                if let error = record.error { Text(error).foregroundStyle(.red).textSelection(.enabled) }
                                if record.status == "Downloading" {
                                    TimelineView(.periodic(from:.now,by:0.5)) { _ in
                                        let bytes = controller.downloadBytes(record)
                                        if bytes.total > 0 {
                                            ProgressView(value:min(1,Double(bytes.received)/Double(bytes.total)))
                                            Text("\(ByteCountFormatter.string(fromByteCount:bytes.received,countStyle:.file)) of \(ByteCountFormatter.string(fromByteCount:bytes.total,countStyle:.file))").foregroundStyle(.secondary)
                                        } else { Text("Downloading · size not supplied by server").foregroundStyle(.secondary) }
                                    }
                                }
                            }.font(.caption)
                        }
                    }.padding(10)
                }.frame(maxHeight:160)
            }
        }.frame(minWidth:400,minHeight:300)
    }
}
