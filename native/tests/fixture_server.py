"""Deterministic Ollama-shaped fixture; never represented as a real model benchmark."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path in ("/page", "/linked"):
            text = '<html><head><title>Native browser fixture</title></head><body><h1>Rendered fixture page</h1><a href="/linked">Open linked page</a><label>Name<input name="name" placeholder="Name"></label><select name="choice" aria-label="Choice"><option value="one">One</option><option value="two">Two</option></select><button type="button" onclick="document.getElementById(\'result\').innerText=document.querySelector(\'input[name=name]\').value+\' \'+document.querySelector(\'select\').value">Show result</button><div id="result"></div><input type="password" aria-label="Password"><form method="post" action="/submit"><button>Submit form</button></form><button type="button" onclick="fetch(\'/write\',{method:\'POST\',body:\'blocked\'}).catch(()=>document.getElementById(\'result\').innerText=\'request-blocked\')">Try script request</button><script>console.log(\'fixture-console\');setTimeout(()=>document.body.append(\' delayed-ready\'),150)</script></body></html>' if self.path=='/page' else '<html><body>linked-page-ok</body></html>'
            self.send_response(200);self.send_header("Content-Type","text/html");self.end_headers();self.wfile.write(text.encode());return
        body = {"models":[{"name":"fixture","size":1}]} if self.path=="/api/tags" else {"version":"fixture"}
        self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(json.dumps(body).encode())
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
        if self.path=="/api/show":
            self.wfile.write(json.dumps(dict(capabilities=["completion","tools"],model_info={"fixture.context_length":8192})).encode());return
        messages=body.get("messages",[])
        if any(m["role"]=="tool" for m in messages):
            rows=[dict(message=dict(role="assistant",content="The tool returned its result. "),done=False),dict(message=dict(role="assistant",content="Task finished."),done=True)]
        else:
            rows=[dict(message=dict(role="assistant",content="I will save the smoke file. ",tool_calls=[dict(function=dict(name="write_file",arguments=dict(path="smoke.txt",content="native-agent-ok\n")))]),done=True)]
        for row in rows:self.wfile.write((json.dumps(row)+"\n").encode());self.wfile.flush()

class Fixture:
    def __enter__(self):
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_port}";return self
    def __exit__(self,*args):self.server.shutdown();self.server.server_close();self.thread.join()

if __name__=="__main__":
    with Fixture() as fixture:
        print(fixture.url,flush=True)
        try:threading.Event().wait()
        except KeyboardInterrupt:pass
