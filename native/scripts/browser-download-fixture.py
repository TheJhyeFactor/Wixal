"""Real streamed download fixture for installed WebKit/UI acceptance.

Run this server, open its printed URL in a reviewed interactive browser, and
exercise Save, Cancel, failure and Show in Finder. This is transport/UI evidence,
not external OAuth acceptance. Files are deterministic; no account is involved.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import time

CHUNK=bytes(range(256))*256
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path in ('/download','/slow','/broken'):
            count=128 if self.path!='/slow' else 1024
            self.send_response(200);self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Disposition','attachment; filename="wixal-download-workload.bin"')
            self.send_header('Content-Length',str(len(CHUNK)*count));self.end_headers()
            sent=0
            try:
                for index in range(count):
                    self.wfile.write(CHUNK);self.wfile.flush();sent+=len(CHUNK)
                    if self.path=='/broken' and index==3:
                        self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();break
                    time.sleep(0.03 if self.path!='/slow' else 0.05)
            except (BrokenPipeError,ConnectionResetError,OSError):pass
            print(json.dumps(dict(path=self.path,sentBytes=sent,expectedBytes=len(CHUNK)*count)),flush=True)
            return
        text='''<!doctype html><title>Wixal download acceptance</title><h1>Browser download workload</h1>
        <p>Downloads use actual streamed bytes. Save to a temporary folder.</p>
        <a href="/download">Download 8 MB</a><br><a href="/slow">Download 64 MB, then cancel</a><br>
        <a href="/broken">Download with interrupted connection</a><br>
        <a target="_blank" href="/target">User-clicked new-window link</a><br>
        <button onclick="window.open('/popup')">Script popup (unsupported)</button>'''
        if self.path=='/target':text='<title>Link destination</title><h1>New-window link opened in the same session</h1>'
        if self.path=='/popup':text='<title>Popup destination</title><h1>Unexpected script popup</h1>'
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(text.encode())

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    print(f'http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
