#!/usr/bin/env python3
"""LAN controller for the native RPiT3K engine. Standard library only."""
import argparse
import mimetypes
from practice import Practice, duration as practice_duration, waveform as practice_waveform
import tempfile
import data_backup
from tonecloud import ToneCloud
from calibration import calibration, valid_number
from capture_info import capture_info
from ir_info import ir_info
import base64
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import select
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
AMP_ART_KEYS = frozenset(("blackface","silverface","tweed","vox","orange","plexi","matchless","dumble","hiewatt","boutique","generic","mesa","gibson","pedal","rat","ts808","centaur","bluesbreaker","tonebender","bigmuff","ramshead","kingsleypage","twinbender","octavio","morningglory","distortionplus"))
AMP_ART_LIMIT = 2 * 1024 * 1024
NAME = re.compile(r"[\w .()+@-]{1,180}", re.UNICODE)
DEFAULT = dict(nam1_enabled=True, model="", second="", ir="", ir2="", ir_mix=.5, hiz=0, hiz_amount=.9, hiz_profile=0, slim=1, slim2=1, input=1, output=.15,
               bass=0, mid=0, treble=0, gate=-81, comp=0, comp_post=0, reverb=0, decay=1.5, reverb_type=0, comp_amount=.35, chorus_amount=.35, delay_amount=.25, reverb_amount=.25, chorus=0, chorus_rate=0.8, chorus_depth=0.5, delay=0, delay_ms=350, delay_feedback=0.35, bypass_nam2=False, bypass_ir=False)
RANGES = dict(hiz=(0,1), hiz_profile=(0,3), ir_mix=(0,1), slim=(0,1), slim2=(0,1), input=(0,2), output=(0,1),
              bass=(-20,20), mid=(-15,15), treble=(-10,10), gate=(-81,-30), comp=(0,1), comp_post=(0,1), reverb=(0,1), decay=(.2,5), reverb_type=(0,2), chorus=(0,1), chorus_rate=(0.1,5), chorus_depth=(0,1), delay=(0,1), delay_ms=(20,1000), delay_feedback=(0,0.85))


# The native protocol retains effective amounts; separate remembered amounts
# preserve settings across bypass and restart, with legacy preset migration.
FX_DEFAULT_AMOUNTS = dict(comp=.35, chorus=.35, delay=.25, reverb=.25)

