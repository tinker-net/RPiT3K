#!/usr/bin/env python3
"""LAN controller for the native RPiT3K engine. Standard library only."""
import argparse
import base64
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 32 * 1024 * 1024
NAME = re.compile(r"[\w .()+@-]{1,180}", re.UNICODE)
DEFAULT = dict(model="", second="", ir="", slim=1, slim2=1, input=1, output=.15,
               bass=0, mid=0, treble=0, bypass=True)
RANGES = dict(slim=(0,1), slim2=(0,1), input=(0,2), output=(0,1),
              bass=(-20,20), mid=(-15,15), treble=(-10,10))

class Controller:
    def __init__(self, args):
        self.args = args
        self.data = Path(args.data).expanduser().resolve()
        self.library = self.data / "library"
        self.library.mkdir(parents=True, exist_ok=True)
        self.statefile = self.data / "presets.json"
        self.lock = threading.RLock()
        self.proc = None
        self.logs = deque(maxlen=100)
        self.active = None
        self.presets = {str(i): dict(DEFAULT) for i in range(1,5)}
        if self.statefile.exists():
            self.presets.update({k:dict(DEFAULT, **v) for k,v in json.loads(self.statefile.read_text()).items()})
        self.exe = ROOT / "build-rpi/rpit3k"
        if not self.exe.is_file():
            raise RuntimeError("Compile build-rpi/rpit3k first")

    def file(self, name, extensions):
        if not isinstance(name,str) or not NAME.fullmatch(name) or Path(name).suffix.lower() not in extensions:
            raise ValueError("Invalid file name or type")
        p = self.library / name
        if p.is_symlink():
            raise ValueError("Symlinks are not allowed")
        return p

    def validate(self, preset):
        if not isinstance(preset,dict):
            raise ValueError("Expected preset object")
        p = dict(DEFAULT)
        for k in p:
            if k in preset:
                p[k] = preset[k]
        if type(p["bypass"]) is not bool:
            raise ValueError("Invalid bypass")
        for k,(lo,hi) in RANGES.items():
            v = p[k]
            if type(v) not in (int,float) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError("Invalid "+k)
        for k,ext in (("model",(".nam",)),("second",(".nam",".wav")),("ir",(".wav",))):
            if p[k] != "" and not self.file(p[k],ext).is_file():
                raise ValueError("Missing "+k)
        if not p["bypass"] and not p["model"]:
            raise ValueError("Choose a NAM capture or enable bypass")
        if str(p["second"]).lower().endswith(".wav"):
            p["slim2"] = 1
        return p

    def command(self,p):
        cmd=[str(self.exe),"--device",self.args.device]
        if p["bypass"]:
            cmd+=["--bypass"]
        else:
            cmd+=["--model",str(self.library/p["model"])]
            if p["second"]:
                cmd+=["--second",str(self.library/p["second"])]
            if p["ir"]:
                cmd+=["--ir",str(self.library/p["ir"])]
        for k in RANGES:
            cmd+=["--"+k,str(p[k])]
        return cmd

    def save(self,slot,p):
        if slot not in self.presets:
            raise ValueError("Invalid preset")
        p=self.validate(p)
        self.presets[slot]=p
        temp=self.statefile.with_suffix(".tmp")
        temp.write_text(json.dumps(self.presets,indent=2))
        os.replace(temp,self.statefile)
        return p

    def stop(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            self.proc=None
        self.active=None

    def drain(self,proc):
        for line in proc.stdout:
            self.logs.append(line.rstrip())

    def apply(self,slot,p):
        p=self.validate(p)
        if slot not in self.presets:
            raise ValueError("Invalid preset")
        cmd=self.command(p)
        # Validate model and measure cost without opening ALSA.
        # Stop first: offline benchmark must not compete with live DSP.
        old_slot,old_p=(self.active,self.presets.get(self.active))
        self.stop()
        self.logs.clear()
        try:
            test=subprocess.run(cmd+["--benchmark"],capture_output=True,text=True,timeout=30)
            if test.returncode:
                raise ValueError(test.stderr.strip() or "Model validation failed")
            self.logs.append(test.stdout.strip())
            self.start(cmd,slot)
            self.save(slot,p)
        except Exception:
            self.stop()
            if old_slot and old_p:
                try:
                    self.start(self.command(old_p),old_slot)
                except Exception as e:
                    self.logs.append("Restore failed: "+str(e))
            raise

    def start(self,cmd,slot):
        self.proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                   text=True,bufsize=1)
        threading.Thread(target=self.drain,args=(self.proc,),daemon=True).start()
        time.sleep(.35)
        if self.proc.poll() is not None:
            raise ValueError("Audio engine stopped: "+"; ".join(list(self.logs)[-5:]))
        self.active=slot

    def status(self):
        return dict(presets=self.presets,active=self.active,
                    running=self.proc is not None and self.proc.poll() is None,
                    files=sorted(p.name for p in self.library.iterdir()
                                 if p.is_file() and not p.is_symlink() and p.suffix.lower() in (".nam",".wav")),
                    logs=list(self.logs), tuner=next((line for line in reversed(list(self.logs)) if line.startswith("TUNER ")), ""))

