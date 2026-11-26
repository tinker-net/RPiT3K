// SPDX-License-Identifier: MIT
#include "../rate_adapter.h"
#include <cassert>
#include <cmath>
#include <iostream>
int main(){
    constexpr double pi=3.14159265358979323846;
    for(double sr:{8000.,22050.,32000.,44100.,88200.,96000.,192000.,384000.}){
        ton3k::RateAdapter a;
        int delay=a.prepare(sr);double e=0,energy=0;
        for(int i=0;i<int(sr*2);++i){
            float x=float(.4*std::sin(2*pi*440*i/sr));
            float y=a.push(x,[](const float* in,float* out){std::copy_n(in,64,out);});
            if(!std::isfinite(y))return 1;
            if(i>delay+int(sr/10)){
                double expected=.4*std::sin(2*pi*440*(i-delay)/sr);
                e+=(y-expected)*(y-expected);energy+=expected*expected;
            }
        }
        if(a.faultCount()!=0||std::sqrt(e/energy)>.025){std::cerr<<sr<<" Hz faults "<<a.faultCount()<<" relative error "<<std::sqrt(e/energy)<<"\n";return 1;}
        std::cout<<sr<<" Hz latency "<<delay<<" samples, relative error "<<std::sqrt(e/energy)<<"\n";
    }
}
