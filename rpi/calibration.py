"""Pure capture-reference inspection. Missing metadata is not a broken model."""
import math

def valid_number(value,lo,hi):
    return type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi

def capture_level(model,slim=1):
    if not isinstance(model,dict): return None
    meta=model.get("metadata")
    level=meta.get("input_level_dbu") if isinstance(meta,dict) else None
    if model.get("architecture")=="SlimmableContainer":
        config=model.get("config")
        subs=config.get("submodels") if isinstance(config,dict) else None
        if isinstance(subs,list) and subs:
            selected=subs[-1]
            for entry in subs:
                if isinstance(entry,dict) and valid_number(entry.get("max_value"),0,1) and slim<entry["max_value"]:
                    selected=entry
                    break
            child=selected.get("model") if isinstance(selected,dict) else None
            cm=child.get("metadata") if isinstance(child,dict) else None
            child_level=cm.get("input_level_dbu") if isinstance(cm,dict) else None
            if valid_number(child_level,-60,60): return child_level
    return level if valid_number(level,-60,60) else None

def calibration(model,ref,slim=1):
    level=capture_level(model,slim)
    result=dict(model_dbu=level,reference_dbu=ref,gain=None,db=None)
    if level is None: return dict(result,status="missing_metadata")
    if not valid_number(ref,-60,30): return dict(result,status="missing_adc")
    db=ref-level
    gain=10**(db/20)
    if not .000001<=gain<=2: return dict(result,status="out_of_range",db=db)
    return dict(result,status="ready",db=db,gain=gain)
