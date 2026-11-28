// SPDX-License-Identifier: MIT
#include <juce_audio_utils/juce_audio_utils.h>
#include "../rpi/plugin_chain.h"
#include "rate_adapter.h"
#include <atomic>
#include <mutex>
#include <array>
#include <juce_gui_extra/juce_gui_extra.h>
#include "BinaryData.h"
#include <map>
#include <set>
#include <thread>
#include <condition_variable>

class Ton3k final : public juce::AudioProcessor, private juce::Timer {
public:
    using State=juce::AudioProcessorValueTreeState;
    static State::ParameterLayout layout(){
        State::ParameterLayout p;
        auto f=[&](const char* id,const char* name,float lo,float hi,float step,float def){
            p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{id,1},name,juce::NormalisableRange<float>(lo,hi,step),def));};
        f("input","Input",0,2,.000001f,1); f("output","Output",0,1,.01f,.5f);
        f("bass","Bass",-20,20,1,0);f("mid","Mid",-15,15,1,0);f("treble","Treble",-10,10,1,0);
        f("gate","Gate (-81 = off)",-81,-30,1,-81);
        f("comp","Compressor",0,1,.01f,0);f("compPost","Compressor position (0 pre / 1 post)",0,1,1,0);
        f("reverb","Reverb",0,1,.01f,0);f("decay","Decay (s)",.2f,5,.01f,1.5f);f("reverbType","Reverb type",0,2,1,0);
        f("mix","IR blend",0,1,.01f,.5f);f("hiz","Hi-Z",0,1,.01f,0);f("profile","Hi-Z profile",0,3,1,0);
        f("chorus","Chorus",0,1,.01f,0);f("chorusRate","Chorus rate",.1f,5,.01f,.8f);f("chorusDepth","Chorus depth",0,1,.01f,.5f);
        f("delay","Delay",0,1,.01f,0);f("delayMs","Delay (ms)",20,1000,1,350);f("feedback","Feedback",0,.85f,.01f,.35f);
        f("stomp","Pedal enabled",0,1,1,1);
        f("amp","Amplifier enabled",0,1,1,1);f("cab","Cabinet enabled",0,1,1,1);
        return p;
    }
    State state;
    Ton3k():AudioProcessor(BusesProperties().withInput("Input",juce::AudioChannelSet::mono(),true).withOutput("Output",juce::AudioChannelSet::stereo(),true)),state(*this,nullptr,"TON3K",layout()){
        for(auto* id:ids) params.push_back(state.getRawParameterValue(id));
        ton3k::Options initial; initial.output=.5f; current=new ton3k::Chain(initial);
        loadLibrary(); loader=std::thread([this]{loadLoop();}); startTimerHz(10);
    }
    ~Ton3k() override {stopTimer(); {std::lock_guard<std::mutex> lock(configLock); quitting=true;} wake.notify_all(); if(loader.joinable())loader.join(); delete current;delete pending.exchange(nullptr);delete retired.exchange(nullptr);}
    const juce::String getName() const override{return "TON3K";}
    bool acceptsMidi() const override{return false;} bool producesMidi() const override{return false;}
    bool isMidiEffect() const override{return false;} double getTailLengthSeconds() const override{return 20.;}
    int getNumPrograms() override{return 1;} int getCurrentProgram() override{return 0;}
    void setCurrentProgram(int) override{} const juce::String getProgramName(int) override{return {};}
    void changeProgramName(int,const juce::String&) override{}
    bool isBusesLayoutSupported(const BusesLayout& l) const override{
        auto i=l.getMainInputChannelSet(),o=l.getMainOutputChannelSet();
        return (i==juce::AudioChannelSet::mono()||i==juce::AudioChannelSet::stereo())&&(o==juce::AudioChannelSet::mono()||o==juce::AudioChannelSet::stereo());}
    void prepareToPlay(double sr,int) override{
        bool valid=std::isfinite(sr)&&sr>=8000&&sr<=384000;hostRate.store(sr);direct=std::abs(sr-48000.)<.01;setLatencySamples(valid?(direct?64:adapter.prepare(sr)):0);supported.store(valid);
        pos=0;std::fill_n(out,64,0.f);std::fill_n(in,64,0.f);
    }
    void releaseResources() override{}
    void processBlock(juce::AudioBuffer<float>& buf,juce::MidiBuffer&) override{
        juce::ScopedNoDenormals guard;
        if(!supported.load()){
            for(int c=getTotalNumInputChannels();c<buf.getNumChannels();++c)buf.clear(c,0,buf.getNumSamples());
            return;
        }
        for(int i=0;i<buf.getNumSamples();++i){
            float x=buf.getSample(0,i);if(!std::isfinite(x))x=0;
            float y=0;
            if(direct){
                in[pos]=x;y=out[pos];
                if(++pos==64){renderBlock(in,out);pos=0;}
            }else y=adapter.push(x,[this](const float* src,float* dst){renderBlock(src,dst);});
            inputPeak.store(std::max(inputPeak.load(),std::abs(x)));
            outputPeak.store(std::max(outputPeak.load(),std::abs(y)));
            for(int c=0;c<getTotalNumOutputChannels();++c)buf.setSample(c,i,y);
        }
    }

    bool hasEditor() const override{return true;}
    juce::AudioProcessorEditor* createEditor() override;
    void getStateInformation(juce::MemoryBlock& b) override{
        auto tree=state.copyState();{std::lock_guard<std::mutex> lock(configLock);savedSlots[std::to_string(activeSlot)]=webPreset();
        for(int i=0;i<4;++i)tree.setProperty("file"+juce::String(i),paths[i],nullptr); tree.setProperty("webSlots",juce::String(savedSlots.dump()),nullptr); tree.setProperty("webActive",activeSlot,nullptr);tree.setProperty("adcReference",juce::String(adcReference.dump()),nullptr);tree.setProperty("appearance",juce::String(appearance.dump()),nullptr); nlohmann::json lib=nlohmann::json::object();for(const auto& [k,v]:library)lib[k.toStdString()]=v.toStdString();tree.setProperty("webLibrary",juce::String(lib.dump()),nullptr);}
        if(auto xml=tree.createXml())copyXmlToBinary(*xml,b);
    }
    void setStateInformation(const void* data,int size) override{
        if(auto xml=getXmlFromBinary(data,size)){
            auto t=juce::ValueTree::fromXml(*xml);if(t.hasType(state.state.getType())){
                state.replaceState(t);
                std::lock_guard<std::mutex> lock(configLock);
                for(int i=0;i<4;++i)paths[i]=t.getProperty("file"+juce::String(i)).toString();
                try{adcReference=nlohmann::json::parse(t.getProperty("adcReference","null").toString().toStdString());appearance=nlohmann::json::parse(t.getProperty("appearance","{}").toString().toStdString());savedSlots=nlohmann::json::parse(t.getProperty("webSlots","{}").toString().toStdString());activeSlot=juce::jlimit(1,4,int(t.getProperty("webActive",1)));if(savedSlots.contains(std::to_string(activeSlot))){auto& pr=savedSlots[std::to_string(activeSlot)];slim=pr.value("slim",1.0);slim2=pr.value("slim2",1.0);}auto lib=nlohmann::json::parse(t.getProperty("webLibrary","{}").toString().toStdString());for(auto it=lib.begin();it!=lib.end();++it)library[juce::String(it.key())]=juce::String(it.value().get<std::string>());}catch(...){savedSlots=nlohmann::json::object();}dirty=true;wake.notify_one();
            }
        }
    }
    std::map<juce::String,juce::String> library;
    std::set<juce::String> favorites, folders;
    static std::mutex& libraryMutex(){static std::mutex m;return m;}
    static juce::File libraryFile(){return juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory).getChildFile("TinkerNet").getChildFile("TON3K").getChildFile("library.json");}
    juce::Time libraryStamp;
    void mergeLibraryUnlocked(){
        try{auto f=libraryFile();if(!f.existsAsFile())return;auto stamp=f.getLastModificationTime();if(stamp==libraryStamp)return;auto j=nlohmann::json::parse(f.loadFileAsString().toStdString());
            for(auto it=j.at("files").begin();it!=j.at("files").end();++it)library[juce::String(it.key())]=juce::String(it.value().get<std::string>());
            favorites.clear();folders.clear();
            for(auto& x:j.value("favorites",nlohmann::json::array()))favorites.insert(juce::String(x.get<std::string>()));
            for(auto& x:j.value("folders",nlohmann::json::array()))folders.insert(juce::String(x.get<std::string>()));libraryStamp=stamp;
        }catch(...){}
    }
    void loadLibrary(){std::lock_guard<std::mutex> g(libraryMutex());mergeLibraryUnlocked();}
    void saveLibraryUnlocked(){
        nlohmann::json j={{"files",nlohmann::json::object()},{"favorites",nlohmann::json::array()},{"folders",nlohmann::json::array()}};
        for(auto& [k,v]:library)j["files"][k.toStdString()]=v.toStdString();
        for(auto& k:favorites)j["favorites"].push_back(k.toStdString());
        for(auto& k:folders)j["folders"].push_back(k.toStdString());
        auto f=libraryFile();f.getParentDirectory().createDirectory();
        if(!f.replaceWithText(juce::String(j.dump(2))))throw std::runtime_error("Cannot save library");libraryStamp=f.getLastModificationTime();
    }
    void registerFile(const juce::File& file,juce::String name){
        int n=2;auto original=name;while(library.count(name)&&library[name]!=file.getFullPathName())name=original.upToLastOccurrenceOf(".",false,false)+" ("+juce::String(n++)+")"+file.getFileExtension();
        library[name]=file.getFullPathName();
        auto parent=name.upToLastOccurrenceOf("/",false,false);while(parent.isNotEmpty()){folders.insert(parent);parent=parent.upToLastOccurrenceOf("/",false,false);}
    }
    void importFiles(const juce::Array<juce::File>& files){
        std::lock_guard<std::mutex> lock(configLock);std::lock_guard<std::mutex> g(libraryMutex());mergeLibraryUnlocked();
        for(auto& f:files){
            if(f.isDirectory()){for(auto& child:f.findChildFiles(juce::File::findFiles,true,"*"))if(child.hasFileExtension("nam;wav"))registerFile(child,f.getFileName()+"/"+child.getRelativePathFrom(f).replaceCharacter('\\','/'));}
            else if(f.existsAsFile()&&f.hasFileExtension("nam;wav"))registerFile(f,f.getFileName());
        }saveLibraryUnlocked();
    }
    nlohmann::json savedSlots=nlohmann::json::object();
    int activeSlot=1;
    nlohmann::json adcReference=nullptr, appearance=nlohmann::json::object();

    using Json=nlohmann::json;
    static constexpr const char* webKeys[]={"input","output","bass","mid","treble","gate","comp","comp_post","reverb","decay","reverb_type","ir_mix","hiz","hiz_profile","chorus","chorus_rate","chorus_depth","delay","delay_ms","delay_feedback"};
    void importFile(const juce::File& file){juce::Array<juce::File> a;a.add(file);importFiles(a);}
    Json webPreset(){
        Json j=Json::object();
        for(int i=0;i<20;++i)j[webKeys[i]]=(i==12||i==13)?0.f:v(i);
        j["nam1_enabled"]=v(20)>.5f;j["bypass_nam2"]=v(21)<.5f;j["bypass_ir"]=v(22)<.5f;
        j["slim"]=slim;j["slim2"]=slim2;
        const char* keys[]={"model","second","ir","ir2"};
        for(int i=0;i<4;++i){
            j[keys[i]]="";
            if(paths[i].isNotEmpty()){
                auto it=std::find_if(library.begin(),library.end(),[&](const auto& kv){return kv.second==paths[i];});
                if(it!=library.end())j[keys[i]]=it->first.toStdString();
                else{auto f=juce::File(paths[i]);auto k=f.getFileName();int n=2;while(library.count(k)&&library[k]!=paths[i])k=f.getFileNameWithoutExtension()+" ("+juce::String(n++)+")"+f.getFileExtension();library[k]=paths[i];j[keys[i]]=k.toStdString();}
            }
        }
        auto key=std::to_string(activeSlot);
        if(savedSlots.contains(key))for(auto* k:{"comp","chorus","delay","reverb","hiz"}){auto a=std::string(k)+"_amount";if(savedSlots[key].contains(a))j[a]=savedSlots[key][a];}
        return j;
    }
    Json webStatus(){
        std::lock_guard<std::mutex> lock(configLock);
        loadLibrary(); auto currentPreset=webPreset();savedSlots[std::to_string(activeSlot)]=currentPreset;
        for(int i=1;i<=4;++i){auto key=std::to_string(i);if(!savedSlots.contains(key)){auto empty=currentPreset;for(auto* k:{"model","second","ir","ir2"})empty[k]="";savedSlots[key]=empty;}}
        Json files=Json::array(), fs=Json::array(), fav=Json::array();for(const auto& kv:library)files.push_back(kv.first.toStdString());for(auto& k:folders)fs.push_back(k.toStdString());for(auto& k:favorites)fav.push_back(k.toStdString());
        return Json{{"files",files},{"folders",fs},{"favorites",fav},{"presets",savedSlots},{"active",std::to_string(activeSlot)},{"settings",{{"last",std::to_string(activeSlot)},{"reference_dbu",adcReference}}},{"running",supported.load()},{"host_rate",hostRate.load()},{"host_latency",getLatencySamples()},{"logs",Json::array({message.toStdString()})},{"cloud_enabled",false},{"poweroff_enabled",false},{"amp_art",Json::object()},{"appearance",appearance}};
    }
    Json webRequest(const juce::String& path,const juce::String& body){
        if(path=="/api/status")return webStatus();
        if(path=="/api/levels")return Json{{"valid",supported.load()},{"input",inputPeak.exchange(0)},{"output",outputPeak.exchange(0)}};
        auto j=body.isEmpty()?Json::object():Json::parse(body.toStdString());
        if(path=="/api/version")return Json{{"edition","Native"},{"version","0.3 development"},{"commit","shared UI"}};
        if(path=="/api/settings"){ {std::lock_guard<std::mutex> lock(configLock);auto x=j.at("reference_dbu");if(!x.is_null()&&(!x.is_number()||x.get<double>()< -60||x.get<double>()>30))throw std::runtime_error("Invalid ADC reference");adcReference=x;}return webStatus();}
        if(path=="/api/appearance"){std::lock_guard<std::mutex> lock(configLock);for(auto& [k,val]:j.at("values").items())appearance[k]=val;return Json{{"appearance",appearance}};}
        if(path=="/api/calibrate"){
            std::lock_guard<std::mutex> lock(configLock);
            auto it=library.find(juce::String(j.at("model").get<std::string>()));if(it==library.end())throw std::runtime_error("Unknown capture");
            std::ifstream f(std::filesystem::u8path(it->second.toStdString()));Json model;f>>model;
            auto level=[](const Json& m)->Json{if(!m.is_object()||!m.contains("metadata")||!m["metadata"].is_object())return nullptr;auto x=m["metadata"].value("input_level_dbu",Json(nullptr));if(x.is_number()&&x.get<double>()>=-60&&x.get<double>()<=60)return x;return nullptr;};
            auto l=level(model);
            if(model.value("architecture",std::string{})=="SlimmableContainer"&&model.contains("config")&&model["config"].contains("submodels")){auto& subs=model["config"]["submodels"];if(subs.is_array()&&!subs.empty()){auto* selected=&subs.back();for(auto& sub:subs)if(sub.contains("max_value")&&sub["max_value"].is_number()&&j.value("slim",1.)<sub["max_value"].get<double>()){selected=&sub;break;}if(selected->contains("model")){auto child=level((*selected)["model"]);if(!child.is_null())l=child;}}}
            Json result={{"model_dbu",l},{"reference_dbu",adcReference},{"gain",nullptr},{"db",nullptr}};
            if(l.is_null())result["status"]="missing_metadata";else if(adcReference.is_null())result["status"]="missing_adc";else{double db=adcReference.get<double>()-l.get<double>(),gain=std::pow(10.,db/20.);result["db"]=db;result["status"]=gain>=.000001&&gain<=2?"ready":"out_of_range";if(gain>=.000001&&gain<=2)result["gain"]=gain;}return result;
        }
        if(path=="/api/edit"||path=="/api/save"){
            auto pr=j.at("preset");
            std::lock_guard<std::mutex> lock(configLock);
            int next=std::stoi(j.at("slot").get<std::string>());if(next<1||next>4)throw std::runtime_error("Invalid preset");
            juce::String newPaths[4];const char* keys[]={"model","second","ir","ir2"};
            for(int i=0;i<4;++i){auto k=juce::String(pr.value(keys[i],std::string{}));if(k.isNotEmpty()){auto it=library.find(k);if(it==library.end())throw std::runtime_error("File not in library");newPaths[i]=it->second;}}
            for(int i=0;i<4;++i)if(paths[i]!=newPaths[i]){paths[i]=newPaths[i];dirty=true;}
            double ns=pr.value("slim",1.0),ns2=pr.value("slim2",1.0);if(ns!=slim||ns2!=slim2){slim=ns;slim2=ns2;dirty=true;} activeSlot=next;savedSlots[std::to_string(next)]=pr;
            auto set=[&](int i,float x){if(auto* q=state.getParameter(ids[i])){auto norm=q->convertTo0to1(x);if(std::abs(q->getValue()-norm)>1e-7f){q->beginChangeGesture();q->setValueNotifyingHost(norm);q->endChangeGesture();}}};
            for(int i=0;i<20;++i)if(i!=12&&i!=13&&pr.contains(webKeys[i])&&pr[webKeys[i]].is_number())set(i,pr[webKeys[i]].get<float>());
            set(20,pr.value("nam1_enabled",true)?1:0);set(21,pr.value("bypass_nam2",false)?0:1);set(22,pr.value("bypass_ir",false)?0:1);wake.notify_one();
         }else if(path=="/api/favorite"||path=="/api/folder"){
            std::lock_guard<std::mutex> lock(configLock);std::lock_guard<std::mutex> g(libraryMutex());mergeLibraryUnlocked();
            auto k=juce::String(j.at("path").get<std::string>());
            if(path=="/api/folder"){if(k.isNotEmpty())folders.insert(k);}
            else if(j.value("enabled",false)){if(library.count(k))favorites.insert(k);}else favorites.erase(k);
            saveLibraryUnlocked();
        }else if(path=="/api/capture-info"){
            juce::String file;{std::lock_guard<std::mutex> lock(configLock);auto it=library.find(juce::String(j.at("model").get<std::string>()));if(it==library.end())throw std::runtime_error("Unknown capture");file=it->second;}
            std::ifstream f(std::filesystem::u8path(file.toStdString()));Json raw;f>>raw;
            raw.erase("weights");if(raw.contains("config"))raw.erase("config");return raw;
        }else throw std::runtime_error("Not available in VST3 preview");
        return webStatus();
    }

    std::atomic<float> inputPeak{0},outputPeak{0};
    void select(int slot,juce::String file){std::lock_guard<std::mutex> lock(configLock);paths[slot]=file;dirty=true;wake.notify_one();}
    juce::String status(){std::lock_guard<std::mutex> lock(configLock);return juce::String(supported.load()?juce::String(hostRate.load()/1000.,1)+" kHz | ":juce::String("Unsupported rate (dry bypass) | "))+message;}
    juce::String filename(int i){std::lock_guard<std::mutex> lock(configLock);return paths[i].isEmpty()?"Empty":juce::File(paths[i]).getFileName();}
