#include "convolution.h"
#include "tuner.h"
#include "noise_gate.h"
#include <iostream>
#include <random>
#include <stdexcept>
int main(){
    NoiseGate gate;
    for(float v:{-.2f,0.f,.00001f,.3f})if(gate.process(v)!=v)throw std::runtime_error("Gate OFF transparency");
    gate.set(-50);
    float y=0;
    for(int i=0;i<96000;++i)y=gate.process(.0005f);
    if(std::abs(y)>1e-7f)throw std::runtime_error("Gate does not close");
    for(int i=0;i<480;++i)y=gate.process(.1f);
    if(std::abs(y-.1f)>1e-5f)throw std::runtime_error("Gate attack");
    for(int i=0;i<960;++i)y=gate.process(.0005f);
    if(y<.00049f)throw std::runtime_error("Gate hold");
    for(int i=0;i<96000;++i)y=gate.process(.0005f);
    if(std::abs(y)>1e-7f)throw std::runtime_error("Gate release");
    gate.set(-81);
    if(gate.process(.0005f)!=.0005f)throw std::runtime_error("Gate disable");
    std::cout<<"Noise gate PASS\n";

    std::mt19937 rng(42);std::uniform_real_distribution<float> rnd(-.2f,.2f);
    for(unsigned len:{1u,63u,64u,65u,4096u,24000u,48000u}){
        std::vector<float> h(len),x(512),y(((len+511+63)/64)*64);
        for(auto& v:h)v=rnd(rng);for(auto& v:x)v=rnd(rng);
        CabinetConvolver c(h);float in[64]{};
        for(size_t i=0;i<y.size();i+=64){
            for(unsigned k=0;k<64;++k)in[k]=i+k<x.size()?x[i+k]:0;
            c.process(in,y.data()+i);
        }
        double maxerr=0;
        for(size_t i=0;i<y.size();++i){
            double expected=0;
            for(size_t j=0;j<x.size()&&j<=i;++j)if(i-j<h.size())expected+=double(x[j])*h[i-j];
            maxerr=std::max(maxerr,std::abs(y[i]-expected));
        }
        std::cout<<"IR "<<len<<" max error "<<maxerr<<"\n";
        if(maxerr>0.0001)throw std::runtime_error("Convolution mismatch");
    }
    for(float hz:{41.2034f,82.4069f,110.f,146.832f,196.f,246.942f,329.628f,440.f}){
        GuitarTuner t;GuitarTuner::Reading r;
        for(unsigned i=0;i<24000;i+=64){
            float x[64];
            for(unsigned j=0;j<64;++j){float p=6.283185307f*hz*(i+j)/48000;x[j]=.1f*(std::sin(p)+.4f*std::sin(2*p));}
            if(t.push(x,64))r=t.analyze();
        }
        double cents=1200*std::log2(r.hz/hz);
        std::cout<<"Tuner "<<hz<<" -> "<<r.hz<<" ("<<cents<<" cents)\n";
        if(!std::isfinite(cents)||std::abs(cents)>5)throw std::runtime_error("Pitch mismatch");
    }
}
