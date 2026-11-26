const fs=require("fs"),vm=require("vm"),assert=require("assert");
const h=fs.readFileSync(__dirname+"/web.html","utf8");
const c=vm.createContext({});vm.runInContext(h.slice(h.indexOf("const captureCatalog="),h.indexOf("let smartEnabled=")),c);
const parse=p=>vm.runInContext("identifyCapture("+JSON.stringify(p)+")",c);
const cases=[
["Amalgam DI/A2/Fender Super Reverb 1965 A2/FNDR BFSR VB Crunch SCP2 DI.nam","Fender Super Reverb (1965) · Vibrato · Crunch · Scooped 2 · A2"],
["Amalgam DI/A2/Tone King Imperial MKII 2022 A2/TK IMP RH Clean WRM DI.nam","Tone King Imperial MKII (2022) · Rhythm · Clean · Warm · A2"],
["Amalgam DI/A2/Fender Pano-Verb 2025/FNDR PANO Edge2 BAL 6V6 DI.nam","Fender Pano-Verb (2025) · Edge 2 · Balanced · 6V6 · A2"],
["IRs/York Audio/YA BMAN 410 P10Q/Minimum Phase Singles/YA BMAN 410 P10Q 121-1.wav","Fender Bassman Tweed 4×10 · Jensen P10Q · Royer R-121-1 · Minimum Phase"],
["IRs/York Audio/YA KW 412 M25-SH/Natural Phase Singles/YA KW 412 M25 121-1.wav","Kerry Wright 4×12 · Celestion G12M25 · Scott Henderson · Royer R-121-1 · Natural Phase"],
["IRs/IRs Amalgam/Fender Deluxe 1957/FNDR TWDLX 1X12 P12R V3.wav","Fender Deluxe (Tweed) 1×12 · Jensen P12R V3"],
["IRs/IRs Amalgam/Amalgam Essential Kit/MRSH 1968 1960A G12M25 75Hz Pulsonic.wav","Marshall 1960A 4×12 (1968) · Celestion G12M25 75 Hz Pulsonic"]
];for(const [p,l] of cases)assert.equal(parse(p).label,l,p);
if(process.argv[2]){const paths=fs.readFileSync(process.argv[2],"utf8").trim().split(/\r?\n/);const labels=new Map();let known=0;for(const p of paths){const x=parse(p);assert(x.raw&&x.label,p);if(x.model)known++;const key=x.label;labels.set(key,(labels.get(key)||0)+1);}console.log("Inventory:",paths.length,"recognized:",known,"duplicate labels:",[...labels.values()].filter(n=>n>1).length);}
console.log("Smart library regression: "+cases.length+" passed");
