#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include "compressor.h"
#include "reverbsc.h"

// Native 48 kHz wrappers. DaisySP-LGPL supplies the actual DSP.
class RigCompressor {
    daisysp::Compressor dsp_{};
    float amount_=0, mix_=0;
public:
    RigCompressor() {
        dsp_.Init(48000.f);
        dsp_.AutoMakeup(false);
        dsp_.SetAttack(.005f);
        dsp_.SetRelease(.15f);
    }
    void set(float amount) {
        amount_=amount;
        dsp_.SetThreshold(-12.f-24.f*amount);
        dsp_.SetRatio(1.f+5.f*amount);
    }
    float process(float x) {
        if(amount_==0 && mix_==0)return x;
        const float wet=dsp_.Process(x);
        mix_+=.00208116f*((amount_>0?1.f:0.f)-mix_);
        if(amount_==0 && mix_<1e-5f){mix_=0;return x;}
        return x+mix_*(wet-x);
    }
};

class RigReverb {
    daisysp::ReverbSc dsp_{};
    float mix_=0, target_=0, cutoff_=3800.f;
    float target_cutoff_=3800.f, feedback_=.75f, target_feedback_=.75f;
    unsigned tail_=0;
public:
    RigReverb() {
        if(dsp_.Init(48000.f)!=0)throw std::runtime_error("DaisySP ReverbSc initialization failed");
        dsp_.SetLpFreq(cutoff_);
        dsp_.SetFeedback(feedback_);
    }
    RigReverb(const RigReverb&)=delete;
    RigReverb& operator=(const RigReverb&)=delete;
    void set(float mix,float decay,int type) {
        target_=mix;
        constexpr std::array<float,3> cutoffs{3800.f,10000.f,6200.f};
        target_cutoff_=cutoffs[std::clamp(type,0,2)];
        // Invert the measured ARM64 T30 anchors of the previous mapping.
        // Piecewise linear in legacy decay parameter, per voicing. The shortest
        // supported nominal target is .30 s; below this, the network's onset
        // dominates the decay estimate. Extrapolate only slightly above 4.7 s.
        constexpr std::array<std::array<float,3>,3> measured{{
            {{.2983129f,1.4231f,4.690807f}},
            {{.2985754f,1.435634f,4.739346f}},
            {{.3010704f,1.428496f,4.718306f}}
        }};
        const auto& m=measured[std::clamp(type,0,2)];
        const float requested=std::clamp(decay,.3f,5.f);
        const float legacy=requested<=m[1]
            ? .2f+1.3f*(requested-m[0])/(m[1]-m[0])
            : 1.5f+3.5f*(requested-m[1])/(m[2]-m[1]);
        target_feedback_=std::clamp(std::pow(.001f,.060f/std::max(.2f,legacy)),0.f,.99f);
        if(mix>0)tail_=0;
    }
    float process(float x) {
        if(target_==0 && mix_==0 && tail_==0)return x;
        if(target_>0)tail_=48000*10;
        else if(tail_>0)--tail_;
        // Smooth feedback; update damping only when the change is significant
        // to avoid evaluating the upstream filter coefficient every sample.
        feedback_+=.00208116f*(target_feedback_-feedback_);
        dsp_.SetFeedback(feedback_);
        const float delta=target_cutoff_-cutoff_;
        if(std::abs(delta)>1.f){
            cutoff_+=std::copysign(std::min(std::abs(delta),16.f),delta);
            dsp_.SetLpFreq(cutoff_);
        }
        float l=0,r=0;
        const float in=target_>0?x:0.f;
        dsp_.Process(in,in,&l,&r);
        mix_+=.00208116f*(target_-mix_);
        if(target_==0 && mix_<1e-5f){mix_=0;return x;}
        return x+mix_*(.5f*(l+r)-x);
    }
};

#include "Effects/chorus.h"
#include "Utility/delayline.h"

class RigChorus {
    daisysp::ChorusEngine dsp_{};
    float mix_=0,target_=0, rate_=.8f, depth_=.5f;
    unsigned tail_=0;
public:
    RigChorus(){dsp_.Init(48000.f);dsp_.SetDelayMs(12.f);dsp_.SetFeedback(0.f);dsp_.SetLfoFreq(rate_);dsp_.SetLfoDepth(depth_);}
    void set(float mix,float rate,float depth){
        target_=mix;rate_=rate;depth_=depth;
        dsp_.SetLfoFreq(rate_);dsp_.SetLfoDepth(depth_);
    }
    float process(float x){
        if(target_==0&&mix_==0&&tail_==0)return x;
        if(target_>0)tail_=2400;else if(tail_)--tail_;
        const float in=target_>0?x:0.f;
        const float wet=dsp_.Process(in);
        mix_+=.00208116f*(target_-mix_);
        if(target_==0&&mix_<1e-5f){mix_=0;return x;}
        return x+mix_*(wet-in);
    }
};
class RigDelay {
    daisysp::DelayLine<float,48002> dsp_{};
    float mix_=0,target_=0, samples_=16800.f,target_samples_=16800.f, feedback_=.35f,target_feedback_=.35f;
    unsigned tail_=0;
public:
    RigDelay(){dsp_.Init();}
    void set(float mix,float ms,float feedback){
        if(target_==0&&mix_==0&&tail_==0)samples_=ms*48.f;
        target_=mix;target_samples_=ms*48.f;target_feedback_=feedback;
    }
    float process(float x){
        if(target_==0&&mix_==0&&tail_==0)return x;
        if(target_>0)tail_=48000*60;else if(tail_)--tail_;
        samples_+=.0002f*(target_samples_-samples_);
        feedback_+=.00208116f*(target_feedback_-feedback_);
        const float wet=dsp_.Read(samples_);
        dsp_.Write((target_>0?x:0.f)+feedback_*wet);
        mix_+=.00208116f*(target_-mix_);
        if(target_==0&&mix_<1e-5f){mix_=0;return x;}
        return x+mix_*(wet-x);
    }
};
