import Foundation
import WixalActivity

func activityRegressionChecks() throws -> Int {
    func encoded(_ value:[String:Any]) throws -> String {String(data:try JSONSerialization.data(withJSONObject:value),encoding:.utf8)!}
    func call(_ id:String,_ name:String)->[String:Any]{["role":"assistant","tool_calls":[["id":id,"function":["name":name,"arguments":[:]]]]]}
    func result(_ id:String,_ name:String,_ value:[String:Any]) throws -> [String:Any]{["role":"tool","toolCallId":id,"tool_name":name,"content":try encoded(value)]}
    let messages:[[String:Any]] = [
        ["role":"user","content":"Inspect the actual output"],
        call("scan","network_scan"),try result("scan","network_scan",["session_id":"job","state":"running"]),
        call("read-one","network_read"),try result("read-one","network_read",["session_id":"job","state":"running","output":"😀A","offset":0]),
        call("read-two","network_read"),try result("read-two","network_read",["session_id":"job","state":"completed","exitCode":0,"output":"Aβ","offset":2]),
        call("failed","run_command"),try result("failed","run_command",["state":"completed","exitCode":2,"output":"REAL ERROR"]),
        call("pending","write_file")
    ]
    let tasks:[[String:Any]] = [["sessionId":"regression","checkpoints":[["id":"pending","status":"started"]]]]
    let rows=TimelineHistory.milestones(messages:messages,tasks:tasks,sessionID:"regression",busy:false,review:nil)
    guard rows==TimelineHistory.milestones(messages:messages,tasks:tasks,sessionID:"regression",busy:false,review:nil),Set(rows.map(\.id)).count==rows.count else{throw CocoaError(.coderInvalidValue)}
    guard rows.count==4,rows.first(where:{$0.id=="scan"})?.output=="😀Aβ",rows.first(where:{$0.id=="scan"})?.status=="completed" else{throw CocoaError(.coderInvalidValue)}
    guard rows.first(where:{$0.id=="failed"})?.status=="failed",rows.first(where:{$0.id=="pending"})?.status=="interrupted" else{throw CocoaError(.coderInvalidValue)}
    for (key,value,expected) in [("status","queued","queued"),("state","paused","paused"),("status","needs_attention","needs attention"),("state","interrupted","interrupted"),("status","waiting_review","waiting review"),("status","waiting_model","waiting model"),("status","running","running"),("status","stopped","stopped")]{
        guard TimelineHistory.resultStatus(try encoded([key:value]))==expected else{throw CocoaError(.coderInvalidValue)}
    }
    return 15
}
