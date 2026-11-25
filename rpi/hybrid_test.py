#!/usr/bin/env python3
"""Controlled offline comparison of the actual hybrid executable, no ALSA."""
import argparse, array, hashlib, json, math, os, random, re, statistics, subprocess, sys, tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("a2",type=Path)
    p.add_argument("a1",type=Path)
    p.add_argument("--exe",type=Path,default=Path("build-rpi/rpit3k"))
    p.add_argument("--ir",type=Path)
    p.add_argument("--ir2",type=Path)
    p.add_argument("--repeats",type=int,default=3)
    a=p.parse_args()
    if sys.byteorder!="little" or a.repeats<1: p.error("Little endian and positive repeats required")
    exe=str(a.exe.resolve())
    rng=random.Random(20261125)
    signal=array.array("f")
    for i in range(192000):
        t=i/48000
        if t<.5 or t>=3.5: v=0.
        elif t<2:
            v=[.005,.025,.1][min(2,int((t-.5)*2))]*sum(math.sin(2*math.pi*f*t) for f in (82.4,147,330,1000,4500))/5
        else: v=.1*rng.uniform(-1,1)*min(1,(3.5-t)*4)
        signal.append(v)
    for model in (a.a2,a.a1):
        print(f"MODEL {model} SHA256={hashlib.sha256(model.read_bytes()).hexdigest()}",flush=True)
    passed=True
    def invoke(flags,mode,expected):
        env=dict(os.environ,RPIT3K_NAM_ENGINE=mode)
        r=subprocess.run([exe,*map(str,flags)],env=env,capture_output=True,text=True,check=True)
        engines=re.findall(r"NAM_ENGINE=(embedded|core) ",r.stderr)
        if engines!=expected:
            raise RuntimeError(f"Expected {expected}, got {engines}: {r.stderr}")
        return r.stdout
    def read(path):
        b=array.array("f");b.frombytes(path.read_bytes());return b
    with tempfile.TemporaryDirectory(prefix="hybrid-test-") as d:
        d=Path(d);src=d/"in.raw";src.write_bytes(signal.tobytes())
        def compare(name,flags,expected,blocks=(64,128,256,512)):
            nonlocal passed
            for block in blocks:
                base=[*flags,"--buffer",block,"--input",1,"--output",.125]
                outs=[]
                for mode,eng in (("auto",expected),("core",["core"]*len(expected))):
                    dst=d/f"{mode}.raw"
                    invoke([*base,"--render-in",src,"--render-out",dst],mode,eng)
                    outs.append(read(dst));dst.unlink()
                x,y=outs
                if len(x)!=len(signal) or len(y)!=len(signal): raise RuntimeError("Length mismatch")
                if not all(math.isfinite(v) for v in (*x,*y)): raise RuntimeError("Nonfinite output")
                ref=math.sqrt(math.fsum(v*v for v in y)/len(y))
                err=[u-v for u,v in zip(x,y)]
                rms=math.sqrt(math.fsum(v*v for v in err)/len(err))
                peak=max(map(abs,y));maxerr=max(map(abs,err))
                db=20*math.log10(rms/ref) if rms and ref else (-math.inf if ref else math.inf)
                ok=ref>1e-8 and peak<.99 and max(map(abs,x))<.99 and db<=-80 and maxerr<=1e-4
                print(f"NULL {name} block={block} engines={'+'.join(expected)} ref_rms={ref:.8g} peak={peak:.8g} residual_rms={rms:.8g} max_error={maxerr:.8g} relative_db={db:.2f} {'PASS' if ok else 'FAIL'}",flush=True)
                passed &= ok
        def bench(name,flags,expected):
            base=[*flags,"--buffer",64,"--input",1,"--output",.125,"--benchmark"]
            values={"auto":[],"core":[]};peaks={"auto":[],"core":[]}
            for i in range(a.repeats):
                for mode in (("core","auto") if i%2 else ("auto","core")):
                    out=invoke(base,mode,expected if mode=="auto" else ["core"]*len(expected))
                    match=re.search(r"mean_us=([0-9.eE+-]+) max_us=([0-9.eE+-]+) deadline_us=([0-9.eE+-]+)",out)
                    if not match: raise RuntimeError(out)
                    mean,peak,deadline=map(float,match.groups())
                    values[mode].append(mean);peaks[mode].append(peak)
            x,y=statistics.median(values["auto"]),statistics.median(values["core"])
            print(f"BENCH {name} auto_median_us={x:.3f} core_median_us={y:.3f} speedup={y/x:.3f} auto_worst_us={max(peaks['auto']):.3f} core_worst_us={max(peaks['core']):.3f} deadline_us={deadline:.3f} repeats={a.repeats}",flush=True)
        full=["--model",a.a2,"--slim",1]
        lite=["--model",a.a2,"--slim",0]
        old=["--model",a.a1]
        if json.loads(a.a2.read_text()).get("architecture")!="SlimmableContainer": p.error("A2 must be a Full/Lite container")
        mixed=[*old,"--second",a.a2,"--slim2",1]
        for name,flags,eng in (("FULL",full,["embedded"]),("LITE",lite,["embedded"]),("A1",old,["core"]),("MIXED",mixed,["core","embedded"])):
            compare(name,flags,eng)
            bench(name,flags,eng)
        if a.ir:
            rig=[*full,"--ir",a.ir]
            if a.ir2: rig.extend(["--ir2",a.ir2,"--ir_mix",.5])
            compare("RIG",rig,["embedded"],(64,128))
            bench("RIG",rig,["embedded"])
    print("HYBRID TEST", "PASS" if passed else "FAIL",flush=True)
    return 0 if passed else 2
if __name__=="__main__": sys.exit(main())
