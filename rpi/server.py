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
import shutil
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
AMP_ART_KEYS = frozenset(("blackface","silverface","tweed","vox","orange","plexi","matchless","dumble","hiewatt","boutique","generic","mesa","gibson","pedal"))
AMP_ART_LIMIT = 2 * 1024 * 1024
NAME = re.compile(r"[\w .()+@-]{1,180}", re.UNICODE)
DEFAULT = dict(model="", second="", ir="", ir2="", ir_mix=.5, hiz=0, hiz_profile=0, slim=1, slim2=1, input=1, output=.15,
               bass=0, mid=0, treble=0, gate=-81, comp=0, comp_post=0, reverb=0, decay=1.5, reverb_type=0, bypass=True)
RANGES = dict(hiz=(0,1), hiz_profile=(0,3), ir_mix=(0,1), slim=(0,1), slim2=(0,1), input=(0,2), output=(0,1),
              bass=(-20,20), mid=(-15,15), treble=(-10,10), gate=(-81,-30), comp=(0,1), comp_post=(0,1), reverb=(0,1), decay=(.2,5), reverb_type=(0,2))

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
        self.settings = dict(buffer=256, periods=3, last="1", device=args.device, input_channel=args.input_channel, input_channels=args.input_channels, output_channels=args.output_channels, output_left=args.output_left, output_right=args.output_right, reference_dbu=None)
        if self.settingsfile.exists(): self.settings.update(json.loads(self.settingsfile.read_text()))
        self.cpu_prev = None
        self.cpu_pct = None
        self.presets = {str(i): dict(DEFAULT) for i in range(1,5)}
        if self.statefile.exists():
            self.presets.update({k:dict(DEFAULT, **v) for k,v in json.loads(self.statefile.read_text()).items()})
        self.favoritesfile=self.data/"favorites.json"
        self.favorites=set(json.loads(self.favoritesfile.read_text())) if self.favoritesfile.exists() else set()
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

    def folder(self,name):
        if name=="": return self.library
        if not isinstance(name,str) or len(name)>900 or len(name.split("/"))>20 or any(not NAME.fullmatch(part) or part in (".","..") for part in name.split("/")):
            raise ValueError("Invalid folder path")
        p=self.library
        for part in name.split("/"):
            p=p/part
            if p.is_symlink(): raise ValueError("Symlinks are not allowed")
        if not p.resolve().is_relative_to(self.library.resolve()):
            raise ValueError("Outside library")
        return p

    def write_json(self,path,value):
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value,indent=2))
        os.replace(tmp,path)

    def set_favorite(self,path,enabled):
        if type(enabled) is not bool or not self.file(path,(".nam",".wav")).is_file():
            raise ValueError("Invalid favorite")
        updated=set(self.favorites)
        if enabled: updated.add(path)
        else: updated.discard(path)
        self.write_json(self.favoritesfile,sorted(updated))
        self.favorites=updated

    def rename_library(self,old,name,kind):
        if not isinstance(name,str) or not NAME.fullmatch(name) or name in (".",".."):
            raise ValueError("Invalid new name")
        if kind=="folder" and old:
            src=self.folder(old)
            if not src.is_dir(): raise ValueError("Folder not found")
            dst=self.folder(str(Path(old).with_name(name)))
        elif kind=="file":
            src=self.file(old,(".nam",".wav"))
            if not src.is_file(): raise ValueError("File not found")
            ext=src.suffix
            if name.lower().endswith(ext.lower()): name=name[:-len(ext)]
            if not name or name in (".",".."): raise ValueError("Invalid new name")
            dst=self.file(str(Path(old).with_name(name+ext)),(".nam",".wav"))
        else: raise ValueError("Invalid item")
        return self.relocate_library(src,dst,old,kind)

    def move_library(self,old,destination,kind):
        if not isinstance(old,str) or not old: raise ValueError("Cannot move library root")
        if not isinstance(destination,str): raise ValueError("Invalid destination")
        parent=self.folder(destination)
        if not parent.is_dir(): raise ValueError("Destination folder not found")
        if kind=="folder":
            src=self.folder(old)
            if not src.is_dir(): raise ValueError("Folder not found")
            if destination==old or destination.startswith(old+"/"):
                raise ValueError("Cannot move a folder into itself")
        elif kind=="file":
            src=self.file(old,(".nam",".wav"))
            if not src.is_file(): raise ValueError("File not found")
        else: raise ValueError("Invalid item")
        new=(destination+"/" if destination else "")+src.name
        dst=self.folder(new) if kind=="folder" else self.file(new,(".nam",".wav"))
        return self.relocate_library(src,dst,old,kind)

    def relocate_library(self,src,dst,old,kind):
        if src==dst: return old
        if dst.exists() or dst.is_symlink(): raise ValueError("Destination already exists")
        new=dst.relative_to(self.library).as_posix()
        def remap(path):
            return new+path[len(old):] if path==old or (kind=="folder" and path.startswith(old+"/")) else path
        presets={slot:{**preset,**{k:remap(preset[k]) for k in ("model","second","ir","ir2")}} for slot,preset in self.presets.items()}
        favorites={remap(path) for path in self.favorites}
        # Audio models are already loaded in memory. Do not restart audio.
        src.rename(dst)
        try:
            self.write_json(self.statefile,presets)
            self.write_json(self.favoritesfile,sorted(favorites))
        except OSError:
            dst.rename(src)
            self.write_json(self.statefile,self.presets)
            self.write_json(self.favoritesfile,sorted(self.favorites))
            raise
        self.presets=presets
        self.favorites=favorites
        return new

    def delete_library(self,path,kind):
        if not isinstance(path,str) or not path: raise ValueError("Cannot delete library root")
        if kind=="folder":
            src=self.folder(path)
            if not src.is_dir(): raise ValueError("Folder not found")
        elif kind=="file":
            src=self.file(path,(".nam",".wav"))
            if not src.is_file(): raise ValueError("File not found")
        else: raise ValueError("Invalid item")
        def contains(value):
            return value==path or (kind=="folder" and value.startswith(path+"/"))
        used=[slot for slot,preset in self.presets.items() if any(contains(preset[k]) for k in ("model","second","ir","ir2"))]
        if used: raise ValueError("Used by preset(s) "+", ".join(used)+". Change those presets before removing this item.")
        updated={f for f in self.favorites if not contains(f)}
        if kind=="folder":
            shutil.rmtree(src)
        else:
            src.unlink()
        self.write_json(self.favoritesfile,sorted(updated))
        self.favorites=updated

    def amp_art_path(self,key):
        if key not in AMP_ART_KEYS: raise ValueError("Unknown amp artwork family")
        folder=self.data/"amp-art"
        if folder.is_symlink(): raise ValueError("Invalid artwork directory")
        path=folder/(key+".webp")
        if path.is_symlink(): raise ValueError("Invalid artwork path")
        return path

    def amp_art_versions(self):
        versions={}
        for key in AMP_ART_KEYS:
            try:
                path=self.amp_art_path(key)
                if path.is_file(): versions[key]=str(path.stat().st_mtime_ns)
            except (ValueError,OSError): pass
        return versions

    def install_amp_art(self,key,data):
        if len(data)<20 or data[:4]!=b"RIFF" or data[8:12]!=b"WEBP" or int.from_bytes(data[4:8],"little")!=len(data)-8 or data[12:16] not in (b"VP8 ",b"VP8L",b"VP8X"):
            raise ValueError("Expected a valid WebP container")
        path=self.amp_art_path(key)
        path.parent.mkdir(mode=0o700,exist_ok=True)
        tmp=path.parent/(key+"-"+secrets.token_hex(8)+".tmp")
        try:
            with tmp.open("xb") as f: f.write(data)
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)

    def library_folders(self):
        folders=[]
        for root,dirs,_ in os.walk(self.library,followlinks=False):
            valid=[]
            for name in dirs:
                p=Path(root)/name
                rel=p.relative_to(self.library).as_posix()
                try:
                    if self.folder(rel).is_dir():
                        valid.append(name)
                        folders.append(rel)
                except (ValueError,OSError): pass
            dirs[:]=valid
        return sorted(folders,key=str.casefold)

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
        if p["comp_post"] not in (0,1) or p["reverb_type"] not in (0,1,2) or p["hiz_profile"] not in (0,1,2,3):
            raise ValueError("Invalid effect mode")
        if p["gate"] != -81 and p["gate"] < -80:
            raise ValueError("Invalid gate threshold")
        for k,ext in (("model",(".nam",)),("second",(".nam",".wav")),("ir",(".wav",)),("ir2",(".wav",))):
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
        return ["--device",self.settings["device"],"--buffer",str(self.settings["buffer"]),"--periods",str(self.settings["periods"])]+[v for k in ("input_channel","input_channels","output_channels","output_left","output_right") for v in ("--"+k.replace("_","-"),str(self.settings[k]))]

    def command(self,p):
        cmd=[str(self.exe)]+self.audio_args()
        if p["bypass"]:
            cmd+=["--bypass"]
        else:
            cmd+=["--model",str(self.library/p["model"])]
            if p["second"]:
                cmd+=["--second",str(self.library/p["second"])]
            if p["ir"]:
                cmd+=["--ir",str(self.library/p["ir"])]
            if p["ir2"]:
                cmd+=["--ir2",str(self.library/p["ir2"])]
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
        keys=("input","output","bass","mid","treble","gate","comp","comp_post","reverb","decay","reverb_type","ir_mix","hiz","hiz_profile")
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
        device=values.get("device",self.settings["device"])
        if not isinstance(device,str) or not re.fullmatch(r"[A-Za-z0-9_.,:=+ -]{1,160}",device):
            raise ValueError("Invalid ALSA PCM name")
        routing={k:values.get(k,self.settings[k]) for k in ("input_channel","input_channels","output_channels","output_left","output_right")}
        if any(type(v) is not int or not 1<=v<=64 for v in routing.values()) or routing["input_channel"]>routing["input_channels"] or max(routing["output_left"],routing["output_right"])>routing["output_channels"]:
            raise ValueError("Invalid channel routing")
        ref=values.get("reference_dbu",self.settings["reference_dbu"])
        if ref is not None and (type(ref) not in (int,float) or not math.isfinite(ref) or not -60<=ref<=30):
            raise ValueError("Invalid ADC reference")
        old=dict(self.settings);slot=self.active
        if device!=old["device"] or routing["input_channel"]!=old["input_channel"] or routing["input_channels"]!=old["input_channels"]:
            if ref==old["reference_dbu"]: ref=None
        self.settings.update(buffer=b,periods=p,device=device,reference_dbu=ref,**routing)
        try:
            if slot: self.apply(slot,self.presets[slot],benchmark=False)
            elif self.proc and self.proc.poll() is None:
                self.stop();self.start([str(self.exe),"--tuner"]+self.audio_args(),None)
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
                    cloud_enabled=not self.args.disable_cloud,
                    poweroff_enabled=os.environ.get("RPIT3K_ENABLE_POWEROFF")=="1",
                    running=self.proc is not None and self.proc.poll() is None,
                    files=self.library_files(),folders=self.library_folders(),favorites=sorted(self.favorites),amp_art=self.amp_art_versions(),
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
        if self.server.server_address[0] == '127.0.0.1':
            host=self.headers.get('Host','').lower()
            allowed={f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}'}
            if self.server.server_port==80: allowed.update(('localhost','127.0.0.1'))
            if host not in allowed:
                self.send(403,dict(error='Invalid Host; use localhost or 127.0.0.1'))
                return False
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
        elif path.startswith("/api/amp-art/"):
            try:
                asset=self.server.controller.amp_art_path(path.rsplit("/",1)[-1])
                if not asset.is_file() or asset.stat().st_size>AMP_ART_LIMIT: raise ValueError("Artwork unavailable")
                self.send(200,asset.read_bytes(),"image/webp")
            except (OSError,ValueError):
                self.send(404,dict(error="Artwork unavailable"))
        elif path=="/api/levels":
            self.send(200,self.server.controller.levels())
        elif path=="/api/devices":
            result={}
            for command in ("aplay","arecord"):
                try: result[command]=subprocess.run([command,"-l"],capture_output=True,text=True,timeout=3,env=dict(os.environ,LC_ALL="C")).stdout
                except (OSError,subprocess.SubprocessError): result[command]="Unavailable"
            self.send(200,result)
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
            if u.path=="/api/poweroff":
                if os.environ.get("RPIT3K_ENABLE_POWEROFF")!="1":
                    self.send(403,dict(error="Power off is not enabled on this installation"));return
                if json.loads(self.body(1024))!={"confirm":"poweroff"}:
                    raise ValueError("Explicit power-off confirmation required")
                with c.lock:
                    c.stop()
                    result=subprocess.run(["/usr/bin/sudo","-n","/usr/bin/systemctl","poweroff"],capture_output=True,text=True,timeout=10)
                    if result.returncode:
                        raise ValueError("Power off failed: "+(result.stderr.strip() or "Permission denied"))
                    self.send(200,dict(powering_off=True))
                return
            if u.path=="/api/calibrate":
                v=json.loads(self.body(65536))
                ref=c.settings.get("reference_dbu")
                if ref is None: raise ValueError("Set the ADC full-scale reference in Audio settings first")
                if type(ref) not in (int,float) or not math.isfinite(ref) or not -60<=ref<=30:
                    raise ValueError("Invalid hardware reference in dBu")
                path=c.file(v["model"],(".nam",))
                if path.stat().st_size>LIMIT: raise ValueError("Model too large")
                model=json.loads(path.read_text())
                metadata=model.get("metadata") or {}
                level=metadata.get("input_level_dbu")
                if type(level) not in (int,float) or not math.isfinite(level) or not -60<=level<=60:
                    raise ValueError("Capture has no valid input_level_dbu metadata")
                db=ref-level
                gain=10**(db/20)
                if gain>2 or gain<.000001: raise ValueError("Calibration outside available input gain range")
                self.send(200,dict(gain=gain,db=db,model_dbu=level,reference_dbu=ref));return
            if u.path.startswith('/api/tone3000/'):
                if c.args.disable_cloud:
                    self.send(403,dict(error='Experimental TONE3000 integration disabled'));return
                v=json.loads(self.body(65536))
                if not isinstance(v,dict): raise ValueError('Expected object')
                self.send(200,c.cloud.action(u.path.rsplit('/',1)[-1],v))
                return
            with c.lock:
                if u.path.startswith("/api/amp-art/"):
                    key=u.path.rsplit("/",1)[-1]
                    c.install_amp_art(key,self.body(AMP_ART_LIMIT))
                elif u.path=="/api/upload":
                    name=parse_qs(u.query).get("name",[""])[0]
                    if not isinstance(name,str): raise ValueError("Invalid filename")
                    folder,name_only=name.rsplit("/",1) if "/" in name else ("",name)
                    parent=c.folder(folder)
                    if not parent.is_dir(): raise ValueError("Create the destination folder first")
                    p=c.file(name,(".nam",".wav"))
                    if p.exists(): raise ValueError("File already exists")
                    data=self.body(LIMIT)
                    with p.open("xb") as f: f.write(data)
                elif u.path=="/api/delete":
                    v=json.loads(self.body(65536))
                    c.delete_library(v["path"],v["kind"])
                elif u.path=="/api/favorite":
                    v=json.loads(self.body(65536))
                    c.set_favorite(v["path"],v["enabled"])
                elif u.path=="/api/rename":
                    v=json.loads(self.body(65536))
                    c.rename_library(v["path"],v["name"],v["kind"])
                elif u.path=="/api/move":
                    v=json.loads(self.body(65536))
                    c.move_library(v["path"],v["destination"],v["kind"])
                elif u.path=="/api/folder":
                    v=json.loads(self.body(65536))
                    name=v["path"]
                    if not name: raise ValueError("Choose a folder name")
                    p=c.folder(name)
                    p.mkdir(parents=True,exist_ok=True)
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
                            c.start([str(c.exe),"--tuner"]+c.audio_args(),None)
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
    p.add_argument("--device",default="default")
    p.add_argument("--input-channel",type=int,default=1)
    p.add_argument("--input-channels",type=int,default=2)
    p.add_argument("--output-channels",type=int,default=2)
    p.add_argument("--output-left",type=int,default=1)
    p.add_argument("--output-right",type=int,default=2)
    p.add_argument("--data",default="~/.local/share/rpit3k-general")
    p.add_argument("--no-auth",action="store_true")
    p.add_argument("--autostart",action="store_true")
    p.add_argument("--disable-cloud",action="store_true")
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
        except Exception as e:
            c.logs.append("Autostart failed: "+str(e))
            print("Autostart failed: "+str(e),flush=True)
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        with c.lock: c.stop()

if __name__=="__main__": main()
