// SPDX-License-Identifier: MIT
#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace ton3k {
// Causal streaming, windowed-sinc rate conversion with a bounded history.
// Coefficients are prepared off the audio thread; push performs no allocation.
class RateStage {
    static constexpr int half=24, taps=2*half, phases=1024, historySize=128;
    std::array<float,historySize> history{};
    std::vector<float> coeff;
    std::int64_t written=0;
    double cursor=0, step=1;
public:
    void prepare(double source,double target){
        history.fill(0);written=0;cursor=0;step=source/target;
        coeff.resize(phases*taps);
        const double cutoff=.94*std::min(1.,target/source), pi=3.14159265358979323846;
        for(int p=0;p<phases;++p){
            double sum=0, frac=double(p)/phases;
            for(int k=0;k<taps;++k){
                double d=k-half+1-frac, a=pi*cutoff*d;
                double s=std::abs(a)<1e-12?1.:std::sin(a)/a;
                double w=std::abs(d)>=half?0.:.5+.5*std::cos(pi*d/half);
                float c=float(cutoff*s*w);coeff[p*taps+k]=c;sum+=c;
            }
            for(int k=0;k<taps;++k)coeff[p*taps+k]/=float(sum);
        }
    }
    template<class Emit> void push(float value,Emit&& emit) noexcept {
        history[std::size_t(written)%historySize]=value;++written;
        while(std::int64_t(std::floor(cursor))+half<written){
            auto center=std::int64_t(std::floor(cursor));
            int phase=std::clamp(int((cursor-double(center))*phases),0,phases-1);
            double result=0;
            for(int k=0;k<taps;++k){
                auto index=center-half+1+k;
                if(index>=0&&index>=written-historySize)
                    result+=double(history[std::size_t(index)%historySize])*coeff[phase*taps+k];
            }
            emit(float(result));cursor+=step;
        }
    }
};
class RateAdapter {
    RateStage toBase, fromBase;
    std::array<float,8192> fifo{};
    std::array<float,64> input{},output{};
    unsigned read=0,write=0,count=0,pos=0;
    unsigned faults=0;
    void enqueue(float v) noexcept {
        if(count==fifo.size()){++faults;return;}
        fifo[write]=v;write=(write+1)%fifo.size();++count;
    }
public:
    int prepare(double host){
        read=write=count=pos=faults=0;fifo.fill(0);input.fill(0);output.fill(0);
        toBase.prepare(host,48000);fromBase.prepare(48000,host);
        // Fixed host-domain delay includes input/output look-ahead and 64-frame block scheduling.
        int latency=int(std::ceil(96.*host/48000.))+32;
        for(int i=0;i<latency;++i)enqueue(0);
        return latency;
    }
    template<class Process> float push(float sample,Process&& process) noexcept {
        toBase.push(sample,[&](float v){
            input[pos++]=v;
            if(pos==64){
                process(input.data(),output.data());
                for(float x:output)fromBase.push(x,[&](float y){enqueue(y);});
                pos=0;
            }
        });
        if(!count){++faults;return 0;}
        float v=fifo[read];read=(read+1)%fifo.size();--count;return v;
    }
    unsigned faultCount()const noexcept{return faults;}
};
}
