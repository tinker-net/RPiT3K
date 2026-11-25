#include <alsa/asoundlib.h>
#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"
#include "../eq3band.h"
#include "convolution.h"
#include "tuner.h"
#include "NAM/wav.h"
#include <cctype>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <iostream>
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
    std::string device = "hw:pisound", model, second, ir;
    double slim = 1., slim2 = 1.;
    float input = 1., output = .25f, bass = 0., mid = 0., treble = 0.;
    bool benchmark = false, bypass = false, tuner = false, live = false;
};
Options parse(int argc, char** argv) {
    Options o;
    for(int i=1;i<argc;++i) {
        std::string k=argv[i];
        if(k=="--live-controls") {o.live=true;continue;}
        if(k=="--benchmark") {o.benchmark=true;continue;}
        if(k=="--tuner") {o.tuner=true;continue;}
        if(k=="--bypass") {o.bypass=true;continue;}
        if(i+1>=argc) throw std::runtime_error("Missing value: "+k);
        std::string v=argv[++i];
        if(k=="--device") o.device=v;
        else if(k=="--buffer") { if(v!="64"&&v!="128"&&v!="256"&&v!="512") throw std::runtime_error("Invalid buffer"); block=std::stoul(v); }
        else if(k=="--periods") { if(v!="2"&&v!="3"&&v!="4") throw std::runtime_error("Invalid periods"); periods=std::stoul(v); }
        else if(k=="--model") o.model=v;
        else if(k=="--second") o.second=v;
        else if(k=="--ir") o.ir=v;
        else if(k=="--slim") o.slim=std::stod(v);
        else if(k=="--slim2") o.slim2=std::stod(v);
        else if(k=="--input") o.input=std::stof(v);
        else if(k=="--output") o.output=std::stof(v);
        else if(k=="--bass") o.bass=std::stof(v);
        else if(k=="--mid") o.mid=std::stof(v);
        else if(k=="--treble") o.treble=std::stof(v);
        else throw std::runtime_error("Unknown option: "+k);
    }
    if(o.model.empty() && !o.bypass && !o.tuner) throw std::runtime_error("--model FILE required");
    for(double x:{o.slim,o.slim2}) if(!std::isfinite(x)||x<0||x>1) throw std::runtime_error("Slim must be 0..1");
    for(float x:{o.input,o.output,o.bass,o.mid,o.treble}) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite control");
    if(o.input<0||o.input>2||o.output<0||o.output>1) throw std::runtime_error("Gain outside range");
    if(std::abs(o.bass)>20||std::abs(o.mid)>15||std::abs(o.treble)>10) throw std::runtime_error("EQ outside range");
    return o;
}
std::unique_ptr<nam::DSP> load(const std::string& path,double slim) {
    if(path.empty()) return {};
    auto m=nam::get_dsp(std::filesystem::path(path));
    if(m->NumInputChannels()!=1||m->NumOutputChannels()!=1) throw std::runtime_error("Mono models/IR only in prototype");
    if(auto* s=dynamic_cast<nam::SlimmableModel*>(m.get())) s->SetSlimmableSize(slim);
    else if(slim!=1.) throw std::runtime_error("Capture is not slimmable: "+path);
    double sr=m->GetExpectedSampleRate();
    if(sr>0&&sr!=rate&&!m->SupportsArbitrarySampleRate()) throw std::runtime_error("Model sample rate differs from 48 kHz");
    m->Reset(rate,block);
    return m;
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
    std::unique_ptr<nam::DSP> a,b;
    std::unique_ptr<CabinetConvolver> ir;
    Eq3Band eq;
    GuitarTuner tuner;
    bool tuning;
    float input,output;
    float target_input,target_output,bass,mid,treble,target_bass,target_mid,target_treble;
    NAM_SAMPLE x[512]{}, y[512]{}, z[512]{};
    Chain(const Options& o):a((o.bypass||o.tuner) ? nullptr : load(o.model,o.slim)),b((o.bypass||o.tuner||is_wav(o.second)) ? nullptr : load(o.second,o.slim2)),ir((o.bypass||o.tuner)?nullptr:load_ir(o.ir.empty()&&is_wav(o.second)?o.second:o.ir)),tuning(o.tuner),input(o.input),output(o.output),target_input(o.input),target_output(o.output),bass(o.bass),mid(o.mid),treble(o.treble),target_bass(o.bass),target_mid(o.mid),target_treble(o.treble) {
        eq.Init(rate);eq.SetBass(o.bass);eq.SetMid(o.mid);eq.SetTreble(o.treble);
    }
    void controls(float i,float o,float b,float m,float t) {
        if(!std::isfinite(i)||!std::isfinite(o)||!std::isfinite(b)||!std::isfinite(m)||!std::isfinite(t))return;
        if(i<0||i>2||o<0||o>1||std::abs(b)>20||std::abs(m)>15||std::abs(t)>10)return;
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
        constexpr float gain_alpha=.0020811647f;
        for(unsigned i=0;i<block;++i){input+=gain_alpha*(target_input-input);if(std::abs(input-target_input)<1e-6f)input=target_input;x[i]*=input;}
        NAM_SAMPLE* in=x;NAM_SAMPLE* out=y;
        if(a) a->process(&in,&out,block);
        else std::copy_n(x,block,y);
        if(b){in=y;out=z;b->process(&in,&out,block);}
        float cab[512];
        if(ir){for(unsigned i=0;i<block;i+=64)ir->process(out+i,cab+i);out=cab;}
        for(unsigned i=0;i<block;++i){
            output+=gain_alpha*(target_output-output);
            if(std::abs(output-target_output)<1e-6f)output=target_output;
            float s=eq.Process(out[i])*output;
            y[i]=std::isfinite(s)?std::clamp(s,-1.f,1.f):0.f;
        }
    }
};
}
int main(int argc,char** argv) {
    try {
        auto o=parse(argc,argv); Chain chain(o);
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
        sched_param sp{};
        sp.sched_priority=60;
        if(sched_setscheduler(0,SCHED_FIFO,&sp)<0)
            std::cerr<<"Realtime scheduling unavailable; continuing with normal priority\n";
        // Private nonblocking stdin pipe from the controller; fixed storage, bounded work.
        if(o.live){int flags=fcntl(STDIN_FILENO,F_GETFL);if(flags<0||fcntl(STDIN_FILENO,F_SETFL,flags|O_NONBLOCK)<0)throw std::runtime_error("Cannot configure live controls");}
        char line[256]{}; unsigned used=0; bool overflow=false;
        auto poll_controls=[&]{
            if(!o.live)return;
            char buf[512];auto n=read(STDIN_FILENO,buf,sizeof(buf));
            if(n<=0)return;
            for(ssize_t k=0;k<n;++k){
                if(buf[k]=='\n'){
                    if(!overflow){line[used]=0;float i,o,b,m,t;char extra;
                        if(std::sscanf(line,"%f %f %f %f %f %c",&i,&o,&b,&m,&t,&extra)==5)chain.controls(i,o,b,m,t);}
                    used=0;overflow=false;
                }else if(used<sizeof(line)-1)line[used++]=buf[k];else overflow=true;
            }
        };
        unsigned xruns=0;
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
                for(unsigned i=0;i<block;++i)chain.x[i]=buf[i*2]/2147483648.0;
                poll_controls();
                chain.process();
                for(unsigned i=0;i<block;++i) {
                    auto s=static_cast<int32_t>(std::clamp(double(chain.y[i])*2147483648.,-2147483648.,2147483647.));
                    buf[i*2]=buf[i*2+1]=s;
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
