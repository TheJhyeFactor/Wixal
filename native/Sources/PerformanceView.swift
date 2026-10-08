import SwiftUI

struct PerformanceView:View {
    @ObservedObject var engine:EngineClient
    @Environment(\.wixalTheme) private var theme
    private var saved:[[String:Any]]{records(engine.state["usage"])}
    private var chat:[[String:Any]]{saved.filter{textValue($0["sessionId"])==textValue(engine.state["activeSession"])}}
    private func total(_ rows:[[String:Any]],_ key:String)->String {
        let values=rows.compactMap{($0[key] as? NSNumber)?.intValue}
        return values.isEmpty ? "Unavailable" : values.reduce(0,+).formatted()
    }
    private func measurement(_ value:Any?,unit:String)->String {guard let number=value as? NSNumber else{return "Unavailable"};return String(format:"%.2f",number.doubleValue)+unit}
    var body:some View {
        WixalPage(eyebrow:"REPORTED MODEL USAGE",title:"Usage & performance",subtitle:"Generation counters reported by the model engine. Benchmarks remain separate from conversation requests."){
            LazyVGrid(columns:[GridItem(.adaptive(minimum:180))],alignment:.leading,spacing:14){
                metric("Chat input tokens",total(chat,"prompt_eval_count"));metric("Chat output tokens",total(chat,"eval_count"));metric("Saved output tokens",total(saved,"eval_count"));metric("Saved requests",saved.count.formatted());metric("Last generation",measurement(saved.last?["tokensPerSecond"],unit:" tok/s"));metric("First output",measurement(saved.last?["timeToFirstToken"],unit:"s"))
            }
            Text("Saved totals cover the latest 2,000 model requests, including tool steps and summaries. Missing counters remain unavailable. These figures do not measure application startup or UI responsiveness.").wixalFont(size:11).foregroundStyle(theme.muted)
            WixalSection(title:"Recent requests"){
                ForEach(Array(saved.suffix(50).reversed().enumerated()),id:\.offset){_,item in
                    HStack{VStack(alignment:.leading,spacing:5){Text(textValue(item["model"]));Text(textValue(item["kind"]).capitalized).wixalFont(size:10).foregroundStyle(theme.muted)};Spacer();Text(total([item],"prompt_eval_count")+" in · "+total([item],"eval_count")+" out");Text(measurement(item["tokensPerSecond"],unit:" tok/s"))}.wixalFont(size:11).wixalCard()
                }
                if saved.isEmpty{Text("Requests appear here after a model finishes.").foregroundStyle(theme.muted)}
            }
            Button("Open model benchmarks"){NotificationCenter.default.post(name:.wixalNavigate,object:"Models")}.buttonStyle(WixalButtonStyle(outlined:true))
        }
    }
    private func metric(_ label:String,_ value:String)->some View{VStack(alignment:.leading,spacing:10){Text(label).wixalFont(size:11).foregroundStyle(theme.muted);Text(value).wixalFont(size:21,weight:.medium,design:.monospaced)}.frame(maxWidth:.infinity,alignment:.leading).wixalCard()}
}
