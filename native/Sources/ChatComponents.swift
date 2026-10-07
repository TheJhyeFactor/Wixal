import SwiftUI
import WixalActivity
import AppKit
import UniformTypeIdentifiers

struct ChatAttachment:Identifiable,Equatable {
    var id=UUID().uuidString
    let type:String
    let name:String
    var path:String=""
    var content:String=""
    var base64:String=""
    var imageId:String=""
    var thumbnail:String=""
    var dictionary:[String:Any]{["type":type,"name":name,"path":path,"content":content,"base64":base64,"imageId":imageId,"thumbnail":thumbnail]}
    init(type:String,name:String,path:String="",content:String="",base64:String="",imageId:String="",thumbnail:String=""){self.type=type;self.name=name;self.path=path;self.content=content;self.base64=base64;self.imageId=imageId;self.thumbnail=thumbnail}
    init(_ data:[String:Any]){type=textValue(data["type"]);name=textValue(data["name"]);path=textValue(data["path"]);content=textValue(data["content"]);base64=textValue(data["base64"]);imageId=textValue(data["imageId"]);thumbnail=textValue(data["thumbnail"])}
    var image:NSImage?{guard let data=Data(base64Encoded:thumbnail.isEmpty ? base64 : thumbnail) else{return nil};return NSImage(data:data)}
}
struct ChatBottomKey:PreferenceKey {static let defaultValue:CGFloat=0;static func reduce(value:inout CGFloat,nextValue:()->CGFloat){value=nextValue()}}

struct AttachmentStrip:View {
    let attachments:[ChatAttachment]
    var remove:((String)->Void)?
    var engine:EngineClient? = nil
    @Environment(\.wixalTheme) private var theme
    @ViewState<ChatAttachment?> private var preview=nil
    var body:some View {
        ScrollView(.horizontal){HStack(spacing:8){ForEach(attachments){item in HStack(spacing:8){
            if let image=item.image{Button{preview=item}label:{Image(nsImage:image).resizable().scaledToFill().frame(width:40,height:36).clipped()}.buttonStyle(.plain).accessibilityLabel("Preview \(item.name)")}
            else if item.type=="image"{Button{preview=item}label:{Image(systemName:"photo").frame(width:40,height:36)}.buttonStyle(.plain).accessibilityLabel("Preview \(item.name)")}else{Image(systemName:"doc.text").foregroundStyle(theme.muted)}
            VStack(alignment:.leading,spacing:3){Text(item.name).font(.system(size:10)).lineLimit(1);if item.type=="file"{Text("\(item.content.count) characters").font(.system(size:9)).foregroundStyle(theme.muted)}}.frame(maxWidth:140,alignment:.leading)
            if let remove{Button{remove(item.id)}label:{Image(systemName:"xmark").font(.system(size:9))}.buttonStyle(.plain).accessibilityLabel("Remove \(item.name)")}
        }.padding(8).background(theme.panel,in:RoundedRectangle(cornerRadius:6)).overlay(RoundedRectangle(cornerRadius:6).stroke(theme.line,lineWidth:1))}}}.fixedSize(horizontal:false,vertical:true)
        .sheet(item:$preview){item in ImageAttachmentPreview(attachment:item,engine:engine,close:{preview=nil})}
    }
}

struct ImageAttachmentPreview:View {
    let attachment:ChatAttachment
    let engine:EngineClient?
    let close:()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState<NSImage?> private var image=nil
    @ViewState<String> private var error=""
    var body:some View{VStack(spacing:14){HStack{Text(attachment.name);Spacer();Button("Close",action:close)};if let image{Image(nsImage:image).resizable().scaledToFit()}else if !error.isEmpty{Text(error).foregroundStyle(theme.muted)}else{ProgressView()}}.padding(20).frame(width:min(680, (NSApp.keyWindow?.frame.width ?? 1000)-60),height:min(520, (NSApp.keyWindow?.frame.height ?? 680)-80)).background(theme.background).task{if !attachment.imageId.isEmpty,let engine{do{let result=try await engine.call("image-read",["id":attachment.imageId]) as? [String:Any] ?? [:];if let data=Data(base64Encoded:textValue(result["base64"])){image=NSImage(data:data)}}catch{self.error=error.localizedDescription}}else{image=Data(base64Encoded:attachment.base64).flatMap{NSImage(data:$0)} ?? attachment.image}}}
}

