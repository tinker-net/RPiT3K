#pragma once
#include <cmath>
#include <algorithm>

// Experimental passive-pickup load compensation. R + L source, shunt
// capacitance C and volume pot Rv. Htarget/Hsource is a stable biquad.
// Values are illustrative, not measurements of a particular guitar.
class HiZCompensation {
    struct Filter { double b0,b1,b2,a1,a2,z1=0,z2=0;
        float process(float x){double y=b0*x+z1;z1=b1*x-a1*y+z2;z2=b2*x-a2*y;return float(y);}
    };
    static Filter design(double R,double L,double C,double Rv){
        const double gs=1./100000+1./Rv,gt=1./1000000+1./Rv,k=96000.;
        // D(s)=1+R*G+(L*G+R*C)*s+L*C*s*s.
        auto polynomial=[&](double G,double* p){
            double a=1+R*G,b=(L*G+R*C)*k,c=L*C*k*k;
            p[0]=a+b+c;p[1]=2*(a-c);p[2]=a-b+c;
        };
        double n[3],d[3];polynomial(gs,n);polynomial(gt,d);
        return {n[0]/d[0],n[1]/d[0],n[2]/d[0],d[1]/d[0],d[2]/d[0]};
    }
    Filter filters[4]={design(8000,3.5,470e-12,250000),design(6000,2.4,470e-12,250000),design(8000,4.5,470e-12,500000),design(8500,5.5,470e-12,500000)};
    float weights[4]{},targets[4]{};
public:
    void set(float amount,int profile){
        if(!std::isfinite(amount)||amount<0||amount>1||profile<0||profile>3)return;
        for(int i=0;i<4;++i)targets[i]=i==profile?amount:0;
    }
    float process(float x){
        float y=x;
        for(int i=0;i<4;++i){
            auto& w=weights[i];w+=.0020811647f*(targets[i]-w);
            if(std::abs(w-targets[i])<1e-6f)w=targets[i];
            float filtered=filters[i].process(x);
            if(w!=0)y+=w*(filtered-x);
        }
        return y;
    }
};
