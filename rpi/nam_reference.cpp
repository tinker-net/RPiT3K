#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>
#include <cmath>
#include <stdexcept>

int main(int argc,char** argv){
    try {
        if(argc!=6)throw std::runtime_error("Usage: nam-reference MODEL SLIM BLOCK INPUT.f32 OUTPUT.f32");
        const double slim=std::stod(argv[2]);
        const int block=std::stoi(argv[3]);
        if(!std::isfinite(slim)||slim<0||slim>1||block<1||block>4096)throw std::runtime_error("Invalid parameters");
        auto model=nam::get_dsp(std::filesystem::path(argv[1]));
        if(model->NumInputChannels()!=1||model->NumOutputChannels()!=1)throw std::runtime_error("Mono model required");
        if(auto* s=dynamic_cast<nam::SlimmableModel*>(model.get()))s->SetSlimmableSize(slim);
        else if(slim!=1.)throw std::runtime_error("Not slimmable");
        if(model->GetExpectedSampleRate()>0&&model->GetExpectedSampleRate()!=48000&&!model->SupportsArbitrarySampleRate())throw std::runtime_error("Unsupported sample rate");
        model->Reset(48000,block);
        if(std::filesystem::exists(argv[5]))throw std::runtime_error("Output already exists");
        std::ifstream in(argv[4],std::ios::binary);
        std::ofstream out(argv[5],std::ios::binary);
        if(!in||!out)throw std::runtime_error("Cannot open files");
        std::vector<float> f(block);
        std::vector<NAM_SAMPLE> x(block),y(block);
        size_t frames=0;
        while(in.read(reinterpret_cast<char*>(f.data()),block*sizeof(float))){
            for(int i=0;i<block;++i){if(!std::isfinite(f[i]))throw std::runtime_error("Nonfinite input");x[i]=f[i];}
            auto* a=x.data();auto* b=y.data();
            model->process(&a,&b,block);
            // Fixed test attenuation, same as production render; no clipping or EQ.
            for(int i=0;i<block;++i){f[i]=static_cast<float>(y[i]*.125);if(!std::isfinite(f[i]))throw std::runtime_error("Nonfinite reference");}
            out.write(reinterpret_cast<const char*>(f.data()),block*sizeof(float));
            if(!out)throw std::runtime_error("Write failed");
            frames+=block;
        }
        if(!in.eof()||in.gcount()!=0||!frames)throw std::runtime_error("Incomplete input");
        out.close();if(!out)throw std::runtime_error("Close failed");
        std::cout<<"REFERENCE frames="<<frames<<" sample_bytes="<<sizeof(NAM_SAMPLE)<<"\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
