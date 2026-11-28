"""Fetch pinned alphaTab distribution and stage only required resources."""
import pathlib, subprocess, sys, tarfile, shutil, tempfile, os
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
if not all((out/f).is_file() for f in ("alphaTab.min.js","Bravura.woff2","sonivox.sf2")):
    with tempfile.TemporaryDirectory() as t:
        npm=shutil.which("npm.cmd" if os.name=="nt" else "npm")
        if not npm:raise RuntimeError("npm required for embedded alphaTab")
        subprocess.run([npm,"pack","@coderline/alphatab@1.8.4","--pack-destination",t],check=True)
        with tarfile.open(next(pathlib.Path(t).glob("*.tgz"))) as a:
            for member in a.getmembers():
                name=pathlib.PurePosixPath(member.name).name
                if not member.isfile():continue
                if member.name.startswith("package/dist/") and (name=="alphaTab.min.js" or name.startswith("Bravura.") or name=="sonivox.sf2" or name.endswith(("worker.js","worklet.js"))):
                    with a.extractfile(member) as f:(out/name).write_bytes(f.read())
                elif member.name.count("/")==1 and "license" in name.lower():
                    with a.extractfile(member) as f:(out/("alphaTab-"+name)).write_bytes(f.read())
for name in ("alphaTab.min.js","Bravura.woff2","sonivox.sf2"):
    if not (out/name).is_file():raise RuntimeError("Missing "+name)
