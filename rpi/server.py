#!/usr/bin/env python3
"""LAN controller for the native RPiT3K engine. Standard library only."""
import argparse
from tonecloud import ToneCloud
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
import struct
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 32 * 1024 * 1024
NAME = re.compile(r"[\w .()+@-]{1,180}", re.UNICODE)
DEFAULT = dict(model="", second="", ir="", slim=1, slim2=1, input=1, output=.15,
               bass=0, mid=0, treble=0, gate=-81, bypass=True)
RANGES = dict(slim=(0,1), slim2=(0,1), input=(0,2), output=(0,1),
              bass=(-20,20), mid=(-15,15), treble=(-10,10), gate=(-81,-30))

class Controller:
    def __init__(self, args):
        self.args = args
        self.data = Path(args.data).expanduser().resolve()
        self.library = self.data / "library"
        self.library.mkdir(parents=True, exist_ok=True)
        self.statefile = self.data / "presets.json"
        self.lock = threading.RLock()
        self.cloud = ToneCloud(self)
        self.proc = None
        self.meter = None
        self.xrun_lock = threading.Lock()
        self.xrun_total = 0
        self.logs = deque(maxlen=100)
        self.active = None
        self.tuner_return = None
        self.settingsfile = self.data / "settings.json"
        self.settings = dict(buffer=64, periods=3, last="1")
        if self.settingsfile.exists(): self.settings.update(json.loads(self.settingsfile.read_text()))
        self.cpu_prev = None
        self.cpu_pct = None
        self.presets = {str(i): dict(DEFAULT) for i in range(1,5)}
        if self.statefile.exists():
            self.presets.update({k:dict(DEFAULT, **v) for k,v in json.loads(self.statefile.read_text()).items()})
        self.exe = ROOT / "build-rpi/rpit3k"
        if not self.exe.is_file():
            raise RuntimeError("Compile build-rpi/rpit3k first")

    def file(self, name, extensions):
        if not isinstance(name,str) or len(name)>1024 or any(not NAME.fullmatch(part) or part in (".","..") for part in name.split("/")) or Path(name).suffix.lower() not in extensions:
            raise ValueError("Invalid library path or type")
        p = self.library
        for part in name.split("/"):
            p = p / part
            if p.is_symlink():
                raise ValueError("Symlinks are not allowed")
        if not p.resolve().is_relative_to(self.library.resolve()):
            raise ValueError("Outside library")
        return p

    def library_files(self):
        files=[]
        for root, dirs, names in os.walk(self.library, followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink()]
            for name in names:
                p=Path(root)/name
                rel=p.relative_to(self.library).as_posix()
                try:
                    if self.file(rel,(".nam",".wav")).is_file():
                        files.append(rel)
                except (ValueError,OSError):
                    pass
        return sorted(files,key=str.casefold)

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
        if p["gate"] != -81 and p["gate"] < -80:
            raise ValueError("Invalid gate threshold")
        for k,ext in (("model",(".nam",)),("second",(".nam",".wav")),("ir",(".wav",))):
            if p[k] != "" and not self.file(p[k],ext).is_file():
                raise ValueError("Missing "+k)
        if not p["bypass"] and not p["model"]:
            raise ValueError("Choose a NAM capture or enable bypass")
        if str(p["second"]).lower().endswith(".wav"):
            p["slim2"] = 1
        return p

    def persist_settings(self):
        temp=self.settingsfile.with_suffix(".tmp")
        temp.write_text(json.dumps(self.settings))
        os.replace(temp,self.settingsfile)

    def audio_args(self):
        return ["--buffer",str(self.settings["buffer"]),"--periods",str(self.settings["periods"])]

    def command(self,p):
        cmd=[str(self.exe),"--device",self.args.device]+self.audio_args()
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
        self.meter=None

    def drain(self,proc):
        # Engine reports a cumulative recovery count, including ALSA suspend
        # recovery. Count deltas, not log lines, to avoid double counting.
        for line in proc.stdout:
            line=line.rstrip()
            self.logs.append(line)
            match=(re.search(r"\bxruns=(\d+)\b",line) if line.startswith("DSP ") else
                   re.fullmatch(r"ALSA (?:xrun/restart #|xruns/restarts: )(\d+)",line))
            if match:
                n=int(match.group(1))
                with self.xrun_lock:
                    old=proc.rpit3k_xruns
                    if n>old:
                        proc.rpit3k_xruns=n
                        self.xrun_total+=n-old
                if n>old:
                    print("ALSA recovery: engine count="+str(n),flush=True)

    def xrun_status(self):
        with self.xrun_lock:
            proc=self.proc
            current=getattr(proc,"rpit3k_xruns",None) if proc and proc.poll() is None else None
            return dict(xruns=current,xruns_total=self.xrun_total)

    def apply(self,slot,p,benchmark=True):
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
            if benchmark:
                test=subprocess.run(cmd+["--benchmark"],capture_output=True,text=True,timeout=30)
                if test.returncode:
                    raise ValueError(test.stderr.strip() or "Model validation failed")
                self.logs.append(test.stdout.strip())
            self.start(cmd,slot)
            self.save(slot,p)
            self.settings["last"]=slot
            self.persist_settings()
        except Exception:
            self.stop()
            if old_slot and old_p:
                try:
                    self.start(self.command(old_p),old_slot)
                except Exception as e:
                    self.logs.append("Restore failed: "+str(e))
            raise

    def drain_meter(self,proc,fd):
        try:
            with os.fdopen(fd,"rb",buffering=0) as f:
                pending=b""
                while True:
                    chunk=f.read(4096)
                    if not chunk: break
                    pending+=chunk
                    while len(pending)>=8:
                        a,b=struct.unpack("=ff",pending[:8])
                        pending=pending[8:]
                        if self.proc is proc:
                            self.meter=(proc,time.monotonic(),a,b)
        except OSError:
            pass

    def levels(self):
        m=self.meter
        if m and m[0] is self.proc and self.proc.poll() is None and time.monotonic()-m[1]<.5:
            return dict(valid=True,input=m[2],output=m[3])
        return dict(valid=False,input=0,output=0)

    def start(self,cmd,slot):
        rd,wr=os.pipe()
        self.meter=None
        try:
            self.proc=subprocess.Popen(cmd+["--live-controls","--meter-fd",str(wr)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                       text=True,bufsize=1,pass_fds=(wr,))
        except Exception:
            os.close(rd)
            raise
        finally:
            os.close(wr)
        self.proc.rpit3k_xruns=0
        threading.Thread(target=self.drain_meter,args=(self.proc,rd),daemon=True).start()
        threading.Thread(target=self.drain,args=(self.proc,),daemon=True).start()
        time.sleep(.35)
        if self.proc.poll() is not None:
            raise ValueError("Audio engine stopped: "+"; ".join(list(self.logs)[-5:]))
        self.active=slot

    def live_controls(self,slot,values):
        if slot!=self.active or self.proc is None or self.proc.poll() is not None:
            raise ValueError("Select the running preset first")
        keys=("input","output","bass","mid","treble","gate")
        p=dict(self.presets[slot])
        for k in keys:
            if k not in values: raise ValueError("Missing "+k)
            p[k]=values[k]
        p=self.validate(p)
        self.proc.stdin.write(" ".join(str(p[k]) for k in keys)+"\n")
        self.proc.stdin.flush()
        self.save(slot,p)

    def next_preset(self):
        slot=str(int(self.settings["last"])%4+1)
        self.apply(slot,self.presets[slot],benchmark=False)

    def configure(self,values):
        b,p=values.get("buffer"),values.get("periods")
        if type(b) is not int or type(p) is not int or b not in (64,128,256,512) or p not in (2,3,4): raise ValueError("Invalid audio settings")
        old=dict(self.settings);slot=self.active
        self.settings.update(buffer=b,periods=p)
        try:
            if slot: self.apply(slot,self.presets[slot],benchmark=False)
            elif self.proc and self.proc.poll() is None:
                self.stop();self.start([str(self.exe),"--device",self.args.device,"--tuner"]+self.audio_args(),None)
            self.persist_settings()
        except Exception:
            self.settings=old
            self.stop()
            if slot: self.start(self.command(self.presets[slot]),slot)
            raise

    def telemetry(self):
        try:
            v=list(map(int,Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
            now=(sum(v),v[3]+v[4])
            if self.cpu_prev:
                dt=now[0]-self.cpu_prev[0];di=now[1]-self.cpu_prev[1]
                if dt>0:self.cpu_pct=round(100*(dt-di)/dt,1)
            self.cpu_prev=now
        except (OSError,ValueError,IndexError): pass
        try: temp=round(int(Path("/sys/class/thermal/thermal_zone0/temp").read_text())/1000,1)
        except (OSError,ValueError): temp=None
        b,p=self.settings["buffer"],self.settings["periods"]
        return dict(cpu=self.cpu_pct,temp=temp,buffer=b,periods=p,period_ms=b/48,buffer_ms=b*p/48,**self.xrun_status())

    def status(self):
        return dict(presets=self.presets,active=self.active,settings=self.settings,telemetry=self.telemetry(),
                    running=self.proc is not None and self.proc.poll() is None,
                    files=self.library_files(),
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
        if self.server.password is None: return True
        expected="Basic "+base64.b64encode((self.server.username+":"+self.server.password).encode()).decode()
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
        elif path=="/api/levels":
            self.send(200,self.server.controller.levels())
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
            if u.path.startswith('/api/tone3000/'):
                v=json.loads(self.body(65536))
                if not isinstance(v,dict): raise ValueError('Expected object')
                self.send(200,c.cloud.action(u.path.rsplit('/',1)[-1],v))
                return
            with c.lock:
                if u.path=="/api/upload":
                    name=parse_qs(u.query).get("name",[""])[0]
                    if "/" in name: raise ValueError("Upload must be a filename")
                    p=c.file(name,(".nam",".wav"))
                    if p.exists(): raise ValueError("File already exists")
                    data=self.body(LIMIT)
                    with p.open("xb") as f: f.write(data)
                elif u.path=="/api/next":
                    if self.client_address[0] not in ("127.0.0.1","::1"): raise ValueError("Local button endpoint only")
                    c.next_preset()
                elif u.path=="/api/controls":
                    v=json.loads(self.body(65536))
                    c.live_controls(v["slot"],v["controls"])
                elif u.path=="/api/settings":
                    c.configure(json.loads(self.body(65536)))
                elif u.path=="/api/tuner":
                    if c.proc and c.proc.poll() is None and c.active is None:
                        previous=c.tuner_return
                        c.stop()
                        c.tuner_return=None
                        if previous:
                            c.apply(previous,c.presets[previous],benchmark=False)
                    else:
                        c.tuner_return=c.active if c.proc and c.proc.poll() is None else None
                        c.stop()
                        c.logs.clear()
                        try:
                            c.start([str(c.exe),"--device",c.args.device,"--tuner"]+c.audio_args(),None)
                        except Exception:
                            previous=c.tuner_return
                            c.stop()
                            c.tuner_return=None
                            if previous: c.apply(previous,c.presets[previous],benchmark=False)
                            raise
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
    p.add_argument("--no-auth",action="store_true")
    p.add_argument("--autostart",action="store_true")
    a=p.parse_args()
    c=Controller(a)
    password=None if a.no_auth else (os.getenv("RPIT3K_PASSWORD") or secrets.token_urlsafe(12))
    server=ThreadingHTTPServer((a.bind,a.port),Handler)
    server.controller=c
    server.password=password
    server.username=os.getenv("RPIT3K_USERNAME","rpit3k")
    print(f"RPiT3K http://{a.bind}:{a.port}  "+("no authentication (trusted LAN only)" if password is None else f"user={server.username}"),flush=True)
    if password and not os.getenv("RPIT3K_PASSWORD"): print("Temporary password: "+password,flush=True)
    if a.autostart:
        try:
            slot=c.settings["last"];c.apply(slot,c.presets[slot],benchmark=False)
        except Exception as e: c.logs.append("Autostart failed: "+str(e))
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        with c.lock: c.stop()

if __name__=="__main__": main()
