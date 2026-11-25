#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <stdexcept>
#include <vector>

// Uniform partitioned overlap-add, one 64-frame input block -> one output block.
// No extra block delay beyond the existing audio callback. No allocation in process.
class CabinetConvolver {
public:
    static constexpr unsigned B=64, N=2*B;
    using C=std::complex<float>;
    using Spectrum=std::array<C,N>;
    explicit CabinetConvolver(const std::vector<float>& ir) {
        if(ir.empty() || ir.size()>48000) throw std::runtime_error("IR must contain 1..48000 samples at 48 kHz");
        for(unsigned k=0;k<N/2;++k) twiddle[k]=std::polar(1.f,-6.283185307179586f*k/N);
        const auto count=(ir.size()+B-1)/B;
        h.resize(count);history.resize(count);
        for(size_t p=0;p<count;++p){
            h[p].fill(C{});history[p].fill(C{});
            for(unsigned i=0;i<B && p*B+i<ir.size();++i){
                if(!std::isfinite(ir[p*B+i]))throw std::runtime_error("Nonfinite IR");
                h[p][i]=ir[p*B+i];
            }
            fft(h[p],false);
        }
    }
    void process(const float* in,float* out) {
        auto& x=history[head];x.fill(C{});
        for(unsigned i=0;i<B;++i)x[i]=in[i];
        fft(x,false);
        Spectrum y{};
        size_t j=head;
        // Real input: accumulate only nonnegative frequencies.
        for(size_t p=0;p<h.size();++p){
            for(unsigned k=0;k<=B;++k)y[k]+=history[j][k]*h[p][k];
            j=j?j-1:h.size()-1;
        }
        for(unsigned k=1;k<B;++k)y[N-k]=std::conj(y[k]);
        fft(y,true);
        for(unsigned i=0;i<B;++i){out[i]=y[i].real()+tail[i];tail[i]=y[i+B].real();}
        head=(head+1)%h.size();
    }
private:
    std::array<C,N/2> twiddle{};
    std::vector<Spectrum> h,history;
    std::array<float,B> tail{};
    size_t head=0;
    void fft(Spectrum& a,bool inverse) const {
        for(unsigned i=1,j=0;i<N;++i){
            unsigned bit=N>>1;
            for(;j&bit;bit>>=1)j^=bit;
            j^=bit;
            if(i<j)std::swap(a[i],a[j]);
        }
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
