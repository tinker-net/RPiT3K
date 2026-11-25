#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

// Mono, 48 kHz. Fixed storage; no allocation in process() or live set().
class RigCompressor {
    float amount_=0, mix_=0, envelope_=0, gain_=1, threshold_=.1f, exponent_=0;
public:
    void set(float amount) {
        amount_=amount;
        threshold_=std::pow(10.f,(-12.f-24.f*amount)/20.f);
        exponent_=1.f-1.f/(1.f+5.f*amount);
    }
    float process(float x) {
        if(amount_==0 && mix_==0)return x;
        envelope_=std::max(std::abs(x),envelope_*.9997917f);
        float target=1.f;
        if(envelope_>threshold_)target=std::pow(threshold_/envelope_,exponent_);
        gain_+=(target<gain_?.004158f:.00013888f)*(target-gain_);
        mix_+=.00208116f*(amount_>0?1.f-mix_:-mix_);
        if(amount_==0 && mix_<1e-5f){mix_=0;gain_=1;envelope_=0;return x;}
        return x*(1.f+mix_*(gain_-1.f));
    }
};

class RigReverb {
    // Four-line orthogonal feedback delay network, distinct fixed line lengths per voicing.
    struct Voice {
        std::array<std::vector<float>,4> lines;
        std::array<unsigned,4> index{};
        std::array<float,4> low{}, feedback{};
        float damping;
        Voice(std::array<unsigned,4> lengths,float d):damping(d) {
            for(unsigned i=0;i<4;++i)lines[i].resize(lengths[i],0.f);
        }
        void decay(float seconds) {
            for(unsigned i=0;i<4;++i)
                feedback[i]=std::pow(.001f,float(lines[i].size())/(48000.f*seconds));
        }
        float process(float x) {
            float a[4];
            for(unsigned i=0;i<4;++i){
                float v=lines[i][index[i]];
                low[i]+=damping*(v-low[i]);
                a[i]=low[i];
            }
            const float h[4]={.5f*(a[0]+a[1]+a[2]+a[3]),.5f*(a[0]-a[1]+a[2]-a[3]),
                              .5f*(a[0]+a[1]-a[2]-a[3]),.5f*(a[0]-a[1]-a[2]+a[3])};
            for(unsigned i=0;i<4;++i){
                float v=.35f*x+feedback[i]*h[i];
                lines[i][index[i]]=std::abs(v)<1e-15f?0.f:v;
                if(++index[i]==lines[i].size())index[i]=0;
            }
            return .5f*(a[0]-a[1]+a[2]-a[3]);
        }
    };
    std::array<Voice,3> voices{Voice({1423,1877,2381,2909},.32f),
                                Voice({1559,2081,2713,3169},.60f),
                                Voice({421,631,887,1153},.40f)};
    float mix_=0, target_=0;
    int type_=0;
    unsigned tail_=0;
    std::array<float,3> weights{1,0,0};
public:
    void set(float mix,float decay,int type) {
        target_=mix;type_=type;
        if(mix>0)tail_=0;
        for(auto& v:voices)v.decay(decay);
    }
    float process(float x) {
        // Initial OFF is an exact, cheap bypass. Drain existing tails on disable.
        if(target_==0 && mix_==0 && tail_==0)return x;
        if(target_>0)tail_=48000*10;
        else if(tail_>0)--tail_;
        float wet=0;
        for(int i=0;i<3;++i){
            weights[i]+=.00208116f*((i==type_?1.f:0.f)-weights[i]);
            wet+=weights[i]*voices[i].process(target_>0?x:0.f);
        }
        mix_+=.00208116f*(target_-mix_);
        if(target_==0 && mix_<1e-5f){mix_=0;return x;}
        return x+mix_*(wet-x);
    }
};
