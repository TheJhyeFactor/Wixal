import SwiftUI
import AppKit

struct AgentTaskSheet:View{
    let agent:AgentProfileDraft
    let project:String
    let start:(String,[AgentSuccessCheck])->Void
    let queue:(String,[AgentSuccessCheck])->Void
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState private var prompt=""
    @ViewState private var checks:[AgentSuccessCheck]=[]
    @ViewState private var sheetSize=AgentSheetSize.preferred(width:640,height:570)
    var body:some View{VStack(spacing:0){AgentEditorHeader(title:"Give \(agent.name) a task",close:close);Divider();ScrollView{VStack(alignment:.leading,spacing:20){AgentRuntimeBanner();VStack(alignment:.leading,spacing:8){Text("Task brief").wixalFont(size:13,weight:.medium);TextEditor(text:$prompt).scrollContentBackground(.hidden).wixalFont(size:13).padding(10).frame(height:130).background(theme.raised,in:RoundedRectangle(cornerRadius:9)).accessibilityLabel("Task brief")};VStack(alignment:.leading,spacing:0){AgentMetadata(title:"Project",value:project);AgentMetadata(title:"Model",value:agent.model);AgentMetadata(title:"Actions",value:agent.reviewPolicy);AgentMetadata(title:"Memory",value:agent.memoryScope)}.wixalCard();AgentChecksEditor(checks:$checks);Text("This brief is sent to the agent's model. It chooses tools, executes within your task boundaries and records evidence.").wixalFont(size:12).foregroundStyle(theme.muted)}.padding(24)};Divider();HStack{Button("Cancel",action:close);Spacer();Button("Queue task"){queue(prompt.trimmingCharacters(in:.whitespacesAndNewlines),checks)}.disabled(prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty);Button("Start agent"){start(prompt.trimmingCharacters(in:.whitespacesAndNewlines),checks)}.disabled(prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty).keyboardShortcut(.defaultAction)}.buttonStyle(WixalButtonStyle(outlined:true)).padding(20)}.frame(width:sheetSize.width,height:sheetSize.height).background(theme.background).foregroundStyle(theme.text).onAppear{checks=agent.successCriteria ?? []}}
}
