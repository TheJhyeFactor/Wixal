import SwiftUI
import WixalActivity
import AppKit
import UniformTypeIdentifiers
import ImageIO

struct ChatView: View {
    @ObservedObject var engine: EngineClient
    var openModels: ()->Void
    var openFiles: ()->Void
    var openTools: ()->Void
    @Environment(\.wixalTheme) private var theme
    @ViewState<String> private var prompt = ""
    @ViewState<String> private var skill = ""
    @ViewState<[ChatAttachment]> private var attachments=[]
    @ViewState<CGFloat> private var editorHeight=58
    @ViewState<Bool> private var followLatest=true
    @ViewState<Bool> private var detailsPresented=false
    @ViewState<String?> private var selectedMilestone=nil
    @ViewState<Bool> private var foldedTimeline=false
    @ViewState<Bool> private var replayingTimeline=false
    @ViewState<Task<Void,Never>?> private var replayTask=nil
    @ViewState<String> private var draftSession=""
    @ViewState<Task<Void,Never>?> private var draftTask=nil
    private var sessionID:String{textValue(engine.state["activeSession"])}
    private var enabledToolNames:[String]{engine.state["enabledTools"] as? [String] ?? []}
    @ViewState private var caret=NSRange(location:0,length:0)
    @ViewState private var mentionIndex=0
    @ViewState private var mentionsDismissed=false
    private var mentionRange:NSRange? {
        guard caret.length==0, !mentionsDismissed else{return nil}
        let prefix=(prompt as NSString).substring(to:min(caret.location,(prompt as NSString).length))
        return (try? NSRegularExpression(pattern:"(?:^|\\s)(@[a-zA-Z0-9_]*)$")).flatMap{$0.firstMatch(in:prefix,range:NSRange(location:0,length:(prefix as NSString).length))?.range(at:1)}
    }
    private var mentionQuery:String?{guard let range=mentionRange else{return nil};return String((prompt as NSString).substring(with:range).dropFirst()).lowercased()}
    private var mentionNames:[String]{guard let query=mentionQuery,engine.supportsTools else{return []};return enabledToolNames.filter{(engine.project != nil || !($0.hasPrefix("website_") || $0.hasPrefix("network_") || $0.hasPrefix("command_") || ["list_files","read_file","search_files","write_file","edit_file","make_directory","run_command"].contains($0))) && (query.isEmpty || $0.lowercased().contains(query))}.sorted()}
    private func insertMention(_ name:String){guard let range=mentionRange else{return};let value="@\(name) ";prompt=(prompt as NSString).replacingCharacters(in:range,with:value);caret=NSRange(location:range.location+(value as NSString).length,length:0);mentionIndex=0}
    private func handleMentionKey(_ code:UInt16)->Bool {
        guard mentionQuery != nil,!mentionNames.isEmpty else{return false}
        switch code {case 125:mentionIndex=(mentionIndex+1)%mentionNames.count;return true
        case 126:mentionIndex=(mentionIndex+mentionNames.count-1)%mentionNames.count;return true
        case 48,36:insertMention(mentionNames[min(mentionIndex,mentionNames.count-1)]);return true
        case 53:mentionsDismissed=true;return true
        default:return false}
    }
    private var workGroups:[[String:Any]]{
        var result:[[String:Any]]=[];var work:[[String:Any]]=[]
        for message in engine.messages {
            if textValue(message["role"])=="tool" || !(message["tool_calls"] as? [[String:Any]] ?? []).isEmpty{work.append(message)}
            else{if !work.isEmpty{result.append(["role":"work","steps":work]);work=[]};result.append(message)}
        }
        if !work.isEmpty{result.append(["role":"work","steps":work])};return result
    }
    private var empty: Bool {engine.messages.isEmpty && engine.streaming.isEmpty}
    private var timelineMilestones:[TimelineMilestone] {
        TimelineHistory.milestones(messages:engine.messages,tasks:records(engine.state["tasks"]),sessionID:sessionID,busy:engine.busy,review:engine.review?.details,activeTool:engine.currentTool)
    }
    var body: some View {
        GeometryReader {geometry in
            VStack(spacing:0){
                if empty {
                    ScrollView{
                        VStack(spacing:0){
                            Spacer(minLength:20)
                            if geometry.size.height >= 550{welcome.frame(maxWidth:776).padding(.horizontal,32)}else{HStack{Wordmark(size:22);Spacer();Text("What are you working on?").font(.system(size:20,weight:.medium))}.padding(.horizontal,32).frame(maxWidth:840)}
                            composer(compact:geometry.size.width<680).padding(.top,24).frame(maxWidth:840)
                            if geometry.size.height >= 550{starters.frame(maxWidth:776).padding(.horizontal,32).padding(.top,18)}
                            HStack(spacing:9){Button("Open a project folder ↗",action:engine.pickProject);Text("·");Button("Edits and commands come to you for review ↗",action:openTools)}.buttonStyle(.plain).font(.system(size:10)).foregroundStyle(theme.muted).padding(.top,18)
                            Spacer(minLength:20)
                        }.frame(minHeight:geometry.size.height).frame(maxWidth:.infinity)
                    }
                } else {
                    ScrollViewReader {proxy in
                        GeometryReader {viewport in
                            ScrollView {
                                LazyVStack(alignment:.leading,spacing:0){
                                    ForEach(Array(workGroups.enumerated()),id:\.offset){index,message in
                                        if textValue(message["role"])=="work"{WorkHistoryView(engine:engine,messages:records(message["steps"])).id(index)}else{MessageView(message:message,engine:engine).id(index)}
                                    }
                                    if !engine.streaming.isEmpty{MessageView(message:["role":"assistant","content":engine.streaming]).id("stream")}
                                    Color.clear.frame(height:1).background(GeometryReader{position in Color.clear.preference(key:ChatBottomKey.self,value:position.frame(in:.named("conversationScroll")).maxY)}).id("bottom")
                                }.padding(.horizontal,32).padding(.top,24).padding(.bottom,24).frame(maxWidth:840).frame(maxWidth:.infinity)
                            }.coordinateSpace(name:"conversationScroll")
                            .onPreferenceChange(ChatBottomKey.self){bottom in followLatest=bottom<viewport.size.height+85}
                            .overlay(alignment:.bottom){if !followLatest{Button{followLatest=true;proxy.scrollTo("bottom",anchor:.bottom)}label:{Label("Jump to latest",systemImage:"arrow.down")}.buttonStyle(WixalButtonStyle(outlined:true)).padding(.bottom,12).background(theme.background.opacity(0.9),in:Capsule())}}
                            .onChange(of:engine.streaming){_,_ in if followLatest{proxy.scrollTo("bottom",anchor:.bottom)}}
                            .onChange(of:engine.messages.count){_,_ in if followLatest{proxy.scrollTo("bottom",anchor:.bottom)}}
                            .onChange(of:sessionID){_,_ in followLatest=true;proxy.scrollTo("bottom",anchor:.bottom)}
                            .onAppear{proxy.scrollTo("bottom",anchor:.bottom)}
                        }
                    }
                    VStack(spacing:8){
                        if !timelineMilestones.isEmpty || engine.busy {
                            TimelineDock(engine:engine,milestones:timelineMilestones,selectedID:$selectedMilestone,folded:$foldedTimeline,replaying:$replayingTimeline,replay:replayTimeline,maximumDetailHeight:max(90,min(220,geometry.size.height*0.24)))
                                .padding(.horizontal,32)
                        }
                        composer(compact:geometry.size.width<680)
                    }.frame(maxWidth:900).padding(.top,8)
                }
            }.frame(width:geometry.size.width,height:geometry.size.height).background(theme.background)
        }.onAppear{restoreActivity();restoreDraft();engine.selectedSkill=skill;engine.refreshContext()}
        .onChange(of:skill){_,value in engine.selectedSkill=value}
        .onChange(of:sessionID){old,new in saveActivity(old);replayTask?.cancel();replayingTimeline=false;restoreActivity();saveDraftImmediately();restoreDraft()}
        .onChange(of:prompt){_,_ in mentionIndex=0;mentionsDismissed=false;queueDraft()}
        .onChange(of:attachments){_,_ in queueDraft()}
        .onDisappear{saveActivity(sessionID);replayTask?.cancel();replayingTimeline=false;saveDraftImmediately()}
        .sheet(isPresented:$detailsPresented){ConversationDetailsView(engine:engine)}
    }
    private func saveActivity(_ id:String){
        guard !id.isEmpty else{return}
        UserDefaults.standard.set(["selection":selectedMilestone ?? "","folded":foldedTimeline] as [String:Any],forKey:"activity.\(id)")
    }
    private func restoreActivity(){
        let saved=UserDefaults.standard.dictionary(forKey:"activity.\(sessionID)") ?? [:]
        let selection=textValue(saved["selection"])
        selectedMilestone=selection.isEmpty ? nil : selection
        foldedTimeline=saved["folded"] as? Bool ?? false
    }
    private func replayTimeline() {
        if replayingTimeline{replayTask?.cancel();replayingTimeline=false;return}
        guard !timelineMilestones.isEmpty, !engine.busy else { return }
        replayingTimeline=true; foldedTimeline=false; replayTask?.cancel()
        let ids=timelineMilestones.map(\.id)
        replayTask=Task { @MainActor in
            for id in ids {
                guard !Task.isCancelled else { replayingTimeline=false;return }
                selectedMilestone=id
                try? await Task.sleep(nanoseconds:420_000_000)
            }
            replayingTimeline=false
        }
    }
    private var welcome: some View {
        VStack(alignment:.leading,spacing:0){
            HStack(spacing:16){Wordmark(size:27);Rectangle().fill(theme.line).frame(width:1,height:20);Text(engine.project.map{textValue($0["name"])} ?? "Personal workspace").font(.system(size:11)).foregroundStyle(theme.muted)}.padding(.bottom,20)
            Text("What are you working on?").font(.system(size:34,weight:.medium)).tracking(-1.1).padding(.bottom,12)
            Text(engine.project == nil ? "Open a project to work with files, or start a personal conversation." : "Explore your project, make a change, or work through a problem.").font(.system(size:13)).foregroundStyle(theme.muted).lineSpacing(5)
            HStack(spacing:0){
                readiness("Project context",value:engine.project.map{textValue($0["name"])} ?? "Choose a folder",icon:"folder",action:engine.pickProject)
                Rectangle().fill(theme.line).frame(width:1)
                readiness("Wixal Local",value:textValue(engine.state["model"]).isEmpty ? "Choose a model" : displayModel,icon:"circle.fill",action:openModels)
            }.frame(height:64).background(theme.panel.opacity(0.6),in:RoundedRectangle(cornerRadius:9)).overlay(RoundedRectangle(cornerRadius:9).stroke(theme.line,lineWidth:1)).padding(.top,24)
        }.frame(maxWidth:.infinity,alignment:.leading)
    }
    private func readiness(_ label:String,value:String,icon:String,action:@escaping()->Void)->some View{
        Button(action:action){HStack(spacing:12){Image(systemName:icon).font(.system(size:icon=="circle.fill" ? 6 : 16)).foregroundStyle(icon=="circle.fill" ? theme.accent : theme.muted);VStack(alignment:.leading,spacing:3){Text(label).font(.system(size:10)).foregroundStyle(theme.muted);Text(value).font(.system(size:12,weight:.medium)).foregroundStyle(theme.text).lineLimit(1)};Spacer();Image(systemName:icon=="circle.fill" ? "chevron.down" : "arrow.up.right").font(.system(size:10)).foregroundStyle(theme.muted)}.padding(.horizontal,16).frame(maxWidth:.infinity,maxHeight:.infinity).contentShape(Rectangle())}.buttonStyle(.plain)
    }
    private var incompatibleImages:Bool {attachments.contains{$0.type=="image"} && engine.modelCapabilitiesKnown && !engine.supportsImages}
    private var displayModel:String{let value=textValue(engine.state["model"]);return value.split(separator:"/").last.map(String.init) ?? value}
    private func composer(compact:Bool) -> some View {
        VStack(spacing:0){
            VStack(spacing:0){
                if !attachments.isEmpty{AttachmentStrip(attachments:attachments,remove:{id in attachments.removeAll{$0.id==id}},engine:engine).padding(.horizontal,18).padding(.top,12)}
                if let query=mentionQuery {mentionSuggestions(query).padding(.horizontal,18).padding(.top,8)}
                HStack(alignment:.top,spacing:14){
                    ZStack(alignment:.topLeading){
                        PromptEditor(text:$prompt,theme:theme,send:send,selection:caret,onSelection:{caret=$0;mentionsDismissed=false},mentionKey:handleMentionKey,onHeight:{editorHeight=$0}).frame(height:min(editorHeight,compact ? 100 : 170))
                        if prompt.isEmpty{Text(engine.project.map{"Ask about \(textValue($0["name"])) or describe a task…"} ?? "Ask a question or describe a task…").font(.system(size:14)).foregroundStyle(theme.muted).padding(.top,4).allowsHitTesting(false)}
                    }
                    Button(action:engine.busy ? engine.stop : send){Image(systemName:engine.busy ? "stop.fill" : "arrow.up").font(.system(size:19,weight:.medium)).foregroundStyle(theme.light ? theme.raised : theme.background).frame(width:32,height:32).background(theme.accent,in:RoundedRectangle(cornerRadius:10))}.buttonStyle(.plain).disabled(!engine.busy && ((prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && attachments.isEmpty) || !engine.connected || incompatibleImages)).accessibilityLabel(engine.busy ? "Stop response" : "Send message").keyboardShortcut(.return,modifiers:.command)
                }.padding(.horizontal,18).padding(.top,18).padding(.bottom,6)
                HStack(spacing:8){
                    if !compact {Button(action:attachFile){Image(systemName:"folder").font(.system(size:15)).frame(width:24,height:26)}.buttonStyle(.plain).foregroundStyle(theme.muted).help("Add file excerpt").accessibilityLabel("Add file excerpt");Button(action:attachImage){Image(systemName:"photo").font(.system(size:15)).frame(width:24,height:26)}.buttonStyle(.plain).foregroundStyle(theme.muted).help("Attach image").accessibilityLabel("Attach image")}else{Menu{Button("Add file excerpt",action:attachFile);Button("Attach image",action:attachImage);Button("Browse project files",action:openFiles);Button("Insert tool mention"){prompt += prompt.isEmpty ? "@" : " @"};Button("Tool permissions",action:openTools);Menu("Skills"){Button("No selected skill"){skill=""};ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset){_,item in Button(textValue(item["name"])){skill=textValue(item["name"])}}}}label:{Image(systemName:"plus.circle").font(.system(size:15))}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(width:24).accessibilityLabel("Composer attachments and tools")}
                    Button(action:openModels){HStack(spacing:7){Image(systemName:"diamond");Text(displayModel.isEmpty ? "Choose a model" : displayModel).lineLimit(1).frame(maxWidth:compact ? 100 : 200);Image(systemName:"chevron.down").font(.system(size:8))}.font(.system(size:11)).fixedSize(horizontal:true,vertical:false)}.buttonStyle(WixalButtonStyle(outlined:true)).help("Choose model")
                    WixalChoiceMenu(title:textValue(engine.state["mode"])=="chat" ? "Chat" : "Agent",outlined:true,choices:[("Agent",{engine.action("settings",["mode":"agent"])}),("Chat",{engine.action("settings",["mode":"chat"])})]).disabled(engine.busy)
                    if !compact && !records(engine.state["skills"]).isEmpty{Menu{Button("No selected skill"){skill=""};ForEach(Array(records(engine.state["skills"]).enumerated()),id:\.offset){_,item in Button(textValue(item["name"])){skill=textValue(item["name"])}}}label:{Text(skill.isEmpty ? "Skills" : skill).font(.system(size:11))}.menuStyle(.borderlessButton).menuIndicator(.hidden).frame(maxWidth:90)}
                    Spacer(minLength:4)
                    WixalChoiceMenu(title:textValue(engine.project?["approvalMode"] ?? engine.state["personalApprovalMode"]) == "bypass" ? (compact ? "Approved" : "Approved all") : (compact ? "Review" : "Review each action"),outlined:false,choices:[("Review each action",{engine.action("settings",["approvalMode":"review"])}),("Approved all",{engine.action("settings",["approvalMode":"bypass"])})]).disabled(engine.busy)
                    if !compact{Button("@ Tools"){prompt += prompt.isEmpty ? "@" : " @"}.buttonStyle(.plain).font(.system(size:10)).foregroundStyle(theme.muted)
                    Text("↵ send · ⇧↵ new line").font(.system(size:9,design:.monospaced)).foregroundStyle(theme.muted).lineLimit(1)}
                }.padding(.horizontal,16).padding(.bottom,14)
            }.background(theme.raised,in:RoundedRectangle(cornerRadius:12)).overlay(RoundedRectangle(cornerRadius:12).stroke(theme.line,lineWidth:1)).shadow(color:.black.opacity(theme.light ? 0.06 : 0.16),radius:12,x:0,y:5)
            HStack(spacing:7){Circle().fill(engine.modelReady ? theme.accent : theme.muted).frame(width:5,height:5);Text(engine.modelConnectionLabel).lineLimit(1);Spacer();Button{detailsPresented=true}label:{Text(contextLabel).lineLimit(1)}.buttonStyle(.plain).help("Context, saved summary and response usage");Text(engine.busy ? engine.activity : "Ready").lineLimit(1)}.font(.system(size:9)).foregroundStyle(theme.muted).padding(.top,14).padding(.bottom,12)
            if incompatibleImages {Button("Choose an Images model to send these attachments",action:openModels).buttonStyle(.plain).font(.system(size:11)).foregroundStyle(theme.accent).padding(.bottom,8)}
            if engine.modelCapabilitiesKnown && !engine.supportsTools && !textValue(engine.state["model"]).isEmpty{Text("Conversation-only model · replies without tools. Choose a model marked Tools for actions.").font(.system(size:10)).foregroundStyle(theme.muted).padding(.bottom,8)}
            if contextRatio>=0.8{HStack{Text("Conversation nearing its context limit. Continue in a new chat to carry the work forward.");Spacer();Button("Continue…"){detailsPresented=true}}.font(.system(size:10)).foregroundStyle(theme.accent).padding(.bottom,8)}
        }.padding(.horizontal,compact ? 16 : 32)
    }
    private var starters: some View {
        HStack(spacing:8){
            starter("Plan a change",detail:"Work out a practical next step",icon:"plus",prompt:"Help me turn an idea into a practical plan. Ask me what I have in mind, then help me work out where to start.")
            starter("Explore the project",detail:"Understand the files and structure",icon:"folder",prompt:"Read the main docs and files in this project, then explain how it works and where I should start.")
            starter("Work through a problem",detail:"Trace the cause and check a fix",icon:"magnifyingglass",prompt:"Help me work through a problem. Ask me what is happening, what I expected, and what I have tried.")
        }
    }
    private func starter(_ title:String,detail:String,icon:String,prompt:String)->some View{
        Button{self.prompt=prompt}label:{HStack(spacing:10){Image(systemName:icon).font(.system(size:15)).foregroundStyle(theme.muted);VStack(alignment:.leading,spacing:4){Text(title).font(.system(size:11,weight:.medium));Text(detail).font(.system(size:10)).foregroundStyle(theme.muted).lineLimit(1)};Spacer(minLength:1);Image(systemName:"arrow.up.right").font(.system(size:9)).foregroundStyle(theme.muted)}.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(theme.panel.opacity(0.5),in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(theme.line,lineWidth:1))}.buttonStyle(.plain)
    }
    private var contextTokens:Int{engine.contextTokens}
    private var contextLimit:Int{engine.state["contextSize"] as? Int ?? 8192}
    private var contextRatio:Double{Double(contextTokens)/Double(max(1,contextLimit))}
    private var contextLabel:String{engine.contextAvailable ? "~\(contextTokens.formatted()) / \(contextLimit.formatted()) context" : "Calculating context…"}
    private func mentionSuggestions(_ query:String)->some View{
        let names=mentionNames
        return VStack(alignment:.leading,spacing:3){Text("ENABLED TOOLS · ↑ ↓ choose · Tab insert").font(.system(size:9,design:.monospaced)).foregroundStyle(theme.muted)
            ScrollViewReader{proxy in ScrollView(.horizontal){HStack{ForEach(Array(names.enumerated()),id:\.element){index,name in Button(name){insertMention(name)}.buttonStyle(WixalButtonStyle(outlined:true)).background(index==mentionIndex ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6)).accessibilityAddTraits(index==mentionIndex ? [.isSelected] : []).id(index)};if names.isEmpty{Text(engine.supportsTools ? "No enabled tools match." : "Choose a model marked Tools to use tool mentions.").font(.system(size:10))}}}.frame(maxHeight:34).onChange(of:mentionIndex){_,index in proxy.scrollTo(index)}}
        }
    }

    private func restoreDraft(){draftTask?.cancel();draftSession=sessionID;let draft=engine.session?["draft"] as? [String:Any] ?? [:];prompt=textValue(draft["text"]);attachments=records(draft["attachments"]).map(ChatAttachment.init)}
    private func queueDraft(){draftTask?.cancel();let id=draftSession;let text=prompt;let values=attachments.map(\.dictionary);draftTask=Task{@MainActor in try? await Task.sleep(nanoseconds:350_000_000);guard !Task.isCancelled,!id.isEmpty else{return};engine.action("draft-save",["sessionId":id,"text":text,"attachments":values])}}
    private func saveDraftImmediately(){draftTask?.cancel();guard !draftSession.isEmpty, records(engine.state["sessions"]).contains(where:{textValue($0["id"])==draftSession}) else{return};engine.action("draft-save",["sessionId":draftSession,"text":prompt,"attachments":attachments.map(\.dictionary)])}
    private func attachFile(){
        guard !engine.root.isEmpty else{engine.error="Open a project folder to add file context";engine.pickProject();return}
        guard !engine.busy else{return}
        guard attachments.count<8 else{engine.error="Attach at most eight files or images";return}
        let projectURL=URL(fileURLWithPath:engine.root).resolvingSymlinksInPath().standardizedFileURL
        let panel=NSOpenPanel();panel.canChooseDirectories=false;panel.allowsMultipleSelection=true;panel.prompt="Add excerpt";panel.directoryURL=projectURL
        guard panel.runModal() == .OK else{return}
        let selected=Array(panel.urls.prefix(8-attachments.count));let id=sessionID
        Task{for url in selected{do{
            let resolved=url.resolvingSymlinksInPath().standardizedFileURL.path
            guard resolved.hasPrefix(projectURL.path+"/") else{throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"Choose a file inside the current project folder"])}
            let relative=String(resolved.dropFirst(projectURL.path.count+1))
            let result=try await engine.call("tool",["name":"read_file","arguments":["path":relative]]) as? [String:Any] ?? [:]
            guard self.sessionID==id else{return}
            let excerpt=textValue(result["content"])
            guard !excerpt.isEmpty else{throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"This file has no readable text to attach"])}
            attachments.append(ChatAttachment(type:"file",name:url.lastPathComponent,path:relative,content:excerpt))
        }catch{engine.error=error.localizedDescription}}}
    }
    private func attachImage(){
        let model=engine.models.first{textValue($0["name"])==textValue(engine.state["model"])}
        guard (model?["capabilities"] as? [String] ?? []).contains("vision") else{engine.error="Choose a model marked Images to attach photos or screenshots";openModels();return}
        guard attachments.count<8 else{engine.error="Attach at most eight files or images";return}
        let panel=NSOpenPanel();panel.allowedContentTypes=[.png,.jpeg,UTType.webP];panel.allowsMultipleSelection=true;panel.prompt="Attach images"
        guard panel.runModal() == .OK else{return}
        for url in panel.urls.prefix(8-attachments.count){do{
            let values=try url.resourceValues(forKeys:[.fileSizeKey])
            guard (values.fileSize ?? 0)<=12_000_000,let source=CGImageSourceCreateWithURL(url as CFURL,nil) else{throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"Choose an image smaller than 12 MB"])}
            let properties=CGImageSourceCopyPropertiesAtIndex(source,0,nil) as? [CFString:Any] ?? [:]
            let width=(properties[kCGImagePropertyPixelWidth] as? NSNumber)?.doubleValue ?? 0
            let height=(properties[kCGImagePropertyPixelHeight] as? NSNumber)?.doubleValue ?? 0
            guard width>0,height>0,width*height<=160_000_000 else{throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"Choose an image below 160 megapixels"])}
            func prepared(_ maximum:Int,_ quality:Double)->Data?{
                let options:[CFString:Any]=[kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceCreateThumbnailWithTransform:true,kCGImageSourceThumbnailMaxPixelSize:maximum,kCGImageSourceShouldCacheImmediately:true]
                guard let image=CGImageSourceCreateThumbnailAtIndex(source,0,options as CFDictionary) else{return nil}
                return NSBitmapImageRep(cgImage:image).representation(using:.jpeg,properties:[.compressionFactor:quality])
            }
            guard let data=prepared(1536,0.85),data.count<=4*1024*1024 else{throw NSError(domain:"Wixal",code:1,userInfo:[NSLocalizedDescriptionKey:"Unable to prepare image below 4 MB"])}
            let thumbnail=prepared(96,0.65)?.base64EncodedString() ?? ""
            attachments.append(ChatAttachment(type:"image",name:url.lastPathComponent,base64:data.base64EncodedString(),thumbnail:thumbnail))
        }catch{engine.error=error.localizedDescription}}
    }
    private func send(){
        guard !incompatibleImages else{engine.error="Choose a model marked Images before sending image attachments";return}
        guard !engine.busy && (!prompt.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || !attachments.isEmpty) else{return}
        let text=prompt.isEmpty ? "Describe the attached images or file excerpts." : prompt;let selected=attachments;let id=sessionID
        draftTask?.cancel();prompt="";attachments=[];followLatest=true
        engine.chat(text,skill:skill,attachments:selected.map(\.dictionary),completion:{success in if !success,self.sessionID==id,self.prompt.isEmpty{self.prompt=text;self.attachments=selected;self.saveDraftImmediately()}})
    }
}

