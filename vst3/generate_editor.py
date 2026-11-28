"""Derive Native editor from current standalone UI; never maintain a second fork."""
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
bridge="async function request(path,body){\n const u=new URL(path,location.href),p=u.pathname;\n if(p===\"/api/practice/import\"){if(!(body instanceof Blob))throw Error(\"Choose audio\");const name=u.searchParams.get(\"name\");if(nativeTracks.has(name))throw Error(\"Track already loaded\");nativeTracks.set(name,body);return {};}\n if(p===\"/api/practice\")return {files:[...nativeTracks.keys()]};\n if(p===\"/api/practice/waveform\"){const f=nativeTracks.get(u.searchParams.get(\"name\"));if(!f)throw Error(\"Choose a track\");if(f.size>128*1024*1024)throw Error(\"Track exceeds 128 MiB\");const ctx=new (window.AudioContext||window.webkitAudioContext)();try{const a=await ctx.decodeAudioData(await f.arrayBuffer()),ch=a.getChannelData(0),peaks=[];for(let i=0;i<1200;i++){let peak=0;for(let j=Math.floor(i*ch.length/1200);j<Math.floor((i+1)*ch.length/1200);j++)peak=Math.max(peak,Math.abs(ch[j]));peaks.push(peak);}return {duration:a.duration,peaks};}finally{await ctx.close();}}\n if(!window.__JUCE__?.backend)throw Error(\"Native plugin bridge unavailable\");\n if(!window.ton3kBridge){\n  let id=0;const pending=new Map(),backend=window.__JUCE__.backend;\n  backend.addEventListener(\"__juce__complete\",({promiseId,result})=>{const cb=pending.get(promiseId);if(cb){pending.delete(promiseId);cb(result);}});\n  window.ton3kBridge=(path,body)=>new Promise((resolve,reject)=>{\n    const resultId=++id;pending.set(resultId,resolve);\n    backend.emitEvent(\"__juce__invoke\",{name:\"ton3k\",params:[path,body||\"\"],resultId});\n    setTimeout(()=>{if(pending.delete(resultId))reject(Error(\"Plugin response timeout\"));},path.startsWith(\"/plugin/import\")?600000:15000);\n  });\n }\n if(body instanceof Blob)throw Error(\"Use Import files to select local files\");\n const raw=await window.ton3kBridge(path,body);const data=JSON.parse(raw);\n if(data.error)throw Error(data.error);return data;\n}\n"
def replace(old,new):
    global src
    if old not in src:raise RuntimeError("Shared UI adapter anchor changed: "+old[:100])
    src=src.replace(old,new,1)
