import Foundation
import SwiftUI
// Use the property-wrapper type explicitly; SDK 27 also exports a State macro.
typealias ViewState<Value> = SwiftUI.State<Value>
import AppKit
import OSLog

func textValue(_ value: Any?) -> String { value as? String ?? "" }
func records(_ value: Any?) -> [[String: Any]] { value as? [[String: Any]] ?? [] }
func pretty(_ value: Any) -> String {
    guard JSONSerialization.isValidJSONObject(value), let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]), let string = String(data: data, encoding: .utf8) else { return String(describing: value) }
    return string
}
struct Review: Identifiable { let id: String; let details: [String: Any] }

@MainActor final class EngineClient: ObservableObject {
    @Published var state: [String: Any] = [:]
    @Published var tools: [[String: Any]] = []
    @Published var models: [[String: Any]] = []
    @Published var imports: [[String: Any]] = []
    @Published var review: Review?
    @Published var busy = false
    @Published var connected = false
    @Published var streaming = ""
    @Published var thinking = ""
    @Published var runStarted:Date?
    @Published var activity = "Starting Python engine…"
    @Published var error = ""
    @Published var commandOutput = ""
    @Published var currentTool:[String:Any]=[:]
    @Published var modelStatus:[String:Any]=[:]
    @Published var assessmentProgress:[String:Any]=[:]
    @Published var contextInfo:[String:Any]=[:]
    @Published var memoryStatus:[String:Any]=[:]
    private var memoryRefresh:Task<Void,Never>?
    @Published var operationRunning = false
    private var contextRefresh: Task<Void, Never>?
    private var contextRevision = 0
    var selectedSkill = "" { didSet { refreshContext() } }
    let terminalSession=TerminalSession()
    let browser = BrowserController()
    private var process: Process?
    private let startupLogger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "app.wixal.native", category: "EngineStartup")
    private let activityLogger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "app.wixal.native", category: "ChatActivity")
    func logUIEvent(_ event:String) {
        activityLogger.info("Chat interaction: \(event, privacy:.public)")
        guard connected else{return}
        Task { _ = try? await call("diagnostic-ui-event",["event":event]) }
    }
    private var startupDeadline: Task<Void, Never>?
    private var startupTimedOut = false
    private var input: FileHandle?
    private var pending: [String: CheckedContinuation<Any, Error>] = [:]
    private var smokeStarted = false
    private var generation = UUID()
    private var deadlines: [String: Task<Void, Never>] = [:]
    private var heartbeat: Task<Void, Never>?
    @Published var restarting = false
    @Published var projectCandidate:String?
    var activeMemory: String {
        let account = state["account"] as? [String: Any] ?? [:]
        return account["signedIn"] as? Bool == true ? textValue(account["globalMemory"]) : textValue(state["globalMemory"])
    }
    var supportsTools: Bool { (models.first { textValue($0["name"]) == textValue(state["model"]) }?["capabilities"] as? [String] ?? []).contains("tools") }
    var supportsImages:Bool {(models.first{textValue($0["name"])==textValue(state["model"])}?["capabilities"] as? [String] ?? []).contains("vision")}
    var modelCapabilitiesKnown:Bool {models.contains{textValue($0["name"])==textValue(state["model"])}}
    private var queuedReviews: [Review] = []
    private var hostRequests:[String:Task<Void,Never>]=[:]
    private var flushTask: Task<Void, Never>?
    private var tokenBuffer = ""
    private var thinkingBuffer = ""
    var project: [String: Any]? { records(state["projects"]).first { textValue($0["id"]) == textValue(state["activeProject"]) } }
    var session: [String: Any]? { records(state["sessions"]).first { textValue($0["id"]) == textValue(state["activeSession"]) } }
    var messages: [[String: Any]] { records(session?["messages"]) }
    var sessions: [[String: Any]] { records(state["sessions"]).filter { textValue($0["projectId"]) == textValue(state["activeProject"]) } }
    var root: String { textValue(project?["root"]) }
    var startupFailed: Bool { activity == "Engine failed to start" || activity == "Engine startup timed out" || activity.hasPrefix("Engine stopped (") }

    func start() {
        guard process == nil else { return }
        StartupEvidence.record("engine-start")
        generation = UUID(); let currentGeneration = generation
        startupTimedOut = false
        let child = Process(), stdinPipe = Pipe(), stdoutPipe = Pipe(), stderrPipe = Pipe()
        let bundle = Bundle.main.resourceURL!
        let packaged = bundle.appendingPathComponent("engine/wixal-engine")
        var arguments: [String] = []
        if FileManager.default.isExecutableFile(atPath: packaged.path) {
            child.executableURL = packaged
            arguments = ["--runtime", bundle.appendingPathComponent("ollama").path]
        } else {
            let directory = ProcessInfo.processInfo.environment["WIXAL_NATIVE_ROOT"] ?? FileManager.default.currentDirectoryPath
            child.executableURL = URL(fileURLWithPath: ProcessInfo.processInfo.environment["WIXAL_NATIVE_PYTHON"] ?? "/opt/homebrew/bin/python3")
            arguments = [directory + "/engine/engine_main.py", "--runtime", URL(fileURLWithPath: directory).deletingLastPathComponent().appendingPathComponent("runtime/ollama").path]
        }
        if let data = ProcessInfo.processInfo.environment["WIXAL_NATIVE_DATA"] ?? Bundle.main.object(forInfoDictionaryKey:"WixalPreviewData") as? String { arguments += ["--data", data] }
        if let endpoint = ProcessInfo.processInfo.environment["WIXAL_NATIVE_ENDPOINT"] ?? Bundle.main.object(forInfoDictionaryKey:"WixalPreviewEndpoint") as? String { arguments += ["--endpoint", endpoint] }
        child.arguments = arguments
        child.standardInput = stdinPipe; child.standardOutput = stdoutPipe; child.standardError = stderrPipe
        input = stdinPipe.fileHandleForWriting
        child.terminationHandler = { [weak self] child in Task { @MainActor in
            guard let self, self.generation == currentGeneration else { return }
            self.startupDeadline?.cancel(); self.startupDeadline = nil
            self.process = nil; self.input = nil; self.heartbeat?.cancel()
            self.busy = false; self.operationRunning=false; self.review = nil; self.queuedReviews = []; self.streaming = ""
            self.hostRequests.values.forEach{$0.cancel()};self.hostRequests.removeAll();self.browser.closeAll()
            self.connected = false
            self.activity = self.startupTimedOut ? "Engine startup timed out" : "Engine stopped (\(child.terminationStatus))"
            self.failPending("The Python engine stopped")
        } }
        do {
            try child.run(); process = child
            StartupEvidence.record("engine-launched")
            // Start pipe readers after launch so Foundation cannot consume an unopened pipe.
            // One dedicated reader preserves JSON event order without blocking AppKit.
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                var buffer = Data()
                while true {
                    let chunk = stdoutPipe.fileHandleForReading.availableData
                    if chunk.isEmpty { break }
                    buffer.append(chunk)
                    while let newline = buffer.firstIndex(of: 10) {
                        let line = buffer.prefix(upTo: newline); buffer.removeSubrange(...newline)
                        if let object = try? JSONSerialization.jsonObject(with: line) as? [String: Any] {
                            Task { @MainActor in guard self?.generation == currentGeneration else { return }; self?.receive(object) }
                        }
                    }
                }
            }
            stderrPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
                let data = handle.availableData
                if !data.isEmpty, let message = String(data: data, encoding: .utf8) {
                    Task { @MainActor in guard self?.generation == currentGeneration else { return }; self?.error = String(message.suffix(3000)) }
                }
            }
            let startupBegan = ContinuousClock.now
            startupLogger.info("Workspace engine process launched")
            startupDeadline = Task { [weak self] in
                do { try await Task.sleep(for: .seconds(30)) } catch { return }
                guard let self, self.generation == currentGeneration, !self.connected else { return }
                self.startupTimedOut = true
                self.startupLogger.error("Workspace engine did not answer its startup handshake within 30 seconds")
                self.error = "Wixal could not open this workspace within 30 seconds. No new action was started. Check that the disk is available, then restart the engine."
                self.activity = "Engine startup timed out"
                if child.isRunning { child.terminate() }
            }
            Task { [self] in
                do {
                    let result = try await call("hello") as? [String: Any] ?? [:]
                    state = result["state"] as? [String: Any] ?? [:]
                    tools = records(result["tools"])
                    guard generation == currentGeneration else { return }
                    startupDeadline?.cancel(); startupDeadline = nil
                    let elapsed = ContinuousClock.now - startupBegan
                    startupLogger.info("Workspace engine startup handshake completed in \(elapsed.components.seconds) seconds")
                    StartupEvidence.record("engine-ready")
                    connected = true; activity = "Python engine ready"; restarting = false
                    heartbeat?.cancel()
                    heartbeat = Task { [weak self] in
                        while !Task.isCancelled {
                            do { try await Task.sleep(for: .seconds(15)); guard let self, self.generation == currentGeneration else { return }; _ = try await self.call("ping", timeout: 8) }
                            catch { guard !Task.isCancelled, let self, self.generation == currentGeneration else { return }; self.connected = false; self.busy = false; self.operationRunning=false;self.hostRequests.values.forEach{$0.cancel()};self.hostRequests.removeAll();self.browser.closeAll(); self.error = "The engine is not responding. Restart it to reconnect. Uncertain actions will not be replayed."; self.failPending(self.error); return }
                        }
                    }
                    if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] == nil {loadModels()}
                    if ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE"] != nil && !smokeStarted { smokeStarted=true; await smoke() }
                } catch {
                    guard generation == currentGeneration else { return }
                    startupDeadline?.cancel(); startupDeadline = nil
                    if startupTimedOut {
                        self.activity = "Engine startup timed out"
                        self.error = "Wixal could not open this workspace within 30 seconds. No new action was started. Check that the disk is available, then restart the engine."
                        return
                    }
                    if !self.connected {
                        self.startupLogger.error("Workspace engine startup failed before handshake")
                        self.activity = "Engine failed to start"
                    }
                    self.error = error.localizedDescription
                }
            }
        } catch { self.error = error.localizedDescription; activity = "Engine failed to start" }
    }
    func failPending(_ message: String) {
        deadlines.values.forEach { $0.cancel() }; deadlines.removeAll()
        let calls = pending; pending.removeAll()
        calls.values.forEach { $0.resume(throwing: NSError(domain: "Wixal", code: 1, userInfo: [NSLocalizedDescriptionKey: message])) }
    }
    func restart() {
        guard !restarting else { return }
        restarting = true; connected = false; busy = false; operationRunning=false; contextInfo=[:]; error = ""; activity = "Restarting engine…"
        startupDeadline?.cancel(); startupDeadline = nil
        heartbeat?.cancel(); failPending("Engine restarted. Inspect interrupted actions before continuing.")
        review = nil; queuedReviews = []; browser.closeAll(); flushTokens(); streaming = ""
        hostRequests.values.forEach{$0.cancel()};hostRequests.removeAll()
        let old = process
        generation = UUID(); process = nil
        try? input?.close(); input = nil
        Task {
            if let old, old.isRunning {
                old.terminate()
                for _ in 0..<30 { if !old.isRunning { break }; try? await Task.sleep(for: .milliseconds(100)) }
                if old.isRunning { kill(old.processIdentifier, SIGKILL) }
                for _ in 0..<30 { if !old.isRunning { break }; try? await Task.sleep(for: .milliseconds(100)) }
                guard !old.isRunning else { restarting = false; error = "The previous engine could not be stopped. Quit and reopen Wixal."; return }
            }
            restarting = false; start()
        }
    }
    func call(_ method: String, _ params: [String: Any] = [:], timeout: Double? = nil) async throws -> Any {
        guard let input, process?.isRunning == true, connected || method == "hello" else { throw NSError(domain: "Wixal", code: 2, userInfo: [NSLocalizedDescriptionKey: "Engine disconnected. Use Restart engine to reconnect."]) }
        let id = UUID().uuidString
        let data = try JSONSerialization.data(withJSONObject: ["id": id, "method": method, "params": params]) + Data([10])
        return try await withCheckedThrowingContinuation { continuation in
            pending[id] = continuation
            let limits:[String:Double] = ["community-report-prepare":165,"skill-evaluate":7215,"workflow-merge":315,"agent-verify":615,"agent-resume":1815,"agent-schedule-run":3615,"agent-run":1815,"workflow-run":3615,"workflow-resume":3615,"mcp-connect":315,"memory-recall":105,"memory-index":105,"memory-review":135,"chat":615,"task-start":615,"assessment-run":615,"tool":615,"session-handoff":125,"model-import":1815,"model-pull":1815,"legacy-import":195,"models":135,"model-status":135]
            let seconds = timeout ?? limits[method,default:75]
            deadlines[id] = Task { [weak self] in
                do { try await Task.sleep(for: .seconds(seconds)) } catch { return }
                guard let self, self.pending[id] != nil else { return }
                self.deadlines.removeValue(forKey: id)
                if method != "ping" && method != "hello" && method != "cancel-request" {
                    do { _ = try await self.call("cancel-request", ["id":id], timeout:10) }
                    catch {
                        self.connected=false;self.operationRunning=false;self.busy=false
                        self.error="The engine did not acknowledge cancellation. Restart it before further work; inspect interrupted actions before retrying."
                        self.failPending(self.error);return
                    }
                }
                self.pending.removeValue(forKey:id)?.resume(throwing:NSError(domain:"Wixal",code:3,userInfo:[NSLocalizedDescriptionKey:"Request timed out. Cancellation was requested; inspect interrupted actions before retrying."]))
            }
            do { try input.write(contentsOf: data) }
            catch { deadlines.removeValue(forKey: id)?.cancel(); pending.removeValue(forKey: id); continuation.resume(throwing: error) }
        }
    }
    func receive(_ message: [String: Any]) {
        let event = textValue(message["event"]), data = message["data"] as? [String: Any] ?? [:]
        switch event {
        case "startup-progress":
            let phase=textValue(data["phase"]),database=textValue(data["database"]),pid=data["pid"] as? Int ?? 0
            startupLogger.info("Workspace startup phase: \(phase, privacy:.public); database: \(database, privacy:.public); helper PID: \(pid, privacy:.public)")
        case "response":
            deadlines.removeValue(forKey: textValue(data["id"]))?.cancel()
            if let continuation = pending.removeValue(forKey: textValue(data["id"])) {
                if let error = data["error"] as? String { continuation.resume(throwing: NSError(domain: "Wixal", code: 1, userInfo: [NSLocalizedDescriptionKey: error])) }
                else { continuation.resume(returning: data["result"] ?? NSNull()) }
            }
        case "state":
            let oldCount=messages.count,oldSession=textValue(state["activeSession"])
            state = data
            if messages.count != oldCount || textValue(state["activeSession"]) != oldSession {
                activityLogger.info("Conversation snapshot applied; messages: \(oldCount) -> \(self.messages.count); session changed: \(textValue(self.state["activeSession"]) != oldSession)")
            }
            busy = operationRunning || records(data["workflowRuns"]).contains { ["running", "waiting_review"].contains(textValue($0["status"])) } || records(data["tasks"]).contains { ["running", "waiting_review"].contains(textValue($0["status"])) }
            if messages.count != oldCount || textValue(state["activeSession"]) != oldSession || !busy {flushTokens();streaming="";thinking=""}
            refreshContext()
            refreshMemory()
        case "catalog": tools = records(message["data"]);refreshContext()
        case "operation":
            operationRunning=data["running"] as? Bool ?? false
            busy=operationRunning || records(state["tasks"]).contains { ["running", "waiting_review"].contains(textValue($0["status"])) }
        case "assistant-start": streaming = ""; thinking = ""; tokenBuffer = ""; thinkingBuffer = "";currentTool=[:];activity = "Generating reply…";if runStarted == nil{runStarted=Date()}
        case "thinking":
            thinkingBuffer += textValue(data["text"])
            if flushTask == nil { flushTask = Task { try? await Task.sleep(nanoseconds: 60_000_000); self.flushTokens() } }
        case "token":
            tokenBuffer += textValue(data["text"])
            if flushTask == nil { flushTask = Task { try? await Task.sleep(nanoseconds: 60_000_000); self.flushTokens() } }
        case "review":
            let item = Review(id: textValue(data["id"]), details: data)
            if review == nil { review = item } else { queuedReviews.append(item) }
            activity = "Waiting for review"
        case "request-closed":
            let id = textValue(data["id"])
            hostRequests.removeValue(forKey:id)?.cancel()
            queuedReviews.removeAll { $0.id == id }
            if review?.id == id { review = queuedReviews.isEmpty ? nil : queuedReviews.removeFirst() }
        case "host":
            let id=textValue(data["id"])
            hostRequests[id]=Task {
                let params = data["params"] as? [String: Any] ?? [:]
                let result: Any
                do {
                    if textValue(data["method"]) == "open-external" {
                        guard let url=URL(string:textValue(params["url"])),url.scheme=="https" else { throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"Authorisation requires an HTTPS URL"]) }
                        result=NSWorkspace.shared.open(url)
                    } else { result = try await browser.execute(params) }
                }
                catch { result = ["error": error.localizedDescription] }
                guard !Task.isCancelled else{return}
                _ = try? await call("respond", ["id": id, "value": result])
            }
        case "tool-start": currentTool=data;activity = "Running \(textValue(data["name"]))…"
        case "tool-result": currentTool=[:];activity = "\(textValue(data["name"])): \(textValue(data["status"]))"
        case "command-output": commandOutput += textValue(data["text"]); commandOutput = String(commandOutput.suffix(100_000))
        case "runtime": activity = "Local models: \(textValue(data["status"]))"
        case "activity":activity=textValue(data["text"]).isEmpty ? textValue(data["message"]) : textValue(data["text"])
        case "model-manager":modelStatus=data;models=records(data["installed"]);refreshContext()
        case "assessment-progress":
            if let taskId=data["taskId"] as? String,taskId != textValue(assessmentProgress["taskId"]) { assessmentProgress=[:] }
            assessmentProgress.merge(data) { _, new in new }
        case "security-progress":
            var runs=records(state["securityRuns"])
            if let index=runs.firstIndex(where:{textValue($0["id"]) == textValue(data["id"])}) {
                runs[index]["output"]=data["output"]
                runs[index]["cases"]=data["cases"]
                state["securityRuns"]=runs
            }
        case "assessment-case":
            assessmentProgress.merge(data) { _, new in new }
            assessmentProgress["state"] = "running"
            assessmentProgress["output"] = String((textValue(assessmentProgress["output"]) + "\n" + pretty(data)).suffix(24000))
        case "error": error = textValue(data["message"])
        default: break
        }
    }
    func flushTokens() { streaming += tokenBuffer; thinking += thinkingBuffer; tokenBuffer = ""; thinkingBuffer = ""; flushTask?.cancel(); flushTask = nil }
    func action(_ method: String, _ params: [String: Any] = [:]) {
        Task { defer { if method == "assessment-run" { busy=false } }; do { _ = try await call(method, params) } catch { self.error = error.localizedDescription } }
    }
    func cancelAssessment() {
        guard busy, !assessmentProgress.isEmpty else { return }
        assessmentProgress["state"] = "stopping"
        Task {
            do {
                let stopped = try await call("assessment-cancel") as? Bool ?? false
                if !stopped, busy {
                    assessmentProgress["state"] = "running"
                    error = "No active assessment was available to stop. Check the engine status before continuing."
                }
            } catch {
                if busy { assessmentProgress["state"] = "running" }
                self.error = "Could not confirm assessment cancellation: \(error.localizedDescription)"
            }
        }
    }
    func chat(_ text: String, resume: String? = nil, skill: String? = nil, attachments:[[String:Any]] = [],completion:((Bool)->Void)? = nil) {
        guard !busy else { return }
        busy = true; error = ""; streaming = ""; thinking = ""; runStarted=Date()
        Task {
            defer { flushTokens(); busy = false; streaming = ""; thinking = ""; activity = "Python engine ready" }
            do {
                var params: [String: Any] = ["text": text]
                params["attachments"]=attachments
                if let resume { params["resume"] = resume }
                if let skill, !skill.isEmpty { params["skill"] = skill }
                _ = try await call("chat", params)
                completion?(true)
            } catch { self.error = error.localizedDescription;completion?(false) }
        }
    }
    func respond(_ allowed: Bool) {
        guard let review else { return }
        action("respond", ["id": review.id, "value": allowed])
        self.review = queuedReviews.isEmpty ? nil : queuedReviews.removeFirst()
    }
    func loadModels() {
        Task { do {
            models = records(try await call("models")); imports = records(try await call("model-imports"));modelStatus=try await call("model-status") as? [String:Any] ?? [:]
        } catch { self.error = error.localizedDescription } }
    }
    func openMemorySource(_ identifier:String) {
        guard let session=records(state["sessions"]).first(where:{textValue($0["id"])==identifier}) else {error="The source conversation is unavailable.";return}
        Task {do {if textValue(state["activeProject"]) != textValue(session["projectId"]){_=try await call("project-select",["id":session["projectId"] ?? NSNull()])};_=try await call("session-select",["id":identifier]);NotificationCenter.default.post(name:.wixalNavigate,object:"Chat")}catch{self.error=error.localizedDescription}}
    }
    func pickProject() {
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.prompt = "Choose folder";panel.canCreateDirectories=true
        if panel.runModal() == .OK, let url = panel.url { projectCandidate=url.path }
    }
    func importSkill() {
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.plainText]; panel.prompt = "Import skill"
        if panel.runModal() == .OK, let url = panel.url { action("skill-add", ["path": url.path]) }
    }
    func stop() { browser.closeAll(); action("stop") }
    func close() { heartbeat?.cancel(); failPending("Wixal closed"); terminalSession.close();browser.closeAll(); try? input?.close(); input = nil }
    var contextTokens:Int {contextInfo["estimatedTokens"] as? Int ?? 0}
    var contextAvailable:Bool {contextInfo["estimatedTokens"] != nil && textValue(contextInfo["sessionId"]) == textValue(state["activeSession"])}
    func refreshContext() {
        contextRevision += 1;let revision=contextRevision
        contextRefresh?.cancel()
        if textValue(contextInfo["sessionId"]) != textValue(state["activeSession"]) {contextInfo=[:]}
        guard connected else{return}
        contextRefresh=Task {
            do {
                try await Task.sleep(for:.milliseconds(200))
                let result=try await call("context-info",["skill":selectedSkill]) as? [String:Any] ?? [:]
                guard !Task.isCancelled,revision==contextRevision else{return}
                contextInfo=result
            } catch {if !Task.isCancelled,revision==contextRevision {contextInfo=[:]}}
        }
    }

    func refreshMemory() {
        memoryRefresh?.cancel()
        let current=generation
        memoryRefresh=Task { @MainActor in
            try? await Task.sleep(for:.milliseconds(100))
            guard !Task.isCancelled,connected else{return}
            do { let value=try await call("memory-status") as? [String:Any] ?? [:];guard current==generation,!Task.isCancelled else{return};memoryStatus=value }
            catch { if !Task.isCancelled { self.error=error.localizedDescription } }
        }
    }
    var modelReady:Bool{["ready","external"].contains(textValue((modelStatus["runtime"] as? [String:Any])?["status"])) && models.contains{textValue($0["name"]) == textValue(state["model"])}}
    var modelConnectionLabel:String{!connected ? "Engine disconnected" : textValue(state["model"]).isEmpty ? "Choose a local model" : modelReady ? "Wixal Local connected" : (modelStatus.isEmpty ? "Checking Wixal Local" : "Wixal Local needs attention")}
    private func smoke() async {
        // Isolated QA only; run with a fixture endpoint and a disposable workspace.
        guard let root = ProcessInfo.processInfo.environment["WIXAL_NATIVE_SMOKE_ROOT"], ProcessInfo.processInfo.environment["WIXAL_NATIVE_ENDPOINT"] != nil else { return }
        do {
            _ = try await call("project-add", ["root": root])
            _ = try await call("settings", ["model": "fixture", "approvalMode": "bypass", "ui": ["theme": "paper"]])
            models = records(try await call("models"))
            _ = try await call("chat", ["text": "Write the smoke file with the tool then report the result."])
            let result = try await call("tool", ["name": "run_command", "arguments": ["command": "printf native-command-ok"]])
            let originalSession=textValue(state["activeSession"])
            let firstTerminal=terminalSession.terminal(root:root)
            let otherTerminal=terminalSession.terminal(root:FileManager.default.temporaryDirectory.path)
            guard firstTerminal !== otherTerminal,terminalSession.terminal(root:root) === firstTerminal else{throw NSError(domain:"Smoke",code:1,userInfo:[NSLocalizedDescriptionKey:"Per-project terminal was replaced"])}
            guard let stopped=process else{throw NSError(domain:"Smoke",code:1)}
            kill(stopped.processIdentifier,SIGSTOP)
            var timedOut=false
            do{_ = try await call("ping",timeout:0.25)}catch{timedOut=true}
            kill(stopped.processIdentifier,SIGCONT)
            guard timedOut else{throw NSError(domain:"Smoke",code:2,userInfo:[NSLocalizedDescriptionKey:"Stalled engine did not time out"])}
            restart()
            for _ in 0..<200 {if connected{break};try await Task.sleep(for:.milliseconds(100))}
            guard connected,textValue(state["activeSession"])==originalSession else{throw NSError(domain:"Smoke",code:3,userInfo:[NSLocalizedDescriptionKey:"Engine restart did not restore state"])}
            process?.terminate()
            for _ in 0..<100 {if process==nil{break};try await Task.sleep(for:.milliseconds(100))}
            guard !connected,process==nil else{throw NSError(domain:"Smoke",code:4,userInfo:[NSLocalizedDescriptionKey:"Engine termination did not clear connection"])}
            var rejected=false
            do{_ = try await call("ping")}catch{rejected=true}
            guard rejected else{throw NSError(domain:"Smoke",code:5)}
            start()
            for _ in 0..<200 {if connected{break};try await Task.sleep(for:.milliseconds(100))}
            guard connected else{throw NSError(domain:"Smoke",code:6)}
            let report: [String: Any] = ["pid":ProcessInfo.processInfo.processIdentifier,"state": state, "command": result, "windowCount": NSApp.windows.count, "models": models,"recovery":"stalled timeout / explicit restart / persisted session / terminated helper / disconnected guard / reconnect passed","terminalRetention":"two project terminals retained by identity"]
            try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted]).write(to: URL(fileURLWithPath: root+"/native-smoke.json"))
            activity = "Native smoke completed"
        } catch { self.error = error.localizedDescription; try? error.localizedDescription.write(toFile: root+"/native-smoke-error.txt", atomically: true, encoding: .utf8) }
    }
}
