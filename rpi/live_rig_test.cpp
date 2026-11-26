#include "live_rig.h"
#include <iostream>
#include <stdexcept>
#include <cstring>

struct FakeRig {
    int value;
    std::thread::id audio;
    std::atomic<int>* destroyed;
    ~FakeRig(){if(std::this_thread::get_id()!=audio)++*destroyed;}
};
int main(){
    using namespace std::chrono_literals;
    int req[2],ack[2];if(pipe(req)||pipe(ack))return 1;
    const auto audio=std::this_thread::get_id();std::atomic<int> destroyed{0};
    auto current=std::unique_ptr<FakeRig>(new FakeRig{0,audio,&destroyed});
    LiveRigLoader<FakeRig> loader(req[0],ack[1],[&](const std::string& s){
        if(std::this_thread::get_id()==audio)throw std::runtime_error("built on audio thread");
        if(s=="bad")throw std::runtime_error("invalid model");
        return std::unique_ptr<FakeRig>(new FakeRig{std::stoi(s),audio,&destroyed});
    });
    auto send=[&](const char* s){if(write(req[1],s,std::strlen(s))!=static_cast<ssize_t>(std::strlen(s)))throw std::runtime_error("write failed");};
    auto receive=[&](){pollfd p{ack[0],POLLIN,0};if(poll(&p,1,2000)<=0)throw std::runtime_error("ack timed out");char buf[1024];auto n=read(ack[0],buf,sizeof(buf));if(n<=0)throw std::runtime_error("ack failed");return std::string(buf,n);};
    send("bad\n");if(receive()!="ERR invalid model\n"||loader.take()!=nullptr||current->value!=0)return 2;
    for(int i=1;i<=20;++i){
        auto msg=std::to_string(i)+"\n";send(msg.c_str());
        FakeRig* replacement=nullptr;auto deadline=std::chrono::steady_clock::now()+2s;
        while(!(replacement=loader.take())){if(std::chrono::steady_clock::now()>=deadline)return 3;std::this_thread::sleep_for(1ms);}
        if(replacement->value!=i||current->value!=i-1)return 4;
        auto* old=current.release();current.reset(replacement);loader.retire(old);
        if(receive()!="OK\n"||destroyed.load()!=i)return 5;
    }
    close(req[1]);close(ack[0]);std::cout<<"20 hot exchanges and invalid-rig retention PASS\n";
}
