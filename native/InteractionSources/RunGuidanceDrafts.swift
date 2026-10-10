import Foundation

/// View recreation must not discard a run's draft or pending acknowledgement.
/// Only text is persisted; a relaunch never resubmits an uncertain request.
public struct RunGuidanceDrafts {
    private var values: [String: AcknowledgedDraft] = [:]
    public init(texts: [String: String] = [:]) {
        for (key, text) in texts {
            var draft = AcknowledgedDraft()
            draft.text = text
            values[key] = draft
        }
    }
    public static func key(owner: String, run: String) -> String {
        // Length-prefix the owner so separators in identifiers cannot collide.
        "\(owner.utf8.count):\(owner)\(run)"
    }
    public subscript(key: String) -> AcknowledgedDraft {
        get { values[key] ?? AcknowledgedDraft() }
        set { values[key] = newValue }
    }
    public var texts: [String: String] {
        values.mapValues(\.text).filter { !$0.value.isEmpty }
    }
}
