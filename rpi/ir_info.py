"""Bounded RIFF/WAVE header and INFO inspection, without decoding audio."""
import struct
import unicodedata


def readable_text(raw):
    # RIFF INFO and BEXT text fields may be NUL-padded. Reject binary data,
    # embedded control characters and invalid UTF-8 instead of displaying it.
    raw=raw.split(b"\0",1)[0].strip()
    if not raw:return None
    try:
        value=raw.decode("utf-8",errors="strict")
    except UnicodeDecodeError:
        return None
    if any(unicodedata.category(ch).startswith("C") and ch not in "\t\r\n" for ch in value):return None
    if not any(ch.isalnum() for ch in value):return None
    return " ".join(value.split())[:512] or None

def ir_info(raw):
    if len(raw)<12 or raw[:4]!=b"RIFF" or raw[8:12]!=b"WAVE":
        raise ValueError("Invalid RIFF WAV")
    end=8+struct.unpack_from("<I",raw,4)[0]
    if end>len(raw):raise ValueError("Truncated WAV")
    fmt=None;size=None;meta={}
    names={b"INAM":"name",b"IART":"author",b"ICMT":"comment",b"ICRD":"date",b"IPRD":"product",b"ISFT":"software",b"ICOP":"copyright"}
    pos=12
    while pos+8<=end:
        tag,n=struct.unpack_from("<4sI",raw,pos);p=pos+8;q=p+n
        if q>end:raise ValueError("Truncated WAV chunk")
        if tag==b"fmt " and n>=16:
            fmt=struct.unpack_from("<HHIIHH",raw,p)
            if fmt[0]==65534 and n>=40:
                fmt=(struct.unpack_from("<H",raw,p+24)[0],*fmt[1:])
        elif tag==b"data" and size is None:size=n
        elif tag==b"LIST" and raw[p:p+4]==b"INFO":
            j=p+4
            while j+8<=q:
                key,l=struct.unpack_from("<4sI",raw,j);a=j+8;b=a+l
                if b>q:break
                if key in names:
                    value=readable_text(raw[a:min(b,a+2048)])
                    if value:meta[names[key]]=value
                j=b+(l&1)
        elif tag==b"bext" and n>=256:
            for key,offset,length in (("description",0,256),("originator",256,32),("date",320,10)):
                if n>=offset+length:
                    v=readable_text(raw[p+offset:p+offset+length])
                    if v:meta.setdefault(key,v)
        pos=q+(n&1)
    if fmt is None or size is None:raise ValueError("Missing WAV format or data")
    code,channels,rate,_,align,bits=fmt
    if not channels or not rate or not align or not bits or size%align:raise ValueError("Invalid WAV format")
    frames=size//align
    effective=(frames*48000+rate-1)//rate
    compatible=channels==1 and 8000<=rate<=384000 and 0<effective<=48000 and code in (1,3)
    return dict(sample_rate=rate,bits=bits,channels=channels,frames=frames,duration_ms=1000*frames/rate,encoding={1:"PCM",3:"IEEE float"}.get(code,"Unsupported"),engine_rate=48000,engine_frames=effective if compatible else None,engine_duration_ms=effective/48 if compatible else None,compatible=compatible,metadata=meta)
