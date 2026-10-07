"""Keep the managed model runner alive only while its owner pipe remains open."""
import os
import select
import signal
import subprocess
import sys


def main():
    executable=sys.argv[sys.argv.index("--supervise-runtime")+1]
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    child=subprocess.Popen([executable,"serve"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        while not stopping and child.poll() is None:
            ready,_,_=select.select([sys.stdin.buffer],[],[],.25)
            if ready and not os.read(sys.stdin.fileno(),1):break
    finally:
        if child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
    return child.returncode
