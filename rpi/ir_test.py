#!/usr/bin/env python3
"""Validate the production WAV loader, IR resampler and convolver against SciPy."""
import argparse
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

def db(x):
    return 20 * np.log10(max(float(x), 1e-30))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, default=Path("build-rpi"))
    args = p.parse_args()
    exe = args.build.resolve() / "rpit3k"
    passed = True
    with tempfile.TemporaryDirectory(prefix="rpit3k-ir-") as tmp:
        root = Path(tmp)
        src, dst, wav = [root / n for n in ("in.f32", "out.f32", "test.wav")]
        # The production chain requires a model unless bypassed, and bypass
        # disables the IR. Use a synthetic identity NAM model (Linear).
        import json
        model = root / "identity.nam"
        model.write_text(json.dumps({"version":"0.5.4","architecture":"Linear",
            "config":{"receptive_field":1,"bias":False},"weights":[1.0],"sample_rate":48000}))
        impulse = np.zeros(49152, dtype="<f4")
        impulse[0] = 1
        impulse.tofile(src)
        def render(h, sr):
            wavfile.write(wav, sr, h.astype(np.float32))
            if dst.exists():
                dst.unlink()
            subprocess.run([str(exe), "--model", str(model), "--ir", str(wav),
                "--input","1","--output","0.125","--buffer","64",
                "--render-in",str(src),"--render-out",str(dst)],check=True)
            y = np.fromfile(dst,dtype="<f4").astype(np.float64)*8
            if len(y)!=len(impulse) or not np.all(np.isfinite(y)):
                raise RuntimeError("Invalid render")
            return y
        for sr in (44100,48000,96000):
            # Smooth, delayed band-limited cabinet-like test impulse.
            n = sr // 20
            t = np.arange(n)/sr - .01
            h = .1 * np.sinc(12000*t) * np.exp(-(t/.0015)**2)
            y = render(h,sr)
            g = math.gcd(sr,48000)
            ref = resample_poly(h,48000//g,sr//g,window=("kaiser",12.0))*sr/48000
            length = len(ref)
            err = db(np.linalg.norm(y[:length]-ref)/np.linalg.norm(ref))
            gain = db(abs(y[:length].sum()/ref.sum()))
            tail = np.max(np.abs(y[length:]))
            peak_shift = abs(int(np.argmax(abs(y)))-int(np.argmax(abs(ref))))
            ok = err <= -50 and abs(gain)<=.1 and tail<=1e-5 and peak_shift<=1
            print(f"IR rate={sr} expected_frames={length} residual_db={err:.2f} dc_gain_db={gain:.4f} peak_shift={peak_shift} tail={tail:.3g} {'PASS' if ok else 'FAIL'}",flush=True)
            passed &= ok
        # Downsampling anti-alias test: equal-amplitude windowed tones
        # at 10 kHz (passband) and 36 kHz (above destination Nyquist).
        sr=96000
        t=np.arange(sr//20)/sr
        w=np.hanning(len(t))
        low=render(.01*w*np.sin(2*np.pi*10000*t),sr)
        high=render(.01*w*np.sin(2*np.pi*36000*t),sr)
        alias=db(np.linalg.norm(high)/np.linalg.norm(low))
        ok=alias<=-50
        print(f"IR alias_rejection_db={alias:.2f} {'PASS' if ok else 'FAIL'}")
        passed &= ok
    print("IR TEST", "PASS" if passed else "FAIL")
    return 0 if passed else 2

if __name__=="__main__":
    raise SystemExit(main())
