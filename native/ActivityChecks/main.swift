import Foundation
import WixalActivity
let input=FileHandle.standardInput.readDataToEndOfFile()
let payload=try JSONSerialization.jsonObject(with:input) as! [String:Any]
let messages=payload["messages"] as! [[String:Any]]
let first=TimelineHistory.milestones(messages:messages,tasks:payload["tasks"] as? [[String:Any]] ?? [],sessionID:payload["sessionID"] as? String ?? "acceptance",busy:false,review:nil)
let second=TimelineHistory.milestones(messages:messages,tasks:payload["tasks"] as? [[String:Any]] ?? [],sessionID:payload["sessionID"] as? String ?? "acceptance",busy:false,review:nil)
guard first==second,Set(first.map(\.id)).count==first.count else{fatalError("Unstable or duplicate milestone identity")}
let rows=first.map{["id":$0.id,"title":$0.title,"status":$0.status,"command":$0.command,"output":$0.output,"turn":$0.turn,"events":$0.rawEvents] as [String:Any]}
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:rows))