class Handler(BaseHTTPRequestHandler):
    def send(self,code,data,mime="application/json"):
        if not isinstance(data,bytes):
            data=json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        expected="Basic "+base64.b64encode(("rpit3k:"+self.server.password).encode()).decode()
        if hmac.compare_digest(self.headers.get("Authorization",""),expected):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate",'Basic realm="RPiT3K"')
        self.send_header("Content-Length","0")
        self.end_headers()
        return False

    def body(self,limit):
        n=int(self.headers.get("Content-Length","0"))
        if not 0<n<=limit:
            raise ValueError("Invalid request size")
        data=self.rfile.read(n)
        if len(data)!=n:
            raise ValueError("Incomplete request")
        return data

    def do_GET(self):
        if not self.authorized(): return
        path=urlsplit(self.path).path
        if path=="/":
            self.send(200,(ROOT/"rpi/web.html").read_bytes(),"text/html; charset=utf-8")
        elif path=="/api/status":
            with self.server.controller.lock:
                self.send(200,self.server.controller.status())
        else: self.send(404,dict(error="Not found"))

    def do_POST(self):
        if not self.authorized(): return
        # Require a custom header: prevents cross-origin browser form submissions.
        if self.headers.get("X-RPiT3K")!="1":
            self.send(403,dict(error="Missing request header"))
            return
        c=self.server.controller
        u=urlsplit(self.path)
        try:
            with c.lock:
                if u.path=="/api/upload":
                    name=parse_qs(u.query).get("name",[""])[0]
                    p=c.file(name,(".nam",".wav"))
                    if p.exists(): raise ValueError("File already exists")
                    data=self.body(LIMIT)
                    with p.open("xb") as f: f.write(data)
                elif u.path=="/api/tuner":
                    c.stop()
                    c.logs.clear()
                    c.start([str(c.exe),"--device",c.args.device,"--tuner"],None)
                elif u.path=="/api/stop":
                    c.stop()
                elif u.path in ("/api/save","/api/apply"):
                    v=json.loads(self.body(65536))
                    if u.path=="/api/save":
                        if c.active==v["slot"] and c.proc and c.proc.poll() is None:
                            raise ValueError("Apply changes to the active preset instead")
                        c.save(v["slot"],v["preset"])
                    else: c.apply(v["slot"],v["preset"])
                else:
                    self.send(404,dict(error="Not found"));return
                self.send(200,c.status())
        except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as e:
            self.send(400,dict(error=str(e)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bind",default="127.0.0.1")
    p.add_argument("--port",type=int,default=8080)
    p.add_argument("--device",default="hw:pisound,0")
    p.add_argument("--data",default="~/.local/share/rpit3k")
    a=p.parse_args()
    c=Controller(a)
    password=os.getenv("RPIT3K_PASSWORD") or secrets.token_urlsafe(12)
    server=ThreadingHTTPServer((a.bind,a.port),Handler)
    server.controller=c
    server.password=password
    print(f"RPiT3K http://{a.bind}:{a.port}  user=rpit3k  password={password}",flush=True)
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        with c.lock: c.stop()

if __name__=="__main__": main()
