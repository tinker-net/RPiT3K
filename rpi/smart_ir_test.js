// Extract pure UI parser directly from web.html.
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const html=fs.readFileSync(__dirname+"/web.html","utf8");
const src=html.slice(html.indexOf("const yorkCabCatalog="),html.indexOf("// Channel aliases"));
const ctx=vm.createContext({});vm.runInContext(src,ctx);
function label(p){return vm.runInContext("identifyIR("+JSON.stringify(p)+","+JSON.stringify(p.split("/").pop().replace(/\.wav$/i,""))+").label",ctx);}
assert.equal(label("YA BMAN 410 P10Q Mix 01.wav"),"Fender Bassman Tweed 4×10 · Jensen P10Q · Mix 01");
assert.equal(label("YA ORNG 412 V30 57m-03.wav"),"Orange PPC412 4×12 · Vintage 30 · Shure SM57 (modern)-03");
assert.equal(label("VX2x12 Alnico Silver V3 LP6K.wav"),"Vox 2×12 Alnico Silver V3 Low-pass 6 kHz");
assert.equal(label("Amalgam/KW 4x12 G12M25 Mix 1.wav"),"Kerry Wright 4×12 G12M25 Greenback Mix 1");
assert.equal(label("YA UNKNOWN Mix 01.wav"),"UNKNOWN Mix 01");
assert.equal(label("York Audio/BMAN 410 P10Q/Mix 01.wav"),"Fender Bassman Tweed 4×10 · Jensen P10Q · Mix 01");
console.log("Smart IR regression: 6 passed");
