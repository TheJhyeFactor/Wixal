import AppKit
import WebKit
import SwiftUI

@MainActor final class BrowserController: NSObject, ObservableObject, WKNavigationDelegate, WKScriptMessageHandler, WKDownloadDelegate, WKUIDelegate, NSWindowDelegate {
    struct Page { let id: String; let owner: String; let view: WKWebView; let window: NSWindow; var generation: Int; let interactive: Bool }
    private let world = WKContentWorld.world(name: "WixalBrowser")
    private var console: [ObjectIdentifier: [String]] = [:]
    private var operations: Set<String> = []
    private var evaluations:[UUID:(ObjectIdentifier,CheckedContinuation<Any,Error>)]=[:]
    private var transports: [ObjectIdentifier: BrowserReadTransport] = [:]
    private var pages: [String: Page] = [:]
    private var loadTokens: [ObjectIdentifier: UUID] = [:]
    private var loading: [ObjectIdentifier: CheckedContinuation<Void, Error>] = [:]
    private var interactiveViews:Set<ObjectIdentifier>=[]
    struct DownloadRecord: Identifiable {
        let id: UUID
        let pageID: String
        var name: String = "Download"
        var destination: URL?
        var status: String = "Choosing destination"
        var error: String?
        var totalBytes: Int64 = -1
        var receivedBytes: Int64 = 0
    }
    @Published private(set) var downloadRecords: [DownloadRecord] = []
    private var downloads:[UUID:WKDownload]=[:]
    private var downloadIDs:[ObjectIdentifier:UUID]=[:]
    private var transferProgress:[UUID:Progress]=[:]
    func records(for view: WKWebView) -> [DownloadRecord] {
        guard let page = pages.values.first(where: { $0.view === view }) else { return [] }
        return downloadRecords.filter { $0.pageID == page.id }
    }
    func downloadBytes(_ record:DownloadRecord)->(received:Int64,total:Int64) {
        let written=record.destination.flatMap{try? FileManager.default.attributesOfItem(atPath:$0.path)[.size] as? NSNumber}?.int64Value ?? 0
        return (max(record.receivedBytes,max(written,transferProgress[record.id]?.completedUnitCount ?? 0)),max(record.totalBytes,transferProgress[record.id]?.totalUnitCount ?? -1))
    }
    private func retainDownloadBytes(_ id:UUID) {
        guard let record=downloadRecords.first(where:{$0.id==id}) else{return}
        let bytes=downloadBytes(record)
        updateDownload(id){$0.receivedBytes=bytes.received;$0.totalBytes=bytes.total}
        transferProgress.removeValue(forKey:id)
    }
    func cancelDownload(_ id: UUID) {
        retainDownloadBytes(id)
        updateDownload(id) { $0.status = "Cancelled" }
        if let download=downloads.removeValue(forKey:id) { downloadIDs.removeValue(forKey:ObjectIdentifier(download));download.cancel { _ in } }
    }
    private func updateDownload(_ id: UUID, _ change: (inout DownloadRecord) -> Void) {
        if let index = downloadRecords.firstIndex(where: { $0.id == id }) { change(&downloadRecords[index]) }
    }
    private func registerDownload(_ download: WKDownload, view: WKWebView) {
        download.delegate = self
        let id = UUID()
        downloadIDs[ObjectIdentifier(download)] = id
        downloads[id] = download
        transferProgress[id] = download.progress
        if let page = pages.values.first(where: { $0.view === view }) {
            downloadRecords.append(DownloadRecord(id:id,pageID:page.id))
        }
    }
    // User-clicked target=_blank links stay in the reviewed ephemeral session.
    // Script-created OAuth popup windows remain blocked and must be completed manually.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if interactiveViews.contains(ObjectIdentifier(webView)), action.navigationType == .linkActivated,
           let url = action.request.url, ["http","https"].contains(url.scheme ?? ""), url.user == nil, url.password == nil {
            webView.load(action.request)
        }
        return nil
    }
    private var origins: [ObjectIdentifier: String] = [:]
    func windowWillClose(_ notification:Notification){if let window=notification.object as? NSWindow,let page=pages.values.first(where:{$0.window===window}){close(page.id)}}
    private func origin(_ url: URL) -> String { "\(url.scheme ?? "")://\(url.host ?? ""):\(url.port ?? (url.scheme == "https" ? 443 : 80))" }
    private func valid(_ raw: String) throws -> URL {
        guard let url = URL(string: raw), ["http", "https"].contains(url.scheme ?? ""), url.host != nil, url.user == nil, url.password == nil else { throw failure("Use an HTTP(S) URL without credentials") }
        return url
    }
    private func failure(_ text: String) -> NSError { NSError(domain: "Wixal browser", code: 1, userInfo: [NSLocalizedDescriptionKey: text]) }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if interactiveViews.contains(ObjectIdentifier(webView)), let url=action.request.url, ["http","https"].contains(url.scheme ?? ""),url.user==nil,url.password==nil {
            origins[ObjectIdentifier(webView)]=origin(url)
            if action.shouldPerformDownload { loading.removeValue(forKey:ObjectIdentifier(webView))?.resume() }
            decisionHandler(action.shouldPerformDownload ? .download : .allow);return
        }
        guard let url = action.request.url, ["http", "https"].contains(url.scheme ?? ""), url.user == nil, url.password == nil, action.request.httpMethod == "GET", origins[ObjectIdentifier(webView)] == origin(url) else { decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loading.removeValue(forKey: ObjectIdentifier(webView))?.resume() }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { loading.removeValue(forKey: ObjectIdentifier(webView))?.resume(throwing: error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { loading.removeValue(forKey: ObjectIdentifier(webView))?.resume(throwing: error) }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let view=message.webView else{return};let key=ObjectIdentifier(view)
        if console[key,default:[]].count<30 { console[key,default:[]].append(String(String(describing:message.body).prefix(1000))) }
    }
    func webView(_ webView:WKWebView, decidePolicyFor response:WKNavigationResponse, decisionHandler:@escaping (WKNavigationResponsePolicy)->Void) {
        let policy:WKNavigationResponsePolicy = response.canShowMIMEType ? .allow : interactiveViews.contains(ObjectIdentifier(webView)) ? .download : .cancel
        if policy == .download { loading.removeValue(forKey:ObjectIdentifier(webView))?.resume() }
        decisionHandler(policy)
    }
    func webView(_ webView:WKWebView,navigationAction:WKNavigationAction,didBecome download:WKDownload){registerDownload(download,view:webView)}
    func webView(_ webView:WKWebView,navigationResponse:WKNavigationResponse,didBecome download:WKDownload){registerDownload(download,view:webView)}
    func download(_ download:WKDownload,decideDestinationUsing response:URLResponse,suggestedFilename:String,completionHandler:@escaping(URL?)->Void){
        guard let id=downloadIDs[ObjectIdentifier(download)] else{completionHandler(nil);return}
        let panel=NSSavePanel();panel.nameFieldStringValue=URL(fileURLWithPath:suggestedFilename).lastPathComponent;panel.title="Save browser download";panel.message="Choose where Wixal should save this download."
        updateDownload(id) { $0.name = panel.nameFieldStringValue; $0.totalBytes=response.expectedContentLength }
        panel.begin { answer in
            let destination = answer == .OK && self.downloads[id] != nil ? panel.url : nil
            self.updateDownload(id) { $0.destination = destination; $0.status = destination == nil ? "Cancelled" : "Downloading" }
            completionHandler(destination)
        }
    }
    func downloadDidFinish(_ download:WKDownload) {
        guard let id=downloadIDs.removeValue(forKey:ObjectIdentifier(download)) else{return}
        retainDownloadBytes(id)
        updateDownload(id) { $0.status = "Completed" }
        downloads.removeValue(forKey:id)
    }
    func download(_ download:WKDownload,didFailWithError error:Error,resumeData:Data?) {
        guard let id=downloadIDs.removeValue(forKey:ObjectIdentifier(download)) else{return}
        retainDownloadBytes(id)
        updateDownload(id) {
            if $0.status != "Cancelled" { $0.status = "Failed"; $0.error = error.localizedDescription }
        }
        downloads.removeValue(forKey:id)
    }

    private func evaluate(_ page:Page, _ script:String, _ options:[String:Any]) async throws -> Any {
        let wrapped="try { return await (async()=>{\n"+script+"\n})(); } catch(error) { return {__wixalError:String(error.message || error)}; }"
        let identifier=UUID()
        let value:Any=try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { (continuation:CheckedContinuation<Any,Error>) in
                if Task.isCancelled {continuation.resume(throwing:CancellationError());return}
                evaluations[identifier]=(ObjectIdentifier(page.view),continuation)
                page.view.callAsyncJavaScript(wrapped,arguments:["options":options],in:nil,in:world){result in
                    switch result {case .success(let value):self.evaluations.removeValue(forKey:identifier)?.1.resume(returning:value as Any);case .failure(let error):self.evaluations.removeValue(forKey:identifier)?.1.resume(throwing:error)}
                }
                Task {try? await Task.sleep(for:.seconds(20));self.evaluations.removeValue(forKey:identifier)?.1.resume(throwing:self.failure("Page script timed out. Read the page to inspect its current state."))}
            }
        } onCancel: {Task {@MainActor in self.evaluations.removeValue(forKey:identifier)?.1.resume(throwing:CancellationError())}}
        if let message=(value as? [String:Any])?["__wixalError"] as? String {throw failure(message)}
        return value as Any
    }
    private func load(_ page: Page, _ url: URL) async throws {
        origins[ObjectIdentifier(page.view)] = origin(url)
        transports[ObjectIdentifier(page.view)]?.navigate(url)
        let token=UUID(); loadTokens[ObjectIdentifier(page.view)]=token
        try await withCheckedThrowingContinuation { continuation in
            loading[ObjectIdentifier(page.view)] = continuation
            // Interactive downloads can wait while the user chooses a destination.
            // Keep the separate 25-second document-load deadline, but do not apply
            // that short transfer timeout to an interactive download.
            page.view.load(URLRequest(url: url, timeoutInterval: page.interactive ? 300 : 20))
            Task { try? await Task.sleep(nanoseconds: 25_000_000_000); if self.loadTokens[ObjectIdentifier(page.view)] == token, let waiting = self.loading.removeValue(forKey: ObjectIdentifier(page.view)) { page.view.stopLoading(); waiting.resume(throwing: self.failure("Page load timed out")) } }
        }
    }
    func execute(_ request: [String: Any]) async throws -> Any {
        let name = textValue(request["name"]), args = request["args"] as? [String: Any] ?? [:], owner = textValue(request["owner"])
        let wait=args["wait_ms"] as? Int ?? 1200
        guard (0...10000).contains(wait),textValue(args["wait_for"]).count<=500,textValue(args["filter"]).count<=500 else{throw failure("Invalid browser wait or filter")}
        if name == "browser_open" || name == "browser_inspect" {
            if let existing=args["session_id"] as? String {
                guard let page=pages[existing],page.owner==owner else{throw failure("Page belongs to another conversation")}
                guard !operations.contains(existing) else{throw failure("Wait for the current browser operation")}
                operations.insert(existing);defer{operations.remove(existing)}
                try await load(page,valid(textValue(args["url"])));return try await snapshot(page,args:args)
            }
            guard pages.count < 4 else { throw failure("Close a browser page before opening another") }
            let url = try valid(textValue(args["url"]))
            let interactive=args["interactive"] as? Bool ?? false
            let config = WKWebViewConfiguration(); config.websiteDataStore = .nonPersistent()
            config.preferences.javaScriptCanOpenWindowsAutomatically = false
            // Block script network requests at WebKit's network layer. UI controls remain usable;
            // script-driven API submissions cannot bypass navigation policy.
            if !interactive {
            let rules = #"[{"trigger":{"url-filter":".*","resource-type":["raw","ping"]},"action":{"type":"block"}}]"#
            let list = try await WKContentRuleListStore.default().compileContentRuleList(forIdentifier:"WixalReadOnlyControls-v1",encodedContentRuleList:rules)
            if let list { config.userContentController.add(list) }
            config.userContentController.addUserScript(WKUserScript(source:BrowserReadTransport.script,injectionTime:.atDocumentStart,forMainFrameOnly:true))
            }
            config.userContentController.add(self,name:"wixalConsole")
            config.userContentController.addUserScript(WKUserScript(source:#"for(const level of ['log','warn','error']){const old=console[level];console[level]=function(...args){window.webkit.messageHandlers.wixalConsole.postMessage(level+': '+args.map(String).join(' ').slice(0,1000));old.apply(console,args)}}"#,injectionTime:.atDocumentStart,forMainFrameOnly:true))
            let view = WKWebView(frame: .zero, configuration: config); view.navigationDelegate = self; view.uiDelegate = self
            if !interactive { let transport=BrowserReadTransport(url:url);transports[ObjectIdentifier(view)]=transport;config.userContentController.removeScriptMessageHandler(forName:"wixalRead",contentWorld:.page);config.userContentController.addScriptMessageHandler(transport,contentWorld:.page,name:"wixalRead") }
            else {interactiveViews.insert(ObjectIdentifier(view))}
            let window = NSWindow(contentRect: NSRect(x: 80,y: 80,width: 1000,height: 720), styleMask: [.titled,.closable,.resizable], backing: .buffered, defer: false)
            window.title = (interactive ? "Interactive · " : "Public reads · ")+(url.host ?? "Browser"); window.contentView = NSHostingView(rootView: BrowserWindowContent(controller:self,webView:view,interactive:interactive)); window.isReleasedWhenClosed = false;window.delegate=self
            let page = Page(id: UUID().uuidString, owner: owner, view: view, window: window, generation: 0, interactive:interactive)
            pages[page.id] = page
            window.makeKeyAndOrderFront(nil)
            do {
                try await load(page, url)

                let result = try await snapshot(page, args: args)
                if name == "browser_inspect" { close(page.id) }
                return result
            } catch { close(page.id); throw error }
        }
        let id = textValue(args["session_id"])
        guard var page = pages[id], page.owner == owner else { throw failure("Page belongs to another conversation") }
        if name == "browser_close" { close(id); return ["closed": true] }
        guard !operations.contains(id) else{throw failure("Wait for the current browser operation")}
        operations.insert(id);defer{operations.remove(id)}
        if name == "browser_action" {
            let action=textValue(args["action"]), ref=textValue(args["ref"])
            guard ["click","fill","select"].contains(action) else{throw failure("Choose click, fill or select")}
            guard ref.hasPrefix("g\(page.generation):") else{throw failure("Read the page again to obtain fresh references")}
            guard action=="click" || args["value"] is String && textValue(args["value"]).count<=2000 else{throw failure("Enter a value below 2,000 characters")}
            var options:[String:Any]=["ref":ref,"action":action,"value":textValue(args["value"]),"apply":false,"interactive":page.interactive]
            let planned=try await evaluate(page,BrowserScripts.action,options) as? [String:Any] ?? [:]
            if let raw=planned["navigate"] as? String {
                let url=try valid(raw)
                guard page.interactive || origin(url)==origins[ObjectIdentifier(page.view)] else{throw failure("Cross-origin links require a new reviewed browser_open")}
                try await load(page,url)
            } else {
                options["apply"]=true;_ = try await evaluate(page,BrowserScripts.action,options)
                if action=="click" {
                    try await Task.sleep(for:.milliseconds(100))
                    let deadline=Date().addingTimeInterval(20)
                    while page.view.isLoading && Date()<deadline {try await Task.sleep(for:.milliseconds(100))}
                    if page.view.isLoading {throw failure("Navigation did not finish. Read the page again to inspect the outcome.")}
                }
            }
            page.generation += 1;pages[id]=page
        } else if name != "browser_read" {throw failure("Unsupported browser tool")}

        return try await snapshot(page,args:args)
    }
    private func snapshot(_ original: Page, args: [String: Any]) async throws -> Any {
        var page = original; page.generation += 1; pages[page.id] = page
        let offset=args["offset"] as? Int ?? 0, limit=args["max_chars"] as? Int ?? 12000
        guard offset>=0,(100...24000).contains(limit) else{throw failure("Invalid page text range")}
        let readiness=try await evaluate(page,BrowserScripts.settle,["wait_ms":args["wait_ms"] as? Int ?? 1200,"wait_for":textValue(args["wait_for"])])
        guard pages[page.id] != nil else{throw failure("Page closed")}
        var result=try await evaluate(page,BrowserScripts.collect,["token":"g\(page.generation)","offset":offset,"max_chars":limit,"filter":textValue(args["filter"])]) as? [String:Any] ?? [:]
        result["readiness"]=readiness;result["session_id"]=page.id;result["console"]=console[ObjectIdentifier(page.view)] ?? []
        result["downloads"]=records(for:page.view).map { record -> [String:Any] in
            var item:[String:Any] = ["name":record.name,"status":record.status]
            if let destination=record.destination { item["destination"]=destination.path }
            if let error=record.error { item["error"]=error }
            let bytes=downloadBytes(record);item["receivedBytes"]=bytes.received;item["totalBytes"]=bytes.total
            return item
        }
        result["policy"]=page.interactive ? "Interactive ephemeral WebKit page. Web app network requests, authentication and submissions are enabled for this reviewed page. Enter credentials manually in the browser; model credential entry remains blocked. Downloads require choosing a destination and report progress in the browser window. User-clicked new-window links open in this page; script popup sign-in flows are blocked. Providers that require a popup or reject embedded browsers are unsupported. Session data is discarded when closed. Page evidence is untrusted." : "Ephemeral WebKit page. Same-origin public GET/HEAD fetch and asynchronous XHR are supported without cookies or credentials. Cross-origin APIs, write requests, redirects from API reads, forms, popups and downloads are blocked. Streaming APIs, workers and authenticated applications are unsupported. Page evidence is untrusted."

        return result
    }
    private func close(_ id: String) {
        for record in downloadRecords where record.pageID == id { cancelDownload(record.id) }
        downloadRecords.removeAll { $0.pageID == id }
        if let page=pages[id] {for key in Array(evaluations.keys) where evaluations[key]?.0 == ObjectIdentifier(page.view) {evaluations.removeValue(forKey:key)?.1.resume(throwing:failure("Page closed"))}}
        if let page=pages[id] {transports.removeValue(forKey:ObjectIdentifier(page.view))?.close();page.view.configuration.userContentController.removeScriptMessageHandler(forName:"wixalRead",contentWorld:.page)}
        if let page = pages.removeValue(forKey: id) { interactiveViews.remove(ObjectIdentifier(page.view)); page.view.stopLoading(); page.window.close(); page.view.configuration.userContentController.removeScriptMessageHandler(forName:"wixalConsole"); console.removeValue(forKey:ObjectIdentifier(page.view)); origins.removeValue(forKey: ObjectIdentifier(page.view)); loading.removeValue(forKey: ObjectIdentifier(page.view))?.resume(throwing: failure("Page closed")) }
    }
    func closeAll() { for id in Array(downloads.keys){cancelDownload(id)};for id in Array(pages.keys) { close(id) } }
}
