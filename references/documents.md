# 飞书双文档创作、发布与回查

使用 Core 或 Local runtime（保持所选 profile）。先确认保存位置和标题信息，日期按视频/用户信息，公司部门与轮次采用用户给定值；标题通常为“日期 公司 部门 轮次 复盘”和对应“问题”。轮次未知不猜，可在询问时继续本地工作。

已安装 lark-doc 时必须读取它的 SKILL.md，并按其 create-workflow、体裁、XML、create/fetch/script 规范执行；目标是飞书在线 Docx，而非上传普通 Markdown 文件。缺少相关 skill 时下面的流程可作为本 skill 自带操作规范，先用 CLI --help 核验兼容性；不可换存到其他产品。

## 草稿流程

两份文档分别调用 init-draft，使用其返回的独占目录与路径。复盘以 workplace.retrospective 契约、问题清单以 router.knowledge 的 reference 任务为起点；以当前 CLI 支持的契约名称为准。完整决策示例（按实际截图数量调整）：

```json
{
  "audience":"候选人本人",
  "reader_task":"根据原面试问答判断回答质量，并据此练习下一场面试",
  "genre_contract":"workplace.retrospective",
  "adapter":"none",
  "presentation_mode":"normal",
  "visual_plan":{"reason":"题目代码画面作为现场实现证据","blocks":[{"type":"img","min_count":1,"purpose":"核验手撕题现场代码"}]}
}
```

没有截图时 blocks 为 []，reason 解释文字已经足够；问题清单 blocks=[]、reader_task 改为按顺序检索本场实际问题。不要强加无关视觉。

```powershell
lark-cli docs +script --command init-draft --presentation-decision '<完整 JSON>' --format json --as user
```

CLI 返回 `data.workspace` 和 `data.draft_path`；直接用文件编辑工具在 draft_path 写完整 XML，初次写入前不要读这个尚不存在的文件。CLI 创建的 .presentation-decision.json 保持原值，两个草稿分别初始化。将返回路径作为 publish.py 参数。

XML 使用唯一 `<title>`，正文 h1 起连续层级，必要编号 `seq="auto"`；QA 项使用 h2 或 h1（与结构匹配），实际回答、评价、建议写具体正文。文本中 &、<、> 要转义，标签不转义。代码：

```xml
<pre lang="python" caption="现场代码"><code>def solve(x):
    return x &lt; 3</code></pre>
<img path="@./本场输出/frames/frame-00000120.000-pyav.png" caption="现场代码画面"/>
```

代码中的文本换行按当前 XML 规范处理；截图路径相对**调用 CLI 的 CWD**，不是 XML 文件目录；本场输出和独占 draft 都应在任务工作区内。使用本地 img path，不生成伪造的云端图片 token。问题清单：

```xml
<title>2026-10-14 公司 一面 问题</title>
<ol seq="auto"><li>第一个实际问题？</li><li>第二个实际问题？</li></ol>
```

写完两份草稿后分别 parse：

```powershell
lark-cli docs +script --command parse --content '@./draft_xxxxxxxx_folder/draft.xml' --format json --as user
```

检查 `data.assessment.status=passed`，不是仅检查 ok:true。按 diagnostics 修复 XML/资源并重验。脚本发布时还会执行 parse 和基础结构检查，不能替代 agent 的逐题内容审核。

## 发布与断点

```powershell
uv run --project "$taskSkill/runtime" --frozen python "$taskSkill/scripts/publish.py" --run "$taskRun" --review './draft_REVIEW_folder/draft.xml' --questions './draft_QUESTIONS_folder/draft.xml' --parent-token '<用户指定的 folder/wiki node token>'
uv run --project "$taskSkill/runtime" --frozen python "$taskSkill/scripts/publish.py" --run "$taskRun" --review './draft_REVIEW_folder/draft.xml' --questions './draft_QUESTIONS_folder/draft.xml' --parent-token '<同一 token>' --execute
```

本地 profile 加 `--extra local`。省略 parent-token 时采用 run.settings 中已有设置；没有设置则保存当前用户云空间根目录，可在用户未限定位置时采用并告知。不能用其他面试的保存位置当新用户默认值。用户自定义分节时加 `--allow-question-sections`，由 agent 另行检查各分节编号/题量。

脚本串行 create、保存 ID、保留本场 documents/review.xml 和 questions.xml，再 fetch 两份全文核验标题、正文覆盖、题量、代码块与图片数。响应中的 warnings/tips 也必须检查；有降级时修复既有文档。run.json 同时保存绑定 XML 指纹，重跑复用已有 ID；本地草稿变化时需要原地 update，不自动再建。

写入 pending/unknown 的恢复与 lark.md 相同：先按 user 身份唯一定位已创建文档，补录 `stages.create_review` 或 `create_questions` 的 complete/response（保持原 input_sha256），再续跑。已明确请求被拒绝而没有创建才改为 failed。不得用新文档替代未核实的创建结果。

发布回查后 agent 再确认：每题现场回答/评价/建议对应，截图足够清晰，代码语言正确，列表连续，技术来源准确；回查计数不等于语义审核。修复时以已记录 document_id 使用当前 lark-doc 的 update 工作流。

最终 XML 与响应已经保存后，按 lark-doc 规范精确删除本次 init-draft 返回的两个临时 workspace；删除前解析绝对路径、验证为任务工作区内且确为本次独占目录。保留输入视频、转写、截图、代码、测试和 run.json。最终给两份文档链接；若授权或内容缺口尚待处理，如实说明本地已完成部分和所需下一步。
