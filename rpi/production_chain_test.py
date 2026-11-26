#!/usr/bin/env python3
"""Exercise real production executable with synthetic NAM and WAV, no hardware."""
import array, json, math, subprocess, sys, tempfile, wave, struct
from pathlib import Path
exe=Path(sys.argv[1]).resolve()
if sys.byteorder!="little": raise SystemExit("Little-endian host required")
def run(root, name, args):
    src=root/"input.f32";dst=root/(name+".f32")
    subprocess.run([str(exe),"--buffer","64","--input","1","--output","0.25",*map(str,args),"--render-in",str(src),"--render-out",str(dst)],check=True)
    y=array.array("f");y.frombytes(dst.read_bytes())
    if len(y)!=4096 or not all(math.isfinite(x) for x in y): raise RuntimeError("Invalid render")
    return y
def close(a,b,msg,tol=2e-6):
    err=max(abs(x-y) for x,y in zip(a,b))
    print(msg,"max_abs_error",err)
    if err>tol: raise RuntimeError(msg)
with tempfile.TemporaryDirectory() as d:
    p=Path(d);model=p/"identity.nam"
    model.write_text(json.dumps({"version":"0.5.4","architecture":"Linear","config":{"receptive_field":1,"bias":False},"weights":[1.0],"sample_rate":48000}))
    x=array.array("f",[0.0]*4096);x[128]=.5;x[512]=-.25;(p/"input.f32").write_bytes(x.tobytes())
    for name,taps in (("a",[16384,0,8192]),("b",[0,8192,0,16384])):
        with wave.open(str(p/(name+".wav")),"wb") as w:
            w.setparams((1,2,48000,0,"NONE","not compressed"));w.writeframes(struct.pack("<"+"h"*len(taps),*taps))
    base=run(p,"bypass",["--bypass"])
    close(run(p,"first",["--model",model]),base,"identity first slot")
    close(run(p,"second",["--second",model]),base,"identity second slot")
    close(run(p,"both",["--model",model,"--second",model]),base,"serial identity slots")
    a=run(p,"ir_a",["--model",model,"--ir",p/"a.wav"])
    b=run(p,"ir_b",["--model",model,"--ir2",p/"b.wav"])
    if max(abs(i-j) for i,j in zip(a,b))<.01:raise RuntimeError("Distinct IRs not applied")
    for mix in (0,.25,.5,1):
        dual=run(p,"dual"+str(mix),["--model",model,"--ir",p/"a.wav","--ir2",p/"b.wav","--ir_mix",mix])
        close(dual,[i+mix*(j-i) for i,j in zip(a,b)],"dual IR blend "+str(mix))
    gain=p/"gain.nam"
    gain.write_text(json.dumps({"version":"0.5.4","architecture":"Linear","config":{"receptive_field":1,"bias":False},"weights":[0.5],"sample_rate":48000}))
    close(run(p,"ir_only",["--ir",p/"a.wav"]),a,"IR without NAM")
    close(run(p,"legacy_ir_only",["--second",p/"a.wav"]),a,"legacy IR without NAM")
    both=run(p,"two_gain",["--model",gain,"--second",gain,"--ir",p/"a.wav"])
    close(both,[v*.25 for v in a],"two NAM plus IR")
    close(run(p,"nam2_off",["--model",gain,"--ir",p/"a.wav"]),[v*.5 for v in a],"NAM 2 bypass leaves IR")
    close(run(p,"ir_off",["--model",gain,"--second",gain]),[v*.25 for v in base],"IR bypass leaves both NAM")
    close(run(p,"nam1_off",["--model",gain,"--nam1-off","--second",gain,"--ir",p/"a.wav"]),[v*.5 for v in a],"NAM 1 stomp leaves NAM 2 and IR")
    close(run(p,"bypass_loaded",["--bypass","--model",model,"--ir",p/"a.wav","--ir2",p/"b.wav"]),base,"NAM/IR bypass")
print("Production chain routing PASS")
