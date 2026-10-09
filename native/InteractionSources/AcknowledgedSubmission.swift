import Foundation

/// Tracks one outstanding request. An obsolete reply cannot settle a newer request.
public struct AcknowledgedSubmission {
    public private(set) var isSubmitting = false
    public private(set) var error = ""
    private var requestID: UUID?
    public init() {}

    public mutating func begin() -> UUID? {
        guard !isSubmitting else { return nil }
        let id = UUID()
        requestID = id
        isSubmitting = true
        error = ""
        return id
    }

    @discardableResult
    public mutating func finish(_ id: UUID, error: String? = nil) -> Bool {
        guard requestID == id else { return false }
        requestID = nil
        isSubmitting = false
        self.error = error ?? ""
        return true
    }
}

/// Retains text through rejection and through edits made while an acknowledgement is pending.
public struct AcknowledgedDraft {
    public var text = "" { didSet { if text != oldValue { revision += 1 } } }
    public private(set) var submission = AcknowledgedSubmission()
    private var revision = 0
    private var submittedRevision: Int?
    public init() {}

    public mutating func begin() -> (id: UUID, text: String)? {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let id = submission.begin() else { return nil }
        submittedRevision = revision
        return (id, text)
    }

    public mutating func finish(_ id: UUID, error: String? = nil) {
        guard submission.finish(id, error: error) else { return }
        if error == nil && submittedRevision == revision { text = "" }
        submittedRevision = nil
    }
}
