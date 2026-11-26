"""Read-only NAM metadata projection; never expose weights or configuration arrays."""
import math

def clean(value,depth=0):
    if depth>5:return "[nested data]"
    if value is None or type(value) is bool:return value
    if isinstance(value,str):return value[:4096]
    if type(value) in (int,float):return value if math.isfinite(value) else None
    if isinstance(value,list):return [clean(v,depth+1) for v in value[:64]]
    if isinstance(value,dict):return {str(k)[:128]:clean(v,depth+1) for k,v in list(value.items())[:64]}
    return None

def capture_info(model):
    if not isinstance(model,dict):raise ValueError("Invalid NAM capture")
    def describe(m):
        return {k:clean(m[k]) for k in ("version","architecture","sample_rate","metadata") if k in m}
    result=describe(model)
    config=model.get("config")
    if model.get("architecture")=="SlimmableContainer" and isinstance(config,dict):
        subs=config.get("submodels")
        if isinstance(subs,list):
            result["submodels"]=[]
            for entry in subs[:32]:
                if not isinstance(entry,dict):continue
                child=entry.get("model")
                if isinstance(child,dict):
                    result["submodels"].append(dict(describe(child),max_value=clean(entry.get("max_value"))))
    return result
