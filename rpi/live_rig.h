#pragma once
#include <atomic>
#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <poll.h>
#include <unistd.h>
#include <cerrno>

// One outstanding request at a time. The worker owns construction and destruction;
// the audio thread only exchanges pointers at a block boundary.
template<class Rig> class LiveRigLoader {
    std::atomic<Rig*> ready{nullptr}, retired{nullptr};
    std::atomic<bool> stopping{false};
    int request_fd, ack_fd;
    std::function<std::unique_ptr<Rig>(const std::string&)> build;
    std::thread worker;
    void ack(std::string s) {
        for(auto& c:s)if(c=='\n'||c=='\r')c=' ';
        if(s.size()>1000)s.resize(1000);
        s+='\n';
        const char* p=s.data();size_t n=s.size();
        while(n&&!stopping.load()){
            auto w=::write(ack_fd,p,n);
            if(w<0&&errno==EINTR)continue;
            if(w<=0)break;
            p+=w;n-=static_cast<size_t>(w);
        }
    }
    void handle(const std::string& line) {
        try {
            auto next=build(line);
            if(stopping.load())return;
            ready.store(next.release(),std::memory_order_release);
            while(!stopping.load()){
                if(auto* old=retired.exchange(nullptr,std::memory_order_acq_rel)){
                    delete old;ack("OK");return;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        } catch(const std::exception& e){ack(std::string("ERR ")+e.what());}
        catch(...){ack("ERR Unknown rig loading error");}
    }
    void run(){
        std::string line;bool overflow=false;
        while(!stopping.load()){
            pollfd fd{request_fd,POLLIN,0};
            int rc=::poll(&fd,1,20);
            if(rc<0&&errno==EINTR)continue;
            if(rc<0)break;
            if(!rc)continue;
            if(!(fd.revents&POLLIN))break;
            char buf[1024];auto n=::read(request_fd,buf,sizeof(buf));
            if(n<0&&errno==EINTR)continue;
            if(n<=0)break;
            for(ssize_t i=0;i<n&&!stopping.load();++i){
                if(buf[i]=='\n'){
                    if(overflow)ack("ERR Rig request too large");
                    else handle(line);
                    line.clear();overflow=false;
                }else if(line.size()<32768)line+=buf[i];
                else overflow=true;
            }
        }
    }
public:
    LiveRigLoader(int req,int ack,std::function<std::unique_ptr<Rig>(const std::string&)> fn)
        :request_fd(req),ack_fd(ack),build(std::move(fn)){
        if(req>=0&&ack>=0)worker=std::thread([this]{run();});
    }
    LiveRigLoader(const LiveRigLoader&)=delete;
    LiveRigLoader& operator=(const LiveRigLoader&)=delete;
    Rig* take() noexcept{return ready.exchange(nullptr,std::memory_order_acq_rel);}
    void retire(Rig* old) noexcept{retired.store(old,std::memory_order_release);}
    ~LiveRigLoader(){
        stopping.store(true);
        if(worker.joinable())worker.join();
        delete ready.exchange(nullptr);delete retired.exchange(nullptr);
        if(request_fd>=0)::close(request_fd);
        if(ack_fd>=0)::close(ack_fd);
    }
};
