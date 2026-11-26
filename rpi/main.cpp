#include <alsa/asoundlib.h>
#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"
#include "hybrid_nam.h"
#include "../eq3band.h"
#include "convolution.h"
#include "live_rig.h"
#include "metronome.h"
#include "json.hpp"
#include "tuner.h"
#include "noise_gate.h"
#include "effects.h"
#include "hiz.h"
#include "NAM/wav.h"
#include <cctype>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <iostream>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <vector>
#include <string>
#include <cstdint>
#include <cerrno>
#include <sched.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstdio>

namespace {
volatile std::sig_atomic_t running = 1;
void stop(int) { running = 0; }
constexpr unsigned rate = 48000;
unsigned block = 64;
unsigned periods = 3;
void check(int rc, const char* what) {
    if (rc < 0) throw std::runtime_error(std::string(what)+": "+snd_strerror(rc));
}
struct Close { void operator()(snd_pcm_t* p) const { if(p) snd_pcm_close(p); } };
using PCM = std::unique_ptr<snd_pcm_t, Close>;
PCM open_pcm(const char* device, snd_pcm_stream_t stream) {
    snd_pcm_t* raw = nullptr;
    check(snd_pcm_open(&raw, device, stream, 0), "open PCM");
    PCM pcm(raw);
    snd_pcm_hw_params_t* hw;
    snd_pcm_hw_params_alloca(&hw);
    check(snd_pcm_hw_params_any(raw, hw), "hw params");
    check(snd_pcm_hw_params_set_access(raw, hw, SND_PCM_ACCESS_RW_INTERLEAVED), "access");
    check(snd_pcm_hw_params_set_format(raw, hw, SND_PCM_FORMAT_S32_LE), "format");
    check(snd_pcm_hw_params_set_channels(raw, hw, 2), "channels");
    check(snd_pcm_hw_params_set_rate(raw, hw, rate, 0), "rate");
    check(snd_pcm_hw_params_set_period_size(raw, hw, block, 0), "period");
    check(snd_pcm_hw_params_set_buffer_size(raw, hw, block*periods), "buffer");
    check(snd_pcm_hw_params(raw, hw), "apply hw");
    snd_pcm_sw_params_t* sw;
    snd_pcm_sw_params_alloca(&sw);
    check(snd_pcm_sw_params_current(raw, sw), "sw params");
    check(snd_pcm_sw_params_set_avail_min(raw, sw, block), "avail min");
    if(stream == SND_PCM_STREAM_PLAYBACK)
        check(snd_pcm_sw_params_set_start_threshold(raw, sw, block*periods), "playback start threshold");
    check(snd_pcm_sw_params(raw, sw), "apply sw");
    return pcm;
}
struct Options {
    std::string device = "hw:pisound", model, second, ir, ir2, render_in, render_out;
    double slim = 1., slim2 = 1.;
    float input = 1., output = .25f, bass = 0., mid = 0., treble = 0.;
    float gate = -81.f;
    float ir_mix=.5f, hiz=0, hiz_profile=0;
    float comp=0, comp_post=0, reverb=0, decay=1.5f, reverb_type=0;
    float chorus=0.0f, chorus_rate=0.8f, chorus_depth=0.5f, delay=0.0f, delay_ms=350.0f, delay_feedback=0.35f;
    int meter_fd = -1, rig_fd = -1, rig_ack_fd = -1;
    bool benchmark = false, bypass = false, tuner = false, live = false, verify = false;
};
bool is_wav(const std::string& path);
Options parse(int argc, char** argv, bool rig_only=false) {
    Options o;
    for(int i=1;i<argc;++i) {
        std::string k=argv[i];
        if(k=="--live-controls") {o.live=true;continue;}
        if(k=="--verify") {o.verify=true;continue;}
        if(k=="--benchmark") {o.benchmark=true;continue;}
        if(k=="--tuner") {o.tuner=true;continue;}
        if(k=="--bypass") {o.bypass=true;continue;}
        if(i+1>=argc) throw std::runtime_error("Missing value: "+k);
        std::string v=argv[++i];
        if(k=="--render-in") o.render_in=v;
        else if(k=="--render-out") o.render_out=v;
        else if(k=="--device") o.device=v;
        else if(k=="--meter-fd") { o.meter_fd=std::stoi(v); if(o.meter_fd<3)throw std::runtime_error("Invalid meter fd"); }
        else if(k=="--rig-fd"||k=="--rig-ack-fd") { if(rig_only)throw std::runtime_error("Invalid rig fd"); auto fd=std::stoi(v);if(fd<3)throw std::runtime_error("Invalid rig fd");(k=="--rig-fd"?o.rig_fd:o.rig_ack_fd)=fd; }
        else if(k=="--buffer") { if(v!="64"&&v!="128"&&v!="256"&&v!="512") throw std::runtime_error("Invalid buffer"); auto b=std::stoul(v);if(rig_only){if(b!=block)throw std::runtime_error("ALSA period requires reopening");}else block=b; }
        else if(k=="--periods") { if(v!="2"&&v!="3"&&v!="4") throw std::runtime_error("Invalid periods"); auto p=std::stoul(v);if(rig_only){if(p!=periods)throw std::runtime_error("ALSA periods require reopening");}else periods=p; }
        else if(k=="--model") o.model=v;
        else if(k=="--second") o.second=v;
        else if(k=="--ir") o.ir=v;
        else if(k=="--ir2") o.ir2=v;
        else if(k=="--ir_mix") o.ir_mix=std::stof(v);
        else if(k=="--hiz") o.hiz=std::stof(v);
        else if(k=="--hiz_profile") o.hiz_profile=std::stof(v);
        else if(k=="--slim") o.slim=std::stod(v);
        else if(k=="--slim2") o.slim2=std::stod(v);
        else if(k=="--comp") o.comp=std::stof(v);
        else if(k=="--comp_post") o.comp_post=std::stof(v);
        else if(k=="--reverb") o.reverb=std::stof(v);
        else if(k=="--decay") o.decay=std::stof(v);
        else if(k=="--reverb_type") o.reverb_type=std::stof(v);
        else if(k=="--chorus") o.chorus=std::stof(v);
        else if(k=="--chorus_rate") o.chorus_rate=std::stof(v);
        else if(k=="--chorus_depth") o.chorus_depth=std::stof(v);
        else if(k=="--delay") o.delay=std::stof(v);
        else if(k=="--delay_ms") o.delay_ms=std::stof(v);
        else if(k=="--delay_feedback") o.delay_feedback=std::stof(v);
        else if(k=="--gate") o.gate=std::stof(v);
        else if(k=="--input") o.input=std::stof(v);
        else if(k=="--output") o.output=std::stof(v);
        else if(k=="--bass") o.bass=std::stof(v);
        else if(k=="--mid") o.mid=std::stof(v);
        else if(k=="--treble") o.treble=std::stof(v);
        else throw std::runtime_error("Unknown option: "+k);
    }
    if(o.model.empty() && (o.second.empty() || is_wav(o.second)) && !o.bypass && !o.tuner) throw std::runtime_error("Choose a NAM capture in either slot");
    for(double x:{o.slim,o.slim2}) if(!std::isfinite(x)||x<0||x>1) throw std::runtime_error("Slim must be 0..1");
    for(float x:{o.input,o.output,o.bass,o.mid,o.treble}) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite control");
    if(o.input<0||o.input>2||o.output<0||o.output>1) throw std::runtime_error("Gain outside range");
    if(std::abs(o.bass)>20||std::abs(o.mid)>15||std::abs(o.treble)>10) throw std::runtime_error("EQ outside range");
    if(!std::isfinite(o.gate)||!(o.gate==-81.f||(o.gate>=-80.f&&o.gate<=-30.f)))throw std::runtime_error("Invalid gate threshold");
    if(!std::isfinite(o.chorus)||o.chorus<0||o.chorus>1||!std::isfinite(o.chorus_rate)||o.chorus_rate<0.1||o.chorus_rate>5||!std::isfinite(o.chorus_depth)||o.chorus_depth<0||o.chorus_depth>1||!std::isfinite(o.delay)||o.delay<0||o.delay>1||!std::isfinite(o.delay_ms)||o.delay_ms<20||o.delay_ms>1000||!std::isfinite(o.delay_feedback)||o.delay_feedback<0||o.delay_feedback>0.85)throw std::runtime_error("Invalid chorus/delay controls");
    if(!std::isfinite(o.comp)||o.comp<0||o.comp>1||!(o.comp_post==0||o.comp_post==1)||!std::isfinite(o.reverb)||o.reverb<0||o.reverb>1||!std::isfinite(o.decay)||o.decay<.2f||o.decay>5||!(o.reverb_type==0||o.reverb_type==1||o.reverb_type==2))throw std::runtime_error("Invalid effects controls");
    if(!std::isfinite(o.ir_mix)||o.ir_mix<0||o.ir_mix>1)throw std::runtime_error("Invalid IR mix");
    if(!std::isfinite(o.hiz)||o.hiz<0||o.hiz>1||!(o.hiz_profile==0||o.hiz_profile==1||o.hiz_profile==2||o.hiz_profile==3))throw std::runtime_error("Invalid Hi-Z compensation");
    return o;
}
std::unique_ptr<hybrid::Model> load(const std::string& path,double slim) {
    return hybrid::load(path,slim,rate,block);
}
bool is_wav(const std::string& path) {
    auto ext=std::filesystem::path(path).extension().string();
    for(auto& c:ext)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return ext==".wav";
}
std::unique_ptr<CabinetConvolver> load_ir(const std::string& path) {
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
        if(a) a->process(&in,&out,block);
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
int main(int argc,char** argv) {
    try {
        auto o=parse(argc,argv); auto initial=std::make_unique<Chain>(o); Chain& chain=*initial;
        if(!o.render_in.empty() || !o.render_out.empty()){
            // Offline path uses the identical production Chain and block size.
            if(o.render_in.empty()||o.render_out.empty()||o.tuner||o.verify||o.benchmark||o.live)
                throw std::runtime_error("Offline render requires both paths and audio mode");
            if(std::filesystem::exists(o.render_out))
                throw std::runtime_error("Render output already exists");
            std::ifstream in(o.render_in,std::ios::binary);
            if(!in)throw std::runtime_error("Cannot open render input");
            std::ofstream out(o.render_out,std::ios::binary);
            if(!out)throw std::runtime_error("Cannot open render output");
            size_t frames=0;
            while(in.read(reinterpret_cast<char*>(chain.x),block*sizeof(float))){
                for(unsigned i=0;i<block;++i)if(!std::isfinite(chain.x[i]))throw std::runtime_error("Nonfinite input");
                chain.process();
                out.write(reinterpret_cast<const char*>(chain.y),block*sizeof(float));
                if(!out)throw std::runtime_error("Render write failed");
                frames+=block;
            }
            if(!in.eof()||in.gcount()!=0||!frames)throw std::runtime_error("Input must contain whole nonempty float32 blocks");
            out.close();if(!out)throw std::runtime_error("Render close failed");
            std::cout<<"RENDER frames="<<frames<<" block="<<block<<"\n";
            return 0;
        }
        if(o.verify){
            // Same Chain as live playback; deterministic signal, no ALSA device.
            auto measure=[&](float hz){
                double sum=0;unsigned count=0,clipped=0;
                for(unsigned i=0;i<96000/block;++i){
                    for(unsigned j=0;j<block;++j)chain.x[j]=.01f*std::sin(6.283185307179586*hz*(i*block+j)/rate);
                    chain.process();
                    if(i>=48000/block)for(unsigned j=0;j<block;++j){
                        double v=chain.y[j];sum+=v*v;++count;if(std::abs(v)>=.99999)++clipped;
                    }
                }
                std::cout<<"frequency="<<hz<<" rms="<<std::sqrt(sum/count)<<" clipped="<<clipped<<"\n";
                return std::sqrt(sum/count);
            };
            std::cout<<"VERIFY NAM="<<bool(chain.a)<<" NAM2="<<bool(chain.b)<<" IR="<<bool(chain.ir)<<" IR2="<<bool(chain.ir2)<<"\n";
            if(o.tuner)throw std::runtime_error("Verify requires audio mode");
            chain.controls(1,.25,0,0,0);double base=measure(440);
            chain.controls(1,.125,0,0,0);double half=measure(440);
            chain.controls(1,0,0,0,0);double mute=measure(440);
            chain.controls(0,.25,0,0,0);double zero_in=measure(440);
            chain.controls(1,.25,0,0,0);double low=measure(80);
            chain.controls(1,.25,10,0,0);double boost_low=measure(80);
            chain.controls(1,.25,0,0,0);double mid=measure(425);
            chain.controls(1,.25,0,10,0);double boost_mid=measure(425);
            chain.controls(1,.25,0,0,0);double high=measure(3000);
            chain.controls(1,.25,0,0,10);double boost_high=measure(3000);
            auto db=[](double a,double b){return 20*std::log10(a/b);};
            std::cout<<"output_half_db="<<db(half,base)<<" mute_rms="<<mute<<" zero_input_rms="<<zero_in
                     <<" bass_delta_db="<<db(boost_low,low)<<" mid_delta_db="<<db(boost_mid,mid)<<" treble_delta_db="<<db(boost_high,high)<<"\n";
            bool pass=base>1e-7&&std::abs(db(half,base)+6.0206)<.2&&mute==0&&
                db(boost_low,low)>5&&db(boost_mid,mid)>7&&db(boost_high,high)>5;
            std::cout<<"VERIFY "<<(pass?"PASS":"FAIL")<<"\n";return pass?0:2;
        }
        if(o.benchmark) {
            using clock=std::chrono::steady_clock;
            double worst=0, total=0;
            const unsigned iterations=480000/block;
            for(unsigned i=0;i<iterations;++i){
                for(unsigned j=0;j<block;++j) chain.x[j]=.05f*std::sin(6.2831853f*220.f*(i*block+j)/rate);
                auto t=clock::now();chain.process();
                double us=std::chrono::duration<double,std::micro>(clock::now()-t).count();
                total+=us;worst=std::max(worst,us);
            }
            std::cout<<"mean_us="<<total/iterations<<" max_us="<<worst<<" deadline_us="<<1e6*block/rate<<"\n";
            return 0;
        }
        std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
        auto cap=open_pcm(o.device.c_str(),SND_PCM_STREAM_CAPTURE);
        auto play=open_pcm(o.device.c_str(),SND_PCM_STREAM_PLAYBACK);
        int32_t buf[1024]{};
        std::signal(SIGPIPE,SIG_IGN);
        auto current=std::move(initial);
        LiveRigLoader<Chain> loader(o.rig_fd,o.rig_ack_fd,[&](const std::string& line){
            auto args=nlohmann::json::parse(line).get<std::vector<std::string>>();
            args.insert(args.begin(),"rpit3k");
            std::vector<char*> argv2;for(auto& a:args)argv2.push_back(a.data());
            auto next=parse(static_cast<int>(argv2.size()),argv2.data(),true);
            if(next.device!=o.device||next.benchmark||next.verify||next.live||!next.render_in.empty()||!next.render_out.empty())
                throw std::runtime_error("Invalid live rig options");
            return std::make_unique<Chain>(next);
        });
        bool fade_in=false;
        sched_param sp{};
        sp.sched_priority=60;
        if(sched_setscheduler(0,SCHED_FIFO,&sp)<0)
            std::cerr<<"Realtime scheduling unavailable; continuing with normal priority\n";
        // Private nonblocking stdin pipe from the controller; fixed storage, bounded work.
        if(o.live){int flags=fcntl(STDIN_FILENO,F_GETFL);if(flags<0||fcntl(STDIN_FILENO,F_SETFL,flags|O_NONBLOCK)<0)throw std::runtime_error("Cannot configure live controls");}
        PracticeMetronome metronome;
        char line[512]{}; unsigned used=0; bool overflow=false;
        auto poll_controls=[&]{
            if(!o.live)return;
            char buf[512];auto n=read(STDIN_FILENO,buf,sizeof(buf));
            if(n<=0)return;
            for(ssize_t k=0;k<n;++k){
                if(buf[k]=='\n'){
                    if(!overflow){line[used]=0;float i,o,b,m,t,g,c,pos,wet,d,type,mix,hz,profile,ch,cr,cd,dl,dm,df;char extra;
                        unsigned enabled,bpm,beats;float level;
                        if(std::sscanf(line,"METRO %u %u %u %f %c",&enabled,&bpm,&beats,&level,&extra)==4&&enabled<=1)metronome.set(enabled!=0,bpm,beats,level);
                        else if(std::sscanf(line,"%f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %c",&i,&o,&b,&m,&t,&g,&c,&pos,&wet,&d,&type,&mix,&hz,&profile,&ch,&cr,&cd,&dl,&dm,&df,&extra)==20)current->controls(i,o,b,m,t,g,c,pos,wet,d,type,mix,hz,profile,ch,cr,cd,dl,dm,df);
                        else if(std::sscanf(line,"%f %f %f %f %f %f %f %f %f %f %f %f %f %f %c",&i,&o,&b,&m,&t,&g,&c,&pos,&wet,&d,&type,&mix,&hz,&profile,&extra)==14)current->controls(i,o,b,m,t,g,c,pos,wet,d,type,mix,hz,profile);
                        else if(std::sscanf(line,"%f %f %f %f %f %f %f %f %f %f %f %f %c",&i,&o,&b,&m,&t,&g,&c,&pos,&wet,&d,&type,&mix,&extra)==12)current->controls(i,o,b,m,t,g,c,pos,wet,d,type,mix);
                        else if(std::sscanf(line,"%f %f %f %f %f %f %f %f %f %f %f %c",&i,&o,&b,&m,&t,&g,&c,&pos,&wet,&d,&type,&extra)==11)current->controls(i,o,b,m,t,g,c,pos,wet,d,type);}
                    used=0;overflow=false;
                }else if(used<sizeof(line)-1)line[used++]=buf[k];else overflow=true;
            }
        };
        if(o.meter_fd>=0){int flags=fcntl(o.meter_fd,F_GETFL);if(flags<0||fcntl(o.meter_fd,F_SETFL,flags|O_NONBLOCK)<0)throw std::runtime_error("Cannot configure meter pipe");std::signal(SIGPIPE,SIG_IGN);}
        float meter[2]{}; unsigned meter_frames=0;
        unsigned xruns=0, measured=0, late=0, clipped=0;
        double total_us=0,worst_us=0,in_peak=0,out_peak=0;
        auto report_at=std::chrono::steady_clock::now();
        auto restart=[&] {
            snd_pcm_drop(play.get());snd_pcm_drop(cap.get());
            check(snd_pcm_prepare(cap.get()),"prepare capture");
            check(snd_pcm_prepare(play.get()),"prepare playback");
            check(snd_pcm_start(cap.get()),"start capture");
        };
        restart();
        std::cerr<<"ALSA started: 48 kHz / "<<block<<" frames / "<<periods<<" periods; Ctrl+C to stop\n";
        while(running){
            unsigned got=0;
            bool failed=false;
            while(got<block && running){
                auto n=snd_pcm_readi(cap.get(),buf+got*2,block-got);
                if(n==-EINTR)continue;
                if(n==-EPIPE || n==-ESTRPIPE){failed=true;break;}
                if(n<0)check(static_cast<int>(n),"capture");
                if(n==0)continue;
                got+=n;
            }
            if(!running)break;
            if(!failed){
                for(unsigned i=0;i<block;++i)current->x[i]=buf[i*2]/2147483648.0;
                for(unsigned i=0;i<block;++i){const float p=std::abs(current->x[i]);in_peak=std::max(in_peak,double(p));meter[0]=std::max(meter[0],p);}
                auto dsp_start=std::chrono::steady_clock::now();
                poll_controls();
                current->process();
                auto* replacement=loader.take();
                // Fade a single chain out/in rather than double its realtime CPU cost.
                if(fade_in){for(unsigned i=0;i<64;++i)current->y[i]*=float(i)/63.f;fade_in=false;}
                if(replacement)for(unsigned i=0;i<64;++i)current->y[block-64+i]*=float(63-i)/63.f;
                metronome.mix(current->y,block,!current->tuning);
                double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-dsp_start).count();
                total_us+=us;worst_us=std::max(worst_us,us);++measured;if(us>1e6*block/rate)++late;
                for(unsigned i=0;i<block;++i){meter[1]=std::max(meter[1],std::abs(current->y[i]));out_peak=std::max(out_peak,double(std::abs(current->y[i])));if(std::abs(current->y[i])>=.99999f)++clipped;}
                for(unsigned i=0;i<block;++i) {
                    auto s=static_cast<int32_t>(std::clamp(double(current->y[i])*2147483648.,-2147483648.,2147483647.));
                    buf[i*2]=buf[i*2+1]=s;
                }
                if(replacement){
                    auto* old=current.release();current.reset(replacement);loader.retire(old);fade_in=true;
                }
                unsigned done=0;
                while(done<block&&running){
                    auto w=snd_pcm_writei(play.get(),buf+done*2,block-done);
                    if(w==-EINTR)continue;
                    if(w==-EPIPE || w==-ESTRPIPE){failed=true;break;}
                    if(w<0)check(static_cast<int>(w),"playback");
                    if(w==0)continue;
                    done+=w;
                }
            }
            if(!failed && o.meter_fd>=0){meter_frames+=block;if(meter_frames>=2400){const auto n=write(o.meter_fd,meter,sizeof(meter));if(n<0&&errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR){close(o.meter_fd);o.meter_fd=-1;}meter[0]=meter[1]=0;meter_frames=0;}}
            auto now=std::chrono::steady_clock::now();
            if(measured && now-report_at>=std::chrono::seconds(5)){
                std::cerr<<"DSP mean_us="<<total_us/measured<<" max_us="<<worst_us<<" deadline_us="<<1e6*block/rate<<" blocks="<<measured<<" late="<<late<<" xruns="<<xruns<<" in_peak="<<in_peak<<" out_peak="<<out_peak<<" clipped_samples="<<clipped<<" NAM="<<bool(current->a)<<" IR="<<bool(current->ir)<<" IR2="<<bool(current->ir2)<<"\n";
                measured=late=clipped=0;total_us=worst_us=in_peak=out_peak=0;report_at=now;
            }
            if(failed && running){
                ++xruns;
                if(xruns<=5 || xruns%100==0)std::cerr<<"ALSA xrun/restart #"<<xruns<<"\n";
                restart();
            }
        }
        std::cerr<<"ALSA xruns/restarts: "<<xruns<<"\n";
        snd_pcm_drop(play.get());snd_pcm_drop(cap.get());
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
