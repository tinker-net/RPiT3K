#!/usr/bin/python3
"""Root-only updater. Never execute or parse a DEB until its detached signature verifies."""
import json, os, pathlib, shutil, stat, struct, subprocess, tempfile
P=pathlib.Path
BASE=P("/var/lib/rpi-ton3k-pisound")
KEY=P("/etc/rpi-ton3k/update-public.pem")
STATUS=P("/run/rpi-ton3k-update/status.json")
SERVICE="rpi-ton3k-pisound.service"
MAX=128*1024*1024
def run(*args):
    return subprocess.run(args,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.strip()
def status(phase,message):
    STATUS.parent.mkdir(mode=0o755,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=STATUS.parent,mode="w",delete=False) as f:
        json.dump(dict(phase=phase,message=message),f);tmp=P(f.name)
    tmp.chmod(0o644);tmp.replace(STATUS)
def unpack(src,deb,sig):
    fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or not 4<st.st_size<=MAX:raise ValueError("Invalid update upload")
        n=struct.unpack(">I",f.read(4))[0]
        if not 1<=n<=16384 or st.st_size<=4+n:raise ValueError("Invalid signature length")
        data=f.read(n)
        if len(data)!=n:raise ValueError("Incomplete signature")
        sig.write_bytes(data)
        remaining=st.st_size-4-n
        with deb.open("wb") as out:
            while remaining:
                chunk=f.read(min(remaining,1024*1024))
                if not chunk:raise ValueError("Incomplete package")
                out.write(chunk);remaining-=len(chunk)
def validate(deb,sig,key):
    if not key.is_file():raise ValueError("No trusted signing key configured")
    st=key.stat()
    if st.st_uid!=0 or st.st_mode&0o022:raise ValueError("Unsafe signing key ownership or permissions")
    run("/usr/bin/openssl","dgst","-sha256","-verify",str(key),"-signature",str(sig),str(deb))
    if run("/usr/bin/dpkg-deb","-f",str(deb),"Package")!="rpi-ton3k-pisound":raise ValueError("Wrong package")
    if run("/usr/bin/dpkg-deb","-f",str(deb),"Architecture")!=run("/usr/bin/dpkg","--print-architecture"):raise ValueError("Wrong architecture")
    new=run("/usr/bin/dpkg-deb","-f",str(deb),"Version")
    old=run("/usr/bin/dpkg-query","-W","-f=${Version}","rpi-ton3k-pisound")
    if subprocess.run(["/usr/bin/dpkg","--compare-versions",new,"gt",old]).returncode:raise ValueError("Only newer versions can be installed")
    return new
def main():
    stopped=False
    status("checking","Checking signature and package")
    try:
        with tempfile.TemporaryDirectory(prefix="ton3k-update-",dir="/var/tmp") as td:
            deb=P(td)/"update.deb";sig=P(td)/"update.sig"
            unpack(BASE/"update-upload.bin",deb,sig)
            version=validate(deb,sig,KEY)
            status("backup","Stopping audio and creating recovery backup")
            run("/usr/bin/systemctl","stop",SERVICE);stopped=True
            # Run backup as the unprivileged service account, never as root.
            import time
            archive=BASE/("before-update-"+str(time.time_ns())+".tar.gz")
            run("/usr/sbin/runuser","-u","rpi-ton3k-pisound","--","/usr/bin/python3","/usr/lib/rpi-ton3k/rpi/data_backup.py","backup",str(archive),"--data",str(BASE/"data"))
            status("installing","Installing signed package "+version)
            run("/usr/bin/apt-get","-y","--no-remove","--no-download","-o","Dpkg::Options::=--force-confold","install",str(deb))
            run("/usr/bin/systemctl","start",SERVICE)
            stopped=False
            status("complete","Installed "+version+"; recovery backup retained")
    except Exception as e:
        if stopped:
            subprocess.run(["/usr/bin/systemctl","start",SERVICE],check=False)
        status("failed",str(e)[-1000:])
        raise
if __name__=="__main__":main()