def normalize_fx(preset):
    p=dict(preset)
    # Legacy global bypass disabled both NAM slots and both cabinets.
    if "bypass" in p:
        legacy=p.pop("bypass")
        if type(legacy) is not bool: raise ValueError("Invalid legacy bypass")
        if legacy:
            p["nam1_enabled"]=False
        p.setdefault("bypass_nam2",legacy)
        p.setdefault("bypass_ir",legacy)
    for k,default in FX_DEFAULT_AMOUNTS.items():
        effective=p.get(k,0)
        if type(effective) not in (int,float) or not math.isfinite(effective) or not 0<=effective<=1:
            raise ValueError("Invalid "+k)
        amount=p.get(k+"_amount",effective if effective>0 else default)
        if type(amount) not in (int,float) or not math.isfinite(amount) or not .01<=amount<=1:
            raise ValueError("Invalid "+k+"_amount")
        p[k+"_amount"]=amount
        p[k]=amount if effective>0 else 0
    # The measured ReverbSc minimum is approximately 0.30 seconds.
    if type(p.get("decay")) in (int,float) and .2<=p["decay"]<.3:
        p["decay"]=.3
    return p

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
        self.metronome = dict(enabled=False,bpm=120,beats=4,volume=.15)
        self.practice=Practice()
        self.practice_analysis=threading.Lock()
        self.settingsfile = self.data / "settings.json"
        self.settings = dict(buffer=64, periods=3, last="1", reference_dbu=1.14)
        if self.settingsfile.exists(): self.settings.update(json.loads(self.settingsfile.read_text()))
        self.cpu_prev = None
        self.cpu_pct = None
        self.presets = {str(i): dict(DEFAULT) for i in range(1,5)}
        if self.statefile.exists():
            self.presets.update({k:dict(DEFAULT, **normalize_fx(v)) for k,v in json.loads(self.statefile.read_text()).items()})
        self.favoritesfile=self.data/"favorites.json"
        self.favorites=set(json.loads(self.favoritesfile.read_text())) if self.favoritesfile.exists() else set()
        self.appearancefile=self.data/"appearance.json"
        self.appearance=json.loads(self.appearancefile.read_text()) if self.appearancefile.exists() else {}
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

    def set_appearance(self,values,merge=False):
        if not isinstance(values,dict): raise ValueError("Invalid appearance map")
        updated=dict(self.appearance)
        for name,key in values.items():
            if key not in AMP_ART_KEYS and key!="auto": raise ValueError("Unknown artwork")
            if not self.file(name,(".nam",)).is_file():
                if merge: continue
                raise ValueError("Capture not found")
            if not merge or name not in updated: updated[name]=key
        self.write_json(self.appearancefile,updated)
        self.appearance=updated

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
        preset=normalize_fx(preset)
        p = dict(DEFAULT)
        for k in p:
            if k in preset:
                p[k] = preset[k]
        if "hiz_amount" not in preset and p["hiz"]>0:
            p["hiz_amount"]=p["hiz"]
        if type(p["hiz_amount"]) not in (int,float) or not math.isfinite(p["hiz_amount"]) or not 0<=p["hiz_amount"]<=1:
            raise ValueError("Invalid Hi-Z amount")
        if type(p["nam1_enabled"]) is not bool: raise ValueError("Invalid NAM 1 state")
        for key in ("bypass_nam2","bypass_ir"):
            if type(p[key]) is not bool: raise ValueError("Invalid "+key)
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
        # Keep the selected paths in the preset; omit only inactive stages from the native rig.
        second_is_ir=p["second"].lower().endswith(".wav")
        if p["model"]:
            cmd+=["--model",str(self.library/p["model"])]
        if p["second"] and ((second_is_ir and not p["bypass_ir"]) or (not second_is_ir and not p["bypass_nam2"])):
            cmd+=["--second",str(self.library/p["second"])]
        if not p["bypass_ir"]:
            for key in ("ir","ir2"):
                if p[key]: cmd+=["--"+key,str(self.library/p[key])]
        if not any(flag in cmd for flag in ("--model","--second","--ir","--ir2")):
            cmd+=["--bypass"]
        if not p["nam1_enabled"]: cmd+=["--nam1-off"]
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
        self.practice.stop(self.proc)
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            for fd in (getattr(self.proc,'rig_write',None),getattr(self.proc,'rig_ack',None),getattr(self.proc,'practice_write',None)):
                if fd is not None:
                    try: os.close(fd)
                    except OSError: pass
            self.proc=None
        self.active=None
        self.meter=None

    def drain(self,proc):
        # Engine reports a cumulative recovery count, including ALSA suspend
        # recovery. Count deltas, not log lines, to avoid double counting.
        for line in proc.stdout:
            line=line.rstrip()
            if line=="PRACTICE STOPPED":
                proc.practice_stopped.set()
                continue
            if line.startswith("TUNER "):
                try:
                    _,hz,confidence=line.split()
                    hz,confidence=float(hz),float(confidence)
                    if not math.isfinite(hz) or not math.isfinite(confidence): raise ValueError("Invalid pitch")
                    proc.rpit3k_pitch=(time.monotonic(),hz,confidence)
                except ValueError:
                    proc.rpit3k_pitch=None
                continue
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

    def apply(self,slot,p,benchmark=True,reopen=False):
        p=self.validate(p)
        if slot not in self.presets:
            raise ValueError("Invalid preset")
        cmd=self.command(p)
        if not reopen and self.proc and self.proc.poll() is None:
            self.replace_rig(cmd,slot)
            self.save(slot,p)
            self.settings['last']=slot
            self.persist_settings()
            return
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

    def tuner_reading(self):
        proc=self.proc
        if proc is None or self.active is not None or proc.poll() is not None:
            return dict(valid=False,hz=0,confidence=0)
        pitch=getattr(proc,"rpit3k_pitch",None)
        if pitch and time.monotonic()-pitch[0]<.35:
            _,hz,confidence=pitch
            return dict(valid=30<=hz<=1200 and confidence>=.8,hz=hz,confidence=confidence)
        return dict(valid=False,hz=0,confidence=0)

    def levels(self):
        m=self.meter
        if m and m[0] is self.proc and self.proc.poll() is None and time.monotonic()-m[1]<.5:
            return dict(valid=True,input=m[2],output=m[3],pitch=self.tuner_reading())
        return dict(valid=False,input=0,output=0,pitch=self.tuner_reading())

    def start(self,cmd,slot):
        rd,wr=os.pipe()
        req_rd,req_wr=os.pipe()
        ack_rd,ack_wr=os.pipe()
        practice_rd,practice_wr=os.pipe()
        self.meter=None
        try:
            self.proc=subprocess.Popen(cmd+["--live-controls","--meter-fd",str(wr),"--rig-fd",str(req_rd),"--rig-ack-fd",str(ack_wr),"--practice-fd",str(practice_rd)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                       text=True,bufsize=1,pass_fds=(wr,req_rd,ack_wr,practice_rd))
        except Exception:
            for fd in (rd,req_wr,ack_rd,practice_wr): os.close(fd)
            raise
        finally:
            for fd in (wr,req_rd,ack_wr,practice_rd): os.close(fd)
        self.proc.practice_stopped=threading.Event()
        self.proc.practice_write=practice_wr
        self.proc.rig_write=req_wr
        self.proc.rig_ack=ack_rd
        self.proc.rpit3k_xruns=0
        self.proc.rpit3k_pitch=None
        threading.Thread(target=self.drain_meter,args=(self.proc,rd),daemon=True).start()
        threading.Thread(target=self.drain,args=(self.proc,),daemon=True).start()
        time.sleep(.35)
        if self.proc.poll() is not None:
            raise ValueError("Audio engine stopped: "+"; ".join(list(self.logs)[-5:]))
        self.active=slot
        self.send_metronome()

    def send_metronome(self):
        if self.proc and self.proc.poll() is None:
            m=self.metronome
            self.proc.stdin.write(f"METRO {int(m['enabled'])} {m['bpm']} {m['beats']} {m['volume']}\n")
            self.proc.stdin.flush()

    def set_metronome(self,v):
        if not isinstance(v,dict): raise ValueError("Expected metronome settings")
        m=dict(self.metronome,**v)
        if set(m)!=set(self.metronome) or type(m["enabled"]) is not bool or type(m["bpm"]) is not int or not 30<=m["bpm"]<=300 or type(m["beats"]) is not int or not 1<=m["beats"]<=12 or not valid_number(m["volume"],0,.5):
            raise ValueError("Invalid metronome settings")
        if m["enabled"] and (not self.proc or self.proc.poll() is not None or self.active is None):
            raise ValueError("Turn Audio ON to hear the metronome")
        old=self.metronome
        self.metronome=m
        try: self.send_metronome()
        except OSError:
            self.metronome=old
            raise

    def replace_rig(self,cmd,slot):
        # Caller holds the controller lock, so there is only one outstanding request.
        proc=self.proc
        old_slot=self.active
        payload=json.dumps(cmd[1:],ensure_ascii=True).encode()+b"\n"
        if len(payload)>32768: raise ValueError("Rig request too large")
        try:
            while payload:
                n=os.write(proc.rig_write,payload)
                if not n: raise OSError("Rig request pipe closed")
                payload=payload[n:]
            response=b""
            deadline=time.monotonic()+30
            while b"\n" not in response:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not select.select([proc.rig_ack],[],[],remaining)[0]:
                    raise TimeoutError("Rig switch timed out")
                chunk=os.read(proc.rig_ack,1024)
                if not chunk: raise OSError("Rig acknowledgement pipe closed")
                response+=chunk
                if len(response)>2048: raise OSError("Invalid rig acknowledgement")
        except OSError:
            # A timed-out request must not activate later after reporting failure.
            self.stop()
            if old_slot:
                self.start(self.command(self.presets[old_slot]),old_slot)
            elif old_slot is None:
                self.start([str(self.exe),"--device",self.args.device,"--tuner"]+self.audio_args(),None)
            raise
        result=response.decode(errors="replace").strip()
        if result!="OK": raise ValueError(result.removeprefix("ERR "))
        proc.rpit3k_pitch=None
        self.active=slot

    def edit_preset(self,slot,p):
        if slot not in self.presets: raise ValueError("Invalid preset")
        p=self.validate(p)
        if self.proc and self.proc.poll() is None and self.active is not None:
            structural=("model","second","ir","ir2","slim","slim2","bypass_nam2","bypass_ir")
            if slot==self.active and all(p[k]==self.presets[slot][k] for k in structural):
                self.live_controls(slot,p)
            else:
                self.apply(slot,p,benchmark=False)
        else:
            self.save(slot,p)
            self.settings["last"]=slot
            if self.tuner_return is not None: self.tuner_return=slot
            self.persist_settings()

    def live_controls(self,slot,values):
        if slot!=self.active or self.proc is None or self.proc.poll() is not None:
            raise ValueError("Select the running preset first")
        keys=("input","output","bass","mid","treble","gate","comp","comp_post","reverb","decay","reverb_type","ir_mix","hiz","hiz_profile","chorus","chorus_rate","chorus_depth","delay","delay_ms","delay_feedback")
        p=dict(self.presets[slot])
        for k in keys:
            if k not in values: raise ValueError("Missing "+k)
            p[k]=values[k]
        for k in FX_DEFAULT_AMOUNTS:
            if k+"_amount" in values:p[k+"_amount"]=values[k+"_amount"]
            elif p[k]>0:p[k+"_amount"]=p[k]
        if "hiz_amount" in values: p["hiz_amount"]=values["hiz_amount"]
        if "nam1_enabled" in values:p["nam1_enabled"]=values["nam1_enabled"]
        p=self.validate(p)
        self.proc.stdin.write("STOMP "+str(int(p["nam1_enabled"]))+"\n")
        self.proc.stdin.write(" ".join(str(p[k]) for k in keys)+"\n")
        self.proc.stdin.flush()
        self.save(slot,p)

    def toggle_stomp(self):
        slot=self.active or self.settings["last"]
        p=dict(self.presets[slot])
        if not p["model"]:raise ValueError("Select NAM 1 first")
        p["nam1_enabled"]=not p["nam1_enabled"]
        if self.proc and self.proc.poll() is None and self.active==slot:
            self.proc.stdin.write("STOMP "+str(int(p["nam1_enabled"]))+"\n")
            self.proc.stdin.flush()
        self.save(slot,p)

    def toggle_audio(self):
        if self.proc and self.proc.poll() is None:
            self.metronome["enabled"]=False
            self.stop()
            self.tuner_return=None
        else:
            slot=self.settings["last"]
            self.apply(slot,self.presets[slot])

    def next_preset(self):
        slot=str(int(self.settings["last"])%4+1)
        self.edit_preset(slot,self.presets[slot])

    def configure(self,values):
        b,p=values.get("buffer"),values.get("periods")
        if type(b) is not int or type(p) is not int or b not in (64,128,256,512) or p not in (2,3,4): raise ValueError("Invalid audio settings")
        old=dict(self.settings);slot=self.active
        ref=values.get("reference_dbu",self.settings["reference_dbu"])
        if ref is not None and (type(ref) not in (int,float) or not math.isfinite(ref) or not -60<=ref<=30): raise ValueError("Invalid ADC reference in dBu")
        self.settings.update(buffer=b,periods=p,reference_dbu=ref)
        try:
            if (b,p)!=(old["buffer"],old["periods"]):
                if slot: self.apply(slot,self.presets[slot],benchmark=False,reopen=True)
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

    def button_status(self):
        return dict(presets={k:dict(v) for k,v in self.presets.items()},active=self.active,settings=dict(self.settings),running=self.proc is not None and self.proc.poll() is None,button_revision=getattr(self,"button_revision",0))

    def status(self):
        return dict(presets=self.presets,active=self.active,settings=self.settings,button_revision=getattr(self,"button_revision",0),telemetry=self.telemetry(),
                    cloud_enabled=not self.args.disable_cloud,
                    poweroff_enabled=os.environ.get("RPIT3K_ENABLE_POWEROFF")=="1",
                    running=self.proc is not None and self.proc.poll() is None,
                    files=self.library_files(),folders=self.library_folders(),favorites=sorted(self.favorites),amp_art=self.amp_art_versions(),appearance=dict(self.appearance),
                    logs=list(self.logs), tuner=self.tuner_reading(), metronome=self.metronome)

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

    def practice_path(self,name):
        if not isinstance(name,str) or not NAME.fullmatch(name) or Path(name).suffix.lower() not in (".wav",".mp3",".flac",".m4a",".ogg"):
            raise ValueError("Invalid track filename")
        root=self.server.controller.data/"practice-tracks"
        if root.is_symlink(): raise ValueError("Invalid tracks directory")
        root.mkdir(exist_ok=True)
        p=root/name
        if p.is_symlink(): raise ValueError("Invalid track")
        return p

    def stream_track(self,p):
        with p.open("rb") as f:
            size=os.fstat(f.fileno()).st_size
            start,end=0,size-1
            header=self.headers.get("Range")
            if header:
                m=re.fullmatch(r"bytes=(\d*)-(\d*)",header)
                if not m or not any(m.groups()):
                    self.send_error(416);return
                a,b=m.groups()
                if a: start=int(a);end=min(end,int(b)) if b else end
                else: start=max(0,size-int(b))
                if start>end or start>=size:
                    self.send_response(416);self.send_header("Content-Range",f"bytes */{size}");self.end_headers();return
            self.send_response(206 if header else 200)
            self.send_header("Content-Type",mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges","bytes")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(end-start+1))
            if header:self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
            self.end_headers()
            f.seek(start);remaining=end-start+1
            while remaining:
                chunk=f.read(min(65536,remaining))
                if not chunk:break
                self.wfile.write(chunk);remaining-=len(chunk)

    def do_GET(self):
        self.dispatch(False)

    def do_POST(self):
        self.dispatch(True)

    def dispatch(self,post):
        # Only maintenance is exclusive; normal audio/control requests remain concurrent.
        maintenance=post and urlsplit(self.path).path in ("/api/backup/export","/api/backup/restore")
        server=self.server
        with server.maintenance_condition:
            if server.maintenance or (maintenance and server.requests_active):
                self.send(409,dict(error="Maintenance or another request is active; retry shortly"));return
            if maintenance:server.maintenance=True
            server.requests_active+=1
        try:
            if post:self.handle_post()
            else:self.handle_get()
        finally:
            with server.maintenance_condition:
                server.requests_active-=1
                if maintenance:server.maintenance=False

    def backup_request(self,c,path):
        if c.proc is not None or c.practice_analysis.locked():
            raise ValueError("Turn Audio OFF and finish waveform analysis first")
        with tempfile.TemporaryDirectory(dir=c.data.parent) as td:
            archive=Path(td)/"ton3k.tar.gz"
            if path=="/api/backup/export":
                data_backup.backup(c.data,archive)
                self.send_response(200)
                self.send_header("Content-Type","application/gzip")
                self.send_header("Content-Disposition",'attachment; filename="ton3k-backup.tar.gz"')
                self.send_header("Cache-Control","no-store")
                self.send_header("Content-Length",str(archive.stat().st_size))
                self.end_headers()
                with archive.open("rb") as f:shutil.copyfileobj(f,self.wfile,1024*1024)
                return
            if self.headers.get("X-TON3K-Restore")!="replace":raise ValueError("Explicit restore confirmation required")
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=data_backup.MAX:raise ValueError("Invalid backup size")
            self.connection.settimeout(60)
            with archive.open("wb") as f:
                while size:
                    chunk=self.rfile.read(min(size,1024*1024))
                    if not chunk:raise ValueError("Incomplete backup upload")
                    f.write(chunk);size-=len(chunk)
            n,old,new=data_backup.restore(c.data,archive,lambda:Controller(c.args))
            self.server.controller=new
            self.send(200,dict(restored=n,previous_data=old.name if old else None))

    def handle_get(self):
        if not self.authorized(): return
        path=urlsplit(self.path).path
        if path=="/":
            self.send(200,(ROOT/"rpi/web.html").read_bytes(),"text/html; charset=utf-8")
        elif path=="/api/practice":
            root=self.server.controller.data/"practice-tracks"
            files=[]
            if root.is_dir() and not root.is_symlink():
                for p in root.iterdir():
                    try:
                        if self.practice_path(p.name).is_file():files.append(p.name)
                    except ValueError:pass
            self.send(200,dict(files=sorted(files,key=str.casefold)))
        elif path=="/api/practice/status":
            self.send(200,self.server.controller.practice.status())
        elif path=="/api/practice/waveform":
            c=self.server.controller
            try:
                p=self.practice_path(parse_qs(urlsplit(self.path).query).get("name",[""])[0])
                if not p.is_file():raise ValueError("Track not found")
                if c.practice.status()["playing"]:raise ValueError("Stop playback before waveform analysis")
                if not c.practice_analysis.acquire(blocking=False):raise ValueError("Analysis busy")
                try:result=practice_waveform(p,c.data/"practice-waveforms")
                finally:c.practice_analysis.release()
                self.send(200,result)
            except (ValueError,OSError,subprocess.SubprocessError) as e:self.send(400,dict(error=str(e)))
        elif path=="/api/practice/audio":
            try:
                p=self.practice_path(parse_qs(urlsplit(self.path).query).get("name",[""])[0])
                if not p.is_file():self.send(404,dict(error="Track not found"));return
                self.stream_track(p)
            except (BrokenPipeError,ConnectionResetError):pass
            except (ValueError,OSError):self.send(400,dict(error="Track unavailable"))
        elif path.startswith("/api/amp-art/"):
            try:
                asset=self.server.controller.amp_art_path(path.rsplit("/",1)[-1])
                if not asset.is_file() or asset.stat().st_size>AMP_ART_LIMIT: raise ValueError("Artwork unavailable")
                self.send(200,asset.read_bytes(),"image/webp")
            except (OSError,ValueError):
                self.send(404,dict(error="Artwork unavailable"))
        elif path=="/api/levels":
            c=self.server.controller
            data=c.levels()
            if c.lock.acquire(blocking=False):
                try: data["button"]=c.button_status()
                finally: c.lock.release()
            self.send(200,data)
        elif path=="/api/button-status":
            c=self.server.controller
            with c.lock: data=c.button_status()
            self.send(200,data)
        elif path=="/api/status":
            with self.server.controller.lock:
                self.send(200,self.server.controller.status())
        else: self.send(404,dict(error="Not found"))

    def handle_post(self):
        if not self.authorized(): return
        # Require a custom header: prevents cross-origin browser form submissions.
        if self.headers.get("X-RPiT3K")!="1":
            self.send(403,dict(error="Missing request header"))
            return
        c=self.server.controller
        u=urlsplit(self.path)
        try:
            if u.path in ("/api/backup/export","/api/backup/restore"):
                self.backup_request(c,u.path);return
            if u.path=="/api/practice/transport":
                v=json.loads(self.body(4096))
                action=v.get("action")
                if action=="stop":
                    with c.lock:c.practice.stop(c.proc)
                elif action=="play":
                    p=self.practice_path(v["name"])
                    if not p.is_file():raise ValueError("Track not found")
                    if c.practice_analysis.locked():raise ValueError("Wait for waveform analysis to finish")
                    length=practice_duration(p)
                    anchor,speed,pitch,volume,end=(v[k] for k in ("anchor","speed","pitch","volume","end"))
                    if not all(type(n) in (float,int) and math.isfinite(n) for n in (anchor,speed,pitch,volume,end)) or not (0<=anchor<end<=length+.01 and .5<=speed<=1.5 and -12<=pitch<=12 and 0<=volume<=1):
                        raise ValueError("Invalid playback controls")
                    with c.lock:
                        if not c.proc or c.proc.poll() is not None or c.active is None:raise ValueError("Turn Audio ON first")
                        c.practice.start(c.proc,p,anchor,speed,pitch,volume,min(end,length))
                else:raise ValueError("Unknown transport action")
                self.send(200,c.practice.status());return
            if u.path=="/api/practice/import":
                p=self.practice_path(parse_qs(u.query).get("name",[""])[0])
                n=int(self.headers.get("Content-Length","0"))
                if not 0<n<=256*1024*1024 or p.exists():raise ValueError("Invalid size or track already exists")
                with tempfile.NamedTemporaryFile(dir=p.parent,prefix=".import-",delete=False) as f:
                    tmp=Path(f.name)
                    try:
                        remaining=n
                        while remaining:
                            chunk=self.rfile.read(min(65536,remaining))
                            if not chunk:raise ValueError("Incomplete upload")
                            f.write(chunk);remaining-=len(chunk)
                        f.flush()
                        os.link(tmp,p)
                    finally:tmp.unlink(missing_ok=True)
                self.send(200,dict(imported=p.name));return
            if u.path in ("/api/poweroff","/api/reboot"):
                if os.environ.get("RPIT3K_ENABLE_POWEROFF")!="1":
                    self.send(403,dict(error="Power controls are not enabled on this installation"));return
                operation="reboot" if u.path=="/api/reboot" else "poweroff"
                if json.loads(self.body(1024))!={"confirm":operation}:
                    raise ValueError("Explicit power confirmation required")
                with c.lock:
                    # Check exact sudo permission before interrupting audio.
                    command=["/usr/bin/sudo","-n","/usr/bin/systemctl",operation]
                    permission=subprocess.run(["/usr/bin/sudo","-n","-l","/usr/bin/systemctl",operation],capture_output=True,text=True,timeout=10)
                    if permission.returncode:
                        raise ValueError("Power action not permitted: "+operation)
                    c.stop()
                    result=subprocess.run(command,capture_output=True,text=True,timeout=10)
                    if result.returncode:
                        raise ValueError("Power action failed: "+(result.stderr.strip() or "Permission denied"))
                    self.send(200,dict(operation=operation,accepted=True))
                return
            if u.path=="/api/ir-info":
                v=json.loads(self.body(65536))
                with c.lock:
                    path=c.file(v["model"],(".wav",))
                    if path.stat().st_size>LIMIT: raise ValueError("IR too large")
                    raw=path.read_bytes()
                self.send(200,ir_info(raw))
                return
            if u.path=="/api/capture-info":
                v=json.loads(self.body(65536))
                with c.lock:
                    path=c.file(v["model"],(".nam",))
                    if path.stat().st_size>LIMIT: raise ValueError("Model too large")
                    model=json.loads(path.read_text())
                self.send(200,capture_info(model))
                return
            if u.path=="/api/calibrate":
                v=json.loads(self.body(65536))
                slim=v.get("slim",1)
                if not valid_number(slim,0,1): raise ValueError("Invalid quality selection")
                with c.lock:
                    ref=c.settings.get("reference_dbu")
                    path=c.file(v["model"],(".nam",))
                    if path.stat().st_size>LIMIT: raise ValueError("Model too large")
                    model=json.loads(path.read_text())
                    self.send(200,calibration(model,ref,slim))
                return
            if u.path.startswith('/api/tone3000/'):
                if c.args.disable_cloud:
                    self.send(403,dict(error='Experimental TONE3000 integration disabled'));return
                v=json.loads(self.body(65536))
                if not isinstance(v,dict): raise ValueError('Expected object')
                self.send(200,c.cloud.action(u.path.rsplit('/',1)[-1],v))
                return
            # Physical controls must not walk the library or render telemetry.
            if u.path in ("/api/stomp","/api/next","/api/audio-toggle"):
                if self.client_address[0] not in ("127.0.0.1","::1"): raise ValueError("Local button endpoint only")
                started=time.monotonic()
                with c.lock:
                    acquired=time.monotonic()
                    if u.path=="/api/stomp": c.toggle_stomp()
                    elif u.path=="/api/next": c.next_preset()
                    else: c.toggle_audio()
                    c.button_revision=getattr(c,"button_revision",0)+1
                    compact=parse_qs(u.query).get("compact")==["1"]
                    data=c.button_status() if compact else c.status()
                print("BUTTON "+u.path.rsplit("/",1)[-1]+" lock_ms=%.1f action_ms=%.1f"%((acquired-started)*1000,(time.monotonic()-acquired)*1000),flush=True)
                self.send(200,data)
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
                elif u.path=="/api/appearance":
                    v=json.loads(self.body(65536))
                    c.set_appearance(v["values"],merge=v.get("merge") is True)
                    self.send(200,dict(appearance=dict(c.appearance)))
                    return
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
                elif u.path=="/api/edit":
                    v=json.loads(self.body(65536))
                    c.edit_preset(v["slot"],v["preset"])
                elif u.path=="/api/controls":
                    v=json.loads(self.body(65536))
                    c.live_controls(v["slot"],v["controls"])
                elif u.path=="/api/metronome":
                    c.set_metronome(json.loads(self.body(4096)))
                elif u.path=="/api/settings":
                    c.configure(json.loads(self.body(65536)))
                elif u.path=="/api/tuner":
                    c.practice.stop(c.proc)
                    if c.proc and c.proc.poll() is None and c.active is None:
                        previous=c.tuner_return
                        if previous:
                            c.apply(previous,c.presets[previous],benchmark=False)
                        else: c.stop()
                        c.tuner_return=None
                    else:
                        previous=c.active if c.proc and c.proc.poll() is None else None
                        cmd=[str(c.exe),"--device",c.args.device,"--tuner"]+c.audio_args()
                        if previous: c.replace_rig(cmd,None)
                        else:
                            c.stop()
                            c.start(cmd,None)
                        c.tuner_return=previous
                elif u.path=="/api/stop":
                    c.metronome["enabled"]=False
                    c.stop()
                    c.tuner_return=None
                elif u.path in ("/api/save","/api/apply"):
                    v=json.loads(self.body(65536))
                    if u.path=="/api/save": c.edit_preset(v["slot"],v["preset"])
                    else: c.apply(v["slot"],v["preset"])
                else:
                    self.send(404,dict(error="Not found"));return
                self.send(200,c.status())
        except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError, data_backup.tarfile.TarError, EOFError) as e:
            self.send(400,dict(error=str(e)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bind",default="127.0.0.1")
    p.add_argument("--port",type=int,default=8080)
    p.add_argument("--device",default="hw:pisound,0")
    p.add_argument("--data",default="~/.local/share/rpit3k")
    p.add_argument("--no-auth",action="store_true")
    p.add_argument("--autostart",action="store_true",help="Deprecated; audio always starts stopped")
    p.add_argument("--disable-cloud",action="store_true")
    a=p.parse_args()
    c=Controller(a)
    password=None if a.no_auth else (os.getenv("RPIT3K_PASSWORD") or secrets.token_urlsafe(12))
    server=ThreadingHTTPServer((a.bind,a.port),Handler)
    server.controller=c
    server.maintenance_condition=threading.Lock()
    server.maintenance=False
    server.requests_active=0
    server.password=password
    server.username=os.getenv("RPIT3K_USERNAME","rpit3k")
    print(f"RPiT3K http://{a.bind}:{a.port}  "+("no authentication (trusted LAN only)" if password is None else f"user={server.username}"),flush=True)
    if password and not os.getenv("RPIT3K_PASSWORD"): print("Temporary password: "+password,flush=True)
    # Always boot silently, including existing service units with --autostart.
    if a.autostart: print("--autostart ignored: audio starts stopped",flush=True)
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        with server.controller.lock: server.controller.stop()

if __name__=="__main__": main()