a=src.index("async function request(path,body)")
b=src.index("function options(id,files,value)",a)
src=src[:a]+"const nativeTracks=new Map();\n"+bridge+src[b:]
replace("let practiceRoute=\"device\"","let practiceRoute=\"browser\"")
replace("let metroRoute=\"device\"","let metroRoute=\"browser\"")
replace("browserAudio.src=\"/api/practice/audio?name=\"+encodeURIComponent(name);","browserAudio.src=URL.createObjectURL(nativeTracks.get(name));")
replace("function browserRelease(){browserStop();","function browserRelease(){browserStop();if(browserAudio.src.startsWith(\"blob:\"))URL.revokeObjectURL(browserAudio.src);")
replace("el(\"uploadBtn\").onclick=()=>{if(!busy)el(\"upload\").click();};","el(\"uploadBtn\").onclick=()=>action(async()=>{state=await request(\"/plugin/import\");render(state.presets[slot]);},\"Library updated\");")
replace("el(\"folderBrowse\").onclick=()=>{if(!busy)el(\"uploadFolder\").click();};","el(\"folderBrowse\").onclick=()=>action(async()=>{state=await request(\"/plugin/import-folder\");render(state.presets[slot]);},\"Library updated\");")
replace("const audioOn=state.running&&state.active!==null;","const audioOn=state.running&&state.active!==null;")
replace("el(\"calibrate\").disabled=busy;","el(\"calibrate\").disabled=busy;")
replace("+1.14 dBu is a nominal Pisound estimate at minimum analog gain. Change this if hardware gain changes; leave blank if unknown.","Enter the full-scale ADC reference of your interface at its current analog gain. DAW input must be unity; leave blank if unknown.")
replace("value=\"1.14\"","value=\"\"")
replace("const t=state.telemetry;if(t){","el(\"latencyDetail\").textContent=\"Host: \"+(state.host_rate||0)+\" Hz · \"+(state.host_latency||0)+\" samples reported plugin latency\";if(!settingsInitialized){el(\"reference_dbu\").value=state.settings.reference_dbu??\"\";settingsInitialized=true;} const t=state.telemetry;if(t){")
replace("Device requires Audio ON.</p>","Local click · independent of DAW transport.</p>")
replace("el(\"slots\").replaceChildren();renderTree();","el(\"slots\").replaceChildren();renderTree();")
replace("</head>","<style>.hiz-panel,.audio-period-row,#poweroff,#cloudOpen,#xrunMetric,#tuner,#status,#practiceOutput,#metroOutput,#scoreToggle,#importAmpArt,#backupExport,#backupRestore,#releaseOpen,#versionCheck,#updateInstall{display:none!important}.telemetry{display:none!important} #practicePitch{display:none!important} #practicePitchValue{display:none!important}</style></head>")
replace("</script></body></html>","el(\"practiceOutput\").value=\"browser\";el(\"metroOutput\").value=\"browser\";el(\"practicePitch\").disabled=true;el(\"practicePitchValue\").textContent=\"Unavailable\";window.addEventListener(\"pagehide\",()=>{browserRelease();metroBrowserStop();});\n</script></body></html>")
# Keep unsupported device-only sections out of the visible editor while retaining shared DOM hooks.
src=src.replace("<h2>Backup &amp; restore</h2>","<h2 hidden>Backup &amp; restore</h2>").replace("<h2>Software updates</h2>","<h2 hidden>Software updates</h2>")
# Native 0.3.1: persistent files and DAW playback at original pitch/rate.
start=src.index("const nativeTracks=new Map();")
end=src.index(" if(!window.__JUCE__?.backend)",start)
src=src[:start]+"""async function request(path,body){
 const u=new URL(path,location.href);
 if(u.pathname==="/api/practice/waveform"){path=u.pathname;body=JSON.stringify({name:u.searchParams.get("name")});}
"""+src[end:]
replace('let practiceRoute="browser"','let practiceRoute="device"')
replace('browserAudio.src=URL.createObjectURL(nativeTracks.get(name));','const media=await fetch("/native-audio/"+encodeURIComponent(name));if(!media.ok)throw Error("Cannot open audio");browserAudio.src=URL.createObjectURL(await media.blob());')
replace('el("practiceImport").onclick=()=>el("practiceFile").click();','el("practiceImport").onclick=async()=>{try{const r=await request("/plugin/import-practice");if(r.cancelled)return;await practiceList();el("practiceTrack").value=r.name;await el("practiceTrack").onchange();}catch(e){msg(e.message);}};')
replace('$("scoreImport").onclick=()=>$("scoreFile").click();','$("scoreImport").onclick=async()=>{try{const r=await request("/plugin/import-score");if(r.cancelled)return;await refreshScores(r.name);await loadSavedScore(r.name);}catch(e){message(e.message);}};')
replace('fetch("/api/scores/file?name="+encodeURIComponent(name))','fetch("/native-score/"+encodeURIComponent(name))')
replace('Run bash rpi/install-score-reader.sh on the Pi','Embedded score renderer unavailable')
replace('#practiceOutput,#metroOutput,#scoreToggle,','#metroOutput,')
replace('#practicePitch{display:none!important} #practicePitchValue{display:none!important}','label:has(#practicePitch){display:none!important} .library-icon[title="File options"],.library-icon[title="Folder options"],.library-icon[title="Import into this folder"],#importDrop,#folderTarget{display:none!important}')
replace('el("practiceOutput").value="browser";','el("practiceOutput").value="device";el("practiceOutput").options[0].textContent="DAW";el("practiceOutput").options[1].textContent="Local";el("practiceSpeed").disabled=true;el("practiceSpeed").title="Use Local output for speed changes";')
replace('paused=false;practiceRoute=next;','paused=false;practiceRoute=next;el("practiceSpeed").disabled=next==="device";if(next==="device"){el("practiceSpeed").value=1;el("practiceRate").textContent="100%";}')
replace('el("practicePitch").disabled=next==="browser";','el("practicePitch").disabled=true;')
replace('Browser cannot decode this track. Try Device output.','Local playback cannot decode this track. Try DAW output.')
replace('if((s.button_revision||0)>=(state.button_revision||0)){state=s;if(s.presets[slot])setStompUI(s.presets[slot].nam1_enabled!==false);status();}','if((s.button_revision||0)>=(state.button_revision||0)){const prior=state.presets[slot];state=s;const focus=document.activeElement;if(s.presets[slot]&&JSON.stringify(prior)!==JSON.stringify(s.presets[slot])&&!document.querySelector("dialog[open]")&&!focus?.matches("input,select,textarea")&&!document.querySelector(".dial:active"))render(s.presets[slot]);status();}')
# Hide the entire unsupported maintenance blocks, not only buttons.
a=src.index("<hr><h2 hidden>Backup &amp; restore")
b=src.index("</dialog>",a)
src=src[:a]+"<div hidden>"+src[a:b]+"</div>"+src[b:]
replace('Audio settings & diagnostics','Host audio & diagnostics')
Path(sys.argv[2]).write_text(src)
