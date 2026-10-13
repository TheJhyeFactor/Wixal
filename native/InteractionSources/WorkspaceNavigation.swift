import Foundation

/// Presentation areas are not engine modes. Tools and Cybersecurity never
/// manufacture a session mode or grant execution authority.
public enum WorkspaceArea: String, CaseIterable, Identifiable {
    case chats = "Chats", agents = "Agents", cybersecurity = "Cybersecurity", tools = "Tools"
    public var id: String { rawValue }
    public var route: String { self == .chats ? "Chat" : rawValue }
    public var symbol: String {
        switch self { case .chats: return "bubble.left"; case .agents: return "diamond"
        case .cybersecurity: return "checkmark.shield"; case .tools: return "wrench.and.screwdriver" }
    }
    public static func destination(_ route: String) -> Self? { allCases.first { $0.route == route || $0.rawValue == route } }
}

public enum SidebarPreferences {
    public static func width(_ saved: Double) -> Double { saved.isFinite ? min(320, max(216, saved)) : 248 }
    public static func isCompact(collapsed: Bool, windowWidth: Double) -> Bool { collapsed || windowWidth < 1100 }
    public static func pins(_ stored: String) -> [String] {
        guard let data = stored.data(using: .utf8), let ids = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        var seen = Set<String>()
        return Array(ids.filter { !$0.isEmpty && $0.count <= 200 && seen.insert($0).inserted }.prefix(100))
    }
    public static func encodePins(_ ids: [String]) -> String {
        guard let data = try? JSONEncoder().encode(ids), let value = String(data: data, encoding: .utf8) else { return "[]" }
        return value
    }
}
