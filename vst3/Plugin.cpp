// SPDX-License-Identifier: MIT
#include <juce_audio_utils/juce_audio_utils.h>
#include "../rpi/plugin_chain.h"
#include <atomic>
#include <mutex>

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
        f("mix","IR blend",0,1,.01f,.5f);f("hiz","Hi-Z",0,1,1,0);f("profile","Hi-Z profile",0,3,1,0);
        f("chorus","Chorus",0,1,.01f,0);f("chorusRate","Chorus rate",.1f,5,.01f,.8f);f("chorusDepth","Chorus depth",0,1,.01f,.5f);
        f("delay","Delay",0,1,.01f,0);f("delayMs","Delay (ms)",20,1000,1,350);f("feedback","Feedback",0,.85f,.01f,.35f);
        f("stomp","Pedal enabled",0,1,1,1);
        f("amp","Amplifier enabled",0,1,1,1);f("cab","Cabinet enabled",0,1,1,1);
        return p;
    }
    State state;
    Ton3k():AudioProcessor(BusesProperties().withInput("Input",juce::AudioChannelSet::mono(),true).withOutput("Output",juce::AudioChannelSet::stereo(),true)),state(*this,nullptr,"TON3K",layout()){
        for(auto* id:ids) params.push_back(state.getRawParameterValue(id));
        current=new ton3k::Chain(ton3k::Options{});
        startTimerHz(10);
    }
    ~Ton3k() override {stopTimer(); delete current;delete pending.exchange(nullptr);delete retired.exchange(nullptr);}
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
        supported.store(std::abs(sr-48000.)<.01);setLatencySamples(supported.load()?64:0);
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
            in[pos]=buf.getSample(0,i);
            for(int c=0;c<getTotalNumOutputChannels();++c)buf.setSample(c,i,out[pos]);
            if(++pos==64){
                bool fade=false;
                if(!retired.load(std::memory_order_acquire)){
                    if(auto* next=pending.exchange(nullptr,std::memory_order_acq_rel)){
                        retired.store(current,std::memory_order_release);current=next;fade=true;
                    }
                }
                current->controls(v(0),v(1),v(2),v(3),v(4),v(5),v(6),v(7),v(8),v(9),v(10),v(11),v(12),v(13),v(14),v(15),v(16),v(17),v(18),v(19));
                current->set_stomp(v(20)>.5f);
                std::copy_n(in,64,current->x);current->process();
                for(int j=0;j<64;++j)out[j]=current->y[j]*(fade?float(j)/63.f:1.f);
                pos=0;
            }
        }
    }
    bool hasEditor() const override{return true;}
    juce::AudioProcessorEditor* createEditor() override;
    void getStateInformation(juce::MemoryBlock& b) override{
        auto tree=state.copyState();{std::lock_guard<std::mutex> lock(configLock);
        for(int i=0;i<4;++i)tree.setProperty("file"+juce::String(i),paths[i],nullptr);}
        if(auto xml=tree.createXml())copyXmlToBinary(*xml,b);
    }
    void setStateInformation(const void* data,int size) override{
        if(auto xml=getXmlFromBinary(data,size)){
            auto t=juce::ValueTree::fromXml(*xml);if(t.hasType(state.state.getType())){
                state.replaceState(t);
                std::lock_guard<std::mutex> lock(configLock);
                for(int i=0;i<4;++i)paths[i]=t.getProperty("file"+juce::String(i)).toString();
                dirty=true;
            }
        }
    }
    void select(int slot,juce::String file){std::lock_guard<std::mutex> lock(configLock);paths[slot]=file;dirty=true;}
    juce::String status(){std::lock_guard<std::mutex> lock(configLock);return (supported.load()?"48 kHz | ":"Set DAW to 48 kHz (dry bypass) | ")+message;}
    juce::String filename(int i){std::lock_guard<std::mutex> lock(configLock);return paths[i].isEmpty()?"Empty":juce::File(paths[i]).getFileName();}
