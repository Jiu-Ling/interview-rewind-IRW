"""Media probe, evidence frames and mono PCM extraction. Originals stay intact."""
import argparse
import json
import shutil
import subprocess
import wave
from pathlib import Path
from common import load_run, save_json

def probe(source):
    import av
    with av.open(str(source)) as container:
        return {"duration":container.duration / av.time_base if container.duration else None,
            "streams":[{"type":stream.type,"codec":stream.codec_context.name,
                "width":getattr(stream.codec_context,"width",None),"height":getattr(stream.codec_context,"height",None),
                "sample_rate":getattr(stream.codec_context,"sample_rate",None)} for stream in container.streams]}

def frame_at(source, seconds, target, backend="pyav"):
    actual = seconds
    if backend == "pyav":
        import av
        with av.open(str(source)) as container:
            if not container.streams.video:
                raise ValueError("输入没有视频流")
            stream = container.streams.video[0]
            container.seek(int(seconds / stream.time_base), stream=stream, backward=True)
            found = None
            for frame in container.decode(stream):
                if frame.time is not None and frame.time + 0.001 >= seconds:
                    found, actual = frame, frame.time
                    break
            if found is None:
                raise ValueError(f"{seconds} 秒处没有可解码帧")
            found.to_image().save(target)
    elif backend == "opencv":
        import cv2
        cap = cv2.VideoCapture(str(source))
        try:
            if not cap.isOpened():
                raise ValueError("OpenCV 无法打开视频")
            cap.set(cv2.CAP_PROP_POS_MSEC,seconds*1000)
            success, pixels = cap.read()
            if not success:
                raise ValueError(f"{seconds} 秒处没有可解码帧")
            actual = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not cv2.imwrite(str(target),pixels):
                raise ValueError("OpenCV 写图失败")
        finally:
            cap.release()
    else:
        binary = shutil.which("ffmpeg")
        if not binary:
            raise FileNotFoundError("请安装 FFmpeg 并加入 PATH，或选择 pyav/opencv")
        subprocess.run([binary,"-hide_banner","-loglevel","error","-n","-ss",str(seconds),"-i",str(source),"-frames:v","1",str(target)],check=True,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if not target.is_file():
            raise ValueError("FFmpeg 没有生成帧，请检查时间点")
        actual = None
    return {"requested_seconds":seconds,"actual_seconds":actual,"path":str(target),"backend":backend}

def audio_pcm(source, target, start=0, end=None, backend="pyav"):
    if end is not None and not 0 <= start < end:
        raise ValueError("音频区间必须满足 0 <= start < end")
    if start < 0:
        raise ValueError("start 不能为负数")
    if backend == "ffmpeg":
        binary = shutil.which("ffmpeg")
        if not binary:
            raise FileNotFoundError("FFmpeg 不在 PATH")
        args = [binary,"-hide_banner","-loglevel","error","-n","-ss",str(start),"-i",str(source)]
        if end is not None:
            args += ["-t",str(end-start)]
        subprocess.run(args+["-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(target)],check=True,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    else:
        import av
        with av.open(str(source)) as container, wave.open(str(target),"wb") as output:
            if not container.streams.audio:
                raise ValueError("输入没有音频流")
            stream = container.streams.audio[0]
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            resampler = av.AudioResampler(format="s16",layout="mono",rate=16000)
            if start:
                container.seek(int(max(0,start-1)/stream.time_base),stream=stream,backward=True)
            def write_frame(frame):
                timestamp = float(frame.pts*frame.time_base) if frame.pts is not None else None
                if timestamp is None:
                    raise ValueError("音频缺少时间戳，改用 FFmpeg 后端")
                left = max(0,round((start-timestamp)*16000))
                right = frame.samples if end is None else min(frame.samples,round((end-timestamp)*16000))
                if left < right:
                    output.writeframes(frame.to_ndarray().tobytes()[left*2:right*2])
            for frame in container.decode(stream):
                if end is not None and frame.time is not None and frame.time > end+1:
                    break
                for converted in resampler.resample(frame):
                    write_frame(converted)
            for converted in resampler.resample(None):
                write_frame(converted)
    with wave.open(str(target),"rb") as result:
        duration = result.getnframes()/result.getframerate()
    if duration <= 0:
        raise ValueError("提取音频为空")
    return {"path":str(target),"duration":duration,"source_start":start,"source_end":end}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run",required=True)
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("probe")
    frames = sub.add_parser("frames")
    frames.add_argument("--at",nargs="+",type=float,required=True)
    frames.add_argument("--backend",choices=["pyav","opencv","ffmpeg"],default="pyav")
    audio = sub.add_parser("audio")
    audio.add_argument("--start",type=float,default=0)
    audio.add_argument("--end",type=float)
    audio.add_argument("--name",default="audio.wav")
    audio.add_argument("--backend",choices=["pyav","ffmpeg"],default="pyav")
    args = parser.parse_args()
    manifest,state = load_run(args.run)
    source = Path(state["source"]["path"])
    if args.command == "probe":
        result = probe(source)
    elif args.command == "frames":
        directory = manifest.parent/"frames"
        directory.mkdir(exist_ok=True)
        result = []
        for seconds in args.at:
            if seconds < 0:
                parser.error("抽帧时间不能为负数")
            target = directory/f"frame-{seconds:012.3f}-{args.backend}.png"
            if target.exists():
                parser.error(f"截图已存在，请读取现有图片：{target}")
            result.append(frame_at(source,seconds,target,args.backend))
        state.setdefault("frames",[]).extend(result)
        save_json(manifest,state)
    else:
        if Path(args.name).name != args.name or Path(args.name).suffix.lower() != ".wav":
            parser.error("name 必须为单个 .wav 文件名")
        directory = manifest.parent/"media"
        directory.mkdir(exist_ok=True)
        target = directory/args.name
        if target.exists():
            parser.error(f"音频已存在，请选择另一个文件名：{target}")
        result = audio_pcm(source,target,args.start,args.end,args.backend)
        state.setdefault("media",[]).append(result)
        save_json(manifest,state)
    print(json.dumps(result,ensure_ascii=False))

if __name__ == "__main__":
    main()
