"""Optional TONE3000 device OAuth and local model import. No audio-engine calls."""
import json
import os
import re
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode, urlsplit, urljoin
from pathlib import Path
import tempfile
import ipaddress
import socket

BASE = "https://www.tone3000.com/api/v1/"
LIMIT = 32 * 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ToneCloud:
    def __init__(self, controller):
        self.c = controller
        self.lock = threading.RLock()
        self.client = ""
        self.tokens = None
        self.pending = None
        self.http = urllib.request.build_opener(NoRedirect())
        self.tokenfile = self.c.data / "tone3000-session.json"
        self.load_tokens()


    def load_tokens(self):
        try:
            with self.tokenfile.open("r") as f: saved=json.load(f)
            if not isinstance(saved,dict) or not isinstance(saved.get("client"),str): return
            data=saved.get("tokens")
            if not isinstance(data,dict) or not isinstance(data.get("access_token"),str): return
            remaining=max(0.0,float(saved["expires_at"])-time.time())
            self.client=saved["client"]
            self.tokens=dict(data,deadline=time.monotonic()+remaining)
        except (OSError,ValueError,TypeError,KeyError,OverflowError):
            return

    def persist_tokens(self):
        if not self.tokens:
            self.tokenfile.unlink(missing_ok=True)
            return
        data={k:v for k,v in self.tokens.items() if k!="deadline"}
        saved=dict(client=self.client,tokens=data,expires_at=time.time()+max(0,self.tokens["deadline"]-time.monotonic()))
        fd,path=tempfile.mkstemp(prefix=".tone3000-",dir=self.tokenfile.parent)
        try:
            with os.fdopen(fd,"w") as f:
                json.dump(saved,f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(path,self.tokenfile)
        finally:
            if os.path.exists(path): os.unlink(path)

    @staticmethod
    def download_redirect(url, location):
        target=urljoin(url,location)
        u=urlsplit(target)
        if u.scheme!='https' or not u.hostname or u.port not in (None,443) or u.username or u.password:
            raise ValueError('Unsafe TONE3000 download redirect')
        host=u.hostname.lower()
        if host not in ('www.tone3000.com','tone3000.com','files.tone3000.com'):
            # External signed download URL: reject non-public addresses and never forward OAuth.
            try:
                addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
                if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                    raise ValueError('Unsafe TONE3000 download redirect host')
            except OSError:
                raise ValueError('TONE3000 download host unavailable') from None
        return target

    def fetch(self, url, form=None, token=None, binary=False):
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname not in ("www.tone3000.com","tone3000.com") or u.port not in (None,443) or u.username or u.password:
            raise ValueError("Unsupported TONE3000 download host")
        # Verified on ARM64 against files.tone3000.com: binary downloads
        # returned 403 with the default urllib headers, but 200 with this pair.
        headers = {"Accept": "application/json"} if not binary else {
            "Accept": "*/*", "User-Agent": "Mozilla/5.0"
        }
        if token: headers["Authorization"] = "Bearer " + token
        data = None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(form).encode()
        # Only authenticated binary GETs may follow redirects. API/OAuth
        # requests remain fail-closed. Once outside the origin, never reattach
        # the bearer credential, even if a subsequent redirect returns.
        for hop in range(6):
            req = urllib.request.Request(url,data=data,headers=headers)
            try:
                with self.http.open(req, timeout=15) as res:
                    raw = res.read(LIMIT+1 if binary else 2*1024*1024+1)
                if len(raw) > (LIMIT if binary else 2*1024*1024):
                    raise ValueError("Response too large")
                return raw if binary else json.loads(raw)
            except urllib.error.HTTPError as e:
                if binary and form is None and e.code in (301,302,303,307,308):
                    location=e.headers.get("Location")
                    e.close()
                    if not location or hop==5:
                        raise ValueError("TONE3000 download redirect missing or limit exceeded") from None
                    target=self.download_redirect(url,location)
                    # Explicitly trusted TONE3000 file origin, observed in a
                    # real download. Never forward a bearer to other hosts.
                    if urlsplit(target).hostname not in ("www.tone3000.com","tone3000.com","files.tone3000.com"):
                        headers.pop("Authorization",None)
                    url=target
                    continue
                if not binary:
                    try: body = json.loads(e.read(65536))
                    except (ValueError,OSError): body = {}
                    if isinstance(body,dict) and body.get("error") in ("authorization_pending","slow_down","expired_token","access_denied","invalid_grant","invalid_client"):
                        return {"error":body["error"]}
                # Do not log paths, query strings, response bodies or credentials.
                host=urlsplit(url).hostname or "unknown"
                stage=("download" if binary else "OAuth" if form is not None else "API")
                detail=f"TONE3000 HTTP {e.code} ({stage}; host={host}; redirects={hop})"
                if binary:
                    try:
                        body=e.read(8192)
                        match=re.search(rb"<Code>([A-Za-z0-9_]{1,64})</Code>",body)
                        if match: detail+="; storage_code="+match.group(1).decode("ascii")
                    except OSError: pass
                e.close()
                raise ValueError(detail) from None
            except urllib.error.URLError:
                raise ValueError("TONE3000 network unavailable") from None

    def store_tokens(self, data):
        if not data.get("access_token"): raise ValueError("Authorization failed")
        self.tokens = dict(data, deadline=time.monotonic()+float(data.get("expires_in",3600)))
        self.persist_tokens()

    def token(self):
        if not self.tokens: raise ValueError("Connect to TONE3000 first")
        if time.monotonic()+30 >= self.tokens["deadline"]:
            if not self.tokens.get("refresh_token"):
                self.tokens=None
                self.persist_tokens()
                raise ValueError("Session expired; reconnect")
            result=self.fetch(BASE+"oauth/token",form={"grant_type":"refresh_token","refresh_token":self.tokens["refresh_token"],"client_id":self.client})
            if not result.get("access_token"):
                self.tokens=None
                self.persist_tokens()
                raise ValueError("Session expired; reconnect")
            result.setdefault("refresh_token",self.tokens["refresh_token"])
            self.store_tokens(result)
        return self.tokens["access_token"]

    def api(self, path):
        return self.fetch(BASE+path,token=self.token())

    def action(self, op, v):
        with self.lock:
            if op=="status":
                return {"connected":bool(self.tokens)}
            if op=="disconnect":
                self.tokens=self.pending=None
                self.client=""
                self.persist_tokens()
                return {"connected":False}
            if op=="connect":
                client=v.get("client_id","").strip()
                if not client or len(client)>256 or client.startswith("t3k_cs_"):
                    raise ValueError("Enter a publishable key, not a secret key")
                result=self.fetch(BASE+"oauth/device_authorization",form={"client_id":client})
                interval=max(5,int(result.get("interval",5)))
                self.client=client
                self.tokens=None
                self.persist_tokens()
                self.pending=dict(code=result["device_code"],deadline=time.monotonic()+int(result["expires_in"]),interval=interval,next=time.monotonic()+interval)
                return {"user_code":result["user_code"],"interval":interval,"expires_in":result["expires_in"]}
            if op=="poll":
                p=self.pending
                if not p or time.monotonic()>=p["deadline"]:
                    self.pending=None
                    raise ValueError("Code expired; connect again")
                if time.monotonic()<p["next"]: return {"connected":False,"interval":p["interval"]}
                result=self.fetch(BASE+"oauth/token",form={"grant_type":"urn:ietf:params:oauth:grant-type:device_code","device_code":p["code"],"client_id":self.client})
                if result.get("error") in ("authorization_pending","slow_down"):
                    if result["error"]=="slow_down": p["interval"]+=5
                    p["next"]=time.monotonic()+p["interval"]
                    return {"connected":False,"interval":p["interval"]}
                self.pending=None
                self.store_tokens(result)
                return {"connected":True}
            if op=="tones":
                mode=v.get("mode","favorited")
                if mode not in ("favorited","downloaded","created","latest","trending"): raise ValueError("Invalid library")
                page=max(1,min(100,int(v.get("page",1))))
                result=self.api("tones/"+mode+("?"+urlencode({"page":page,"page_size":20}) if mode not in ("latest","trending") else ""))
                return {"data":[{k:t.get(k) for k in ("id","title","user","format","license","url")} for t in result.get("data",[])]}
            if op=="models":
                tid=int(v["tone_id"])
                arch=str(v.get("architecture","2"))
                if tid<1 or arch not in ("1","2"): raise ValueError("Invalid model selection")
                page=max(1,min(100,int(v.get("page",1))))
                result=self.api("models?"+urlencode({"tone_id":tid,"architecture":arch,"page":page,"page_size":50}))
                return {"data":[{k:m.get(k) for k in ("id","name","architecture_version")} for m in result.get("data",[])]}
            if op=="download":
                mid=int(v["model_id"])
                if mid<1: raise ValueError("Invalid model ID")
                model=self.api("models/"+str(mid))
                tone=self.api("tones/"+str(int(model["tone_id"])))
                ext={"nam":".nam","ir":".wav"}.get(tone.get("format"))
                if not ext: raise ValueError("Unsupported tone format")
                name=re.sub(r"[^\w .()+@-]","_",str(model.get("name") or "Model"))[:100].strip(" .") or "Model"
                rel="TONE3000/"+str(mid)+" - "+name+ext
                dest=self.c.file(rel,(ext,))
                if dest.exists(): return {"file":rel}
                raw=self.fetch(model["model_url"],token=self.token(),binary=True)
                if ext==".nam":
                    obj=json.loads(raw)
                    if not isinstance(obj,dict) or not obj.get("architecture"): raise ValueError("Not a NAM capture")
                elif raw[:4]!=b"RIFF" or raw[8:12]!=b"WAVE": raise ValueError("Not a WAV IR")
                with self.c.lock:
                    dest.parent.mkdir(exist_ok=True)
                    dest=self.c.file(rel,(ext,))
                    if not dest.exists():
                        with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as f:
                            tmp=Path(f.name)
                            try:
                                f.write(raw)
                                f.flush()
                                os.link(tmp,dest)
                            finally: tmp.unlink(missing_ok=True)
                return {"file":rel}
            raise ValueError("Unknown TONE3000 action")
