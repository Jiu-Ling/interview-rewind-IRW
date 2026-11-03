"""Validate XML, publish sequentially with checkpoints, then verify the content."""
import argparse
import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from common import cli, load_run, save_json, write_stage

def xml_root(content):
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper() or content.lstrip().startswith("<?xml"):
        raise ValueError("使用飞书 XML 片段，不使用 XML 声明或 DTD")
    return ET.fromstring("<root>"+content+"</root>")

def text_of(node):
    return "".join(node.itertext()).strip()

def normalized(text):
    return "".join(text.split())

def inspect_xml(path, kind, allow_sections=False):
    content=Path(path).read_text(encoding="utf-8-sig")
    root=xml_root(content)
    titles=list(root.iter("title"))
    if len(titles)!=1 or not len(root) or root[0].tag!="title" or not text_of(titles[0]):
        raise ValueError("文档必须以唯一非空 title 开头")
    questions=[]
    if kind=="review" and len(root)<2:
        raise ValueError("复盘正文不能为空")
    if kind=="questions" and not allow_sections:
        if [node.tag for node in root]!=["title","ol"]:
            raise ValueError("问题文档应为 title 加单个 ol；自定义分节用 --allow-question-sections")
        if root[1].attrib.get("seq","auto") not in {"auto","1"}:
            raise ValueError("问题序号应从 1 开始")
        questions=[text_of(item) for item in root[1] if item.tag=="li"]
        if not questions or any(not text for text in questions) or root[1].find(".//ol") is not None or root[1].find(".//ul") is not None:
            raise ValueError("问题列表必须包含非空、连续编号的 li")
    for block in root.iter("pre"):
        if block.find("code") is None:
            raise ValueError("pre 需要 code 子元素")
    return {"title":text_of(titles[0]),"questions":questions,"question_count":len(questions),
        "code_count":len(list(root.iter("pre"))),"image_count":len(list(root.iter("img"))),
        "code_texts":[text_of(block) for block in root.iter("pre")],
        "body_texts":[text_of(block) for block in root if block.tag not in {"title","img"} and text_of(block)],
        "sha256":hashlib.sha256(content.encode("utf-8")).hexdigest()}

def verify_content(expected, content):
    root=xml_root(content)
    titles=list(root.iter("title"))
    issues=[]
    if len(titles)!=1 or normalized(text_of(titles[0]))!=normalized(expected["title"]):
        issues.append("title")
    if len(list(root.iter("pre")))!=expected["code_count"]:
        issues.append("code_count")
    if len(list(root.iter("img")))<expected["image_count"]:
        issues.append("image_count")
    actual_text=normalized(text_of(root))
    for value in expected["code_texts"]+expected["questions"]+expected["body_texts"]:
        if normalized(value) not in actual_text:
            issues.append("content_missing")
            break
    if expected["questions"]:
        items=[text_of(item) for item in root.iter("li")]
        if len(items)!=expected["question_count"]:
            issues.append("question_count")
    return {"passed":not issues,"issues":issues,"question_count":expected["question_count"],
        "code_count":expected["code_count"],"image_count":expected["image_count"]}

def publish(manifest,state,review,questions,cwd,parent=None,execute=False,allow_sections=False,runner=cli):
    cwd=Path(cwd).resolve()
    files={"review":Path(review).resolve(strict=True),"questions":Path(questions).resolve(strict=True)}
    specs={kind:inspect_xml(path,kind,allow_sections) for kind,path in files.items()}
    existing_parent=state.get("document_parent")
    parent=parent or existing_parent or state["settings"]["documents"].get("parent_token")
    if existing_parent and parent!=existing_parent:
        raise ValueError("续跑文档的目标位置已固定；移动既有文档需单独执行")
    for kind,path in files.items():
        if not path.is_relative_to(cwd):
            raise ValueError("草稿需位于 --cwd 之下，避免 CLI 文件参数越界")
        existing=state["documents"].get(kind,{})
        if existing and existing.get("sha256")!=specs[kind]["sha256"]:
            raise ValueError(f"{kind} 已创建且草稿内容发生变化，请更新既有文档而非再次创建")
        if not existing:
            if not (path.parent/".presentation-decision.json").is_file():
                raise ValueError("先执行 docs +script init-draft，再在返回路径编写草稿")
            relative="@./"+path.relative_to(cwd).as_posix()
            assessment=runner(["docs","+script","--command","parse","--content",relative,"--as","user","--format","json"],cwd=cwd)
            if assessment["data"].get("assessment",{}).get("status")!="passed":
                raise ValueError(f"{kind} parse 未通过：{json.dumps(assessment['data'],ensure_ascii=False)}")
    if not execute:
        return {"plan":"create review -> create questions -> fetch both","parent_token":parent,"documents":specs}
    state["document_parent"]=parent
    save_json(manifest,state)
    for kind,path in files.items():
        existing=state["documents"].get(kind)
        if not existing:
            relative="@./"+path.relative_to(cwd).as_posix()
            stage_name="create_"+kind
            prior=state["stages"].get(stage_name,{})
            if prior.get("input_sha256") and prior["input_sha256"]!=specs[kind]["sha256"]:
                raise ValueError("上次创建请求绑定的草稿已变化；核验已有文档并原地更新")
            state["stages"].setdefault(stage_name,{})["input_sha256"]=specs[kind]["sha256"]
            if prior.get("status")=="complete":
                data=prior["response"]
            else:
                args=["docs","+create","--doc-format","xml","--content",relative,"--as","user","--format","json"]
                if parent:
                    args += ["--parent-token",parent]
                data=write_stage(manifest,state,stage_name,lambda:runner(args,cwd=cwd))["data"]
            doc=data.get("document",{})
            if not doc.get("document_id"):
                raise ValueError(f"{kind} 创建响应已保存，请核验并补录 document_id")
            existing={"document_id":doc["document_id"],"url":doc.get("url"),"sha256":specs[kind]["sha256"],
                "warnings":data.get("warnings",[]),"tips":data.get("tips","")}
            state["documents"][kind]=existing
            save_json(manifest,state)
        snapshot=manifest.parent/"documents"
        snapshot.mkdir(exist_ok=True)
        snapshot_path=snapshot/f"{kind}.xml"
        if path!=snapshot_path:
            shutil.copy2(path,snapshot_path)
    results={}
    for kind,record in state["documents"].items():
        response=runner(["docs","+fetch","--doc",record["document_id"],"--doc-format","xml","--detail","simple","--as","user","--format","json"],cwd=cwd)
        save_json(manifest.parent/"documents"/f"{kind}-fetch.json",response)
        verification=verify_content(specs[kind],response["data"]["document"]["content"])
        record["verification"]=verification
        save_json(manifest,state)
        results[kind]={"url":record.get("url"),"document_id":record["document_id"],"verification":verification,"warnings":record.get("warnings",[])}
        if not verification["passed"]:
            raise ValueError(f"{kind} 回查不符：{verification['issues']}；修复已有文档后继续回查")
    return results

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",required=True)
    parser.add_argument("--review",required=True)
    parser.add_argument("--questions",required=True)
    parser.add_argument("--cwd",type=Path,default=Path.cwd())
    parser.add_argument("--parent-token")
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--allow-question-sections",action="store_true")
    args=parser.parse_args()
    manifest,state=load_run(args.run)
    print(json.dumps(publish(manifest,state,args.review,args.questions,args.cwd,args.parent_token,args.execute,args.allow_question_sections),ensure_ascii=False))

if __name__=="__main__":
    main()
