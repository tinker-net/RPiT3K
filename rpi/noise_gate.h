#pragma once
#include <cmath>
#include <algorithm>

// Input-keyed downward expander, 48 kHz. Gain applied downstream.
// 6 dB soft knee, 4:1 expansion below knee, no lookahead.
class NoiseGate {
    float threshold_=0, env_=0, gain_=1, target_=1;
    unsigned tick_=0;
    bool enabled_=false;
public:
    void set(float db) {
        if(db<-80){enabled_=false;env_=0;gain_=target_=1;tick_=0;return;}
        threshold_=db;
        if(!enabled_){env_=0;gain_=target_=1;tick_=0;}
        enabled_=true;
    }
    bool enabled() const {return enabled_;}
    float gain() const {return enabled_?gain_:1.f;}
    static float attenuation_db(float level,float threshold) {
        const float d=level-threshold;
        if(d>=3.f)return 0.f;
        if(d<=-3.f)return std::max(-90.f,3.f*d);
        const float x=3.f-d;
        return -.25f*x*x; // continuous slope at both edges
    }
    float process(float x) {
        if(!enabled_)return x;
        env_=std::max(std::abs(x),env_*0.9993058f); // 30 ms peak decay
        // Recalculate gain every 16 samples; open promptly on a strong onset.
        if(++tick_>=16){tick_=0;
            const float level=20.f*std::log10(std::max(env_,1e-12f));
            target_=std::pow(10.f,attenuation_db(level,threshold_)/20.f);
        }
        gain_+=(target_>gain_?0.0206178f:0.00005952204f)*(target_-gain_);
        return x*gain_;
    }
};
