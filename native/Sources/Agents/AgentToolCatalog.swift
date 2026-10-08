import SwiftUI

// Inspection only: the Agents UI never changes the runtime tool allowlist.
struct AgentToolCatalog:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    @ViewState private var query=""
    private var discovered:[[String:Any]] {
        engine.tools.compactMap{$0["function"] as? [String:Any]}.filter{
            query.isEmpty || textValue($0["name"]).localizedCaseInsensitiveContains(query) || textValue($0["description"]).localizedCaseInsensitiveContains(query)
        }
    }
    var body:some View {VStack(alignment:.leading,spacing:18){
        WixalSection(title:"Model chooses tools",detail:"The agent reads each tool's purpose and inputs, selects the tools the task needs, and uses their results to decide its next step."){
            Label("Automatic selection",systemImage:"sparkles").wixalFont(size:13,weight:.medium)
            Text("Tool discovery comes from the workspace and its connected services. You give the agent a goal; its activity shows the tools it chose, the requests it made and their results.").wixalFont(size:12).foregroundStyle(theme.muted)
        }
        WixalSection(title:"Discovered tools",detail:"Live workspace inventory · Inspection only. Saved-agent runs discover and choose tools automatically."){
            TextField("Find a tool by name or purpose",text:$query).wixalField().accessibilityLabel("Search discovered tools")
            if engine.tools.isEmpty {Text("Waiting for the workspace tool inventory. No availability is assumed.").wixalFont(size:12).foregroundStyle(theme.muted)}
            else if discovered.isEmpty {Text("No tools match this search.").wixalFont(size:12).foregroundStyle(theme.muted)}
            ForEach(Array(discovered.enumerated()),id:\.offset){_,tool in
                let name=textValue(tool["name"])
                DisclosureGroup {
                    VStack(alignment:.leading,spacing:10){
                        Text(textValue(tool["description"])).wixalFont(size:12).textSelection(.enabled)
                        Text("Inputs").wixalFont(size:11,weight:.medium)
                        Text(pretty(tool["parameters"] ?? [:])).wixalFont(size:10,design:.monospaced).textSelection(.enabled)
                        Text("Discovered · The model can select this tool within its task scope").wixalFont(size:11).foregroundStyle(theme.muted)
                    }.padding(.top,10)
                } label:{Label(name,systemImage:"wrench.and.screwdriver").wixalFont(size:12)}.wixalCard()
            }
        }
        WixalSection(title:"Tool usage",detail:"Runs retain tool requests and results in its activity."){
            Text("Inspect Runs to see tool requests, results and errors recorded by the engine.").wixalFont(size:12).foregroundStyle(theme.muted)
        }
    }}
}
