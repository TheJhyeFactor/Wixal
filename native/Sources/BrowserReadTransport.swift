import Foundation
import WebKit

/// Public same-origin reads only. The WebKit content rule still blocks direct raw requests.
@MainActor final class BrowserReadTransport: NSObject, WKScriptMessageHandlerWithReply {
    private final class RedirectPolicy: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
        func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    }
    private let session: URLSession
    private var allowedOrigin: String
    private var active = true
    private var count = 0
    private var inflight = 0
    static func origin(_ url: URL) -> String { "\(url.scheme ?? "")://\(url.host ?? ""):\(url.port ?? (url.scheme == "https" ? 443 : 80))" }
    init(url: URL) {
        allowedOrigin=Self.origin(url)
        let config=URLSessionConfiguration.ephemeral
        config.httpCookieStorage=nil;config.urlCredentialStorage=nil;config.urlCache=nil
        config.httpShouldSetCookies=false;config.timeoutIntervalForRequest=15;config.timeoutIntervalForResource=20
        config.httpMaximumConnectionsPerHost=4
        session=URLSession(configuration:config,delegate:RedirectPolicy(),delegateQueue:nil)
    }
    func navigate(_ url: URL) {allowedOrigin=Self.origin(url);count=0}
    func close() {active=false;session.invalidateAndCancel()}
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage, replyHandler: @escaping (Any?, String?) -> Void) {
        guard active, message.frameInfo.isMainFrame, let frameURL=message.frameInfo.request.url,
              Self.origin(frameURL)==allowedOrigin, let args=message.body as? [String:Any],
              let raw=args["url"] as? String, raw.count<=8192, let url=URL(string:raw),
              ["http","https"].contains(url.scheme ?? ""), Self.origin(url)==allowedOrigin,
              url.user==nil, url.password==nil, let method=args["method"] as? String,
              ["GET","HEAD"].contains(method), count<128, inflight<4 else {
            replyHandler(nil,"Only bounded, public same-origin GET/HEAD reads are permitted.");return
        }
        count += 1;inflight += 1
        Task {
            defer{inflight -= 1}
            do {
                var request=URLRequest(url:url);request.httpMethod=method
                request.setValue("application/json, text/plain, */*",forHTTPHeaderField:"Accept")
                let (bytes,response)=try await session.bytes(for:request)
                guard let http=response as? HTTPURLResponse, !(300..<400).contains(http.statusCode), response.expectedContentLength<=2*1024*1024 else{throw URLError(.badServerResponse)}
                var data=Data()
                for try await byte in bytes {
                    guard data.count<2*1024*1024, active else{throw URLError(.dataLengthExceedsMaximum)}
                    data.append(byte)
                }
                guard active else{throw URLError(.cancelled)}
                replyHandler(["status":http.statusCode,"body":data.base64EncodedString(),"contentType":http.value(forHTTPHeaderField:"Content-Type") ?? "application/octet-stream"],nil)
            } catch {replyHandler(nil,"Public read failed: "+error.localizedDescription)}
        }
    }
    static let script = #"""
    (() => {
      const bridge=window.webkit.messageHandlers.wixalRead;
      const read=async (input,init={})=>{
        const request=new Request(input,init);
        if(!['GET','HEAD'].includes(request.method)) throw new TypeError('Browser submissions are blocked');
        if(request.headers.has('authorization') || request.headers.has('x-api-key')) throw new TypeError('Authenticated reads are unsupported');
        if(request.signal.aborted) throw new DOMException('Aborted','AbortError');
        const result=await bridge.postMessage({url:request.url,method:request.method});
        if(request.signal.aborted) throw new DOMException('Aborted','AbortError');
        const body=Uint8Array.from(atob(result.body),c=>c.charCodeAt(0));
        return new Response([204,205,304].includes(result.status)||request.method==='HEAD'?null:body,{status:result.status,headers:{'Content-Type':result.contentType}});
      };
      Object.defineProperty(window,'fetch',{value:read,writable:false,configurable:false});
      class PublicReadXHR extends EventTarget {
        constructor(){super();this.readyState=0;this.status=0;this.responseType='';this.response=null;this.responseText='';this.timeout=0;this.withCredentials=false;this.upload=new EventTarget();this.headers={};this.controller=null}
        fire(name){const event=new Event(name);this.dispatchEvent(event);if(typeof this['on'+name]==='function')this['on'+name](event)}
        state(value){this.readyState=value;this.fire('readystatechange')}
        open(method,url,async=true,user,password){if(!async||user||password)throw new TypeError('Only public asynchronous reads are supported');this.method=method.toUpperCase();this.url=new URL(url,location.href).href;this.headers={};this.state(1)}
        setRequestHeader(name,value){this.headers[name]=value}
        getResponseHeader(name){return this.result?.headers.get(name)||null}
        getAllResponseHeaders(){return this.result?[...this.result.headers].map(([k,v])=>k+': '+v+'\r\n').join(''):''}
        overrideMimeType(type){this.mime=type}
        abort(){this.controller?.abort();this.state(0);this.fire('abort');this.fire('loadend')}
        send(body=null){
          if(body!==null||this.withCredentials)throw new TypeError('Submissions and credentials are blocked');
          this.controller=new AbortController();const controller=this.controller;
          let timer=this.timeout?setTimeout(()=>{controller.abort();this.fire('timeout')},this.timeout):null;
          this.fire('loadstart');
          read(this.url,{method:this.method,headers:this.headers,signal:controller.signal}).then(async response=>{
            if(controller.signal.aborted)return;
            this.result=response;this.status=response.status;this.statusText=response.statusText;this.responseURL=this.url;this.state(2);
            const bytes=await response.arrayBuffer();this.state(3);
            if(this.responseType==='arraybuffer')this.response=bytes;
            else if(this.responseType==='blob')this.response=new Blob([bytes],{type:this.mime||response.headers.get('content-type')});
            else{this.responseText=new TextDecoder().decode(bytes);this.response=this.responseType==='json'?JSON.parse(this.responseText):this.responseType==='document'?new DOMParser().parseFromString(this.responseText,'text/html'):this.responseText;this.responseXML=this.responseType==='document'?this.response:null}
            this.state(4);this.fire('load');this.fire('loadend');
          }).catch(()=>{if(!controller.signal.aborted){this.state(4);this.fire('error');this.fire('loadend')}}).finally(()=>clearTimeout(timer));
        }
      }
      for(const [name,value] of Object.entries({UNSENT:0,OPENED:1,HEADERS_RECEIVED:2,LOADING:3,DONE:4})){PublicReadXHR[name]=value;PublicReadXHR.prototype[name]=value}
      Object.defineProperty(window,'XMLHttpRequest',{value:PublicReadXHR,writable:false,configurable:false});
    })();
    """#
}