private:
    static constexpr const char* ids[]={"input","output","bass","mid","treble","gate","comp","compPost","reverb","decay","reverbType","mix","hiz","profile","chorus","chorusRate","chorusDepth","delay","delayMs","feedback","stomp","amp","cab"};
    std::vector<std::atomic<float>*> params;
    float v(int i) const{return params[i]->load(std::memory_order_relaxed);}
    std::atomic<bool> supported{false};
    ton3k::Chain* current=nullptr;
    std::atomic<ton3k::Chain*> pending{nullptr},retired{nullptr};
    float in[64]{},out[64]{};unsigned pos=0;
    std::mutex configLock;juce::String paths[4],message="Ready";bool dirty=true;
    bool lastAmp=true,lastCab=true;
    void timerCallback() override{
        delete retired.exchange(nullptr,std::memory_order_acq_rel);
        std::lock_guard<std::mutex> lock(configLock);
        bool amp=v(21)>.5f,cab=v(22)>.5f;
        if(amp!=lastAmp||cab!=lastCab){dirty=true;lastAmp=amp;lastCab=cab;}
        if(!dirty)return;dirty=false;
        try{
            ton3k::Options o;
            o.model=paths[0].toStdString();if(amp)o.second=paths[1].toStdString();
            if(cab){o.ir=paths[2].toStdString();o.ir2=paths[3].toStdString();}
            o.input=v(0);o.output=v(1);o.nam1_enabled=v(20)>.5f;
            auto next=std::make_unique<ton3k::Chain>(o);
            delete pending.exchange(next.release(),std::memory_order_acq_rel);message="Rig loaded";
        }catch(const std::exception& e){message=juce::String("Load failed: ")+e.what();}
    }
};

class Editor final:public juce::AudioProcessorEditor,private juce::Timer{
    Ton3k& p;
    juce::GenericAudioProcessorEditor controls;
    juce::Label header,statusLabel;
    juce::TextButton files[4],clear[4];
    std::unique_ptr<juce::FileChooser> chooser;
public:
    explicit Editor(Ton3k& proc):AudioProcessorEditor(proc),p(proc),controls(proc){
        header.setText("TON3K | Native NAM guitar processor",juce::dontSendNotification);
        header.setFont(juce::FontOptions(20.f,juce::Font::bold));
        addAndMakeVisible(header);addAndMakeVisible(statusLabel);addAndMakeVisible(controls);
        for(int i=0;i<4;++i){
            addAndMakeVisible(files[i]);addAndMakeVisible(clear[i]);clear[i].setButtonText("Clear");
            files[i].onClick=[this,i]{
                chooser=std::make_unique<juce::FileChooser>("Select local capture or cabinet IR",juce::File{},i<2?"*.nam":"*.wav");
                auto safe=juce::Component::SafePointer<Editor>(this);
                chooser->launchAsync(juce::FileBrowserComponent::openMode|juce::FileBrowserComponent::canSelectFiles,[safe,i](const juce::FileChooser& c){
                    if(safe!=nullptr&&c.getResult().existsAsFile())safe->p.select(i,c.getResult().getFullPathName());
                });
            };
            clear[i].onClick=[this,i]{p.select(i,{});};
        }
        setResizable(true,true);setSize(740,720);startTimerHz(5);timerCallback();
    }
    ~Editor() override{stopTimer();}
    void resized() override{
        auto a=getLocalBounds().reduced(12);header.setBounds(a.removeFromTop(32));statusLabel.setBounds(a.removeFromTop(26));
        for(int i=0;i<4;++i){auto row=a.removeFromTop(30).reduced(0,2);clear[i].setBounds(row.removeFromRight(72));files[i].setBounds(row);}
        controls.setBounds(a);
    }
    void timerCallback() override{
        const char* labels[]={"Pedal","Amplifier","IR A","IR B"};
        for(int i=0;i<4;++i)files[i].setButtonText(juce::String(labels[i])+": "+p.filename(i));
        statusLabel.setText(p.status(),juce::dontSendNotification);
    }
};
juce::AudioProcessorEditor* Ton3k::createEditor(){return new Editor(*this);}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter(){return new Ton3k();}
