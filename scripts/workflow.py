import argparse
from datetime import date
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from common import PREFERENCES, load_json, save_json, source_fingerprint

def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(dest="command", required=True)
    actions.add_parser("doctor")
    preferences = actions.add_parser("preferences")
    preferences.add_argument("action", choices=["get","set-mode","reset-mode"])
    preferences.add_argument("mode", choices=["local","lark"], nargs="?")
    preferences.add_argument("--config", type=Path, default=PREFERENCES)
    init = actions.add_parser("init")
    init.add_argument("--video", type=Path, required=True)
    init.add_argument("--company", required=True)
    init.add_argument("--date", required=True)
    init.add_argument("--round", default="")
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--mode", choices=["local","lark"])
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps({"python":sys.version.split()[0],"uv":shutil.which("uv"),
            "lark_cli":shutil.which("lark-cli"),"ffmpeg":shutil.which("ffmpeg"),
            "ffprobe":shutil.which("ffprobe"),"modules":{name:importlib.util.find_spec(name) is not None
                for name in ["av","cv2","PIL","faster_whisper","huggingface_hub"]}},ensure_ascii=False))
    elif args.command == "preferences":
        config = load_json(args.config)
        if args.action == "set-mode":
            if not args.mode:
                parser.error("set-mode 需要 local 或 lark")
            config["transcription_mode"] = args.mode
            save_json(args.config, config)
        elif args.action == "reset-mode":
            config["transcription_mode"] = None
            save_json(args.config, config)
        print(json.dumps({"config":str(args.config.resolve()),"needs_preference":config.get("transcription_mode") is None,"preferences":config},ensure_ascii=False))
    else:
        try:
            if date.fromisoformat(args.date).isoformat()!=args.date:
                raise ValueError("date format")
        except ValueError:
            parser.error("date 必须为 YYYY-MM-DD")
        config = load_json(PREFERENCES)
        mode = args.mode or config.get("transcription_mode")
        if not mode:
            parser.error("首次使用需要询问并保存转写偏好，或明确 --mode")
        source = source_fingerprint(args.video)
        output = args.output.resolve()
        manifest = output / "run.json"
        if manifest.exists():
            prior = load_json(manifest)
            if prior["source"] != source or prior["mode"] != mode or prior["company"] != args.company or prior["date"] != args.date or prior["round"] != args.round:
                parser.error("运行目录属于不同输入/面试，请选择独立目录")
            print(json.dumps({"run":str(manifest),"reused":True},ensure_ascii=False))
            return
        if output.exists() and any(output.iterdir()):
            parser.error("运行目录非空且没有 run.json，请选择独立目录")
        title = " ".join(x for x in [args.date,args.company,args.round] if x)
        state = {"schema_version":1,"source":source,"company":args.company,"date":args.date,
                 "round":args.round,"title_prefix":title,"mode":mode,"settings":config,
                 "stages":{},"documents":{}}
        save_json(manifest, state)
        print(json.dumps({"run":str(manifest),"mode":mode,"title_prefix":title},ensure_ascii=False))

if __name__ == "__main__":
    main()
