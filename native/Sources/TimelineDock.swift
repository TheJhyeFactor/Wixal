import SwiftUI
import AppKit
import WixalActivity

/// One status line; command output and intermediate work stay behind Details.
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
    @Environment(\.wixalTextSize) private var textSize

    private var thinking:String {
        if !engine.thinking.isEmpty{return engine.thinking}
        let start=engine.messages.lastIndex{ textValue($0["role"])=="user" } ?? 0
        return engine.messages.suffix(from:start).compactMap{$0["thinking"] as? String}.joined(separator:"\n\n")
    }
    private var status:String {
        if engine.review != nil{return "Waiting for approval"}
        if !engine.currentTool.isEmpty{return "Running " + textValue(engine.currentTool["name"]).replacingOccurrences(of:"_",with:" ")}
        if !engine.streaming.isEmpty{return "Writing response"}
        if !engine.thinking.isEmpty{return "Thinking"}
        return engine.activity == "Generating reply…" ? "Waiting for model" : engine.activity
    }
    private var selected:TimelineMilestone? {milestones.first{$0.id==selectedID} ?? milestones.last}
    var body:some View {
        VStack(alignment:.leading,spacing:12){
            HStack(spacing:10){
                if engine.busy {
                    Image(systemName:engine.review != nil ? "checkmark.shield" : "circle.dotted")
                        .foregroundStyle(theme.muted)
                        .symbolEffect(.pulse,options:.repeating,isActive:engine.review == nil && !reduceMotion)
                    Text(status).id(status).transition(.opacity).lineLimit(2)
                    if let started=engine.runStarted {
                        TimelineView(.periodic(from:started,by:1)){context in Text("\(max(0,Int(context.date.timeIntervalSince(started)))) s").monospacedDigit().foregroundStyle(theme.muted)}
                    }
                }
                Button {
                    withAnimation(reduceMotion ? nil : .easeInOut(duration:0.22)){folded.toggle()}
                } label:{
                    HStack(spacing:5){Text("Details");Image(systemName:"chevron.right").font(.system(size:9)).rotationEffect(.degrees(folded ? 0 : 90))}
                }.buttonStyle(.plain).foregroundStyle(theme.muted).accessibilityLabel(folded ? "Show response details" : "Hide response details")
                Spacer(minLength:5)
                if engine.busy {Button("Stop",action:engine.stop).buttonStyle(.plain).foregroundStyle(theme.muted).accessibilityLabel("Stop current work")}
            }.wixalFont(size:11).frame(minHeight:24)
                .animation(reduceMotion ? nil : .easeInOut(duration:0.16),value:status)
            if !folded {
                ScrollView {
                    VStack(alignment:.leading,spacing:14){
                        if !thinking.isEmpty {
                            DisclosureGroup(engine.busy ? "Model thinking · live" : "Model thinking") {
                                Text(thinking).font(.system(size:max(12,textSize-1))).foregroundStyle(theme.muted).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(.top,8)
                            }
                        }
                        ForEach(milestones){step in
                            DisclosureGroup {
                                VStack(alignment:.leading,spacing:9){
                                    if !step.command.isEmpty {Text(step.command).textSelection(.enabled)}
                                    if !step.output.isEmpty {Text(step.output).textSelection(.enabled)}
                                    if !step.updates.isEmpty {DisclosureGroup("Updates"){ForEach(Array(step.updates.enumerated()),id:\.offset){_,update in MarkdownMessage(content:update)}}}
                                    DisclosureGroup("Technical events"){Text(step.rawEvents.joined(separator:"\n\n")).textSelection(.enabled)}
                                    Button("Copy output"){NSPasteboard.general.clearContents();NSPasteboard.general.setString(step.output,forType:.string)}.buttonStyle(.plain).disabled(step.output.isEmpty)
                                }.wixalFont(size:11,design:.monospaced).padding(.top,7)
                            } label:{HStack{Text(step.title);Spacer();Text(step.status.replacingOccurrences(of:"_",with:" ").capitalized).foregroundStyle(theme.muted)}}
                        }
                        let sources=records(engine.messages.last(where:{textValue($0["role"])=="assistant"})?["memoryEvidence"])
                        if !sources.isEmpty {
                            DisclosureGroup("Sources"){
                                ForEach(Array(sources.enumerated()),id:\.offset){_,source in
                                    VStack(alignment:.leading,spacing:6){
                                        Text(textValue(source["excerpt"])).textSelection(.enabled)
                                        if !textValue(source["sourceSession"]).isEmpty{Button("Open source conversation"){engine.openMemorySource(textValue(source["sourceSession"]))}.buttonStyle(.plain).disabled(engine.busy)}
                                    }.padding(.vertical,6)
                                }
                            }
                        }
                        if let usage=engine.messages.last(where:{textValue($0["role"])=="assistant"})?["usage"] as? [String:Any] {
                            HStack(spacing:12){if let count=usage["eval_count"] as? Int{Text("\(count) tokens")};if let seconds=usage["elapsedSeconds"] as? Double{Text(String(format:"%.1f s",seconds))}}
                                .foregroundStyle(theme.muted)
                        }
                        if milestones.isEmpty && thinking.isEmpty {Text("Waiting for the model’s first output.").foregroundStyle(theme.muted)}
                    }.wixalFont(size:11).padding(.vertical,4).frame(maxWidth:.infinity,alignment:.leading)
                }.frame(maxHeight:maximumDetailHeight).transition(.opacity.combined(with:.move(edge:.top)))
                    .accessibilityElement(children:.contain).accessibilityLabel("Response details")
            }
        }.padding(.vertical,4)
    }
}
