#pragma once
#include <array>
#include <cmath>
#include <algorithm>

// Monophonic pitch estimator, decimated to 6 kHz with a boxcar antialias stage.
// Normalized difference (YIN-style), suitable for standard guitar/bass tuning.
class GuitarTuner {
    static constexpr unsigned N=1200, MAXLAG=200, MINLAG=5;
    std::array<float,N> ring{};
    unsigned head=0, filled=0, dec=0, since=0;
    float sum=0;
public:
    struct Reading {float hz=0, confidence=0;};
    bool push(const float* in,unsigned n) {
        for(unsigned i=0;i<n;++i){
            sum+=in[i];
            if(++dec==8){ring[head]=sum/8;head=(head+1)%N;filled=std::min(N,filled+1);sum=0;dec=0;++since;}
        }
        if(filled==N&&since>=300){since=0;return true;}
        return false;
    }
    Reading analyze() const {
        std::array<float,N> x{};
        double mean=0,energy=0;
        for(unsigned i=0;i<N;++i){x[i]=ring[(head+i)%N];mean+=x[i];}
        mean/=N;
        for(auto& v:x){v-=mean;energy+=v*v;}
        if(energy/N<1e-7)return {};
        std::array<float,MAXLAG+1> d{};
        float cumulative=0;d[0]=1;
        for(unsigned lag=1;lag<=MAXLAG;++lag){
            float v=0;
            for(unsigned i=0;i<N-MAXLAG;++i){float e=x[i]-x[i+lag];v+=e*e;}
            cumulative+=v;d[lag]=cumulative>0?v*lag/cumulative:1;
        }
        unsigned best=0;
        for(unsigned lag=MINLAG;lag<MAXLAG;++lag)
            if(d[lag]<.20f&&d[lag]<=d[lag-1]&&d[lag]<=d[lag+1]){best=lag;break;}
        if(!best)return {};
        float a=d[best-1],b=d[best],c=d[best+1],den=a-2*b+c;
        float delta=std::abs(den)>1e-8f?std::clamp(.5f*(a-c)/den,-.5f,.5f):0;
        const float hz=6000.f/(best+delta);
        return (hz>=30.f&&hz<=1200.f)?Reading{hz,1-b}:Reading{};
    }
};
