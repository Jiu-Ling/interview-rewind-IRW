"""Behavioral tests; cloud operations use mocks and no account credentials."""
import copy
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from common import CliFailure, PREFERENCES, load_json, load_run, save_json, source_fingerprint, write_stage
from media import audio_pcm, frame_at, probe
from lark_transcribe import process
from publish import inspect_xml, publish, verify_content

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="interview-rewind-test-")
        self.root=Path(self.temp.name)
        self.source=self.root/"面试.wav"
        with wave.open(str(self.source),"wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x10\x00"*32000)
        self.manifest=self.root/"run"/"run.json"
        self.state={"mode":"lark","source":source_fingerprint(self.source),"stages":{},"documents":{},"settings":load_json(PREFERENCES)}
        save_json(self.manifest,self.state)
        self.review=self.draft("review",'<title>面试 复盘</title><h1>QA</h1><p>现场回答和评价。</p><pre lang="python"><code>print(1 &lt; 2)</code></pre>')
        self.questions=self.draft("questions",'<title>面试 问题</title><ol seq="auto"><li>问题一？</li><li>问题二？</li></ol>')
        self.calls=[]

    def tearDown(self):
        self.temp.cleanup()

    def draft(self,kind,xml):
        path=self.root/kind/"draft.xml"
        save_json(path.parent/".presentation-decision.json",{"test":True})
        path.write_text(xml,encoding="utf-8")
        return path

    def cloud(self,args,cwd):
        self.calls.append(args)
        command=args[:2]
        if command==["drive","+upload"]:
            self.assertFalse(Path(args[args.index("--file")+1]).is_absolute())
            self.assertEqual(Path(cwd),self.source.parent)
            data={"file_token":"file-test"}
        elif command==["minutes","+upload"]:
            data={"minute_token":"minute-test","minute_url":"https://my.feishu.cn/minutes/minute-test"}
        elif command==["minutes","+detail"]:
            target=self.manifest.parent/"transcripts"/"lark"/"artifact"/"transcript.txt"
            target.parent.mkdir(exist_ok=True)
            target.write_text("面试官：问题。\n候选人：回答。",encoding="utf-8")
            data={"minutes":[{"minute_token":"minute-test","artifacts":{"transcript_file":str(target)}}]}
        elif command==["docs","+script"]:
            data={"assessment":{"status":"passed"}}
        elif command==["docs","+create"]:
            name="review" if "review" in args[args.index("--content")+1] else "questions"
            data={"document":{"document_id":name,"url":"https://my.feishu.cn/docx/"+name}}
        elif command==["docs","+fetch"]:
            name=args[args.index("--doc")+1]
            xml=(self.review if name=="review" else self.questions).read_text(encoding="utf-8")
            data={"document":{"content":xml}}
        else:
            raise AssertionError(args)
        self.assertEqual(args[args.index("--as")+1],"user")
        return {"ok":True,"data":data}

    def test_preferences_roundtrip(self):
        config=self.root/"preferences.json"
        save_json(config,load_json(PREFERENCES))
        script=Path(__file__).with_name("workflow.py")
        result=subprocess.run([sys.executable,str(script),"preferences","set-mode","local","--config",str(config)],capture_output=True,check=True)
        self.assertEqual(load_json(config)["transcription_mode"],"local")
        self.assertFalse(json.loads(result.stdout)["needs_preference"])
        subprocess.run([sys.executable,str(script),"preferences","reset-mode","--config",str(config)],capture_output=True,check=True)
        self.assertIsNone(load_json(config)["transcription_mode"])

    def test_source_change_detected(self):
        self.source.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            load_run(self.manifest)

    def test_write_unknown_stops_retry(self):
        def failed():
            raise CliFailure({"error":"timeout"},unknown=True)
        with self.assertRaises(CliFailure):
            write_stage(self.manifest,self.state,"upload",failed)
        self.assertEqual(load_json(self.manifest)["stages"]["upload"]["status"],"unknown")
        with self.assertRaises(RuntimeError):
            write_stage(self.manifest,self.state,"upload",lambda:self.fail("must not retry"))

    def test_structured_error_requires_reconciliation(self):
        with self.assertRaises(CliFailure):
            write_stage(self.manifest,self.state,"upload",lambda:(_ for _ in ()).throw(CliFailure({"error":"partial failure"})))
        self.assertEqual(self.state["stages"]["upload"]["status"],"unknown")

    def test_probe_and_audio_trim(self):
        self.assertAlmostEqual(probe(self.source)["duration"],2,places=2)
        target=self.root/"clip.wav"
        result=audio_pcm(self.source,target,0.5,1.25)
        self.assertAlmostEqual(result["duration"],0.75,places=3)
        with wave.open(str(target),"rb") as clip:
            self.assertEqual((clip.getnchannels(),clip.getsampwidth(),clip.getframerate()),(1,2,16000))

    def test_media_frames_both_backends(self):
        import av
        import numpy as np
        video=self.root/"video.mp4"
        with av.open(str(video),mode="w") as output:
            stream=output.add_stream("mpeg4",rate=10)
            stream.width=64
            stream.height=48
            stream.pix_fmt="yuv420p"
            for number in range(20):
                pixels=np.full((48,64,3),number*10,dtype=np.uint8)
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format="rgb24")):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
        from PIL import Image
        for backend in ["pyav","opencv"]:
            target=self.root/f"{backend}.png"
            info=frame_at(video,1.1,target,backend)
            with Image.open(target) as screenshot:
                self.assertEqual(screenshot.size,(64,48))
            self.assertAlmostEqual(info["actual_seconds"],1.1,places=2)
            with self.assertRaises(ValueError):
                frame_at(video,8,self.root/f"bad-{backend}.png",backend)

    def test_lark_plan_has_no_cloud_call(self):
        result=process(self.manifest,self.state,runner=lambda *args,**kwargs:self.fail("cloud call"))
        self.assertIn("plan",result)

    def test_lark_upload_then_resume(self):
        first=process(self.manifest,self.state,True,self.cloud)
        self.assertTrue(Path(first["file"]).is_file())
        self.assertEqual(len(self.calls),3)
        process(self.manifest,self.state,True,self.cloud)
        self.assertEqual(len(self.calls),3)

    def test_lark_unknown_never_reuploads(self):
        self.state["stages"]["drive_upload"]={"status":"pending"}
        with self.assertRaises(RuntimeError):
            process(self.manifest,self.state,True,self.cloud)
        self.assertEqual(self.calls,[])

    def test_questions_structure(self):
        spec=inspect_xml(self.questions,"questions")
        self.assertEqual(spec["question_count"],2)
        bad=self.draft("bad",'<title>问题</title><h1>一</h1><ol><li>问题</li></ol>')
        with self.assertRaises(ValueError):
            inspect_xml(bad,"questions")

    def test_publisher_plan_does_not_create(self):
        publish(self.manifest,self.state,self.review,self.questions,self.root,execute=False,runner=self.cloud)
        self.assertEqual([x[:2] for x in self.calls],[["docs","+script"]]*2)
        self.assertEqual(self.state["documents"],{})

    def test_publisher_sequential_create_and_resume(self):
        result=publish(self.manifest,self.state,self.review,self.questions,self.root,parent="parent",execute=True,runner=self.cloud)
        self.assertTrue(all(item["verification"]["passed"] for item in result.values()))
        creates=[args for args in self.calls if args[:2]==["docs","+create"]]
        self.assertEqual(len(creates),2)
        self.assertIn("review",creates[0][creates[0].index("--content")+1])
        self.calls=[]
        publish(self.manifest,self.state,self.review,self.questions,self.root,parent="parent",execute=True,runner=self.cloud)
        self.assertEqual([x[:2] for x in self.calls],[["docs","+fetch"]]*2)

    def test_parse_failed_cannot_publish(self):
        with self.assertRaises(ValueError):
            publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,
                runner=lambda *args,**kwargs:{"ok":True,"data":{"assessment":{"status":"failed"}}})
        self.assertEqual(self.state["documents"],{})

    def test_missing_draft_decision_stops(self):
        (self.review.parent/".presentation-decision.json").unlink()
        with self.assertRaises(ValueError):
            publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,runner=self.cloud)
        self.assertEqual(self.calls,[])

    def test_changed_published_xml_does_not_create(self):
        publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,runner=self.cloud)
        self.review.write_text('<title>改版</title><p>新内容</p>',encoding="utf-8")
        self.calls=[]
        with self.assertRaises(ValueError):
            publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,runner=self.cloud)
        self.assertEqual(self.calls,[])

    def test_fetch_detects_missing_content_and_code(self):
        spec=inspect_xml(self.review,"review")
        actual='<title>面试 复盘</title><h1>QA</h1>'
        check=verify_content(spec,actual)
        self.assertFalse(check["passed"])
        self.assertIn("content_missing",check["issues"])
        self.assertIn("code_count",check["issues"])

    def test_question_count_verification(self):
        spec=inspect_xml(self.questions,"questions")
        actual='<title>面试 问题</title><ol><li>问题一？</li></ol>'
        self.assertIn("question_count",verify_content(spec,actual)["issues"])

    def test_parent_change_stops(self):
        self.state["document_parent"]="first-parent"
        with self.assertRaises(ValueError):
            publish(self.manifest,self.state,self.review,self.questions,self.root,parent="other-parent",execute=True,runner=self.cloud)
        self.assertEqual(self.calls,[])

    def test_unknown_second_create_reuses_first(self):
        def interrupted(args,cwd):
            if args[:2]==["docs","+create"] and "questions" in args[args.index("--content")+1]:
                raise CliFailure({"error":"network lost"},unknown=True)
            return self.cloud(args,cwd)
        with self.assertRaises(CliFailure):
            publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,runner=interrupted)
        self.assertIn("review",self.state["documents"])
        self.assertEqual(self.state["stages"]["create_questions"]["status"],"unknown")
        self.calls=[]
        with self.assertRaises(RuntimeError):
            publish(self.manifest,self.state,self.review,self.questions,self.root,execute=True,runner=self.cloud)
        self.assertFalse(any(call[:2]==["docs","+create"] for call in self.calls))

    def test_init_reuses_exact_source(self):
        script=Path(__file__).with_name("workflow.py")
        destination=self.root/"initialized"
        args=[sys.executable,str(script),"init","--video",str(self.source),"--company","测试公司","--date","2026-10-14","--mode","local","--output",str(destination)]
        subprocess.run(args,capture_output=True,check=True)
        result=subprocess.run(args,capture_output=True,check=True)
        self.assertTrue(json.loads(result.stdout)["reused"])
        bad=args.copy()
        bad[bad.index("--company")+1]="另一公司"
        self.assertNotEqual(subprocess.run(bad,capture_output=True).returncode,0)

    def test_offline_asr_clip_timeline_and_vad(self):
        import transcribe
        self.state["mode"]="local"
        save_json(self.manifest,self.state)
        word=SimpleNamespace(start=0.1,end=0.3,word="你好",probability=0.9)
        segment=SimpleNamespace(id=1,start=0.1,end=0.3,text="你好",avg_logprob=-0.1,no_speech_prob=0.01,words=[word])
        observed={}
        class Model:
            def __init__(model_self,path,**kwargs):
                observed["constructor"]=kwargs
            def transcribe(model_self,source,**kwargs):
                observed["options"]=kwargs
                observed["source"]=source
                return iter([segment]),SimpleNamespace(language="zh",duration=0.75)
        with patch.dict(sys.modules,{"faster_whisper":SimpleNamespace(WhisperModel=Model)}), \
             patch.object(transcribe,"resolve_model",return_value=self.root), \
             patch.object(sys,"argv",["transcribe.py","--run",str(self.manifest),"--clip","0.5","1.25"]), \
             contextlib.redirect_stdout(io.StringIO()):
            transcribe.main()
        result=load_json(self.manifest.parent/"transcripts"/"clip-0.500-1.250.json")
        self.assertAlmostEqual(result["segments"][0]["start"],0.6)
        self.assertAlmostEqual(result["segments"][0]["words"][0]["end"],0.8)
        self.assertTrue(observed["constructor"]["local_files_only"])
        self.assertTrue(observed["options"]["vad_filter"])
        self.assertNotIn("clip_timestamps",observed["options"])
        self.assertTrue(Path(observed["source"]).is_file())

    def test_model_check_disallows_network(self):
        import prepare_model
        (self.root/"model.bin").touch()
        save_json(self.root/"config.json",{})
        calls=[]
        def download(model,**options):
            calls.append(options)
            return str(self.root)
        with patch.dict(sys.modules,{"faster_whisper.utils":SimpleNamespace(download_model=download)}):
            self.assertEqual(prepare_model.resolve_model("test-model"),self.root)
            self.assertTrue(calls[0]["local_files_only"])

if __name__=="__main__":
    unittest.main(verbosity=2)
