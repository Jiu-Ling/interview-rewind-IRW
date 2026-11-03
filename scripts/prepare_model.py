"""Resolve cached CTranslate2 models; downloads require an explicit flag."""
import argparse
import json
from pathlib import Path
from common import PREFERENCES, load_json

def resolve_model(model, download=False, cache_dir=None):
    from faster_whisper.utils import download_model
    path = Path(model).expanduser()
    if path.is_dir():
        result = path.resolve()
    else:
        result = Path(download_model(model, cache_dir=cache_dir, local_files_only=not download))
    if not (result / "model.bin").is_file() or not (result / "config.json").is_file():
        raise ValueError("模型目录需要 CTranslate2 model.bin 与 config.json")
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=load_json(PREFERENCES)["local"]["model"])
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--cache-dir")
    args = parser.parse_args()
    try:
        path = resolve_model(args.model, args.download, args.cache_dir)
    except Exception as error:
        parser.exit(2, f"模型准备失败：{error}\n确认网络与磁盘后用 --download 准备，或传入已有模型目录。\n")
    print(json.dumps({"model":args.model,"model_path":str(path),"ready":True},ensure_ascii=False))

if __name__ == "__main__":
    main()
