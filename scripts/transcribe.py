"""Offline ASR, timestamped outputs and independent clip rechecks."""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import argparse
import json
from pathlib import Path
from common import load_run, save_json
from prepare_model import resolve_model

def stamp(seconds):
    milliseconds = round(seconds * 1000)
    return f"{milliseconds//3600000:02d}:{milliseconds//60000%60:02d}:{milliseconds//1000%60:02d}.{milliseconds%1000:03d}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--model")
    parser.add_argument("--device", choices=["cpu","cuda"])
    parser.add_argument("--compute-type")
    parser.add_argument("--clip", nargs=2, type=float, metavar=("START","END"))
    parser.add_argument("--prompt", default="")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest, state = load_run(args.run)
    if state["mode"] != "local":
        parser.error("此脚本用于本地模式；临时复核请建立 mode=local 的独立运行目录")
    if args.clip and not 0 <= args.clip[0] < args.clip[1]:
        parser.error("clip 必须满足 0 <= START < END")
    settings = state["settings"]["local"]
    model_path = resolve_model(args.model or settings["model"])
    tag = "transcript" if not args.clip else f"clip-{args.clip[0]:.3f}-{args.clip[1]:.3f}"
    directory = manifest.parent / "transcripts"
    directory.mkdir(exist_ok=True)
    paths = {suffix:directory / f"{tag}.{suffix}" for suffix in ["json","jsonl","txt"]}
    if not args.overwrite and any(path.exists() for path in paths.values()):
        parser.error("转写文件已存在；先读取现有结果，需要覆盖时显式 --overwrite")
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_path), device=args.device or settings["device"],
        compute_type=args.compute_type or settings["compute_type"],
        cpu_threads=settings["cpu_threads"], local_files_only=True)
    options = {"language":settings["language"],"beam_size":settings["beam_size"],
        "vad_filter":True,"initial_prompt":args.prompt or None,"word_timestamps":True}
    audio_source = state["source"]["path"]
    offset = 0
    if args.clip:
        # Clip timestamps disable VAD in faster-whisper. Extract PCM instead,
        # so silence filtering remains enabled and the original timeline is explicit.
        from media import audio_pcm, probe
        duration = probe(audio_source)["duration"]
        if duration is not None and args.clip[1] > duration+0.05:
            parser.error("clip 结束时间超过源文件时长")
        media_directory = manifest.parent/"media"
        media_directory.mkdir(exist_ok=True)
        clipped = media_directory/f"{tag}.wav"
        if not clipped.exists() or args.overwrite:
            audio_pcm(audio_source,clipped,*args.clip)
        audio_source = str(clipped)
        offset = args.clip[0]
    state["stages"][tag] = {"status":"running","model_path":str(model_path)}
    save_json(manifest, state)
    segments, info = model.transcribe(audio_source, **options)
    rows = []
    with paths["jsonl"].open("w", encoding="utf-8") as lines, paths["txt"].open("w",encoding="utf-8") as plain:
        for segment in segments:
            row = {"id":segment.id,"start":segment.start+offset,"end":segment.end+offset,
                "text":segment.text.strip(),"avg_logprob":segment.avg_logprob,
                "no_speech_prob":segment.no_speech_prob,
                "words":[{"start":word.start+offset,"end":word.end+offset,"word":word.word,"probability":word.probability}
                    for word in segment.words or []]}
            probabilities=[word["probability"] for word in row["words"]]
            row["review_hint"]="核验识别文字" if probabilities and sum(probabilities)/len(probabilities)<0.35 else None
            rows.append(row)
            lines.write(json.dumps(row,ensure_ascii=False)+"\n")
            lines.flush()
            plain.write(f"[{stamp(row['start'])} --> {stamp(row['end'])}] {row['text']}\n")
            plain.flush()
            print(json.dumps({"progress_seconds":row["end"],"text":row["text"]},ensure_ascii=False),flush=True)
    result = {"source":state["source"],"model_path":str(model_path),"language":info.language,
        "duration":info.duration,"clip":args.clip,"timeline_offset":offset,"initial_prompt":args.prompt,"segments":rows}
    save_json(paths["json"], result)
    state["stages"][tag].update({"status":"complete","files":{key:str(value) for key,value in paths.items()},"segment_count":len(rows)})
    save_json(manifest,state)
    print(json.dumps({"complete":True,"files":{key:str(value) for key,value in paths.items()}},ensure_ascii=False))

if __name__ == "__main__":
    main()
