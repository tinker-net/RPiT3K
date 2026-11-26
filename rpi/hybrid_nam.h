#pragma once
#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"
#include "NAM/wavenet/a2_fast.h"
#include <fstream>
#include <memory>
#include <vector>
#include <cmath>
#include <cstdlib>
#include <iostream>
#ifdef RPIT3K_EMBEDDED
extern "C" {
#include "nam_a2lite.h"
#include "nam_a2full.h"
}
#endif

namespace hybrid {
struct Model {
    virtual ~Model() = default;
    virtual void process(float** in,float** out,int n)=0;
};
struct Core final : Model {
    std::unique_ptr<nam::DSP> dsp;
    explicit Core(std::unique_ptr<nam::DSP> p):dsp(std::move(p)){}
    void process(float** in,float** out,int n) override { dsp->process(in,out,n); }
};
#ifdef RPIT3K_EMBEDDED
template<class W,class I,class S, auto Load,auto Init,auto Warm,auto Process>
struct Embedded final : Model {
    W weights{}; I instance{}; S state{};
    explicit Embedded(const std::vector<float>& w) {
        if(Load(&weights,w.data(),static_cast<int>(w.size()))!=0)
            throw std::runtime_error("Embedded weight count mismatch");
        Init(&instance,&weights,&state); Warm(&instance);
    }
    void process(float** in,float** out,int n) override {
        // Engine compiled for 64 frames. Larger ALSA blocks are split without resetting state.
        for(int i=0;i<n;i+=64) {
            const float* src[]={in[0]+i}; float* dst[]={out[0]+i};
            Process(&instance,src,dst,std::min(64,n-i));
        }
    }
};
using Lite=Embedded<nam_a2lite_weights_t,nam_a2lite_t,nam_a2lite_state_t,nam_a2lite_load_weights,nam_a2lite_init,nam_a2lite_prewarm,nam_a2lite_process>;
using Full=Embedded<nam_a2full_weights_t,nam_a2full_t,nam_a2full_state_t,nam_a2full_load_weights,nam_a2full_init,nam_a2full_prewarm,nam_a2full_process>;

inline std::unique_ptr<Model> try_embedded(const std::string& path,double slim) {
    std::ifstream f(path);
    nlohmann::json root; f>>root;
    const nlohmann::json* selected=&root;
    if(root.value("architecture",std::string{})=="SlimmableContainer") {
        const auto& subs=root.at("config").at("submodels");
        if(!subs.is_array()||subs.empty()) return {};
        // Match Core's strict less-than boundary and final-child fallback.
        const auto* entry=&subs.back();
        for(const auto& s:subs) if(slim<s.at("max_value").get<double>()) {entry=&s;break;}
        selected=&entry->at("model");
    }
    if(selected->value("architecture",std::string{})!="WaveNet" ||
       nam::get_sample_rate_from_nam_file(*selected)!=48000) return {};
    int channels=0;
    if(!nam::wavenet::a2_fast::is_a2_shape(selected->at("config"),&channels)) return {};
    const auto& raw=selected->at("weights");
    if(!raw.is_array()||raw.size()!=(channels==3?1871u:12146u)) return {};
    auto w=raw.get<std::vector<float>>();
    for(float x:w) if(!std::isfinite(x)) return {};
    if(channels==3) return std::make_unique<Lite>(w);
    if(channels==8) return std::make_unique<Full>(w);
    return {};
}
#endif

inline std::unique_ptr<Model> load(const std::string& path,double slim,unsigned rate,unsigned block) {
    if(path.empty()) return {};
    // Preserve upstream validation, slim selection, and fallback behavior.
    auto m=nam::get_dsp(std::filesystem::path(path));
    if(m->NumInputChannels()!=1||m->NumOutputChannels()!=1) throw std::runtime_error("Mono models only");
    if(auto* s=dynamic_cast<nam::SlimmableModel*>(m.get())) s->SetSlimmableSize(slim);
    else if(slim!=1.) throw std::runtime_error("Capture is not slimmable: "+path);
    double sr=m->GetExpectedSampleRate();
    if(sr>0&&sr!=rate&&!m->SupportsArbitrarySampleRate()) throw std::runtime_error("Model sample rate differs from 48 kHz");
#ifdef RPIT3K_EMBEDDED
    const char* force=std::getenv("RPIT3K_NAM_ENGINE");
    if(!force||std::string(force)!="core") {
        try {
            if(auto e=try_embedded(path,slim)) {
                std::cerr<<"NAM_ENGINE=embedded path="<<path<<" slim="<<slim<<"\n";
                return e;
            }
        } catch(const std::exception& e) {std::cerr<<"Embedded fallback: "<<e.what()<<"\n";}
    }
#endif
    m->Reset(rate,block);
    std::cerr<<"NAM_ENGINE=core path="<<path<<" slim="<<slim<<"\n";
    return std::make_unique<Core>(std::move(m));
}
}
