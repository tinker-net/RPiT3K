#pragma once
#include "hybrid_nam.h"
#include "../eq3band.h"
#include "convolution.h"
#include "tuner.h"
#include "noise_gate.h"
#include "effects.h"
#include "hiz.h"
#include "NAM/wav.h"
#include <cctype>
#include <algorithm>
#include <filesystem>
#include <iostream>
#include <memory>
#include <vector>
namespace ton3k {
inline constexpr unsigned rate=48000, block=64;
struct Options {
    std::string device = "hw:pisound", model, second, ir, ir2, render_in, render_out;
    double slim = 1., slim2 = 1.;
    float input = 1., output = .25f, bass = 0., mid = 0., treble = 0.;
    float gate = -81.f;
    float ir_mix=.5f, hiz=0, hiz_profile=0;
    float comp=0, comp_post=0, reverb=0, decay=1.5f, reverb_type=0;
    float chorus=0.0f, chorus_rate=0.8f, chorus_depth=0.5f, delay=0.0f, delay_ms=350.0f, delay_feedback=0.35f;
    int meter_fd = -1, rig_fd = -1, rig_ack_fd = -1;
    bool nam1_enabled = true;
    bool benchmark = false, bypass = false, tuner = false, live = false, verify = false;
};

inline std::unique_ptr<hybrid::Model> load(const std::string& path,double slim) {
    return hybrid::load(path,slim,rate,block);
}
inline bool is_wav(const std::string& path) {
    auto ext=std::filesystem::path(path).extension().string();
    for(auto& c:ext)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return ext==".wav";
}
inline std::unique_ptr<CabinetConvolver> load_ir(const std::string& path) {
    if(path.empty())return {};
    double sr=0;int channels=0;
    auto samples=nam::detail::load_wav_ir(std::filesystem::path(path),sr,channels);
    if(channels!=1||!std::isfinite(sr)||sr<8000||sr>384000||samples.empty())
        throw std::runtime_error("IR must be mono WAV with valid sample rate");
    if(sr!=rate){
        // Windowed sinc, preserving original time alignment and DC gain.
        const double ratio=rate/sr, cutoff=std::min(1.,ratio);
        const auto n=static_cast<size_t>(std::ceil(samples.size()*ratio));
        if(n>48000)throw std::runtime_error("IR exceeds 1 second");
        std::vector<float> resampled(n);
        for(size_t i=0;i<n;++i){
            double t=i/ratio, sum=0;
            long center=static_cast<long>(std::floor(t));
            for(long j=center-32;j<=center+32;++j){
                if(j<0||static_cast<size_t>(j)>=samples.size())continue;
                double d=t-j;if(std::abs(d)>=32)continue;
                double a=3.141592653589793*d*cutoff;
                double sinc=std::abs(a)<1e-12?1:std::sin(a)/a;
                sum+=samples[j]*cutoff*sinc*(.5+.5*std::cos(3.141592653589793*d/32));
            }
            resampled[i]=static_cast<float>(sum/ratio);
        }
        samples=std::move(resampled);
    }
    return std::make_unique<CabinetConvolver>(samples);
}
struct Chain {
    std::unique_ptr<hybrid::Model> a,b;
    std::unique_ptr<CabinetConvolver> ir,ir2;
    float ir_mix,target_ir_mix;
    bool has_nam1=false;
    float nam1_mix=1.f,nam1_target=1.f;
    void set_stomp(bool enabled){nam1_target=enabled?1.f:0.f;}
    Eq3Band eq;
    GuitarTuner tuner;
    NoiseGate gate;
    HiZCompensation hiz;
    RigCompressor pre, post;
    RigReverb verb;
    RigChorus chorus;
    RigDelay delay;
    bool tuning;
    float input,output;
    float target_input,target_output,bass,mid,treble,target_bass,target_mid,target_treble;
    NAM_SAMPLE x[512]{}, y[512]{}, z[512]{};
    Chain(const Options& o):a((o.bypass||o.tuner) ? nullptr : (o.model.empty()&&!is_wav(o.second)?load(o.second,o.slim2):load(o.model,o.slim))),b((o.bypass||o.tuner||o.model.empty()||is_wav(o.second)) ? nullptr : load(o.second,o.slim2)),ir((o.bypass||o.tuner)?nullptr:load_ir(o.ir.empty()&&is_wav(o.second)?o.second:o.ir)),ir2((o.bypass||o.tuner)?nullptr:load_ir(o.ir2)),ir_mix(o.ir_mix),target_ir_mix(o.ir_mix),tuning(o.tuner),input(o.input),output(o.output),target_input(o.input),target_output(o.output),bass(o.bass),mid(o.mid),treble(o.treble),target_bass(o.bass),target_mid(o.mid),target_treble(o.treble) {
        has_nam1=!o.model.empty()&&bool(a);
        nam1_mix=nam1_target=o.nam1_enabled?1.f:0.f;
        hiz.set(o.hiz,int(o.hiz_profile));
        gate.set(o.gate);
        effects(o.comp,o.comp_post,o.reverb,o.decay,o.reverb_type);
        chorus.set(o.chorus,o.chorus_rate,o.chorus_depth);delay.set(o.delay,o.delay_ms,o.delay_feedback);
        eq.Init(rate);eq.SetBass(o.bass);eq.SetMid(o.mid);eq.SetTreble(o.treble);
    }
    void effects(float c,float pos,float wet,float d,float type){
        if(!std::isfinite(c)||c<0||c>1||!(pos==0||pos==1)||!std::isfinite(wet)||wet<0||wet>1||!std::isfinite(d)||d<.2f||d>5||!(type==0||type==1||type==2))return;
        pre.set(pos==0?c:0);post.set(pos==1?c:0);verb.set(wet,d,int(type));
    }
    void controls(float i,float o,float b,float m,float t,float g=-81.f,float c=0,float pos=0,float wet=0,float d=1.5f,float type=0,float mix=-1,float hz=-1,float profile=0,float ch=0.0f,float cr=0.8f,float cd=0.5f,float dl=0.0f,float dm=350.0f,float df=0.35f) {
        if(!std::isfinite(i)||!std::isfinite(o)||!std::isfinite(b)||!std::isfinite(m)||!std::isfinite(t))return;
        if(i<0||i>2||o<0||o>1||std::abs(b)>20||std::abs(m)>15||std::abs(t)>10)return;
        if(!std::isfinite(g)||!(g==-81.f||(g>=-80.f&&g<=-30.f)))return;
        if(std::isfinite(mix)&&mix>=0&&mix<=1)target_ir_mix=mix;
        if(std::isfinite(profile)&&(profile==0||profile==1||profile==2||profile==3))hiz.set(hz,int(profile));
        gate.set(g);
        effects(c,pos,wet,d,type);
        if(!(!std::isfinite(ch)||ch<0||ch>1||!std::isfinite(cr)||cr<0.1||cr>5||!std::isfinite(cd)||cd<0||cd>1||!std::isfinite(dl)||dl<0||dl>1||!std::isfinite(dm)||dm<20||dm>1000||!std::isfinite(df)||df<0||df>0.85)){chorus.set(ch,cr,cd);delay.set(dl,dm,df);}
        target_input=i;target_output=o;target_bass=b;target_mid=m;target_treble=t;
    }
    void process() {
        if(tuning){
            if(tuner.push(x,block)){
                auto r=tuner.analyze();
                std::cerr<<"TUNER "<<r.hz<<" "<<r.confidence<<"\n";
            }
            std::fill_n(y,block,0.f);return;
        }
        // Smooth gains sample by sample; move EQ gains gradually at block boundaries.
        const float alpha=1.f-std::exp(-float(block)/(rate*.02f));
        auto approach=[alpha](float& v,float target,auto setter){
            if(v==target)return;
            v+=alpha*(target-v);
            if(std::abs(v-target)<.001f)v=target;
            setter(v);
        };
        approach(bass,target_bass,[&](float v){eq.SetBass(v);});
        approach(mid,target_mid,[&](float v){eq.SetMid(v);});
        approach(treble,target_treble,[&](float v){eq.SetTreble(v);});
        float gate_gain[512];
        const bool gated=gate.enabled();
        if(gated)for(unsigned i=0;i<block;++i){gate.process(x[i]);gate_gain[i]=gate.gain();}
        constexpr float gain_alpha=.0020811647f;
        for(unsigned i=0;i<block;++i){input+=gain_alpha*(target_input-input);if(std::abs(input-target_input)<1e-6f)input=target_input;x[i]=hiz.process(x[i])*input;x[i]=pre.process(x[i]);}
        NAM_SAMPLE* in=x;NAM_SAMPLE* out=y;
        if(a) {
            a->process(&in,&out,block);
            if(has_nam1)for(unsigned i=0;i<block;++i){
                const float step=1.f/480.f;
                nam1_mix+=std::clamp(nam1_target-nam1_mix,-step,step);
                y[i]=nam1_mix<=0.f?x[i]:nam1_mix>=1.f?y[i]:x[i]+nam1_mix*(y[i]-x[i]);
            }
        }
        else std::copy_n(x,block,y);
        if(b){in=y;out=z;b->process(&in,&out,block);}
        float cab[512],cab2[512];
        if(ir)for(unsigned i=0;i<block;i+=64)ir->process(out+i,cab+i);
        if(ir2)for(unsigned i=0;i<block;i+=64)ir2->process(out+i,cab2+i);
        if(ir&&ir2){for(unsigned i=0;i<block;++i){ir_mix+=gain_alpha*(target_ir_mix-ir_mix);if(std::abs(ir_mix-target_ir_mix)<1e-6f)ir_mix=target_ir_mix;cab[i]=cab[i]+ir_mix*(cab2[i]-cab[i]);}out=cab;}
        else if(ir)out=cab;
        else if(ir2)out=cab2;
        for(unsigned i=0;i<block;++i){
            output+=gain_alpha*(target_output-output);
            if(std::abs(output-target_output)<1e-6f)output=target_output;
            float s=eq.Process(out[i]);
            if(gated)s*=gate_gain[i];
            s=verb.process(delay.process(chorus.process(post.process(s))))*output;
            y[i]=std::isfinite(s)?std::clamp(s,-1.f,1.f):0.f;
        }
    }
};
}
