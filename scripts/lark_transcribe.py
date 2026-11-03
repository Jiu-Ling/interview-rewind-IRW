"""Checkpointed upload -> Minutes -> full transcript; plan by default."""
import argparse
import json
import os
from pathlib import Path
from common import cli, load_run, save_json, write_stage

def process(manifest,state,execute=False,runner=cli):
    if state["mode"] != "lark":
        raise ValueError("运行记录的模式必须为 lark")
    source = Path(state["source"]["path"])
    from media import probe
    metadata = probe(source)
    if state["source"]["size"] > 6*1024**3 or (metadata["duration"] or 0) > 6*3600:
        raise ValueError("妙记文件超过 6 GB 或 6 小时；先明确拆分方案")
    allowed = {".wav",".mp3",".m4a",".aac",".ogg",".wma",".amr",".avi",".wmv",".mov",".mp4",".m4v",".mpeg",".flv"}
    if source.suffix.lower() not in allowed:
        raise ValueError("妙记不支持此扩展名；先用 media.py audio 提取支持格式，再为该文件建立运行记录")
    if not execute:
        return {"plan":["drive +upload","minutes +upload","minutes +detail --wait-ready --transcript"],"source":str(source),"stages":state["stages"]}
    def stage(name,args,cwd=None):
        prior = state["stages"].get(name,{})
        if prior.get("status") == "complete":
            return prior["response"]
        return write_stage(manifest,state,name,lambda:runner(args+["--as","user","--format","json"],cwd=cwd or manifest.parent))["data"]
    uploaded = stage("drive_upload",["drive","+upload","--file","./"+source.name],cwd=source.parent)
    token = uploaded.get("file_token")
    if not token:
        raise ValueError("上传已返回，请核验 drive_upload.response 并补录 file_token；不重新上传")
    minute = stage("minutes_upload",["minutes","+upload","--file-token",token])
    minute_token = minute.get("minute_token")
    if not minute_token:
        from urllib.parse import urlparse
        parsed = urlparse(minute.get("minute_url",""))
        parts = parsed.path.strip("/").split("/")
        if len(parts)==2 and parts[0]=="minutes":
            minute_token=parts[1]
    if not minute_token:
        raise ValueError("妙记已生成，请核验 minutes_upload.response 并补录 minute_token")
    previous = state["stages"].get("lark_transcript",{})
    if previous.get("status")=="complete" and Path(previous.get("file","")).is_file():
        return previous
    output = manifest.parent/"transcripts"/"lark"
    output.mkdir(parents=True,exist_ok=True)
    relative = "./"+os.path.relpath(output,manifest.parent).replace(os.sep,"/")
    response = runner(["minutes","+detail","--minute-tokens",minute_token,"--wait-ready","--transcript",
        "--output-dir",relative,"--overwrite","--as","user","--format","json"],cwd=manifest.parent)
    save_json(manifest.parent/"minutes-detail.json",response)
    minutes = response["data"].get("minutes",[])
    matches = [item for item in minutes if item.get("minute_token")==minute_token]
    if len(matches)!=1:
        raise ValueError("妙记详情缺少对应逐字稿，读取 minutes-detail.json 后按 token 续查")
    filename = matches[0].get("artifacts",{}).get("transcript_file")
    if not filename:
        raise ValueError("逐字稿尚未返回；沿用已有 minute_token 继续查询")
    path = Path(filename)
    if not path.is_absolute():
        path=manifest.parent/path
    path=path.resolve()
    if not path.is_relative_to(output.resolve()) or not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
        raise ValueError("逐字稿路径、文件或内容未通过检查；核验详情响应")
    record={"status":"complete","file":str(path),"minute_token":minute_token,"minute_url":minute.get("minute_url")}
    state["stages"]["lark_transcript"]=record
    save_json(manifest,state)
    return record

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    manifest,state=load_run(args.run)
    print(json.dumps(process(manifest,state,args.execute),ensure_ascii=False))

if __name__=="__main__":
    main()
