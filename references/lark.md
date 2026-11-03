# 飞书妙记转写

用户选择 lark 表示音视频会上传飞书；解释该数据流。仅用户要求转写的文件在上传范围内，不批量上传其他文件。运行 Core profile，并按 runtime.md 完成 lark-cli/user 授权。已安装 lark-minutes、lark-drive、lark-shared 时读其实际技能与对应 upload/detail 参考；当前 CLI help/schema 比历史参数优先。

```powershell
uv run --project "$taskSkill/runtime" --frozen python "$taskSkill/scripts/lark_transcribe.py" --run "$taskRun"
uv run --project "$taskSkill/runtime" --frozen python "$taskSkill/scripts/lark_transcribe.py" --run "$taskRun" --execute
```

默认检查原媒体格式、大小、时长并展示计划；`--execute` 上传。支持原格式约束按 CLI 规范（6 GB / 6 小时）；需拆分时先说明区间和最终合并方案，片段转写换算回源视频时间轴。

脚本流程：

1. `drive +upload --file ./文件名 --as user`，调用 CWD 为媒体目录；成功响应立即记录 file_token。
2. `minutes +upload --file-token ... --as user`，记录 minute_token / minute_url。
3. `minutes +detail --minute-tokens ... --wait-ready --transcript --output-dir ./transcripts/lark --overwrite --as user`，调用 CWD 为 run 目录。
4. 检查返回 `data.minutes[].artifacts.transcript_file` 确实为输出目录内的非空文件；保存 minutes-detail.json、run.json 路径记录。全量读取逐字稿后才评价。

总结、章节、关键词可辅助定位，不能替代完整逐字稿。妙记原说话人标签也需按上下文核验面试官/候选人身份。

## 续跑与未知写入

状态 `complete` 复用资源；detail 只读可再次查询，不重新上传。写请求前保存 `pending`，响应错误/进程中断记录为 `unknown` 或仍 pending；停止写流程，先以相同 user 身份在云空间/妙记中定位原文件/妙记。依据响应、文件名、大小、创建时间、内容等确认唯一匹配，不凭标题自动绑定。

确认实际资源后由 agent 用文件编辑工具补录对应 stage：

```json
{"status":"complete","response":{"file_token":"已核验的 file_token"}}
```

妙记 stage 的 response 用 minute_token、minute_url。只有确定请求被拒绝且没有产生资源时，才将该 stage 的 status 改为 `failed`，完成授权恢复后重试；保留错误记录。脚本不自动推断服务器是否写入。

等待产物期间保持当前 token；不要上传第二份来“催促”。过期授权按 split-flow 处理，不能将失败自动改为离线模式或切换身份。脚本本身不续办认证。
