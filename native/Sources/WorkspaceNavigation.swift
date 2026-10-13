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
    @ViewState private var presented = false
    @FocusState private var focusedArea: WorkspaceArea?
    private func description(_ area:WorkspaceArea)->String {
        switch area {case .chats:return "Conversations and project history";case .agents:return "Agents, workflows, runs and schedules";case .cybersecurity:return "Scope, investigations and evidence";case .tools:return "Library and installed tools"}
    }
    var body: some View {
        Button {presented.toggle()} label: {
            HStack(spacing:8) {
                Image(systemName:selected.symbol).wixalFont(size:14).foregroundStyle(theme.muted)
                Text(selected.rawValue).wixalFont(size:14,weight:.semibold)
                Image(systemName:"chevron.down").wixalFont(size:9).foregroundStyle(theme.muted)
            }.padding(.horizontal,8).frame(height:36).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityLabel("Workspace: \(selected.rawValue)")
            .accessibilityValue(presented ? "Expanded" : "Collapsed")
            .help("Switch workspace")
            .popover(isPresented:$presented,arrowEdge:.bottom) {
                VStack(alignment:.leading,spacing:2) {
                    Text("Workspace").wixalFont(size:11,weight:.medium).foregroundStyle(theme.muted).padding(.horizontal,10).padding(.vertical,6)
                    ForEach(WorkspaceArea.allCases) { area in
                        Button {presented=false;choose(area)} label: {
                            HStack(spacing:12) {
                                Image(systemName:area.symbol).wixalFont(size:16).frame(width:20).foregroundStyle(theme.muted)
                                VStack(alignment:.leading,spacing:4) {
                                    Text(area.rawValue).wixalFont(size:13,weight:.medium)
                                    Text(description(area)).wixalFont(size:11).foregroundStyle(theme.muted)
                                }
                                Spacer(minLength:8)
                                if area==selected {Image(systemName:"checkmark").wixalFont(size:12).foregroundStyle(theme.accent)}
                            }.padding(.horizontal,10).frame(height:54).contentShape(Rectangle())
                                .background(area==selected ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:5))
                        }.buttonStyle(WixalButtonStyle()).disabled(busy && area == .chats)
                            .focused($focusedArea,equals:area)
                            .accessibilityLabel(area.rawValue+", "+description(area))
                            .accessibilityAddTraits(area==selected ? [.isSelected] : [])
                    }
                }.padding(6).frame(width:300).background(theme.panel).foregroundStyle(theme.text)
                    .onAppear{focusedArea=selected}.onExitCommand{presented=false}
                    .onKeyPress(keys:[.downArrow,.upArrow]) { press in
                        let areas=WorkspaceArea.allCases
                        let index=areas.firstIndex(of:focusedArea ?? selected) ?? 0
                        focusedArea=areas[(index+(press.key == .downArrow ? 1 : areas.count-1))%areas.count]
                        return .handled
                    }
            }
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
