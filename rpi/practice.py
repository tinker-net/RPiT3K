"""On-demand backing track decoder and bounded waveform cache."""
import subprocess, json, math, os, struct, time, threading, hashlib, pathlib, tempfile, shutil

def background_command(args):
    """Lower priority and exclude the engine CPU on systems with >= 4 allowed CPUs."""
    prefix=[]
    cpus=sorted(os.sched_getaffinity(0))
    if len(cpus)>=4 and shutil.which("taskset") and os.getenv("RPIT3K_AUDIO_AFFINITY","1")!="0":
        prefix+=["taskset","-c",",".join(map(str,cpus[:-1]))]
    if shutil.which("nice"):prefix+=["nice","-n","10"]
    if shutil.which("ionice"):prefix+=["ionice","-c","2","-n","7"]
    return prefix+args

def ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("Install ffmpeg and ffprobe (sudo apt install ffmpeg)")
    return "ffmpeg"

def duration(path):
    ffmpeg()
    n=float(subprocess.check_output(background_command(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)]),text=True,timeout=20))
    if not math.isfinite(n) or not 0<n<=7200:raise ValueError("Track duration unsupported")
    return n

def waveform(path,cache):
    st=path.stat()
    key=hashlib.sha256((str(path)+str(st.st_size)+str(st.st_mtime_ns)).encode()).hexdigest()
    cache.mkdir(exist_ok=True)
    dest=cache/(key+".json")
    if dest.is_file():return json.loads(dest.read_text())
    seconds=duration(path)
    # Decode at low rate; bounded peak envelope, not a whole-song PCM allocation.
    proc=subprocess.Popen(background_command([ffmpeg(),"-nostdin","-v","error","-threads","1","-filter_threads","1","-i",str(path),"-vn","-ac","1","-ar","4000","-f","s16le","pipe:1"]),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    peaks=[0]*1200; pos=0
    try:
        while True:
            data=proc.stdout.read(8192)
            if not data:break
            for (v,) in struct.iter_unpack("<h",data):
                i=min(1199,int(pos*1200/(seconds*4000)))
                peaks[i]=max(peaks[i],abs(v));pos+=1
        if proc.wait(timeout=10):raise ValueError("Cannot decode track")
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
        proc.stdout.close()
    result=dict(duration=seconds,peaks=[round(v/32768,4) for v in peaks])
    with tempfile.NamedTemporaryFile(dir=cache,mode="w",delete=False) as f:
        tmp=pathlib.Path(f.name);json.dump(result,f)
    os.replace(tmp,dest)
    return result

class Practice:
    def __init__(self):
        self.decoder=None
        self.started=0.
        self.anchor=0.
        self.speed=1.
        self.end=0.
        self.volume=.25
    def stop(self,engine):
        if self.decoder is not None:
            if self.decoder.poll() is None:
                self.decoder.terminate()
                try:self.decoder.wait(timeout=.4)
                except subprocess.TimeoutExpired:self.decoder.kill();self.decoder.wait()
            self.decoder=None
        if engine and engine.poll() is None:
            engine.practice_stopped.clear()
            try:engine.stdin.write("PRACTICE 0 0\n");engine.stdin.flush()
            except OSError:pass
    def start(self,engine,path,anchor,speed,pitch,volume,end):
        ffmpeg()
        self.stop(engine)
        # Drain old pipe contents in the controller before starting the new decoder.
        # Audio thread also drains on disable. Both only discard old audio here.
        # Wait for the realtime reader to acknowledge the stop and discard stale PCM.
        if not engine.practice_stopped.wait(timeout=.5):raise ValueError("Audio transport did not acknowledge stop")
        self.anchor,self.speed,self.end,self.volume=anchor,speed,end,volume
        ratio=2**(pitch/12)
        filters=[]
        if pitch:
            filters.append("rubberband=tempo="+str(speed)+":pitch="+str(ratio))
        elif speed!=1:filters.append("atempo="+str(speed))
        args=[ffmpeg(),"-nostdin","-v","error","-threads","1","-filter_threads","1","-ss",str(anchor),"-i",str(path),"-t",str((end-anchor)/speed),"-vn","-ac","2","-ar","48000"]
        if filters:args+=["-af",",".join(filters)]
        args+=["-f","f32le","pipe:1"]
        # FFmpeg runs at ordinary priority; pipe backpressure limits memory.
        self.decoder=subprocess.Popen(background_command(args),stdout=engine.practice_write,stderr=subprocess.DEVNULL)
        engine.stdin.write(f"PRACTICE 1 {volume}\n");engine.stdin.flush()
        self.started=time.monotonic()
    def status(self):
        playing=self.decoder is not None and self.decoder.poll() is None
        return dict(error="Decoder failed" if self.decoder is not None and self.decoder.poll() not in (None,0) else None,playing=playing,position=min(self.end,self.anchor+(time.monotonic()-self.started)*self.speed) if playing else self.anchor)
