"""Fixed-origin release discovery shared by controller and privileged installer."""
import json, pathlib, re, subprocess, urllib.request
REPO="tinker-net/RPiT3K"
KEY=pathlib.Path("/usr/share/rpi-ton3k/update-public.pem")
STATUS=pathlib.Path("/run/rpi-ton3k-update/status.json")
INFO=pathlib.Path("/usr/lib/rpi-ton3k/rpi/build-info.json")
def fetch(url,limit):
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"TON3K-updater","Accept":"application/vnd.github+json"}),timeout=25) as f:
        data=f.read(limit+1)
    if len(data)>limit:raise ValueError("Release response too large")
    return data
def newer(a,b):
    return subprocess.run(["/usr/bin/dpkg","--compare-versions",a,"gt",b]).returncode==0
def candidate(info):
    package="rpi-ton3k-pisound" if info["edition"]=="PiSound DEB" else "rpi-ton3k"
    arch=subprocess.check_output(["/usr/bin/dpkg","--print-architecture"],text=True).strip()
    cpu=info["cpu"]
    suffix=arch+("-"+cpu if cpu!="portable" else "")
    pattern=re.compile(re.escape(package)+"_([0-9][0-9A-Za-z.+~:-]*)_"+re.escape(suffix)+r"\.deb")
    releases=json.loads(fetch("https://api.github.com/repos/"+REPO+"/releases?per_page=30",4*1024*1024))
    best=None
    for rel in releases:
        tag=rel.get("tag_name","")
        if rel.get("draft") or not re.fullmatch(r"ton3k-experimental-[0-9]+",tag):continue
        assets={a["name"]:a for a in rel.get("assets",[])}
        for name,a in assets.items():
            m=pattern.fullmatch(name)
            if not m or name+".sig" not in assets or not newer(m[1],info["version"]):continue
            if best and not newer(m[1],best["version"]):continue
            base="https://github.com/"+REPO+"/releases/download/"+tag+"/"
            best=dict(version=m[1],name=name,url=base+name,sig=base+name+".sig",package=package,arch=arch,cpu=cpu)
    return best
def check():
    if not INFO.is_file():return dict(available=False,message="Source installation: install a matching DEB first.")
    if not KEY.is_file():return dict(available=False,message="No trusted release signing key in this installation.")
    c=candidate(json.loads(INFO.read_text()))
    return dict(available=bool(c),version=c["version"] if c else None,message="Signed update available" if c else "No newer signed release found")
def status():
    try:return json.loads(STATUS.read_text())
    except (OSError,ValueError):return dict(phase="idle",message="")