struct MessageView: View {
    let message:[String:Any]
    var engine:EngineClient? = nil
    @Environment(\.wixalTheme) private var theme
    @Environment(\.wixalTextSize) private var textSize
    private var role:String{textValue(message["role"])}
    private var messageAttachments:[ChatAttachment]{
        var result=records(message["attachments"]).map(ChatAttachment.init)
        let images=message["images"] as? [String] ?? [];let names=message["imageNames"] as? [String] ?? []
        result += images.enumerated().map{index,image in ChatAttachment(type:"image",name:index<names.count ? names[index] : "Image \(index+1)",base64:image)}
        return result
    }
    var body: some View {
        if role == "tool"{
            DisclosureGroup{Text(textValue(message["content"])).font(.system(size:11,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(.top,8)}label:{HStack{Text(textValue(message["tool_name"]));Spacer();Text("Tool result").foregroundStyle(theme.muted)}}.font(.system(size:11)).padding(12).background(theme.panel,in:RoundedRectangle(cornerRadius:8)).overlay(RoundedRectangle(cornerRadius:8).stroke(theme.line,lineWidth:1)).padding(.vertical,5)
        }else{
            HStack{
                if role == "user"{Spacer(minLength:50)}
                VStack(alignment:.leading,spacing:12){
                    HStack(spacing:8){Text(role=="user" ? "▸ You" : "Wixal").font(.system(size:11)).foregroundStyle(role=="user" ? theme.muted : theme.accent);if let time=message["created"] as? Double{Text(Date(timeIntervalSince1970:time/1000),style:.time).font(.system(size:9)).foregroundStyle(theme.muted)};Spacer();Button{NSPasteboard.general.clearContents();NSPasteboard.general.setString(textValue(message["content"]),forType:.string)}label:{Image(systemName:"doc.on.doc").font(.system(size:10))}.buttonStyle(.plain).foregroundStyle(theme.muted).help("Copy message").accessibilityLabel("Copy \(role == "user" ? "your" : "Wixal") message")}
                    if role=="user", !messageAttachments.isEmpty{AttachmentStrip(attachments:messageAttachments,engine:engine)}
                    if role=="user"{Text(textValue(message["displayContent"] ?? message["content"])).font(.system(size:textSize)).lineSpacing(6).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}else{MarkdownMessage(content:textValue(message["content"]))}
                    if role=="assistant",!records(message["memoryEvidence"]).isEmpty {
                        DisclosureGroup("Memory references · \(records(message["memoryEvidence"]).count)") {
                            ForEach(Array(records(message["memoryEvidence"]).enumerated()),id:\.offset){_,item in
                                VStack(alignment:.leading,spacing:6){Text("\(textValue(item["scope"]).capitalized) · \(textValue(item["kind"])) · source: \(textValue(item["sourceRole"]))").foregroundStyle(theme.muted);Text(textValue(item["excerpt"])).textSelection(.enabled);if let engine,!textValue(item["sourceSession"]).isEmpty{Button("Open source conversation ↗"){engine.openMemorySource(textValue(item["sourceSession"]))}.buttonStyle(.plain).foregroundStyle(theme.accent).disabled(engine.busy)}}.padding(.vertical,6)
                            }
                        }.font(.system(size:11)).padding(.top,4)
                    }
                    if let usage=message["usage"] as? [String:Any], let count=usage["eval_count"] as? Int{HStack(spacing:12){Text("\(count) tokens");if let rate=usage["tokensPerSecond"] as? Double{Text(String(format:"%.1f tokens/s",rate))};if let seconds=usage["elapsedSeconds"] as? Double{Text(String(format:"%.1fs",seconds))}}.font(.system(size:9,design:.monospaced)).foregroundStyle(theme.muted)}
                }.padding(role=="user" ? 18 : 0).frame(maxWidth:role=="user" ? 650 : .infinity,alignment:.leading).background(role=="user" ? theme.panel : .clear,in:RoundedRectangle(cornerRadius:10)).overlay(RoundedRectangle(cornerRadius:10).stroke(role=="user" ? theme.line : .clear,lineWidth:1))
            }.padding(.vertical,role=="user" ? 12 : 24)
        }
    }
}
struct ReviewView: View {
    @ObservedObject var engine:EngineClient
    let review:Review
    @Environment(\.wixalTheme) private var theme
    private var name:String{textValue(review.details["name"])}
    private var fileAction:Bool{["write_file","edit_file","make_directory"].contains(name)}
    private var command:String{textValue(review.details["command"])}
    private var title:String{switch name{case "write_file":return "Review file write";case "edit_file":return "Review file edit";case "make_directory":return "Review new directory";case "command_start","run_command","command_write":return "Review command";case "save_memory":return "Review saved memory";case "network_scan":return "Review network scan";case "website_assess","website_simulate":return "Review website assessment";default:return "Review " + name.replacingOccurrences(of:"_",with:" ")}}
    var body:some View{
        VStack(alignment:.leading,spacing:16){
            Label(title,systemImage:"checkmark.shield").font(.system(size:22,weight:.medium))
            Text(fileAction ? "Check the destination and content below. Approval applies to this exact action." : !command.isEmpty ? "This command will run in your project folder. Check the full command before allowing it." : "Inspect the target and requested action before allowing it.").font(.system(size:13)).foregroundStyle(theme.muted)
            ScrollView{VStack(alignment:.leading,spacing:16){
                if !textValue(review.details["path"]).isEmpty{Label(textValue(review.details["path"]),systemImage:"doc").font(.system(size:12,design:.monospaced)).textSelection(.enabled)}
                if !command.isEmpty{Text(command).font(.system(size:13,design:.monospaced)).textSelection(.enabled).padding(14).frame(maxWidth:.infinity,alignment:.leading).background(theme.inset,in:RoundedRectangle(cornerRadius:8));if !textValue(review.details["root"]).isEmpty{Text("Working folder: " + textValue(review.details["root"])).font(.system(size:11)).foregroundStyle(theme.muted).textSelection(.enabled)}}
                if fileAction{if name != "make_directory"{HStack(alignment:.top,spacing:12){preview("Before",text:textValue(review.details["before"]));preview("After",text:textValue(review.details["content"]))}}}
                else if name=="save_memory"{Text(textValue(review.details["content"])).textSelection(.enabled).padding(14).frame(maxWidth:.infinity,alignment:.leading).background(theme.inset,in:RoundedRectangle(cornerRadius:8))}
                else{ForEach(Array(review.details.filter{$0.key != "id" && $0.key != "name" && $0.key != "command" && $0.key != "root"}.keys.sorted()),id:\.self){key in VStack(alignment:.leading,spacing:5){Text(key.replacingOccurrences(of:"_",with:" ").capitalized).font(.system(size:10,weight:.medium)).foregroundStyle(theme.muted);Text(review.details[key] as? String ?? pretty(review.details[key] ?? "")).font(.system(size:12,design:.monospaced)).textSelection(.enabled)}.padding(10).frame(maxWidth:.infinity,alignment:.leading).background(theme.inset,in:RoundedRectangle(cornerRadius:6))}}
            }}
            HStack{Button("Decline",role:.cancel){engine.respond(false)}.buttonStyle(WixalButtonStyle(outlined:true));Spacer();Button("Approve"){engine.respond(true)}.buttonStyle(.borderedProminent).keyboardShortcut(.return)}
        }.padding(24).frame(width:min(720, (NSApp.keyWindow?.frame.width ?? 1000)-60),height:min(560, (NSApp.keyWindow?.frame.height ?? 680)-80)).background(theme.panel).interactiveDismissDisabled()
    }
    private func preview(_ label:String,text:String)->some View{VStack(alignment:.leading,spacing:8){Text(label).font(.system(size:11,weight:.medium));Text(text.isEmpty ? "(empty)" : text).font(.system(size:11,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}.padding(12).frame(maxWidth:.infinity,alignment:.topLeading).background(theme.inset,in:RoundedRectangle(cornerRadius:8))}
}
