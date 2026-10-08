import Foundation

public struct TimelineMilestone: Identifiable, Equatable {
    public let id: String
    public let title: String
    public let subtitle: String
    public let status: String
    public let command: String
    public let output: String
    public var turn: Int = 0
    public var rawEvents: [String] = []
    public var updates: [String] = []
    public var name:String = ""
}

/// A stable projection of persisted messages. A call and its results are one action.
public enum TimelineHistory {
    private static func textValue(_ value:Any?)->String{value as? String ?? ""}
    private static func records(_ value:Any?)->[[String:Any]]{value as? [[String:Any]] ?? []}
    private static func pretty(_ value:Any)->String{guard JSONSerialization.isValidJSONObject(value),let data=try? JSONSerialization.data(withJSONObject:value,options:[.prettyPrinted,.sortedKeys]),let text=String(data:data,encoding:.utf8) else{return String(describing:value)};return text}
    public static func decode(_ value:Any?) -> [String:Any] {
        if let object=value as? [String:Any] {return object}
        guard let text=value as? String,let data=text.data(using:.utf8) else{return [:]}
        return (try? JSONSerialization.jsonObject(with:data)) as? [String:Any] ?? [:]
    }
    public static func resultStatus(_ text:String)->String {
        let value=decode(text),state=textValue(value["state"])
        let readable=(try? JSONSerialization.jsonObject(with:Data(text.utf8),options:.fragmentsAllowed)) as? String ?? text
        if state=="cancelled" || textValue(value["status"])=="cancelled" {return "cancelled"}
        if readable.hasPrefix("User declined") {return "declined"}
        if readable.hasPrefix("Execution interrupted") {return "interrupted"}
        if readable.hasPrefix("Error:") || value["error"] != nil || state=="failed" || textValue(value["status"])=="failed" || (value["exitCode"] as? Int ?? 0) != 0 || (value["status"] as? Int ?? 0)>=400 {return "failed"}
        if value["stopped"] as? Bool == true || state=="stopped" {return "stopped"}
        return state=="running" ? "running" : "completed"
    }
    public static func milestones(messages:[[String:Any]],tasks:[[String:Any]],sessionID:String,busy:Bool,review:[String:Any]?,activeTool:[String:Any]=[:]) -> [TimelineMilestone] {
        var rows:[TimelineMilestone]=[],turn=0,updates:[String]=[],sessions:[String:Int]=[:],pending:[String:[Int]]=[:]
        let related=tasks.filter{textValue($0["sessionId"])==sessionID}
        let checkpoints=related.flatMap{records($0["checkpoints"])}
        let checkpointsByID=Dictionary(checkpoints.map{(textValue($0["id"]),$0)},uniquingKeysWith:{_,latest in latest})
        let finalTurn=messages.reduce(0){$0 + (textValue($1["role"])=="user" ? 1 : 0)}
        for (index,message) in messages.enumerated() {
            let role=textValue(message["role"]),content=textValue(message["content"])
            if role=="user" {turn+=1;updates=[];sessions=[:];pending=[:];rows.append(TimelineMilestone(id:"\(sessionID):request:\(index)",title:"Request \(turn)",subtitle:String(content.prefix(70)),status:busy && index==messages.indices.last ? "running" : "completed",command:content,output:"",turn:turn));continue}
            if role=="assistant" {
                if !content.isEmpty {updates.append(content)}
                if records(message["tool_calls"]).isEmpty,let request=rows.indices.last(where:{rows[$0].turn==turn && rows[$0].id.contains(":request:")}) {
                    let old=rows[request];rows[request]=TimelineMilestone(id:old.id,title:old.title,subtitle:old.subtitle,status:"completed",command:old.command,output:content,turn:turn)
                }
                for (offset,call) in records(message["tool_calls"]).enumerated() {
                    let function=decode(call["function"]),args=decode(function["arguments"]),name=textValue(function["name"])
                    let callID=textValue(call["id"]),id=callID.isEmpty ? "\(sessionID):\(index):\(offset)" : callID
                    let checkpoint=checkpointsByID[id]
                    let checkpointStatus=textValue(checkpoint?["status"])
                    let awaiting=review != nil && textValue(review?["name"])==name && turn==finalTurn
                    let running=busy && textValue(activeTool["name"])==name && turn==finalTurn
                    let status=awaiting ? "awaiting review" : running ? "running" : checkpointStatus=="error" ? "failed" : checkpointStatus=="cancelled" ? "cancelled" : checkpointStatus=="interrupted" ? "interrupted" : checkpointStatus=="started" ? (busy ? "running" : "interrupted") : busy && turn==finalTurn ? "pending" : "no result"
                    let title=textValue(args["path"]).isEmpty ? name.replacingOccurrences(of:"_",with:" ").capitalized : "\(name.replacingOccurrences(of:"_",with:" ").capitalized) · \(textValue(args["path"]))"
                    pending[name,default:[]].append(rows.count)
                    rows.append(TimelineMilestone(id:id,title:title,subtitle:"Request \(turn)",status:status,command:textValue(args["command"]).isEmpty ? pretty(args) : textValue(args["command"]),output:"",turn:turn,rawEvents:[pretty(call)],updates:updates,name:name))
                }
            }
            if role=="tool" {
                let name=textValue(message["tool_name"]),id=textValue(message["toolCallId"]),value=decode(content),jobID=textValue(value["session_id"])
                let exact=id.isEmpty ? nil : rows.indices.first{rows[$0].id==id}
                let match=exact ?? pending[name]?.first
                if let match {pending[name]?.removeAll{$0==match}}
                let original=jobID.isEmpty ? nil : sessions[jobID]
                var target=original ?? match
                if target==nil {rows.append(TimelineMilestone(id:"\(sessionID):result:\(index)",title:name.replacingOccurrences(of:"_",with:" ").capitalized,subtitle:"Request \(turn)",status:"completed",command:"",output:"",turn:turn,updates:updates));target=rows.count-1}
                guard let target else{continue}
                var actual=target
                if let original,let match,original != match {
                    rows.remove(at:match);if actual>match{actual-=1}
                    sessions=sessions.mapValues{$0>match ? $0-1 : $0}
                    pending=pending.mapValues{$0.map{$0>match ? $0-1 : $0}}
                }
                let old=rows[actual]
                let readable=textValue(value["output"] ?? value["stdout"] ?? value["text"] ?? value["content"])
                let output=readable.isEmpty ? content : readable
                let combined=evidence(old.rawEvents+[content],fallback:output)
                rows[actual]=TimelineMilestone(id:old.id,title:old.title,subtitle:old.subtitle,status:resultStatus(content),command:textValue(value["command"]).isEmpty ? old.command : textValue(value["command"]),output:combined,turn:turn,rawEvents:old.rawEvents+[content],updates:old.updates,name:name)
                if !jobID.isEmpty {sessions[jobID]=actual}
            }
        }
        return rows
    }
    private static func evidence(_ events:[String],fallback:String)->String {
        let outputs=events.map(decode).filter{$0["output"] is String}
        guard !outputs.isEmpty else{return fallback}
        let ranges=outputs.allSatisfy{$0["offset"] is Int} ? outputs.sorted{($0["offset"] as! Int)<($1["offset"] as! Int)} : outputs
        var seen=Set<String>(),covered:Int?,text=""
        for range in ranges {
            let value=textValue(range["output"]),offset=range["offset"] as? Int
            let key="\(offset ?? -1):\(value)"
            guard seen.insert(key).inserted else{continue}
            if let offset {
                let count=(value as NSString).length,end=offset+count
                if let covered,end<=covered{continue}
                if let covered,offset>covered{text+="\n[Gap in captured output]\n"}
                let start=max(0,(covered ?? offset)-offset)
                text+=(value as NSString).substring(from:min(start,count));covered=end
            }else{text+=value}
        }
        if resultStatus(fallback)=="failed" || resultStatus(fallback)=="declined" {text+="\n"+fallback}
        return text.isEmpty ? "(No output)" : text
    }
}