private:
    static constexpr const char* ids[]={"input","output","bass","mid","treble","gate","comp","compPost","reverb","decay","reverbType","mix","hiz","profile","chorus","chorusRate","chorusDepth","delay","delayMs","feedback","stomp","amp","cab"};
    std::vector<std::atomic<float>*> params;
    float v(int i) const{return params[i]->load(std::memory_order_relaxed);}
    std::atomic<bool> supported{false};
    std::atomic<double> hostRate{0};
    bool direct=true;
    ton3k::RateAdapter adapter;
    void renderBlock(const float* src,float* dst) noexcept{
        bool fade=false;
        if(!retired.load(std::memory_order_acquire)){
            if(auto* next=pending.exchange(nullptr,std::memory_order_acq_rel)){
                retired.store(current,std::memory_order_release);current=next;fade=true;
            }
        }
        current->controls(v(0),v(1),v(2),v(3),v(4),v(5),v(6),v(7),v(8),v(9),v(10),v(11),0.f,0.f,v(14),v(15),v(16),v(17),v(18),v(19));
        current->set_stomp(v(20)>.5f);
        std::copy_n(src,64,current->x);current->process();
        for(int j=0;j<64;++j)dst[j]=current->y[j]*(fade?float(j)/63.f:1.f);
    }
    ton3k::Chain* current=nullptr;
    std::atomic<ton3k::Chain*> pending{nullptr},retired{nullptr};
    float in[64]{},out[64]{};unsigned pos=0;
    std::mutex configLock;std::condition_variable wake;std::thread loader;bool quitting=false;double slim=1.,slim2=1.;juce::String paths[4],message="Ready";bool dirty=true;
    bool lastAmp=true,lastCab=true;
    void timerCallback() override{
        delete retired.exchange(nullptr,std::memory_order_acq_rel);
        {std::lock_guard<std::mutex> lock(configLock);
        bool amp=v(21)>.5f,cab=v(22)>.5f;
        if(amp!=lastAmp||cab!=lastCab){dirty=true;lastAmp=amp;lastCab=cab;}}
        wake.notify_one();
    }
    void loadLoop(){
        for(;;){
            ton3k::Options o;
            {std::unique_lock<std::mutex> lock(configLock);wake.wait(lock,[&]{return quitting||dirty;});if(quitting)return;dirty=false;
            o.model=paths[0].toStdString();if(v(21)>.5f)o.second=paths[1].toStdString();
            if(v(22)>.5f){o.ir=paths[2].toStdString();o.ir2=paths[3].toStdString();}
            o.slim=slim;o.slim2=slim2;o.input=v(0);o.output=v(1);o.nam1_enabled=v(20)>.5f;message="Loading rig";}
            try{auto next=std::make_unique<ton3k::Chain>(o);
                std::lock_guard<std::mutex> lock(configLock);if(quitting)return;if(dirty)continue;
                delete pending.exchange(next.release(),std::memory_order_acq_rel);message="Rig loaded";
            }catch(const std::exception& e){std::lock_guard<std::mutex> lock(configLock);message=juce::String("Load failed: ")+e.what();}
        }
    }
};

