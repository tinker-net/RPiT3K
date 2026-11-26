#include "metronome.h"
#include <iostream>
#include <vector>
#include <stdexcept>
int main(){
    for(unsigned block:{64u,128u,256u,512u}){
        PracticeMetronome m;float dry[512];std::fill_n(dry,512,.125f);m.mix(dry,block);
        for(unsigned i=0;i<block;++i)if(dry[i]!=.125f)throw std::runtime_error("OFF transparency");
        m.set(true,120,4,.15f);
        std::vector<float> audio(96000+512);
        for(unsigned i=0;i<96000;i+=block)m.mix(audio.data()+i,block);
        for(unsigned beat=0;beat<4;++beat){
            unsigned start=beat*24000;float peak=0;
            for(unsigned i=start;i<start+960;++i)peak=std::max(peak,std::abs(audio[i]));
            if(peak<.02f||peak>.15f)throw std::runtime_error("Missing or unsafe click");
            for(unsigned i=start+960;i<start+24000;++i)if(audio[i]!=0)throw std::runtime_error("Timing mismatch");
        }
        m.set(false,120,4,.15f);std::fill_n(dry,512,.125f);m.mix(dry,block);
        for(unsigned i=0;i<block;++i)if(dry[i]!=.125f)throw std::runtime_error("Stop transparency");
        m.set(true,137,3,.5f);float muted[512]{};m.mix(muted,block,false);
        for(float v:muted)if(v!=0)throw std::runtime_error("Tuner mute");
    }
    std::cout<<"Metronome timing, gain, mute and bypass PASS\n";
}
