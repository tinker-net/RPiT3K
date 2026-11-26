#!/usr/bin/env python3
"""Offline data backup/restore. Run as service user with service stopped."""
import argparse, os, tarfile, tempfile, pathlib, shutil, datetime
P=pathlib.Path
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=["backup","restore"])
    p.add_argument("archive",type=P)
    p.add_argument("--data",type=P,default=P.home()/".local/share/rpit3k")
    a=p.parse_args()
    data=a.data.expanduser().absolute()
    archive=a.archive.expanduser().absolute()
    if archive.is_relative_to(data):p.error("Archive must be outside data directory")
    if a.operation=="backup":
        if not data.is_dir() or data.is_symlink():p.error("Invalid data directory")
        if archive.exists():p.error("Archive exists")
        with tempfile.NamedTemporaryFile(dir=archive.parent,delete=False) as f:
            temp=P(f.name)
        try:
            with tarfile.open(temp,"w:gz") as t:
                def check(m):
                    if not (m.isfile() or m.isdir()):raise ValueError("Unsupported archive entry: "+m.name)
                    return m
                t.add(data,arcname="rpit3k",filter=check)
            os.link(temp,archive)
        finally:temp.unlink(missing_ok=True)
    else:
        if data.is_symlink():p.error("Invalid data directory")
        data.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=data.parent) as tmp:
            with tarfile.open(archive,"r:gz") as t:
                members=t.getmembers()
                if not members or any(not (m.isfile() or m.isdir()) or not P(m.name).parts or P(m.name).parts[0]!="rpit3k" or ".." in P(m.name).parts for m in members):
                    p.error("Invalid backup archive")
                t.extractall(tmp,filter="data")
            restored=P(tmp)/"rpit3k"
            if not restored.is_dir():p.error("Missing data directory")
            old=data.with_name(data.name+".before-restore-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
            if old.exists():p.error("Previous restore path exists")
            if data.exists():data.rename(old)
            try:restored.rename(data)
            except Exception:
                if old.exists():old.rename(data)
                raise
            if old.exists():print("Previous data retained at",old)
    print(a.operation,"complete:",archive)
if __name__=="__main__":main()
