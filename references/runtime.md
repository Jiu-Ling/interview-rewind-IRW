# 运行环境与冷启动

支持 Windows PowerShell；Python 脚本也可在 macOS/Linux 使用 uv 命令运行。默认 CPU/int8，Python 固定 3.12。环境独占 `runtime/.venv`，`runtime/uv.lock` 锁定依赖；不要复制或挪动现成 venv。所有 Python 调用由 uv 执行。

## uv 检查与安装引导

运行 `uv --version`。找不到时说明需要 uv，给用户 [官方安装入口](https://docs.astral.sh/uv/getting-started/installation/)；Windows 可用：

```powershell
winget install --id=astral-sh.uv -e
```

打开官方网页供用户安装，或展示以上命令。网络安装器与系统软件安装遵循当前授权；不要自动执行远程安装脚本。用户安装后重新打开终端，验证 `uv --version`；若当前进程 PATH 尚未刷新，可查用户确认安装位置并显式调用 uv.exe。确认 uv 后再继续。

## 独占 Python 与库

`taskSkill` 为实际 skill 目录；`taskRun` 为用户工作区下本场独占输出目录。命令中的示例值应替换为真实输入。

```powershell
$taskSkill = '<skills-root>\interview-rewind'
powershell -NoProfile -File "$taskSkill\scripts\bootstrap.ps1" -Profile Local
```

`Local` 安装媒体处理和 ASR；`Core` 只安装媒体处理，用于妙记和发布。uv 会自动准备 Python 3.12。首次需要网络；缓存完整后可加 `-Offline`。脚本找不到 uv 时退出并提供安装指引。

macOS/Linux 对应：`uv sync --project '<skill_dir>/runtime' --python 3.12 --frozen --extra local`；Core 省略 `--extra local`。

库通过 `pyproject.toml` + `uv.lock` 维护。需要加库时用 `uv add --project ...` 并更新锁文件，运行前同步；不使用 pip 或全局 Python 安装。后续命令保留所选 profile：本地模式统一加 `--extra local`，否则 uv 的精确同步可能移除 ASR 库。

```powershell
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/workflow.py" doctor
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/workflow.py" preferences get
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/workflow.py" preferences set-mode local
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/workflow.py" init --video 'C:\Videos\面试.mp4' --company '公司 部门' --date 2026-10-14 --round '一面' --output "$taskRun"
```

只在收到用户选择后执行 set-mode。首次回答本次与长期偏好相同则保存；临时指定用 init 的 `--mode`。偏好文件位于 `config/preferences.json`，不保存任何授权密钥。目录只读时按平台权限流程恢复该配置的写入权限，不能悄悄改存另一个位置。

## 媒体工具

PyAV 自带解码库；OpenCV 用于画面定位，无需单独安装 FFmpeg 即可抽帧/导出 PCM。可选安装 [FFmpeg](https://ffmpeg.org/download.html)，验证 `ffmpeg -version` 与 `ffprobe -version`，然后选择 `--backend ffmpeg`。不自动更改系统 PATH。

```powershell
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/media.py" --run "$taskRun" probe
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/media.py" --run "$taskRun" frames --at 600 660 720 --backend opencv
uv run --project "$taskSkill/runtime" --frozen --extra local python "$taskSkill/scripts/media.py" --run "$taskRun" audio --start 600 --end 630 --name clip-600-630.wav
```

时间单位为秒，输出为 PNG、16 kHz 单声道 PCM WAV。每帧记录请求时间、实际解码时间（FFmpeg 后端不报告实际时间）；要抄代码时原分辨率看图。文件已存在时读取现有证据或换名称，不覆盖原始视频。

## 飞书 CLI 与授权

需要 `lark-cli`、Node.js/npm。优先复用已有安装，缺失时引导安装 Node.js LTS 与 `npm install -g @larksuite/cli`，验证 `lark-cli --version`。应用配置用 `lark-cli config init --new`；不要打印 appSecret/accessToken。执行当前 lark-shared（若已安装）；缺少该 skill 时按以下最小流程处理：

1. `lark-cli auth status --json --verify` 检查用户身份与有效授权。
2. 缺 user scope 时按错误 `missing_scopes` 请求最小范围：`lark-cli auth login --scope '<所需 scope>' --no-wait --json`；新完整工作流可请求 docs、drive、minutes 业务域，先核验 CLI 的域名称。
3. 将返回 URL 原样用 `lark-cli auth qrcode '<URL>' --output './本场/auth.png'` 生成二维码，展示原链接和二维码；结束本轮并请用户完成后回复。
4. 用户回复后由 agent 执行 `lark-cli auth login --device-code '<本次 code>'`。不把 URL/code 存进偏好文件，也不复用过期 code。
5. 资源 ACL 缺失需所有者授权，不能靠切换 bot 绕过；整条链路显式 `--as user`。

CLI 文件参数相对调用 CWD。脚本用 argv 数组和 Windows PowerShell shim，不拼接 shell 字符串。`ok:true` 才是命令成功；解析检查还需要 `assessment.status=passed`。

uv 缓存、模型下载或全局 skill 配置被沙箱拒绝时，按环境权限机制对具体命令请求提升权限；不迁移用户数据或关闭保护。长任务用可返回 session ID 的运行方式，并间隔报告实际进度。
