# 本地离线转写

运行环境采用 Local profile。默认 faster-whisper / large-v3-turbo / CPU / int8；短片先验证模型和输入，再跑整场。GPU 是用户可选优化，需确认 CUDA/cuDNN 与 CTranslate2 兼容性；未确认时用 CPU。

## 模型准备与离线运行

```powershell
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/prepare_model.py" --model large-v3-turbo
```

该命令只检查缓存。缺缓存时说明首次模型准备需要联网、磁盘和下载时间，执行显式下载：

```powershell
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/prepare_model.py" --model large-v3-turbo --download
```

也可 `--model '<已有 CTranslate2 模型目录>'`；模型目录需含 model.bin、config.json。不要把 OpenAI .pt 或 GGUF 当作兼容模型。环境已有下载缓存可直接复用。保存 `model_path` 以方便检查；模型缓存不打包进 skill。

```powershell
uv run --project "$taskSkill/runtime" --frozen --extra local --offline python "$taskSkill/scripts/transcribe.py" --run "$taskRun" --clip 223 238
uv run --project "$taskSkill/runtime" --frozen --extra local --offline python "$taskSkill/scripts/transcribe.py" --run "$taskRun" --prompt 'Java、Redis、MySQL、Kafka'
```

脚本同时设置 HF_HUB_OFFLINE、TRANSFORMERS_OFFLINE、local_files_only，并以已解析的本地目录加载模型；音视频保持本地。术语 prompt 只是识别提示，不代表实际出现了这些词。可用 `--model`、`--device`、`--compute-type` 临时覆盖；常用设置在 preferences.local 中维护。

## 产物与质量检查

- `transcripts/transcript.json`：完整元数据和段落，作为分析主输入。
- `transcript.jsonl`：逐段流式落地；便于中断后定位已有进度。
- `transcript.txt`：带时间戳的可读逐字稿；显示时间不代表说话人已识别。
- `clip-START-END.*`：独立复核，不修改主转写。片段时间保留源视频时间轴。

实时进度报告来自识别段落结束时间，不给未经测量的 ETA。执行失败保留已经落地的分段输出；确认后可用 `--overwrite` 从头转写（覆盖该场该转写输出），或使用另一独占 run 目录。未完成 JSONL 不能冒充完整面试。

片段先提取 PCM 再转写，以保留 VAD 静音过滤并减少解码开销；段落与单词时间加回源时间偏移。`review_hint` 使用单词识别概率做粗略核验提示，不是经过校准的准确率。静音段可能为空，带 prompt 的文字需对照音频和上下文，不能把技术术语提示当作真实内容。

完整读取 TXT/JSON，并校验末尾发言、面试开场/结尾、长时间无文本区间。VAD 无法保证覆盖所有低音量发言；疑似漏段可用音频片段复听/再次转写，必要时调试 VAD。离线模型不提供可靠声纹角色划分：依据语义和画面人工判断，争议段在工作底稿标记待核验，最终结论按证据置信度表达。

参考实现与依赖行为以 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 当前文档和锁定版本为准。模型识别文字不是答案正确性的证明。
