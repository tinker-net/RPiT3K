#pragma once
#include <cmath>
#include <algorithm>

// Peak envelope before digital input gain. No lookahead or allocations.
class NoiseGate {
    float threshold_=0, close_=0, env_=0, gain_=1;
    unsigned hold_=0;
    bool enabled_=false, open_=true;
public:
    void set(float db) {
        bool enable=db>=-80;
        if(!enable){enabled_=false;open_=true;env_=0;gain_=1;hold_=0;return;}
        threshold_=std::pow(10.f,db/20.f);
        close_=threshold_*0.7079458f; // 3 dB hysteresis
        if(!enabled_){open_=false;hold_=0;env_=0;}
        enabled_=true;
    }
    bool enabled() const {return enabled_;}
    float gain() const {return enabled_?gain_:1.f;}
    float process(float x) {
        if(!enabled_)return x;
        env_=std::max(std::abs(x),env_*0.9979188f); // 10 ms peak decay at 48 kHz
        if(env_>=threshold_){open_=true;hold_=5760;}
        else if(open_){if(env_>=close_)hold_=5760;else if(hold_)--hold_;else open_=false;}
        gain_+=(open_?0.0206178f:0.00005952204f)*((open_?1.f:0.f)-gain_); // 1 ms opening / 350 ms closing time constants
        if(!open_&&gain_<1e-7f)gain_=0;
        return x*gain_;
    }
};
