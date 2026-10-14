import Foundation

/// Displays controller-recorded facts; never derives them from assistant prose.
public struct NetworkEvidenceSummary: Equatable {
    public let stage: String
    public let state: String
    public let sessionID: String
    public let sourceID: String
    public let requestedCount: Int?
    public let examinedCount: Int?
    public let endpoints: [String]
    public let omittedEndpoints: Int
    public let limitation: String

    public static func decode(_ content: String) -> [NetworkEvidenceSummary] {
        guard let data=content.data(using:.utf8),
              let value=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else{return []}
        let reports=(value["evidenceReport"] as? [[String:Any]]) ?? (value["evidenceReport"] as? [String:Any]).map{[$0]} ?? []
        return reports.compactMap { row in
            guard let stage=row["stage"] as? String, ["discovery","inspection"].contains(stage) else{return nil}
            let endpoints=row["observedEndpoints"] as? [[String:Any]] ?? []
            return NetworkEvidenceSummary(stage:stage,state:row["skipped"] as? Bool == true ? "skipped" : row["state"] as? String ?? "unknown",
                sessionID:row["sessionId"] as? String ?? "",sourceID:row["sourceSessionId"] as? String ?? "",
                requestedCount:row["requestedPortCount"] as? Int,examinedCount:row["examinedPortCount"] as? Int,
                endpoints:endpoints.prefix(24).compactMap { endpoint in
                    guard let host=endpoint["host"] as? String,let port=endpoint["port"] as? Int,let state=endpoint["state"] as? String else{return nil}
                    return "\(host):\(port) — \(state)"
                },omittedEndpoints:max(0,endpoints.count-24),limitation:row["limitation"] as? String ?? "")
        }
    }
}
