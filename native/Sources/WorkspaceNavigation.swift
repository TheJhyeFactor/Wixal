import SwiftUI
import WixalInteractions

struct NavigationRailButton: View {
    let title: String
    let symbol: String
    var selected = false
    let action: () -> Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var hovered = false
    var body: some View {
        Button(action: action) {
            Image(systemName: symbol).wixalFont(size: 16)
                .frame(width: 36, height: 36).contentShape(Rectangle())
                .background(selected ? theme.selected : hovered ? theme.raised : .clear, in: RoundedRectangle(cornerRadius: 5))
                .overlay(alignment: .leading) { if selected { Rectangle().fill(theme.accent).frame(width: 2, height: 18) } }
        }.buttonStyle(.plain).foregroundStyle(selected ? theme.text : theme.muted)
            .onHover { hovered = $0 }.help(title).accessibilityLabel(title)
            .accessibilityAddTraits(selected ? [.isSelected] : [])
    }
}

struct WorkspaceSelector: View {
    let selected: WorkspaceArea
    let busy: Bool
    let choose: (WorkspaceArea) -> Void
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        Menu {
            ForEach(WorkspaceArea.allCases) { area in
                Button { choose(area) } label: {
                    Label(area.rawValue + (area == selected ? " ✓" : ""), systemImage: area.symbol)
                }.disabled(busy && area == .chats)
            }
        } label: {
            HStack(spacing: 8) {
                Text(selected.rawValue).wixalFont(size: 14, weight: .semibold)
                Image(systemName: "chevron.down").wixalFont(size: 9).foregroundStyle(theme.muted)
            }.frame(minHeight: 32)
        }.menuStyle(.borderlessButton).menuIndicator(.hidden)
            .fixedSize().accessibilityLabel("Workspace: \(selected.rawValue)")
            .help("Switch between Chats, Agents, Cybersecurity and the Tools library")
    }
}

struct SidebarResizeHandle: View {
    @Binding var width: Double
    @ViewState private var startWidth: Double?
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        Rectangle().fill(theme.line).frame(width: 1)
            .frame(width: 7).contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 1).onChanged { value in
                if startWidth == nil { startWidth = SidebarPreferences.width(width) }
                width = SidebarPreferences.width((startWidth ?? width) + value.translation.width)
            }.onEnded { _ in startWidth = nil })
            .accessibilityElement().accessibilityLabel("Sidebar width")
            .accessibilityValue("\(Int(SidebarPreferences.width(width))) points")
            .accessibilityAdjustableAction { direction in
                width = SidebarPreferences.width(width + (direction == .increment ? 16 : -16))
            }
            .help("Drag to resize sidebar; adjust width in the sidebar menu")
    }
}
