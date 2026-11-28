#pragma once
#include <juce_audio_formats/juce_audio_formats.h>
#include <mutex>
#include <cmath>
#include <nlohmann/json.hpp>
namespace ton3k {
class PracticePlayer {
    using Json=nlohmann::json;
    std::mutex mutex;
    juce::AudioBuffer<float> pcm;
    juce::String loaded;
    double rate=0, cursor=0, end=0;
    float volume=.5f;
    bool playing=false;
    juce::AudioFormatManager formats;
public:
    PracticePlayer(){formats.registerBasicFormats();}
    static juce::File root(bool score=false){
        return juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
            .getChildFile("TinkerNet").getChildFile("TON3K").getChildFile(score?"practice-scores":"practice-tracks");
    }
    static juce::File file(juce::String name,bool score=false){
        if(name.isEmpty()||name=="."||name==".."||name.containsAnyOf("/\\")||name.startsWithChar('.'))throw std::runtime_error("Invalid file name");
        auto f=root(score).getChildFile(name);
        if(!f.existsAsFile()||f.isSymbolicLink())throw std::runtime_error("File unavailable");
        return f;
    }
    static juce::String import(const juce::File& source,bool score=false){
        if(!source.existsAsFile()||source.isSymbolicLink()||!source.hasFileExtension(score?"gp;gp3;gp4;gp5;gpx":"wav;flac;mp3;aif;aiff;ogg")||source.getSize()<=0||source.getSize()>(score?64LL:128LL)*1024*1024)throw std::runtime_error("Unsupported file or size");
        auto dir=root(score);if(dir.createDirectory().failed())throw std::runtime_error("Cannot create library");
        auto dest=dir.getNonexistentChildFile(source.getFileNameWithoutExtension(),source.getFileExtension(),false);
        if(!source.copyFileTo(dest))throw std::runtime_error("Cannot copy file");
        return dest.getFileName();
    }
    static Json list(bool score=false){
        Json files=Json::array();
        for(auto& f:root(score).findChildFiles(juce::File::findFiles,false,"*"))
            if(!f.isSymbolicLink()&&f.hasFileExtension(score?"gp;gp3;gp4;gp5;gpx":"wav;flac;mp3;aif;aiff;ogg"))files.push_back(f.getFileName().toStdString());
        std::sort(files.begin(),files.end());return Json{{"files",files}};
    }
    void stop(){std::lock_guard<std::mutex> guard(mutex);playing=false;}
    Json waveform(const juce::String& name){
        // Decode outside the callback; cap decoded stereo memory at 128 MiB.
        std::unique_ptr<juce::AudioFormatReader> reader(formats.createReaderFor(file(name)));
        if(!reader||reader->lengthInSamples<=0||reader->lengthInSamples>16777216||!std::isfinite(reader->sampleRate)||reader->sampleRate<=0)throw std::runtime_error("Unsupported audio or decoded track exceeds 128 MiB");
        int n=int(reader->lengthInSamples),channels=reader->numChannels>1?2:1;
        juce::AudioBuffer<float> next(channels,n);
        if(!reader->read(&next,0,n,0,true,channels>1))throw std::runtime_error("Cannot decode audio");
        Json peaks=Json::array();
        for(int i=0;i<1200;++i){int a=int(int64_t(i)*n/1200),z=int(int64_t(i+1)*n/1200);float peak=0;for(int ch=0;ch<channels;++ch)for(int j=a;j<z;++j)peak=std::max(peak,std::abs(next.getSample(ch,j)));peaks.push_back(std::isfinite(peak)?peak:0);}
        double duration=n/reader->sampleRate;
        {std::lock_guard<std::mutex> guard(mutex);playing=false;pcm=std::move(next);rate=reader->sampleRate;loaded=name;cursor=end=0;}
        return Json{{"duration",duration},{"peaks",peaks}};
    }
    Json status(){std::lock_guard<std::mutex> guard(mutex);return Json{{"playing",playing},{"position",rate>0?cursor/rate:0}};}
    Json transport(const Json& j){
        if(j.at("action")=="stop"){stop();return status();}
        if(j.at("action")!="play")throw std::runtime_error("Invalid transport");
        auto name=juce::String(j.at("name").get<std::string>());
        bool needsLoad;{std::lock_guard<std::mutex> guard(mutex);needsLoad=loaded!=name;}
        if(needsLoad)waveform(name);
        std::lock_guard<std::mutex> guard(mutex);
        double a=j.at("anchor"),z=j.at("end"),s=j.at("speed"),p=j.at("pitch"),v=j.at("volume");
        if(!std::isfinite(a)||!std::isfinite(z)||!std::isfinite(v)||s!=1||p!=0||a<0||z<=a||v<0||v>1)throw std::runtime_error("Native playback supports normal speed and pitch in this preview");
        cursor=std::clamp(a*rate,0.,double(pcm.getNumSamples()));end=std::clamp(z*rate,cursor,double(pcm.getNumSamples()));volume=float(v);playing=cursor<end;
        return Json{{"playing",playing},{"position",cursor/rate}};
    }
    void mix(juce::AudioBuffer<float>& out,int outputs,double hostRate) noexcept {
        // Never wait for the UI or allocate in the audio callback.
        std::unique_lock<std::mutex> guard(mutex,std::try_to_lock);
        if(!guard.owns_lock()||!playing||hostRate<=0)return;
        double step=rate/hostRate;
        for(int i=0;i<out.getNumSamples();++i){
            if(cursor>=end||cursor>=pcm.getNumSamples()){playing=false;break;}
            int a=int(cursor),b=std::min(a+1,pcm.getNumSamples()-1);float f=float(cursor-a);
            for(int ch=0;ch<outputs;++ch){int c=std::min(ch,pcm.getNumChannels()-1);float x=pcm.getSample(c,a),y=pcm.getSample(c,b);float value=(x+(y-x)*f)*volume;if(std::isfinite(value))out.setSample(ch,i,out.getSample(ch,i)+value);}
            cursor+=step;
        }
    }
};
}
