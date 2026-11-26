#!/usr/bin/env python3
"""Versioned portable TON3K backup; offline CLI or exclusive web maintenance."""
import argparse, hashlib, json, os, pathlib, shutil, tarfile, tempfile, uuid
P=pathlib.Path
MAX=8*1024**3
MAX_FILES=100000
ROOTS={"library","presets.json","settings.json","favorites.json","appearance.json","amp-art","practice-tracks","trash"}
MANIFEST="manifest.json"
def digest(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def allowed(name):
    parts=name.split("/")
    return bool(parts and parts[0] in ROOTS and all(x not in ("",".","..") and "\\" not in x and not x.startswith(".") for x in parts))
def inventory(data):
    files={}
    for root in sorted(ROOTS):
        p=data/root
        if not p.exists() and not p.is_symlink():continue
        for x in [p,*p.rglob("*")]:
            name=x.relative_to(data).as_posix()
            if not allowed(name):continue
            if x.is_symlink() or not (x.is_file() or x.is_dir()):raise ValueError("Unsupported entry: "+name)
            if x.is_file():files[name]={"size":x.stat().st_size,"sha256":digest(x)}
    if len(files)>MAX_FILES or sum(v["size"] for v in files.values())>MAX:raise ValueError("Backup exceeds limits")
    return files
def backup(data,archive):
    if not data.is_dir() or data.is_symlink():raise ValueError("Invalid data directory")
    if archive.exists():raise ValueError("Archive already exists")
    if archive.resolve().is_relative_to(data.resolve()):raise ValueError("Archive must be outside data directory")
    files=inventory(data)
    import io
    with tempfile.NamedTemporaryFile(dir=archive.parent,delete=False) as f:tmp=P(f.name)
    try:
        with tarfile.open(tmp,"w:gz",compresslevel=3) as t:
            raw=json.dumps({"format":"ton3k-backup","version":1,"files":files},sort_keys=True).encode()
            m=tarfile.TarInfo(MANIFEST);m.size=len(raw);t.addfile(m,io.BytesIO(raw))
            for root in sorted(ROOTS):
                p=data/root
                if not p.exists():continue
                def filt(m):
                    if not allowed(m.name):return None
                    if not (m.isfile() or m.isdir()):raise ValueError("Unsupported entry")
                    m.uid=m.gid=0;m.uname=m.gname="";return m
                t.add(p,arcname=root,filter=filt)
        with tempfile.TemporaryDirectory(dir=archive.parent) as td:extract(tmp,P(td))
        os.link(tmp,archive)
    finally:tmp.unlink(missing_ok=True)
    return len(files)
def extract(archive,dest):
    """Stream bounded regular files into a private directory; reject links and duplicates."""
    seen=set();files={};total=0;manifest=None
    with tarfile.open(archive,"r|gz") as t:
        for m in t:
            name=m.name.rstrip("/")
            if name in seen or len(seen)>=MAX_FILES+1000:raise ValueError("Duplicate or excessive archive entries")
            seen.add(name)
            if not (m.isfile() or m.isdir()):raise ValueError("Unsupported archive entry")
            if name==MANIFEST:
                if not m.isfile() or m.size>32*1024**2:raise ValueError("Invalid manifest")
                manifest=json.load(t.extractfile(m));continue
            if not allowed(name):raise ValueError("Invalid archive path: "+name)
            p=dest/name
            if m.isdir():p.mkdir(parents=True,exist_ok=True);continue
            total+=m.size
            if total>MAX or m.size<0:raise ValueError("Expanded backup exceeds limit")
            p.parent.mkdir(parents=True,exist_ok=True)
            with p.open("xb") as f:shutil.copyfileobj(t.extractfile(m),f,1024*1024)
            files[name]={"size":p.stat().st_size,"sha256":digest(p)}
    if not isinstance(manifest,dict) or manifest.get("format")!="ton3k-backup" or manifest.get("version")!=1 or manifest.get("files")!=files:raise ValueError("Manifest or checksum mismatch")
    for name,kind in [("presets.json",dict),("settings.json",dict),("favorites.json",list),("appearance.json",dict)]:
        p=dest/name
        if p.exists() and not isinstance(json.loads(p.read_text()),kind):raise ValueError("Invalid "+name)
    return len(files)
def restore(data,archive,validate=None):
    if data.is_symlink():raise ValueError("Invalid data directory")
    data.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data.parent) as td:
        staged=P(td)/"data";staged.mkdir()
        count=extract(archive,staged)
        old=data.with_name(data.name+".before-restore-"+uuid.uuid4().hex[:12])
        if data.exists():data.rename(old)
        try:
            staged.rename(data)
            value=validate() if validate else None
        except BaseException:
            if data.exists():data.rename(staged)
            if old.exists():old.rename(data)
            raise
        return count,old if old.exists() else None,value
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=["backup","verify","restore"])
    p.add_argument("archive",type=P);p.add_argument("--data",type=P,default=P.home()/".local/share/rpit3k")
    a=p.parse_args();data=a.data.expanduser().absolute();archive=a.archive.expanduser().absolute()
    if archive.resolve().is_relative_to(data.resolve()):p.error("Archive must be outside data directory")
    if a.operation=="backup":print("Files:",backup(data,archive))
    elif a.operation=="verify":
        with tempfile.TemporaryDirectory(dir=archive.parent) as td:print("Verified files:",extract(archive,P(td)))
    else:
        n,old,_=restore(data,archive);print("Restored files:",n,"Previous data:",old)
if __name__=="__main__":main()
