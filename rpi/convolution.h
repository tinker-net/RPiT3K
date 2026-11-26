#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <stdexcept>
#include <vector>

// Uniform partitioned overlap-add: all taps, no extra callback delay.
// Split, padded positive-frequency arrays allow portable SIMD auto-vectorization.
class CabinetConvolver {
public:
    static constexpr unsigned B=64, N=2*B, K=72;
    using C=std::complex<float>;
    using Spectrum=std::array<C,N>;
    explicit CabinetConvolver(const std::vector<float>& ir) {
        if(ir.empty() || ir.size()>48000) throw std::runtime_error("IR must contain 1..48000 samples at 48 kHz");
        for(unsigned k=0;k<N/2;++k) twiddle[k]=std::polar(1.f,-6.283185307179586f*k/N);
        for(unsigned i=1,j=0;i<N;++i){
            unsigned bit=N>>1;
            for(;j&bit;bit>>=1)j^=bit;
            j^=bit;reverse[i]=j;
        }
        const auto count=(ir.size()+B-1)/B;
        h.resize(count);history.resize(count);
        for(size_t p=0;p<count;++p){
            Spectrum a{};
            for(unsigned i=0;i<B && p*B+i<ir.size();++i){
                if(!std::isfinite(ir[p*B+i]))throw std::runtime_error("Nonfinite IR");
                a[i]=ir[p*B+i];
            }
            fft(a,false);pack(a,h[p]);
        }
    }
    void process(const float* in,float* out) {
        Spectrum a{};
        for(unsigned i=0;i<B;++i)a[i]=in[i];
        fft(a,false);pack(a,history[head]);
        Half y{};
        size_t j=head;
        for(size_t p=0;p<h.size();++p){
            const auto& x=history[j];const auto& w=h[p];
            for(unsigned k=0;k<K;++k){
                y.re[k]+=x.re[k]*w.re[k]-x.im[k]*w.im[k];
                y.im[k]+=x.re[k]*w.im[k]+x.im[k]*w.re[k];
            }
            j=j?j-1:h.size()-1;
        }
        for(unsigned k=0;k<=B;++k)a[k]=C(y.re[k],y.im[k]);
        for(unsigned k=1;k<B;++k)a[N-k]=std::conj(a[k]);
        fft(a,true);
        for(unsigned i=0;i<B;++i){out[i]=a[i].real()+tail[i];tail[i]=a[i+B].real();}
        head=(head+1)%h.size();
    }
private:
    struct alignas(32) Half { std::array<float,K> re{},im{}; };
    std::array<C,N/2> twiddle{};
    std::array<unsigned,N> reverse{};
    std::vector<Half> h,history;
    std::array<float,B> tail{};
    size_t head=0;
    static void pack(const Spectrum& a,Half& b){
        for(unsigned k=0;k<=B;++k){b.re[k]=a[k].real();b.im[k]=a[k].imag();}
    }
    void fft(Spectrum& a,bool inverse) const {
        for(unsigned i=1;i<N;++i)if(i<reverse[i])std::swap(a[i],a[reverse[i]]);
        for(unsigned len=2;len<=N;len*=2){
            for(unsigned i=0;i<N;i+=len)
                for(unsigned j=0;j<len/2;++j){
                    C w=twiddle[j*N/len];if(inverse)w=std::conj(w);
                    C u=a[i+j],v=a[i+j+len/2]*w;
                    a[i+j]=u+v;a[i+j+len/2]=u-v;
                }
        }
        if(inverse)for(auto& v:a)v/=float(N);
    }
};
