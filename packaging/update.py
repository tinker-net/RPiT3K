#!/usr/bin/python3
"""Privileged fixed-origin update; no client-supplied URLs, paths or commands."""
import sys, json, pathlib, subprocess, tempfile, time, os
sys.path.insert(0,"/usr/lib/rpi-ton3k/rpi")
import release_update as u
P=pathlib.Path
def run(*a):
    return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT).strip()
def status(phase,message):
    u.STATUS.parent.mkdir(mode=0o755,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=u.STATUS.parent,mode="w",delete=False) as f:
        json.dump(dict(phase=phase,message=message),f);tmp=P(f.name)
    tmp.chmod(0o644);tmp.replace(u.STATUS)
def main():
    package=sys.argv[1]
    if package not in ("rpi-ton3k","rpi-ton3k-pisound"):raise ValueError("Invalid profile")
    service=package+".service";base=P("/var/lib")/package
    stopped=False
    status("checking","Checking signed release")
    try:
        info=json.loads(u.INFO.read_text())
        c=u.candidate(info)
        if not c or c["package"]!=package:raise ValueError("No matching newer signed release")
        st=u.KEY.stat()
        if st.st_uid!=0 or st.st_mode&0o022:raise ValueError("Unsafe signing key")
        with tempfile.TemporaryDirectory(prefix="ton3k-update-",dir="/var/tmp") as td:
            deb=P(td)/c["name"];sig=P(td)/"update.sig"
            status("download","Downloading "+c["version"])
            deb.write_bytes(u.fetch(c["url"],128*1024*1024));sig.write_bytes(u.fetch(c["sig"],16384))
            run("/usr/bin/openssl","dgst","-sha256","-verify",str(u.KEY),"-signature",str(sig),str(deb))
            for field,value in (("Package",package),("Architecture",c["arch"]),("Version",c["version"]),("X-TON3K-CPU",c["cpu"])):
                if run("/usr/bin/dpkg-deb","-f",str(deb),field)!=value:raise ValueError("Wrong update "+field)
            old=run("/usr/bin/dpkg-query","-W","-f=${Version}",package)
            if not u.newer(c["version"],old):raise ValueError("Only newer versions allowed")
            status("backup","Stopping audio and creating recovery backup")
            run("/usr/bin/systemctl","stop",service);stopped=True
            archive=base/("before-update-"+str(time.time_ns())+".tar.gz")
            run("/usr/sbin/runuser","-u",package,"--","/usr/bin/python3","/usr/lib/rpi-ton3k/rpi/data_backup.py","backup",str(archive),"--data",str(base/"data"))
            status("installing","Installing "+c["version"])
            run("/usr/bin/apt-get","-y","--no-remove","--no-download","-o","Dpkg::Options::=--force-confold","install",str(deb))
            run("/usr/bin/systemctl","start",service)
            stopped=False
            status("complete","Installed "+c["version"]+"; backup retained")
    except Exception as e:
        if stopped:subprocess.run(["/usr/bin/systemctl","start",service],check=False)
        status("failed",str(e)[-1000:])
        raise
if __name__=="__main__":main()
