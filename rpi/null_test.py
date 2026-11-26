#!/usr/bin/env python3
"""Compare production Chain to separately built upstream default NAM Core."""
import argparse
import array
import hashlib
import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

def read(path):
    a = array.array("f")
    a.frombytes(path.read_bytes())
    if sys.byteorder != "little":
        a.byteswap()
    return a

def run(args):
    subprocess.run([str(x) for x in args], check=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("model", type=Path)
    p.add_argument("--build", type=Path, default=Path("build-rpi"))
    args = p.parse_args()
    if sys.byteorder != "little":
        raise SystemExit("Little-endian host required")
    model = args.model.resolve()
    data = json.loads(model.read_text())
    sizes = [1, 0] if data.get("architecture") == "SlimmableContainer" else [1]
    print("Model SHA256:", hashlib.sha256(model.read_bytes()).hexdigest(), flush=True)
    rng = random.Random(20261125)
    samples = array.array("f")
    # Four seconds: silence, multitone, broadband excitation and decay.
    for i in range(192000):
        t = i / 48000
        if t < .5 or t >= 3.5:
            v = 0.
        elif t < 2:
            u = t - .5
            amp = [.005, .025, .1][min(2, int(u * 2))]
            v = amp * sum(math.sin(2*math.pi*f*t) for f in (82.4, 147, 330, 1000, 4500)) / 5
        else:
            v = .1 * rng.uniform(-1, 1) * min(1, (3.5-t)*4)
        samples.append(v)
    passed = True
    with tempfile.TemporaryDirectory(prefix="rpit3k-null-") as tmp:
        root = Path(tmp)
        src = root / "input.f32"
        src.write_bytes(samples.tobytes())
        for slim in sizes:
            for block in (64, 128):
                a, b = root / "production.f32", root / "reference.f32"
                run([args.build.resolve() / "rpit3k", "--model", model, "--slim", slim,
                     "--buffer", block, "--input", 1, "--output", .125,
                     "--render-in", src, "--render-out", a])
                run([args.build.resolve() / "nam-reference", model, slim, block, src, b])
                x, y = read(a), read(b)
                if len(x) != len(samples) or len(y) != len(samples):
                    raise RuntimeError("Render length mismatch")
                if not all(math.isfinite(v) for v in x) or not all(math.isfinite(v) for v in y):
                    raise RuntimeError("Nonfinite render")
                peak = max(map(abs, y))
                err = [u-v for u,v in zip(x,y)]
                rms = math.sqrt(math.fsum(v*v for v in err)/len(err))
                ref = math.sqrt(math.fsum(v*v for v in y)/len(y))
                relative = 20*math.log10(rms/ref) if rms and ref else (-math.inf if ref else math.inf)
                maxerr = max(map(abs, err))
                ok = ref > 1e-8 and peak < .99 and relative <= -80 and maxerr <= 1e-4
                print(f"NULL slim={slim} block={block} reference_rms={ref:.9g} reference_peak={peak:.9g} error_rms={rms:.9g} max_error={maxerr:.9g} relative_db={relative:.3f} {'PASS' if ok else 'FAIL'}", flush=True)
                passed &= ok
                a.unlink()
                b.unlink()
    print("NULL TEST", "PASS" if passed else "FAIL")
    return 0 if passed else 2

if __name__ == "__main__":
    sys.exit(main())
