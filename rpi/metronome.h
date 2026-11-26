#pragma once
#include <array>
#include <cmath>
#include <algorithm>

// Sample-clock metronome, independent of the loaded rig and ALSA period.
class PracticeMetronome {
    static constexpr unsigned rate=48000, length=960;
    std::array<float,length> regular{}, accent{};
    bool enabled=false;
    unsigned bpm=120, beats=4, beat=0, tick=length;
    double until=0;
    float volume=.15f;
    bool accented=false;
public:
    PracticeMetronome(){
        for(unsigned i=0;i<length;++i){
            double t=double(i)/rate;
            double env=std::min(1.,double(i)/24.)*std::exp(-t*250.)*std::min(1.,double(length-1-i)/48.);
            regular[i]=float(env*std::sin(6.283185307179586*1000*t));
            accent[i]=float(env*std::sin(6.283185307179586*1600*t));
        }
    }
    void set(bool on,unsigned tempo,unsigned meter,float level){
        if(tempo<30||tempo>300||meter<1||meter>12||!std::isfinite(level)||level<0||level>.5f)return;
        if(on&&!enabled){until=0;beat=0;tick=length;}
        if(!on)tick=length;
        if(tempo!=bpm&&enabled&&on)until*=double(bpm)/tempo;
        if(meter!=beats)beat%=meter;
        enabled=on;bpm=tempo;beats=meter;volume=level;
    }
    void mix(float* out,unsigned n,bool audible=true){
        if(!enabled)return;
        for(unsigned i=0;i<n;++i){
            if(until<=0){
                accented=(beat==0);beat=(beat+1)%beats;tick=0;
                until+=double(rate)*60/bpm;
            }
            if(tick<length){
                if(audible)out[i]=std::clamp(out[i]+volume*(accented?accent[tick]:.65f*regular[tick]),-1.f,1.f);
                ++tick;
            }
            until-=1;
        }
    }
};
