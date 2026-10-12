import SwiftUI

struct EngagementAssuranceView:View {
    @ObservedObject var engine:EngineClient
    let engagement:[String:Any]
    let perform:(String,[String:Any])->Void
    @ViewState private var section="API checks"
    @ViewState private var target=""
    @ViewState private var label=""
    @ViewState private var token=""
    @ViewState private var credential=""
    @ViewState private var paths="/"
    @ViewState private var purpose="Observe the selected API paths under the declared identity"
    @ViewState private var objective=""
    @ViewState private var validator="api_access_boundary"
    @ViewState private var pointer="/private"
    @ViewState private var expected="true"
    @ViewState private var allowed=""
    @ViewState private var denied="anonymous"
    @ViewState private var port=443
    @ViewState private var positiveState="open"
    @ViewState private var baselineState="closed"
    @ViewState private var header="x-content-type-options"
    @ViewState private var contract=""
    @ViewState private var positive=""
    @ViewState private var baseline=""
    @ViewState private var importPath=""
    @ViewState private var telemetry=""
    @ViewState private var run=""
    @ViewState private var eventType="network_connection"
    @ViewState private var localError=""
    @Environment(\.wixalTheme) private var theme
    private var id:String{engagementText(engagement["id"])}
    private func rows(_ key:String)->[[String:Any]]{records(engine.state[key]).filter{engagementText($0["engagementId"]) == id && engagementText($0["projectId"]) == engagementText(engagement["projectId"])}}
    private var targets:[[String:Any]]{records(engine.state["securityTargets"]).filter{(engagement["targetIds"] as? [String] ?? []).contains(engagementText($0["id"]))}}
    private var credentials:[[String:Any]]{rows("securityCredentials").filter{!($0["revoked"] as? Bool ?? false)}}
    private var closed:Bool{["completed","closed_incomplete","cancelled"].contains(engagementText(engagement["status"]))}
    private func picker(_ title:String,_ selection:Binding<String>,_ items:[[String:Any]])->some View {
        Picker(title,selection:selection){Text("Choose…").tag("");ForEach(items,id:\.engagementID){row in Text(engagementText(row["label"] ?? row["title"] ?? row["name"] ?? row["address"] ?? row["validator"] ?? row["sensor"] ?? row["id"])).tag(engagementText(row["id"]))}}
    }
    private func field(_ title:String,_ value:Binding<String>)->some View {
        VStack(alignment:.leading,spacing:5){Text(title).foregroundStyle(theme.muted);TextField(title,text:value).wixalField().accessibilityLabel(title)}
    }
    var body:some View {
        VStack(alignment:.leading,spacing:16){
            Text("Validation and identities").wixalFont(size:18,weight:.medium)
            Picker("Assurance view",selection:$section){ForEach(["API checks","Identities","Validation","Defensive evidence","Imports"],id:\.self){Text($0)}}
            if !localError.isEmpty{Text(localError).foregroundStyle(.orange)}
            switch section {
            case "Identities":identities
            case "Validation":validation
            case "Defensive evidence":defensive
            case "Imports":imports
            default:api
            }
        }.padding(.vertical,14).wixalFont(size:12).buttonStyle(WixalButtonStyle())
        .onChange(of:id){_,_ in token="";target="";credential="";objective="";contract="";positive="";baseline="";telemetry="";run=""}
        .onDisappear{token=""}
    }
    private var identities:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Bearer tokens stay in macOS Keychain. Leases are bound to a target and scope revision, expire after one hour or at the testing-window end, and require review before use.").foregroundStyle(theme.muted)
            picker("Target",$target,targets.filter{engagementText($0["type"]) == "Website / API"})
            field("Identity label",$label)
            Text("Bearer token").foregroundStyle(theme.muted)
            SecureField("Bearer token",text:$token).wixalField().accessibilityLabel("Identity bearer token")
            Button("Review and save identity lease"){
                let secret=token;token=""
                perform("security-credential-save",["targetId":target,"label":label,"secret":secret,"seconds":3600])
            }.disabled(closed || target.isEmpty || label.isEmpty || token.isEmpty)
            ForEach(rows("securityCredentials"),id:\.engagementID){row in
                HStack{VStack(alignment:.leading){Text(engagementText(row["label"]));Text((row["revoked"] as? Bool ?? false) ? "Revoked" : "Scope revision \(engagementText(row["scopeRevision"])) · expires \(Date(timeIntervalSince1970:(row["expires"] as? Double ?? 0)/1000).formatted())").foregroundStyle(theme.muted)};Spacer();Button("Revoke"){perform("security-credential-revoke",["credentialId":engagementText(row["id"])])}.disabled(closed || (row["revoked"] as? Bool ?? false))}.wixalCard()
            }
        }
    }
    private var api:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Queue one bounded recon assignment. GET requests use the selected target origin, no redirects and no cookie session. Each identity use has its own review.").foregroundStyle(theme.muted)
            picker("API target",$target,targets.filter{engagementText($0["type"]) == "Website / API"})
            Picker("Identity",selection:$credential){Text("Anonymous").tag("");ForEach(credentials,id:\.engagementID){row in Text(engagementText(row["label"])).tag(engagementText(row["id"]))}}
            Text("Same-origin paths, one per line").foregroundStyle(theme.muted)
            TextField("Same-origin paths, one per line",text:$paths,axis:.vertical).wixalField()
            field("Operation purpose",$purpose)
            Button("Queue reviewed API observation"){
                perform("security-specialist-operate",["role":"recon_operator","capability":"api_observe","targetId":target,"question":purpose,"arguments":["paths":paths.split(separator:"\n").map(String.init),"credentialId":credential]])
            }.disabled(closed || target.isEmpty || paths.isEmpty || purpose.isEmpty)
        }
    }
    private var validation:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Define the exact requirement before evaluating two independently collected runs. A validated requirement applies to its declared access boundary, port state or response header.").foregroundStyle(theme.muted)
            picker("Objective",$objective,rows("securityObjectives").filter{engagementText($0["status"]) != "superseded"})
            Picker("Contract",selection:$validator){Text("API access boundary").tag("api_access_boundary");Text("Network port state").tag("network_port_state");Text("Response header").tag("website_header_value")}
            if validator == "network_port_state" {
                field("Observed host",$paths);Stepper("Port \(port)",value:$port,in:1...65535)
                Picker("Positive state",selection:$positiveState){ForEach(["open","closed","filtered"],id:\.self){Text($0)}}
                Picker("Baseline state",selection:$baselineState){ForEach(["open","closed","filtered"],id:\.self){Text($0)}}
            }else {
                field("Exact response path",$paths)
                if validator == "api_access_boundary" {
                    picker("Allowed identity",$allowed,credentials)
                    Picker("Denied identity",selection:$denied){Text("Anonymous").tag("anonymous");ForEach(credentials,id:\.engagementID){row in Text(engagementText(row["label"])).tag(engagementText(row["id"]))}}
                    field("JSON signal location, for example /private",$pointer)
                    field("Expected JSON scalar, for example true",$expected)
                }else {field("Response header name",$header);field("Expected header value",$expected)}
            }
            Button("Save validation contract"){
                var config:[String:Any]
                if validator == "api_access_boundary" {
                    guard let data=expected.data(using:.utf8),let scalar=try? JSONSerialization.jsonObject(with:data,options:.fragmentsAllowed) else{localError="Use a JSON scalar for the expected signal.";return}
                    config=["path":paths,"pointer":pointer,"expected":scalar,"allowedIdentityId":allowed,"deniedIdentityId":denied]
                }else if validator == "network_port_state"{config=["host":paths,"port":port,"positiveState":positiveState,"baselineState":baselineState]}
                else{config=["path":paths,"header":header,"expected":expected]}
                perform("security-contract-validator-save",["objectiveId":objective,"validator":validator,"config":config])
            }.disabled(closed || objective.isEmpty)
            Divider();picker("Saved contract",$contract,rows("securityValidationContracts"))
            picker("Positive run evidence",$positive,rows("securityEvidence").filter{engagementText($0["kind"]) == "run"})
            picker("Control run evidence",$baseline,rows("securityEvidence").filter{engagementText($0["kind"]) == "run"})
            Button("Evaluate retained observations"){perform("security-contract-validator-run",["contractId":contract,"evidenceIds":[positive,baseline]])}.disabled(closed || contract.isEmpty || positive.isEmpty || baseline.isEmpty || positive == baseline)
            ForEach(rows("securityVerifications").filter{$0["contractId"] != nil},id:\.engagementID){row in Text(engagementText(row["validator"])+" · "+engagementText(row["status"])).wixalCard()}
        }
    }
    private var defensive:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Import sensor JSON with sensor, starts, ends and events. Each event needs time, runId and type. Declared coverage without a matching event is ‘not observed’; missing coverage remains ‘unknown’. Imported sensor claims retain their external provenance.").foregroundStyle(theme.muted)
            field("Telemetry JSON path inside project",$importPath)
            Button("Import defensive evidence"){perform("security-telemetry-import",["path":importPath])}.disabled(closed || importPath.isEmpty)
            picker("Sensor observation",$telemetry,rows("securityTelemetry"));picker("Operation",$run,rows("securityRuns"))
            field("Expected event type",$eventType)
            Button("Correlate operation and sensor coverage"){perform("security-telemetry-correlate",["telemetryId":telemetry,"runId":run,"eventType":eventType])}.disabled(closed || telemetry.isEmpty || run.isEmpty || eventType.isEmpty)
            ForEach(rows("securityEngagementEvents").filter{engagementText($0["kind"]) == "defensive_correlation"},id:\.engagementID){row in let detail=row["detail"] as? [String:Any] ?? [:];Text(engagementText(detail["expected"])+" · "+engagementText(detail["status"])).wixalCard()}
        }
    }
    private var imports:some View {
        VStack(alignment:.leading,spacing:12){Text("Import a structured JSON export containing a findings array with title and status. External statuses are retained as unverified claims; scope, approvals, commands and confirmed findings are never inherited.").foregroundStyle(theme.muted);field("Export JSON path inside project",$importPath);Button("Import external claims"){perform("security-engagement-structured-import",["path":importPath])}.disabled(closed || importPath.isEmpty)}
    }
}