class Editor final:public juce::AudioProcessorEditor,private juce::Timer{
    using Attachment=juce::AudioProcessorValueTreeState::SliderAttachment;
    Ton3k& p;
    const juce::Colour ink{0xffeeeeef}, muted{0xffa0a0a7}, yellow{0xffffff00}, panel{0xff202024};
    struct Knob {
        juce::Slider slider;juce::Label label;
        std::unique_ptr<Attachment> attachment;
    };
    std::array<Knob,20> knobs;
    juce::Label statusLabel;
    juce::TextButton files[4],clear[4], switches[3], tabs[2];
    std::unique_ptr<juce::FileChooser> chooser;
    int page=0;
    float inMeter=0,outMeter=0;
    static constexpr const char* ids[]={"input","output","bass","mid","treble","gate","comp","compPost","reverb","decay","reverbType","mix","hiz","profile","chorus","chorusRate","chorusDepth","delay","delayMs","feedback"};
    static constexpr const char* names[]={"INPUT","OUTPUT","BASS","MID","TREBLE","GATE","COMP","POSITION","REVERB","DECAY","TYPE","IR BLEND","HI-Z","PROFILE","CHORUS","RATE","DEPTH","DELAY","TIME","FEEDBACK"};
    static constexpr const char* switchIds[]={"stomp","amp","cab"};
    void toggle(int i){
        if(auto* q=p.state.getParameter(switchIds[i])){
            q->beginChangeGesture();q->setValueNotifyingHost(q->getValue()>.5f?0.f:1.f);q->endChangeGesture();
        }
    }
    void setPage(int n){page=n;resized();repaint();}
    void card(juce::Graphics& g,juce::Rectangle<int> r){
        g.setColour(panel);g.fillRoundedRectangle(r.toFloat(),8);g.setColour(juce::Colour(0xff39393d));g.drawRoundedRectangle(r.toFloat(),8,1);
    }
    void meter(juce::Graphics& g,juce::Rectangle<int> r,float value,const char* name){
        g.setColour(muted);g.setFont(11.f);g.drawText(name,r.removeFromLeft(28),juce::Justification::centredLeft);
        g.setColour(juce::Colour(0xff101012));g.fillRoundedRectangle(r.toFloat(),3);
        auto db=juce::Decibels::gainToDecibels(value,-60.f);
        auto width=juce::jlimit(0.f,1.f,(db+60.f)/60.f)*r.getWidth();
        g.setColour(value>=.99f?juce::Colour(0xffff453a):yellow);g.fillRoundedRectangle(r.withWidth(int(width)).toFloat(),3);
    }
public:
    explicit Editor(Ton3k& proc):AudioProcessorEditor(proc),p(proc){
        setOpaque(true);
        statusLabel.setColour(juce::Label::textColourId,muted);
        addAndMakeVisible(statusLabel);
        for(int i=0;i<20;++i){
            auto& k=knobs[i];
            k.slider.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
            k.slider.setTextBoxStyle(juce::Slider::TextBoxBelow,false,78,22);
            k.slider.setColour(juce::Slider::rotarySliderFillColourId,yellow);
            k.slider.setColour(juce::Slider::rotarySliderOutlineColourId,juce::Colour(0xff454549));
            k.slider.setColour(juce::Slider::thumbColourId,ink);
            k.slider.setColour(juce::Slider::textBoxTextColourId,ink);
            k.slider.setColour(juce::Slider::textBoxBackgroundColourId,juce::Colour(0xff101012));
            k.slider.setColour(juce::Slider::textBoxOutlineColourId,juce::Colour(0xff454549));
            k.attachment=std::make_unique<Attachment>(p.state,ids[i],k.slider);
            k.slider.setTooltip(names[i]);
            if(i<6){
                k.slider.textFromValueFunction=[i](double x){
                    if(i==5&&x<=-81)return juce::String("OFF");
                    if(i<=1){if(x<=0)return juce::String("-inf dB");return juce::String(20*std::log10(x),2)+" dB";}
                    return juce::String(x,0)+" dB";
                };
                k.slider.valueFromTextFunction=[i](const juce::String& t){
                    if(i==5&&t.trim().equalsIgnoreCase("OFF"))return -81.;
                    if(i<=1){if(t.containsIgnoreCase("inf"))return 0.;return std::pow(10.,t.getDoubleValue()/20.);}
                    return t.getDoubleValue();
                };
                k.slider.updateText();
            }
            k.label.setText(names[i],juce::dontSendNotification);k.label.setJustificationType(juce::Justification::centred);
            k.label.setColour(juce::Label::textColourId,muted);k.label.setFont(juce::FontOptions(12.f));
            addAndMakeVisible(k.slider);addAndMakeVisible(k.label);
        }
        for(int i=0;i<4;++i){
            addAndMakeVisible(files[i]);addAndMakeVisible(clear[i]);clear[i].setButtonText("X");
            files[i].onClick=[this,i]{
                chooser=std::make_unique<juce::FileChooser>("Select local capture or cabinet IR",juce::File{},i<2?"*.nam":"*.wav");
                auto safe=juce::Component::SafePointer<Editor>(this);
                chooser->launchAsync(juce::FileBrowserComponent::openMode|juce::FileBrowserComponent::canSelectFiles,[safe,i](const juce::FileChooser& c){
                    if(safe!=nullptr&&c.getResult().existsAsFile())safe->p.select(i,c.getResult().getFullPathName());
                });
            };
            clear[i].onClick=[this,i]{p.select(i,{});};
        }
        for(int i=0;i<3;++i){addAndMakeVisible(switches[i]);switches[i].onClick=[this,i]{toggle(i);};}
        tabs[0].setButtonText("AMP / CAB");tabs[1].setButtonText("EFFECTS");
        for(int i=0;i<2;++i){addAndMakeVisible(tabs[i]);tabs[i].onClick=[this,i]{setPage(i);};}
        setResizable(true,true);setResizeLimits(760,600,1600,1100);setSize(960,690);
        startTimerHz(20);timerCallback();
    }
    ~Editor() override{stopTimer();}
    void paint(juce::Graphics& g) override{
        g.fillAll(juce::Colour(0xff111113));
        auto r=getLocalBounds().reduced(16);
        auto top=r.removeFromTop(58);
        auto logo=top.removeFromLeft(175);
        g.setFont(juce::FontOptions(35.f,juce::Font::bold|juce::Font::italic));
        g.setColour(juce::Colour(0xffff1600));g.drawText("Ton3K",logo.translated(0,-2),juce::Justification::centredLeft);
        g.setColour(juce::Colour(0xff1600ff));g.drawText("Ton3K",logo.translated(0,2),juce::Justification::centredLeft);
        g.setColour(yellow);g.drawText("Ton3K",logo,juce::Justification::centredLeft);
        auto met=top.removeFromRight(220).reduced(2,8);meter(g,met.removeFromTop(17),inMeter,"IN");met.removeFromTop(5);meter(g,met.removeFromTop(17),outMeter,"OUT");
        r.removeFromTop(6);auto rig=r.removeFromTop(150);card(g,rig);
        auto title=rig.reduced(12).removeFromTop(20);g.setColour(muted);g.setFont(12.f);g.drawText("SIGNAL CHAIN   /   PEDAL  >  AMPLIFIER  >  CABINET",title,juce::Justification::centredLeft);
        r.removeFromTop(8);r.removeFromTop(32);r.removeFromTop(8);card(g,r);
        if(page==0){
            auto amp=r.reduced(18).removeFromTop(105);
            g.setColour(juce::Colour(0xff0e0e10));g.fillRoundedRectangle(amp.toFloat(),7);
            g.setColour(juce::Colour(0xff39393d));
            for(int y=amp.getY()+5;y<amp.getBottom()-3;y+=4)g.drawHorizontalLine(y,float(amp.getX()+5),float(amp.getRight()-5));
            g.setColour(ink);g.setFont(juce::FontOptions(20.f,juce::Font::bold));
            g.drawFittedText(p.filename(1),amp.reduced(10),juce::Justification::centred,2);
        }
    }
    void resized() override{
        auto r=getLocalBounds().reduced(16);auto top=r.removeFromTop(58);
        top.removeFromLeft(175);top.removeFromRight(220);statusLabel.setBounds(top);
        r.removeFromTop(6);auto rig=r.removeFromTop(150).reduced(12);rig.removeFromTop(24);
        auto row=rig.removeFromTop(44);
        for(int i=0;i<4;++i){auto a=row.removeFromLeft(row.getWidth()/(4-i)).reduced(3);clear[i].setBounds(a.removeFromRight(25));files[i].setBounds(a);}
        row=rig.removeFromTop(40);
        for(int i=0;i<3;++i)switches[i].setBounds(row.removeFromLeft(row.getWidth()/(3-i)).reduced(3));
        r.removeFromTop(8);auto bar=r.removeFromTop(32);tabs[0].setBounds(bar.removeFromLeft(150).reduced(2));tabs[1].setBounds(bar.removeFromLeft(150).reduced(2));r.removeFromTop(8);r=r.reduced(12);
        for(auto& k:knobs){k.label.setVisible(false);k.slider.setVisible(false);}
        auto place=[&](int idx,juce::Rectangle<int> a){
            auto& k=knobs[idx];k.label.setVisible(true);k.slider.setVisible(true);k.label.setBounds(a.removeFromTop(20));k.slider.setBounds(a.reduced(5));
        };
        if(page==0){
            r.removeFromTop(115);
            auto row=r.removeFromTop(r.getHeight()*2/3);
            for(int i=0;i<6;++i)place(i,row.removeFromLeft(row.getWidth()/(6-i)));
            auto bottom=r;place(11,bottom);
        }else{
            int indices[]={6,7,8,9,10,14,15,16,17,18,19};
            for(int j=0;j<2;++j){auto row=r.removeFromTop(r.getHeight()/(2-j));int n=j==0?6:5;for(int k=0;k<n;++k)place(indices[j*6+k],row.removeFromLeft(row.getWidth()/(n-k)));}
        }
    }
    void timerCallback() override{
        const char* labels[]={"Pedal","Amplifier","IR A","IR B"};
        for(int i=0;i<4;++i)files[i].setButtonText(juce::String(labels[i])+": "+p.filename(i));
        const char* sw[]={"PEDAL","AMP","CAB"};
        for(int i=0;i<3;++i){
            bool enabled=p.state.getRawParameterValue(switchIds[i])->load()>.5f;
            switches[i].setButtonText(juce::String(sw[i])+(enabled?" ON":" OFF"));
            switches[i].setColour(juce::TextButton::buttonColourId,enabled?yellow:panel);
            switches[i].setColour(juce::TextButton::textColourOffId,enabled?juce::Colours::black:ink);
        }
        for(int i=0;i<2;++i){tabs[i].setColour(juce::TextButton::buttonColourId,i==page?yellow:panel);tabs[i].setColour(juce::TextButton::textColourOffId,i==page?juce::Colours::black:ink);}
        statusLabel.setText(p.status(),juce::dontSendNotification);
        inMeter=std::max(inMeter*.82f,p.inputPeak.exchange(0));outMeter=std::max(outMeter*.82f,p.outputPeak.exchange(0));repaint();
    }
};

