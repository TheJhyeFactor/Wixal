import Foundation

/// Stable identifiers are persisted by the engine; display names belong to the UI.
struct WixalPalette {
    let name: String
    let light: Bool
    let background, sidebar, panel, raised, inset, line, text, muted, accent, secondary: UInt32
    var id: String { name.lowercased() }
    var icon: String { id }

    static let all: [Self] = [
        .init(name:"Pearl", light:true,
              background:0xFAFAF8, sidebar:0xF0F0EE, panel:0xFFFFFF, raised:0xFFFFFF,
              inset:0xEAECEA, line:0xD5D7D8, text:0x25272B, muted:0x646870, accent:0x4D61BA, secondary:0x70838B),
        .init(name:"Cloud", light:true,
              background:0xF1F5FA, sidebar:0xE5ECF5, panel:0xFFFFFF, raised:0xFFFFFF,
              inset:0xDFE7F1, line:0xCCD7E5, text:0x233247, muted:0x56667B, accent:0x2669BD, secondary:0x577C8D),
        .init(name:"Paper", light:true,
              background:0xF3F2EF, sidebar:0xEBE9E4, panel:0xFAF9F6, raised:0xFFFEFA,
              inset:0xEAE7E0, line:0xDCD9D2, text:0x2F2D2A, muted:0x696259, accent:0x70543B, secondary:0x6B7457),
        .init(name:"Dune", light:true,
              background:0xEAE1D3, sidebar:0xE0D4C3, panel:0xF6EFE5, raised:0xFFF9F1,
              inset:0xDACEBB, line:0xC9BBA8, text:0x382F28, muted:0x635344, accent:0x874625, secondary:0x66684D),
        .init(name:"Graphite", light:false,
              background:0x24262A, sidebar:0x292C31, panel:0x2E3136, raised:0x383C43,
              inset:0x1C1E22, line:0x484C54, text:0xEEEFF1, muted:0xB0B4BC, accent:0xBAC5D9, secondary:0xA9B9B0),
        .init(name:"Sakura", light:false,
              background:0x17181B, sidebar:0x1B1C20, panel:0x1D1E22, raised:0x232428,
              inset:0x111215, line:0x303136, text:0xE8E7E5, muted:0xA6A5AE, accent:0xE9A5BD, secondary:0xBAADD8),
        .init(name:"Forest", light:false,
              background:0x151C18, sidebar:0x19231D, panel:0x1E2822, raised:0x29362D,
              inset:0x101612, line:0x34473B, text:0xE5EDE7, muted:0xA5B7AA, accent:0xA6D9B8, secondary:0xD1B789),
        .init(name:"Midnight", light:false,
              background:0x141822, sidebar:0x181E2B, panel:0x1D2432, raised:0x293247,
              inset:0x0E121B, line:0x35415B, text:0xE7ECF6, muted:0xA5B0C7, accent:0xA8BBEF, secondary:0xC2AFE6),
        .init(name:"Aurora", light:false,
              background:0x101A1D, sidebar:0x142126, panel:0x19272C, raised:0x23363D,
              inset:0x0B1316, line:0x304A53, text:0xE2F0F0, muted:0x9FB8BE, accent:0x76DCCB, secondary:0xB8A0EF),
        .init(name:"Obsidian", light:false,
              background:0x0B0C0E, sidebar:0x101215, panel:0x15171A, raised:0x202329,
              inset:0x060709, line:0x30343B, text:0xF1F2F4, muted:0xA6ACB7, accent:0xE8B47A, secondary:0x9AAAC2)
    ]

    static func resolve(_ name: String) -> Self {
        all.first { $0.id == name.lowercased() } ?? all.first { $0.id == "sakura" }!
    }
    static let iconVariants = all.map(\.icon) + ["copper"]
}
