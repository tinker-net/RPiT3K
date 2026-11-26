// SPDX-License-Identifier: MIT
#include <juce_audio_utils/juce_audio_utils.h>
#include "../rpi/plugin_chain.h"
#include <atomic>
#include <mutex>
#include <array>

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
        ton3k::Options initial; initial.output=.5f; current=new ton3k::Chain(initial);
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
            in[pos]=buf.getSample(0,i); if(!std::isfinite(in[pos])) in[pos]=0.f; inputPeak.store(std::max(inputPeak.load(),std::abs(in[pos]))); outputPeak.store(std::max(outputPeak.load(),std::abs(out[pos])));
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
    std::atomic<float> inputPeak{0},outputPeak{0};
    void select(int slot,juce::String file){std::lock_guard<std::mutex> lock(configLock);paths[slot]=file;dirty=true;}
    juce::String status(){std::lock_guard<std::mutex> lock(configLock);return juce::String(supported.load()?"48 kHz | ":"Set DAW to 48 kHz (dry bypass) | ")+message;}
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
            auto bottom=r;int indices[]={11,12,13};for(int j=0;j<3;++j)place(indices[j],bottom.removeFromLeft(bottom.getWidth()/(3-j)));
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
juce::AudioProcessorEditor* Ton3k::createEditor(){return new Editor(*this);}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter(){return new Ton3k();}
