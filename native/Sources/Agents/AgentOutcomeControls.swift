import SwiftUI

indirect enum AgentCheckValue: Codable, Equatable {
    case string(String), number(Double), bool(Bool), array([AgentCheckValue]), object([String:AgentCheckValue]), null
    init(from decoder:Decoder) throws {
        let c=try decoder.singleValueContainer()
        if c.decodeNil(){self = .null}
        else if let v=try? c.decode(Bool.self){self = .bool(v)}
        else if let v=try? c.decode(Double.self){self = .number(v)}
        else if let v=try? c.decode(String.self){self = .string(v)}
        else if let v=try? c.decode([AgentCheckValue].self){self = .array(v)}
        else{self = .object(try c.decode([String:AgentCheckValue].self))}
    }
    func encode(to encoder:Encoder) throws {
        var c=encoder.singleValueContainer()
        switch self{case .string(let v):try c.encode(v);case .number(let v):try c.encode(v);case .bool(let v):try c.encode(v);case .array(let v):try c.encode(v);case .object(let v):try c.encode(v);case .null:try c.encodeNil()}
    }
    var text:String{if case .string(let v)=self{return v};return json}
    var json:String{String(data:(try? JSONEncoder().encode(self)) ?? Data(),encoding:.utf8) ?? "null"}
}
struct AgentSuccessCheck:Codable,Equatable {
    var kind="file_exists"
    var path:String?=""
    var value:AgentCheckValue?=nil
    var pointer:String?=nil
    var command:String?=nil
    var tool:String?=nil
    var label:String?=nil
    var sourcePath:String?=nil
    var sourcePointer:String?=nil
    var transform:String?=nil
}
struct AgentAuthorityDraft:Codable,Equatable {
    var writePaths:[String]?=[]
    var commands:[String]?=[]
    var targets:[String]?=[]
}
struct AgentJSONCheckField:View{
    @Binding var value:AgentCheckValue?
    @ViewState private var input=""
    var body:some View{VStack(alignment:.leading,spacing:5){TextField("Expected JSON value, e.g. 21",text:$input).wixalField().accessibilityLabel("Expected JSON value");if !input.isEmpty && value==nil{Text("Enter valid JSON, including quotes for text values.").wixalFont(size:10).foregroundStyle(.orange)}}.onAppear{input=value?.json ?? ""}.onChange(of:input){_,text in value=text.data(using:.utf8).flatMap{try? JSONDecoder().decode(AgentCheckValue.self,from:$0)}}}
}
struct AgentChecksEditor:View {
    @Binding var checks:[AgentSuccessCheck]
    @Environment(\.wixalTheme) private var theme
    private let kinds=["file_exists","file_contains","json_equals","command_exit","tool_succeeded","tool_contains"]
    var body:some View{VStack(alignment:.leading,spacing:12){
        HStack{Text("Success checks").wixalFont(size:14,weight:.medium);Spacer();Button("Add check"){checks.append(AgentSuccessCheck())}.disabled(checks.count>=20).buttonStyle(WixalButtonStyle(outlined:true))}
        Text("The engine checks these outcomes after the agent finishes. Without checks, a finished response remains unverified.").wixalFont(size:11).foregroundStyle(theme.muted)
        ForEach(checks.indices,id:\.self){i in VStack(alignment:.leading,spacing:8){
            HStack{Picker("Check \(i+1)",selection:$checks[i].kind){ForEach(kinds,id:\.self){Text($0.replacingOccurrences(of:"_",with:" ")).tag($0)}};Button("Remove",role:.destructive){checks.remove(at:i)}.buttonStyle(WixalButtonStyle())}
            if ["file_exists","file_contains","json_equals"].contains(checks[i].kind){TextField("Project-relative file path",text:Binding(get:{checks[i].path ?? ""},set:{checks[i].path=$0})).wixalField().accessibilityLabel("Check artifact path")}
            if checks[i].kind=="command_exit"{TextField("Exact test command",text:Binding(get:{checks[i].command ?? ""},set:{checks[i].command=$0})).wixalField().accessibilityLabel("Verification command")}
            if ["tool_succeeded","tool_contains"].contains(checks[i].kind){TextField("Tool name",text:Binding(get:{checks[i].tool ?? ""},set:{checks[i].tool=$0})).wixalField().accessibilityLabel("Required tool")}
            if ["file_contains","tool_contains"].contains(checks[i].kind){TextField("Required evidence text",text:Binding(get:{checks[i].value?.text ?? ""},set:{checks[i].value = .string($0)})).wixalField().accessibilityLabel("Required evidence text")}
            if checks[i].kind=="json_equals"{TextField("JSON pointer, e.g. /total",text:Binding(get:{checks[i].pointer ?? ""},set:{checks[i].pointer=$0})).wixalField();AgentJSONCheckField(value:$checks[i].value)}
        }.wixalCard()}
    }.wixalFont(size:12)}
}
struct AgentAuthorityEditor:View {
    @Binding var authority:AgentAuthorityDraft
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:12){
        Text("Approved scope").wixalFont(size:14,weight:.medium)
        Text("The model chooses tools. These boundaries authorise specific effects, including during a scheduled run. Leave a field empty to require review.").wixalFont(size:11).foregroundStyle(theme.muted)
        lines("Permitted report files or folders",hint:"reports/\nsummary.md",values:Binding(get:{authority.writePaths ?? []},set:{authority.writePaths=$0}))
        lines("Exact approved commands",hint:"python3 -m unittest discover",values:Binding(get:{authority.commands ?? []},set:{authority.commands=$0}))
        lines("Authorised target origins, hosts or IP ranges",hint:"https://lab.example.test\n127.0.0.1",values:Binding(get:{authority.targets ?? []},set:{authority.targets=$0}))
    }}
    private func lines(_ title:String,hint:String,values:Binding<[String]>)->some View{AgentAuthorityLines(title:title,hint:hint,values:values)}
}
struct AgentAuthorityLines:View{
    let title:String
    let hint:String
    @Binding var values:[String]
    @ViewState private var input=""
    @Environment(\.wixalTheme) private var theme
    var body:some View{VStack(alignment:.leading,spacing:6){Text(title).wixalFont(size:12);TextEditor(text:$input).scrollContentBackground(.hidden).wixalFont(size:11,design:.monospaced).padding(8).frame(height:70).background(theme.raised,in:RoundedRectangle(cornerRadius:8)).accessibilityLabel(title);Text(hint).wixalFont(size:10).foregroundStyle(theme.muted)}.onAppear{input=values.joined(separator:"\n")}.onChange(of:input){_,text in values=text.components(separatedBy:"\n").filter{!$0.trimmingCharacters(in:.whitespaces).isEmpty}}}
}
func agentOutcomeLabel(_ run:[String:Any])->String {
    let status=textValue(run["status"]),verification=run["verification"] as? [String:Any] ?? [:]
    if status=="completed"{return textValue(verification["status"])=="passed" ? "Verified" : "Finished · unverified"}
    return status.replacingOccurrences(of:"_",with:" ").capitalized
}
