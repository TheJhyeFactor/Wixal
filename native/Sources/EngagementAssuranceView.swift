import SwiftUI

struct EngagementAssuranceView:View {
    @ObservedObject var engine:EngineClient
    let engagement:[String:Any]
    let perform:(String,[String:Any])->Void
    @ViewState private var section="API checks"
    @ViewState private var target=""
    @ViewState private var label=""
    @ViewState private var token=""
    @ViewState private var identityKind="bearer"
    @ViewState private var apiMethod="GET"
    @ViewState private var mutationBody="{}"
    @ViewState private var vendor="suricata_eve"
    @ViewState private var coverageStart=""
    @ViewState private var coverageEnd=""
    @ViewState private var controllerPlan=""
    @ViewState private var mutationRun=""
    @ViewState private var beforeState="false"
    @ViewState private var oauthClient=""
    @ViewState private var oauthScope=""
    @ViewState private var authorizationPath="/authorize"
    @ViewState private var tokenPath="/token"
    @ViewState private var authorizationURL=""
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
            Text("Identity secrets stay in macOS Keychain. Leases bind to a target and scope revision and require review before use. OAuth access tokens can be imported from your authorized provider flow.").foregroundStyle(theme.muted)
            picker("Target",$target,targets.filter{engagementText($0["type"]) == "Website / API"})
            field("Identity label",$label)
            Picker("Identity type",selection:$identityKind){Text("Bearer token").tag("bearer");Text("Cookie session").tag("cookie");Text("OAuth access token").tag("oauth_access_token")}
            Text(identityKind == "cookie" ? "Cookie header, for example session=value" : "Access token").foregroundStyle(theme.muted)
            SecureField("Identity secret",text:$token).wixalField().accessibilityLabel("Identity secret")
            Button("Review and save identity lease"){
                let secret=token;token=""
                perform("security-credential-save",["targetId":target,"label":label,"secret":secret,"kind":identityKind,"seconds":3600])
            }.disabled(closed || target.isEmpty || label.isEmpty || token.isEmpty)
            DisclosureGroup("OAuth authorization code with PKCE") {
                Text("Public clients with same-origin authorization and token endpoints. A temporary loopback callback expires after five minutes. Provider registration must allow the returned loopback redirect.").foregroundStyle(theme.muted)
                field("OAuth client ID",$oauthClient);field("OAuth scopes",$oauthScope)
                field("Authorization path",$authorizationPath);field("Token endpoint path",$tokenPath)
                Button("Review OAuth authorization") {
                    Task {do {
                        let result=try await engine.call("security-oauth-start",["engagementId":id,"targetId":target,"label":label,"clientId":oauthClient,"scope":oauthScope,"authorizationPath":authorizationPath,"tokenPath":tokenPath]) as? [String:Any]
                        authorizationURL=engagementText(result?["authorizationUrl"]);localError=""
                    }catch{localError=error.localizedDescription}}
                }.disabled(closed || target.isEmpty || label.isEmpty || oauthClient.isEmpty)
                if let url=URL(string:authorizationURL),!authorizationURL.isEmpty{Link("Continue authorization in browser",destination:url)}
                ForEach(rows("securityOAuthFlows"),id:\.engagementID){row in Text(engagementText(row["label"])+" · "+engagementText(row["status"]))}
            }
            ForEach(rows("securityCredentials"),id:\.engagementID){row in
                HStack{VStack(alignment:.leading){Text(engagementText(row["label"]));Text((row["revoked"] as? Bool ?? false) ? "Revoked" : "Scope revision \(engagementText(row["scopeRevision"])) · expires \(Date(timeIntervalSince1970:(row["expires"] as? Double ?? 0)/1000).formatted())").foregroundStyle(theme.muted)};Spacer();Button("Revoke"){perform("security-credential-revoke",["credentialId":engagementText(row["id"])])}.disabled(closed || (row["revoked"] as? Bool ?? false))}.wixalCard()
            }
        }
    }
    private var api:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Requests stay on the selected target origin without redirects or automatic cookie updates. Identity use and every mutation require review. Mutation effects need separate cleanup inspection.").foregroundStyle(theme.muted)
            picker("API target",$target,targets.filter{engagementText($0["type"]) == "Website / API"})
            Picker("Identity",selection:$credential){Text("Anonymous").tag("");ForEach(credentials,id:\.engagementID){row in Text(engagementText(row["label"])).tag(engagementText(row["id"]))}}
            Picker("HTTP method",selection:$apiMethod){ForEach(["GET","POST","PUT","PATCH","DELETE"],id:\.self){Text($0)}}
            Text(apiMethod == "GET" ? "Same-origin paths, one per line" : "One exact same-origin path").foregroundStyle(theme.muted)
            TextField("Request paths",text:$paths,axis:.vertical).wixalField()
            if apiMethod != "GET" {TextField("JSON request body",text:$mutationBody,axis:.vertical).wixalField().accessibilityLabel("JSON request body")}
            field("Operation purpose",$purpose)
            Button(apiMethod == "GET" ? "Queue reviewed API observation" : "Queue reviewed API mutation"){
                var arguments:[String:Any]=["paths":paths.split(separator:"\n").map(String.init),"credentialId":credential]
                if apiMethod != "GET" {
                    guard let data=mutationBody.data(using:.utf8),let body=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else {localError="Use a JSON object for the mutation body.";return}
                    arguments=["path":paths,"method":apiMethod,"body":body,"credentialId":credential]
                }
                localError=""
                perform("security-specialist-operate",["role":apiMethod == "GET" ? "recon_operator" : "api_operator","capability":apiMethod == "GET" ? "api_observe" : "api_mutate","targetId":target,"question":purpose,"arguments":arguments])
            }.disabled(closed || target.isEmpty || paths.isEmpty || purpose.isEmpty)
        }
    }
    private var validation:some View {
        VStack(alignment:.leading,spacing:12){
            Text("Define the exact requirement before evaluating two independently collected runs. A validated requirement applies to its declared access boundary, port state or response header.").foregroundStyle(theme.muted)
            picker("Objective",$objective,rows("securityObjectives").filter{engagementText($0["status"]) != "superseded"})
            Picker("Contract",selection:$validator){Text("API access boundary").tag("api_access_boundary");Text("API mutation state").tag("api_mutation_state");Text("Network port state").tag("network_port_state");Text("Response header").tag("website_header_value")}
            if validator == "network_port_state" {
                field("Observed host",$paths);Stepper("Port \(port)",value:$port,in:1...65535)
                Picker("Positive state",selection:$positiveState){ForEach(["open","closed","filtered"],id:\.self){Text($0)}}
                Picker("Baseline state",selection:$baselineState){ForEach(["open","closed","filtered"],id:\.self){Text($0)}}
            }else {
                field("Exact response path",$paths)
                if validator == "api_access_boundary" || validator == "api_mutation_state" {
                    if validator == "api_access_boundary" {
                        picker("Allowed identity",$allowed,credentials)
                        Picker("Denied identity",selection:$denied){Text("Anonymous").tag("anonymous");ForEach(credentials,id:\.engagementID){row in Text(engagementText(row["label"])).tag(engagementText(row["id"]))}}
                    }else {
                        picker("Completed mutation",$mutationRun,rows("securityRuns").filter{engagementText($0["capability"]) == "api_mutate" && engagementText($0["status"]) == "completed"})
                        field("Expected state before mutation",$beforeState)
                    }
                    field("JSON signal location, for example /private",$pointer)
                    field("Expected JSON scalar, for example true",$expected)
                }else {field("Response header name",$header);field("Expected header value",$expected)}
            }
            Button("Save validation contract"){
                var config:[String:Any]
                if validator == "api_access_boundary" || validator == "api_mutation_state" {
                    guard let data=expected.data(using:.utf8),let scalar=try? JSONSerialization.jsonObject(with:data,options:.fragmentsAllowed) else{localError="Use a JSON scalar for the expected signal.";return}
                    if validator == "api_access_boundary" {config=["path":paths,"pointer":pointer,"expected":scalar,"allowedIdentityId":allowed,"deniedIdentityId":denied]}
                    else {
                        guard let data=beforeState.data(using:.utf8),let before=try? JSONSerialization.jsonObject(with:data,options:.fragmentsAllowed) else {localError="Use a JSON scalar for the baseline state.";return}
                        config=["path":paths,"pointer":pointer,"after":scalar,"before":before,"mutationRunId":mutationRun]
                    }
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
            DisclosureGroup("Suricata / Zeek log import") {
                Picker("Vendor format",selection:$vendor){Text("Suricata EVE JSON lines").tag("suricata_eve");Text("Zeek JSON lines").tag("zeek_json")}
                picker("Collected operation",$run,rows("securityRuns"))
                field("Coverage start, Unix milliseconds",$coverageStart);field("Coverage end, Unix milliseconds",$coverageEnd)
                Button("Import vendor log"){
                    guard let starts=Int64(coverageStart),let ends=Int64(coverageEnd) else {localError="Enter coverage timestamps in Unix milliseconds.";return}
                    perform("security-vendor-telemetry-import",["path":importPath,"vendor":vendor,"runId":run,"starts":starts,"ends":ends])
                }.disabled(closed || importPath.isEmpty || run.isEmpty)
                Text("Exact IP/port and operation-time matches only. Raw logs retain external provenance.").foregroundStyle(theme.muted)
            }
            picker("Sensor observation",$telemetry,rows("securityTelemetry"));picker("Operation",$run,rows("securityRuns"))
            field("Expected event type",$eventType)
            Button("Correlate operation and sensor coverage"){perform("security-telemetry-correlate",["telemetryId":telemetry,"runId":run,"eventType":eventType])}.disabled(closed || telemetry.isEmpty || run.isEmpty || eventType.isEmpty)
            ForEach(rows("securityEngagementEvents").filter{engagementText($0["kind"]) == "defensive_correlation"},id:\.engagementID){row in let detail=row["detail"] as? [String:Any] ?? [:];Text(engagementText(detail["expected"])+" · "+engagementText(detail["status"])).wixalCard()}
        }
    }
    private var imports:some View {
        VStack(alignment:.leading,spacing:12){Text("Import a structured JSON export containing a findings array with title and status. External statuses remain unverified claims.").foregroundStyle(theme.muted);field("Export JSON path inside project",$importPath);Button("Import external claims"){perform("security-engagement-structured-import",["path":importPath])}.disabled(closed || importPath.isEmpty)
            DisclosureGroup("External controller proposals") {
                Text("Import a JSON proposal with name, targetId and typed nodes. Importing grants no authority. Execution requires a separate review and uses the existing scoped queue.").foregroundStyle(theme.muted)
                Button("Import controller proposal"){perform("security-controller-plan-import",["path":importPath])}.disabled(closed || importPath.isEmpty)
                picker("Imported proposal",$controllerPlan,records(engine.state["securityPlans"]).filter{engagementText($0["controllerEngagementId"]) == id})
                Button("Review and queue proposal"){perform("security-controller-plan-run",["planId":controllerPlan])}.disabled(closed || controllerPlan.isEmpty)
            }
        }
    }
}
