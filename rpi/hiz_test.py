#!/usr/bin/env python3
"""Measure the actual production Chain, not a duplicate of the C++ filter.
Only Python stdlib required. No ALSA device or NAM capture needed."""
import array, cmath, math, pathlib, subprocess, sys, tempfile
fs=48000
profiles=[("Telecaster",8000,3.5,250000),("Stratocaster",6000,2.4,250000),("PAF",8000,4.5,500000),("P90",8500,5.5,500000)]
freqs=[82,440,1000,2000,3000,4000,5000,8000]
exe=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "build-rpi/rpit3k").resolve()
def render(x,amount,profile,folder,name):
    src=folder/"input.raw";dst=folder/(name+".raw")
    src.write_bytes(array.array("f",x).tobytes())
    subprocess.run([str(exe),"--bypass","--buffer","64","--input","1","--output",".25","--hiz",str(amount),"--hiz_profile",str(profile),"--render-in",str(src),"--render-out",str(dst)],check=True,stdout=subprocess.DEVNULL)
    y=array.array("f");y.frombytes(dst.read_bytes())
    assert len(y)==len(x)
    return y
def phasor(y,f):
    return sum(y[i]*cmath.exp(-2j*math.pi*f*i/fs) for i in range(fs,2*fs))
def reference(f,R,L,Rv):
    # Independent circuit evaluation using complex impedances.
    s=1j*2*fs*math.tan(math.pi*f/fs)
    Z=R+s*L
    def H(load):
        Y=1/load+1/Rv+s*470e-12
        return 1/(1+Z*Y)
    return H(1e6)/H(1e5)
with tempfile.TemporaryDirectory() as d:
    folder=pathlib.Path(d)
    for p,(name,R,L,Rv) in enumerate(profiles):
        maxerr=0
        print(name)
        for f in freqs:
            x=[.025*math.sin(2*math.pi*f*i/fs) for i in range(2*fs)]
            off=render(x,0,p,folder,f"{p}-{f}-off")
            on=render(x,1,p,folder,f"{p}-{f}-on")
            partial=render(x,.8,p,folder,f"{p}-{f}-80")
            base=phasor(off,f)
            expected=reference(f,R,L,Rv)
            measured=phasor(on,f)/base
            measured80=phasor(partial,f)/base
            err=max(abs(measured-expected),abs(measured80-(.2+.8*expected)))
            maxerr=max(maxerr,err)
            residual=math.sqrt(sum((a-b)**2 for a,b in zip(on[fs:],off[fs:]))/fs)
            print(f"  {f:5} Hz: {20*math.log10(abs(measured)):+6.2f} dB | 80% {20*math.log10(abs(measured80)):+6.2f} dB | residual RMS {residual:.7f} | complex error {err:.3g}")
            if err>1e-4: raise SystemExit("FAIL: model mismatch")
        print(f"  PASS: maximum complex error {maxerr:.3g}")
print("PASS: production DSP Hi-Z compensation matches circuit model.")
