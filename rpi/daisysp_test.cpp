// Reproducible characterization of the actual production wrappers, at 48 kHz.
#include "effects.h"
#include <iostream>
#include <iomanip>
#include <vector>
#include <chrono>
#include <limits>
#include <numeric>
constexpr int sr=48000;
void check(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
float db(float v){return 20.f*std::log10(std::max(1e-20f,std::abs(v)));}
template<class E> void bypass(E& e,const char* name){
    for(int i=0;i<sr;++i){float x=.4f*std::sin(i*.027f);check(e.process(x)==x,name);}
}
void compressor(){
    RigCompressor c;bypass(c,"compressor initial bypass");
    for(float a:{.25f,.5f,1.f}){
        c.set(a);float th=-12-24*a,ratio=1+5*a;
        for(float input:{-60.f,-40.f,-24.f,-12.f,-6.f}){
            float x=std::pow(10.f,input/20.f),y=0;
            for(int i=0;i<2*sr;++i)y=c.process(x);
            float expected=input>th?th+(input-th)/ratio:input;
            float measured=db(y);
            std::cout<<"compressor amount="<<a<<" input_dBFS="<<input<<" output_dBFS="<<measured<<" expected="<<expected<<" error_dB="<<measured-expected<<"\n";
            check(std::isfinite(measured)&&std::abs(measured-expected)<.5f,"compressor static curve");
        }
    }
    c.set(1);for(int i=0;i<sr;++i)c.process(.001f);
    float attack[3]{};for(int i=0;i<sr;++i){float y=c.process(.5f);if(i==239)attack[0]=db(y/.5f);if(i==2399)attack[1]=db(y/.5f);if(i==sr-1)attack[2]=db(y/.5f);}
    float release[3]{};for(int i=0;i<2*sr;++i){float y=c.process(.001f);if(i==7199)release[0]=db(y/.001f);if(i==35999)release[1]=db(y/.001f);if(i==2*sr-1)release[2]=db(y/.001f);}
    std::cout<<"compressor gain_dB attack_5ms_50ms_1s="<<attack[0]<<","<<attack[1]<<","<<attack[2]<<" release_150ms_750ms_2s="<<release[0]<<","<<release[1]<<","<<release[2]<<"\n";
    check(attack[2]<attack[0]&&release[2]>release[0]&&std::abs(release[2])<.5f,"compressor dynamics");
    c.set(0);for(int i=0;i<sr;++i)c.process(0);bypass(c,"compressor recovered bypass");
}
void delay(){
    RigDelay d;bypass(d,"delay initial bypass");
    for(int ms:{20,100,350,1000})for(float fb:{0.f,.35f,.85f}){
        RigDelay v;v.set(.5f,float(ms),fb);
        for(int i=0;i<sr;++i)v.process(0);
        const int n=ms*48;float dry=v.process(.5f);double unexpected=0;
        check(std::abs(dry-.25f)<.0001f,"delay dry mix");
        for(int i=1;i<=3*n;++i){
            float y=v.process(0);check(std::isfinite(y),"delay finite");
            if(i%n==0){float expected=.25f*std::pow(fb,i/n-1);
                std::cout<<"delay ms="<<ms<<" feedback="<<fb<<" echo="<<i/n<<" sample="<<i<<" amplitude="<<y<<" expected="<<expected<<"\n";
                check(std::abs(y-expected)<.0002f,"delay echo amplitude/timing");}
            else unexpected+=y*y;
        }
        check(unexpected<1e-8,"delay unexpected samples");
        v.set(0,float(ms),fb);for(int i=0;i<sr;++i)v.process(0);bypass(v,"delay recovered bypass");
    }
}
void chorus(){
    RigChorus c;bypass(c,"chorus initial bypass");
    for(float mix:{.25f,.5f,1.f}){
        RigChorus v;v.set(mix,.8f,0);for(int i=0;i<sr;++i)v.process(0);
        float dry=v.process(.5f),echo=0;double other=0;
        for(int i=1;i<=1200;++i){float y=v.process(0);if(i==576)echo=y;else other+=y*y;}
        std::cout<<"chorus depth=0 mix="<<mix<<" dry="<<dry<<" delay_sample=576 echo="<<echo<<"\n";
        // Upstream ChorusEngine already applies a 50/50 dry/wet blend.
        check(std::abs(dry-.5f*(1-.5f*mix))<.0002f&&std::abs(echo-.25f*mix)<.0002f&&other<1e-8,"chorus static impulse/mix");
    }
    for(float rate:{.5f,2.f}){
        RigChorus v;v.set(1,rate,.5f);for(int i=0;i<sr;++i)v.process(0);
        std::vector<int> lag;constexpr int step=4800;
        for(int j=0;j<60;++j){v.process(.5f);float peak=0;int pos=0;for(int i=1;i<step;++i){float y=v.process(0);check(std::isfinite(y),"chorus finite");if(std::abs(y)>peak){peak=std::abs(y);pos=i;}}lag.push_back(pos);}
        auto [lo,hi]=std::minmax_element(lag.begin(),lag.end());int period=int(std::lround(10/rate));double err=0;for(size_t i=period;i<lag.size();++i)err+=std::abs(lag[i]-lag[i-period]);err/=lag.size()-period;
        std::cout<<"chorus rate_Hz="<<rate<<" delay_min_samples="<<*lo<<" delay_max_samples="<<*hi<<" period_recurrence_mean_error_samples="<<err<<"\n";
        check(*lo>=280&&*hi<=880&&*hi-*lo>300&&err<15,"chorus modulation depth/rate");
        v.set(0,rate,.5f);for(int i=0;i<sr;++i)v.process(0);bypass(v,"chorus recovered bypass");
    }
}
struct ReverbMetrics{double rt60,brightness,energy;};
ReverbMetrics response(float decay,int type){
    RigReverb v;v.set(1,decay,type);for(int i=0;i<sr;++i)v.process(0);
    v.process(.25f);std::vector<double> energy(12*sr);double total=0,diff=0,previous=0;
    for(auto& e:energy){float y=v.process(0);check(std::isfinite(y),"reverb finite");e=double(y)*y;total+=e;diff+=(y-previous)*(y-previous);previous=y;}
    check(total>1e-10,"reverb nonzero response");
    double sum=total,sx=0,sy=0,sxx=0,sxy=0;int n=0;
    for(size_t i=0;i<energy.size();++i){double level=10*std::log10(std::max(1e-300,sum/total));sum-=energy[i];if(i%48==0&&level<=-5&&level>=-35){double t=double(i)/sr;sx+=t;sy+=level;sxx+=t*t;sxy+=t*level;++n;}}
    check(n>10,"reverb T30 fit interval");
    double slope=(n*sxy-sx*sy)/(n*sxx-sx*sx);check(slope<0,"reverb decay slope");
    double rt=-60/slope;std::cout<<"reverb type="<<type<<" requested_decay_s="<<decay<<" estimated_RT60_T30_s="<<rt<<" brightness_diff_energy_ratio="<<diff/total<<" impulse_energy="<<total<<"\n";
    v.set(0,decay,type);for(int i=0;i<sr;++i)v.process(0);bypass(v,"reverb recovered bypass");
    return {rt,diff/total,total};
}
void reverb(){
    RigReverb r;bypass(r,"reverb initial bypass");
    for(int type=0;type<3;++type){auto a=response(.2f,type),b=response(1.5f,type),c=response(5.f,type);check(a.rt60<b.rt60&&b.rt60<c.rt60,"reverb monotonic decay");}
    auto dark=response(1.5f,0),bright=response(1.5f,1);check(bright.brightness>dark.brightness,"reverb voicing");
}
void benchmark(){
    RigCompressor c;RigChorus h;RigDelay d;RigReverb r;
    c.set(.6f);h.set(.6f,1.3f,.6f);d.set(.5f,350,.65f);r.set(.5f,2,1);
    auto start=std::chrono::steady_clock::now();double checksum=0;float maxabs=0;
    for(int i=0;i<10*sr;++i){if(i%4800==0){float f=float((i/4800)%11)/10;c.set(f);h.set(f,.1f+4.9f*f,f);d.set(f,20+980*f,.85f*f);r.set(f,.2f+4.8f*f,(i/4800)%3);}float x=.2f*std::sin(i*.071f),y=r.process(d.process(h.process(c.process(x))));check(std::isfinite(y),"FX automation finite");maxabs=std::max(maxabs,std::abs(y));checksum+=y*y;}
    double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::cout<<"combined_fx_automation audio_seconds=10 elapsed_seconds="<<elapsed<<" realtime_percent="<<10*elapsed<<" peak="<<maxabs<<" energy="<<checksum<<" (DSP-only; not ALSA deadline utilization)\n";
    check(checksum>0&&maxabs<4,"combined FX stability");
}
int main(){std::cout<<std::setprecision(7);compressor();delay();chorus();reverb();benchmark();std::cout<<"DaisySP characterization PASS\n";}
