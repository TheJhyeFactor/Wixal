import SwiftUI
import AppKit
import WixalActivity

struct TimelineDock: View {
    @ObservedObject var engine: EngineClient
    let milestones: [TimelineMilestone]
    @Binding var selectedID: String?
    @Binding var folded: Bool
    @Binding var replaying: Bool
    let replay: () -> Void
    var maximumDetailHeight:CGFloat = 220
    @Environment(\.wixalTheme) private var theme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @FocusState private var dockFocused:Bool

    private var selected: TimelineMilestone? {
        if let selectedID,let value=milestones.first(where:{$0.id==selectedID}) {return value}
        return milestones.last
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 9) {
                Image(systemName: engine.busy ? "bolt.horizontal.circle" : "clock.arrow.circlepath")
                    .foregroundStyle(engine.busy ? theme.accent : theme.muted)
                Text(engine.review != nil ? "Waiting for approval" : engine.busy ? "Running" : "Activity")
                    .font(.system(size: 11, weight: .semibold))
                if !milestones.isEmpty { Text("· \(milestones.count) milestones").foregroundStyle(theme.muted) }
                Spacer()
                Button(folded ? "Show activity" : "Hide details") { folded.toggle() }
                    .buttonStyle(.plain).font(.system(size: 10)).foregroundStyle(theme.muted)
                Button(replaying ? "Stop replay" : "Replay run", action: replay)
                    .buttonStyle(WixalButtonStyle(outlined: true)).font(.system(size: 10)).disabled(milestones.isEmpty || engine.busy)
            }

            if !folded {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        ForEach(milestones) { milestone in
                            Button {
                                selectedID = milestone.id
                                dockFocused = true
                            } label: {
                                HStack(spacing: 6) {
                                    Image(systemName: icon(for: milestone.status)).font(.system(size: 9))
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(milestone.title).lineLimit(1)
                                        Text(milestone.subtitle).font(.system(size: 9)).foregroundStyle(theme.muted).lineLimit(1)
                                    }
                                }.padding(.horizontal, 9).padding(.vertical, 7)
                            }.buttonStyle(WixalButtonStyle(outlined: true))
                                .background(selectedID == milestone.id ? theme.selected : .clear, in: RoundedRectangle(cornerRadius: 7))
                                .accessibilityAddTraits(selectedID == milestone.id ? [.isSelected] : [])
                        }
                    }
                }
            }

            if !folded, let selected {
                ScrollView {VStack(alignment: .leading, spacing: 7) {
                    HStack {
                        Label(selected.title, systemImage: icon(for: selected.status))
                            .font(.system(size: 11, weight: .medium))
                        Spacer()
                        Text(selected.status.capitalized)
                            .font(.system(size: 9)).foregroundStyle(theme.muted)
                    }
                    if !selected.command.isEmpty {
                        ScrollView {Text(selected.command).font(.system(size: 10, design: .monospaced)).textSelection(.enabled)
                            .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                            .background(theme.inset, in: RoundedRectangle(cornerRadius: 6))}.frame(height:CGFloat(min(80,max(32,selected.command.components(separatedBy:"\n").count*14+16))))
                    }
                    if !selected.output.isEmpty {
                        ScrollView {Text(selected.output).font(.system(size: 10,design:.monospaced)).foregroundStyle(theme.muted).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}.frame(height:CGFloat(min(100,max(28,(selected.output.components(separatedBy:"\n").count+selected.output.count/90)*14+10))))
                    } else if !engine.busy {
                        Text("No output recorded for this milestone yet.").font(.system(size: 10)).foregroundStyle(theme.muted)
                    }
                    HStack {Text(engine.project.map{textValue($0["name"])} ?? "Personal workspace");Spacer();Button("Copy output"){NSPasteboard.general.clearContents();NSPasteboard.general.setString(selected.output,forType:.string)}.disabled(selected.output.isEmpty)}.font(.system(size:10)).foregroundStyle(theme.muted)
                    if !selected.updates.isEmpty {DisclosureGroup("Approach & updates"){ScrollView{ForEach(Array(selected.updates.enumerated()),id:\.offset){_,update in MarkdownMessage(content:update)}}.frame(height:120)}}
                    DisclosureGroup("Raw events · \(selected.rawEvents.count)"){ScrollView{Text(selected.rawEvents.joined(separator:"\n\n")).font(.system(size:10,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}.frame(height:120)}
                }.padding(10)}.frame(maxHeight:maximumDetailHeight).background(theme.panel, in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(theme.line, lineWidth: 1))
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Dock: \(selected.title), \(selected.status)")
                    .focusable().focused($dockFocused)
            }
            if engine.busy {HStack{Label(engine.review != nil ? "Waiting for your approval" : engine.activity,systemImage:engine.review != nil ? "checkmark.shield" : "arrow.triangle.2.circlepath").font(.system(size:10)).foregroundStyle(theme.accent);Spacer();Button("Stop",action:engine.stop).buttonStyle(WixalButtonStyle(outlined:true)).accessibilityLabel("Stop current work")}}
        }.padding(12).background(theme.raised, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(theme.line, lineWidth: 1))
            .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: folded)
    }

    private func icon(for status: String) -> String {
        switch status.lowercased() {
        case "finished", "completed", "success": return "checkmark.circle.fill"
        case "waiting_review", "awaiting review": return "checkmark.shield"
        case "running", "requested", "pending": return "circle.dotted"
        case "stopped", "cancelled": return "stop.circle.fill"
        case "failed", "error", "declined", "interrupted", "no result": return "exclamationmark.circle.fill"
        default: return "circle"
        }
    }
}