struct WorkHistoryView:View {
    @ObservedObject var engine:EngineClient
    let messages:[[String:Any]]
    @Environment(\.wixalTheme) private var theme
    @ViewState private var selected=0
    private var actions:[TimelineMilestone] {TimelineHistory.milestones(messages:messages,tasks:records(engine.state["tasks"]),sessionID:textValue(engine.state["activeSession"]),busy:engine.busy,review:engine.review?.details,activeTool:engine.currentTool)}
    var body:some View {
        DisclosureGroup {
            VStack(alignment:.leading,spacing:12) {
                ScrollView(.horizontal){HStack{ForEach(Array(actions.enumerated()),id:\.element.id){index,action in
                    Button{selected=index}label:{VStack(alignment:.leading,spacing:4){Text(action.title);Text(action.status.capitalized).font(.system(size:9)).foregroundStyle(theme.muted)}}.buttonStyle(WixalButtonStyle(outlined:true)).accessibilityAddTraits(index==selected ? [.isSelected] : [])
                }}}
                if !actions.isEmpty {
                    let action=actions[min(selected,actions.count-1)]
                    Text(action.command).font(.system(size:10,design:.monospaced)).textSelection(.enabled)
                    Text(action.output.isEmpty ? "Action "+action.status+" · no result yet" : action.output).font(.system(size:11,design:.monospaced)).textSelection(.enabled)
                    HStack{Spacer();Button("Copy output"){NSPasteboard.general.clearContents();NSPasteboard.general.setString(action.output,forType:.string)}.disabled(action.output.isEmpty)}
                    DisclosureGroup("Raw events · \(action.rawEvents.count)"){Text(action.rawEvents.joined(separator:"\n\n")).font(.system(size:10,design:.monospaced)).textSelection(.enabled)}
                }
                let updates=messages.filter{textValue($0["role"]) != "tool" && !textValue($0["content"]).isEmpty}
                if !updates.isEmpty{DisclosureGroup("Approach & updates"){ForEach(Array(updates.enumerated()),id:\.offset){_,message in MarkdownMessage(content:textValue(message["content"]))}}}
            }
        } label:{HStack(spacing:8){Image(systemName:"checklist");Text("Work history");Text("\(actions.count) actions").foregroundStyle(theme.muted);Spacer()}}
        .font(.system(size:11)).padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(theme.line,lineWidth:1)).padding(.vertical,8)
    }
}
struct StructuredToolResult:View {
    let message:[String:Any]
    @Environment(\.wixalTheme) private var theme
    private var decoded:[String:Any]?{guard let data=textValue(message["content"]).data(using:.utf8) else{return nil};return (try? JSONSerialization.jsonObject(with:data)) as? [String:Any]}
    var body:some View {VStack(alignment:.leading,spacing:8){
        Label(textValue(message["tool_name"]).replacingOccurrences(of:"_",with:" "),systemImage:decoded?["error"]==nil ? "checkmark.circle" : "exclamationmark.circle").font(.system(size:11,weight:.medium))
        if let value=decoded{
            if let error=value["error"] as? String{Text(error).foregroundStyle(.red).textSelection(.enabled)}
            if let output=value["output"] as? String ?? value["stdout"] as? String{Text(output).font(.system(size:11,design:.monospaced)).textSelection(.enabled)}
            let findings=records(value["findings"])
            if !findings.isEmpty{ForEach(Array(findings.enumerated()),id:\.offset){_,finding in HStack(alignment:.top){Text(textValue(finding["severity"]).uppercased()).font(.system(size:9,weight:.semibold));VStack(alignment:.leading){Text(textValue(finding["title"]));Text(textValue(finding["evidence"] ?? finding["description"])).foregroundStyle(theme.muted)}}}}
            DisclosureGroup("Full result"){Text(pretty(value)).font(.system(size:10,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}
        }else{Text(textValue(message["content"])).font(.system(size:11,design:.monospaced)).textSelection(.enabled)}
    }.font(.system(size:11)).padding(10).frame(maxWidth:.infinity,alignment:.leading).background(theme.inset,in:RoundedRectangle(cornerRadius:6))}
}

struct ConversationDetailsView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @Environment(\.dismiss) private var dismiss
    private var summary:[String:Any]{engine.session?["summary"] as? [String:Any] ?? [:]}
    private var usage:[[String:Any]]{engine.messages.compactMap{$0["usage"] as? [String:Any]}}
    var body:some View {VStack(alignment:.leading,spacing:18){HStack{Text("Conversation context and usage").font(.system(size:20,weight:.medium));Spacer();Button("Close"){dismiss()}};ScrollView{VStack(alignment:.leading,spacing:18){
        Text(engine.contextAvailable ? "Estimated context: ~\(engine.contextTokens.formatted()) / \(engine.state["contextSize"] as? Int ?? 8192) tokens" : "Calculating context…").foregroundStyle(theme.muted)
        Text("Includes the prepared messages, instructions, selected skill, tool definitions and image allowance. Actual token counts depend on the model tokenizer.").font(.system(size:11)).foregroundStyle(theme.muted)
        if engine.contextAvailable{Text("Global preferences: \(textValue(engine.contextInfo["memoryScope"]).capitalized) · \(engine.contextInfo["globalMemoryIncluded"] as? Bool == true ? "included" : "disabled by recall preferences")").font(.system(size:11)).foregroundStyle(theme.muted)}
        Text("Actual model usage").font(.system(size:13,weight:.semibold))
        if usage.isEmpty{Text("Usage is reported after a model finishes a response.").foregroundStyle(theme.muted)}else{Grid(alignment:.leading,horizontalSpacing:24,verticalSpacing:8){GridRow{Text("Response");Text("Input tokens");Text("Output tokens");Text("Tokens/sec");Text("Seconds")};ForEach(Array(usage.enumerated()),id:\.offset){index,item in GridRow{Text("\(index+1)");Text("\(item["prompt_eval_count"] as? Int ?? 0)");Text("\(item["eval_count"] as? Int ?? 0)");Text(String(format:"%.1f",item["tokensPerSecond"] as? Double ?? 0));Text(String(format:"%.1f",item["elapsedSeconds"] as? Double ?? 0))}}}.font(.system(size:11,design:.monospaced))}
        if !usage.isEmpty{Text("Total: \(usage.reduce(0){$0+($1["prompt_eval_count"] as? Int ?? 0)}) input tokens · \(usage.reduce(0){$0+($1["eval_count"] as? Int ?? 0)}) output tokens").font(.system(size:11,design:.monospaced)).foregroundStyle(theme.muted)}
        Divider();Toggle("Automatically summarize long conversations",isOn:Binding(get:{engine.state["autoSummary"] as? Bool ?? true},set:{engine.action("settings",["autoSummary":$0])})).disabled(engine.busy)
        Text("Saved summary").font(.system(size:13,weight:.semibold));if summary.isEmpty{Text("No summary has been saved for this conversation.").foregroundStyle(theme.muted)}else{Text(textValue(summary["method"])=="model" ? "Created with the selected local model" : "Labelled excerpts used because a model summary was unavailable").font(.system(size:11)).foregroundStyle(theme.muted);MarkdownMessage(content:textValue(summary["content"]));Button("Clear saved summary",role:.destructive){engine.action("summary-clear")}.disabled(engine.busy)}
    }};HStack{Text(engine.operationRunning ? engine.activity : "The original conversation remains saved.").foregroundStyle(theme.muted);Spacer();if engine.operationRunning{Button("Stop",action:engine.stop).buttonStyle(WixalButtonStyle(outlined:true))}else{Button("Continue in new chat"){Task{do{_ = try await engine.call("session-handoff");dismiss()}catch{engine.error=error.localizedDescription}}}.buttonStyle(WixalButtonStyle(outlined:true)).disabled(engine.busy || engine.messages.isEmpty)}}}.font(.system(size:12)).padding(24).frame(width:min(720, (NSApp.keyWindow?.frame.width ?? 1000)-60),height:min(620, (NSApp.keyWindow?.frame.height ?? 680)-80)).background(theme.background)}
}