class WebEditor final:public juce::AudioProcessorEditor{
    using Browser=juce::WebBrowserComponent;
    Ton3k& p;
    std::unique_ptr<juce::FileChooser> chooser;
    std::unique_ptr<Browser> browser;
    std::unique_ptr<Editor> fallback;
    juce::TextButton switcher{"Native controls"};
    Browser::Options options(){
        auto o=Browser::Options{}.withNativeIntegrationEnabled()
            .withResourceProvider([](const juce::String& path)->std::optional<Browser::Resource>{
                if(path!="/"&&path!="/plugin.html")return std::nullopt;
                auto* begin=reinterpret_cast<const std::byte*>(BinaryData::plugin_html);
                return Browser::Resource{std::vector<std::byte>(begin,begin+BinaryData::plugin_htmlSize),"text/html"};
            })
            .withNativeFunction("ton3k",[this](const juce::Array<juce::var>& args,Browser::NativeFunctionCompletion done){
                try{
                    if(args.size()<2)throw std::runtime_error("Invalid request");
                    auto path=args[0].toString();
                    if(path=="/plugin/import"||path=="/plugin/import-folder"){
                        bool directory=path=="/plugin/import-folder";chooser=std::make_unique<juce::FileChooser>(directory?"Import library folder":"Import NAM and WAV files",juce::File{},directory?"*":"*.nam;*.wav");
                        auto safe=juce::Component::SafePointer<WebEditor>(this);
                        chooser->launchAsync(juce::FileBrowserComponent::openMode|(directory?juce::FileBrowserComponent::canSelectDirectories:juce::FileBrowserComponent::canSelectFiles|juce::FileBrowserComponent::canSelectMultipleItems),[safe,done](const juce::FileChooser& c){
                            if(safe==nullptr)return;
                            try{safe->p.importFiles(c.getResults());done(juce::String(safe->p.webStatus().dump()));}catch(const std::exception& e){done(juce::String(Ton3k::Json{{"error",e.what()}}.dump()));}
                        });return;
                    }
                    done(juce::String(p.webRequest(path,args[1].toString()).dump()));
                }catch(const std::exception& e){done(juce::String(Ton3k::Json{{"error",e.what()}}.dump()));}
            });
        #if JUCE_WINDOWS
        o=o.withBackend(Browser::Options::Backend::webview2);
        #endif
        return o;
    }
    void toggle(){
        if(!fallback){fallback=std::make_unique<Editor>(p);addAndMakeVisible(*fallback);if(browser)browser->setVisible(false);switcher.setButtonText("Original UI");}
        else if(browser){fallback.reset();browser->setVisible(true);switcher.setButtonText("Native controls");}
        resized();
    }
public:
    explicit WebEditor(Ton3k& proc):AudioProcessorEditor(proc),p(proc){
        auto o=options();
        if(Browser::areOptionsSupported(o)){browser=std::make_unique<Browser>(o);addAndMakeVisible(*browser);browser->goToURL(Browser::getResourceProviderRoot());}
        else{fallback=std::make_unique<Editor>(p);addAndMakeVisible(*fallback);switcher.setEnabled(false);}
        addAndMakeVisible(switcher);switcher.onClick=[this]{toggle();};
        setResizable(true,true);setResizeLimits(760,560,2000,1400);setSize(1280,820);
    }
    void resized() override{auto r=getLocalBounds();switcher.setBounds(r.removeFromTop(24).removeFromRight(150));if(browser)browser->setBounds(r);if(fallback)fallback->setBounds(r);}
};

juce::AudioProcessorEditor* Ton3k::createEditor(){return new WebEditor(*this);}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter(){return new Ton3k();}
