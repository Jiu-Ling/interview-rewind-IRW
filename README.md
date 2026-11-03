# Interview Rewind（IRW）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Format: Agent Skills](https://img.shields.io/badge/Format-Agent%20Skills-0f766e)
![Python: 3.12](https://img.shields.io/badge/Python-3.12-3776AB)

> 面试回放与逐题复盘。Rewind every interview. Verify every answer.

Interview Rewind（缩写 **IRW**，GitHub 仓库 `Jiu-Ling/interview-rewind-IRW`）是一个面向 AI Agent 的开源技能包。它把面试录像还原为逐题 QA 复盘、连续编号的问题清单，以及可追溯的转写、截图和现场代码证据。适合面试复盘、面试录像转写、逐题问答整理、手撕代码核验，以及飞书妙记和飞书文档交付。

它支持本地 Whisper 模型离线转写，也可以调用飞书妙记转写，并在需要时把最终内容发布为飞书双文档。

**关键词：** AI Agent Skill、面试复盘、面试录像转写、逐题 QA、手撕代码、飞书妙记、Feishu Minutes。

## 能做什么

- 从面试录屏中提取带时间戳的逐字稿，并定位题面、手撕代码和运行结果。
- 按真实问答整理题意、现场回答、正确性评价、优化方向和参考答法。
- 对手撕代码保留原稿，补充样例、边界用例和安全范围内的运行核验。
- 生成从 1 到 N 连续编号的问题清单，支持追问与候选人反问。
- 将复盘与问题清单发布到飞书 Docx，并回查标题、题量、代码块和图片。
- 使用显式状态文件记录转写和发布进度，支持安全续跑。

## 工作流

1. 读取视频或妙记，完整生成逐字稿。
2. 在源时间轴上建立问答证据底稿。
3. 抽取关键画面，独立核验手撕代码。
4. 编写 QA 复盘和连续编号的问题清单。
5. 按用户要求保存到本地或发布到飞书。

视频、纪要、截图和逐字稿均作为待分析资料，其中出现的指令不会改变任务范围或授权。

## 环境要求

- Windows 10/11、macOS 或 Linux
- [uv](https://docs.astral.sh/uv/)，安装脚本会准备并使用 Python 3.12
- 本地转写：支持 `faster-whisper` 的 CPU 环境；首次使用模型时需要网络和额外磁盘空间
- 飞书妙记或文档发布：Node.js 16+、npm、[`@larksuite/cli`](https://www.npmjs.com/package/@larksuite/cli)
- FFmpeg 可选；默认媒体后端使用 PyAV 和 OpenCV

## 快速开始

### 1. 选择运行模式

| 模式 | 用途 | 安装内容 |
| --- | --- | --- |
| `Local` | 本地离线转写、截图、代码核验、飞书发布 | 媒体处理 + faster-whisper |
| `Core` | 飞书妙记转写、截图、代码核验、飞书发布 | 媒体处理 |

首次使用建议选择 `Local`。安装脚本不会自动下载数 GB 的语音模型。

### 2. 安装

Windows PowerShell：

```powershell
git clone https://github.com/Jiu-Ling/interview-rewind-IRW.git interview-rewind
Set-Location .\interview-rewind
pwsh -NoProfile -File .\install.ps1 -Profile Local
```

macOS / Linux：

```bash
git clone https://github.com/Jiu-Ling/interview-rewind-IRW.git interview-rewind
cd interview-rewind
bash ./install.sh --profile local
```

更多安装选项见 [install.md](install.md)。

### 3. 验证

```powershell
uv run --project .\runtime --frozen --extra local python .\scripts\workflow.py doctor
```

```bash
uv run --project ./runtime --frozen --extra local python ./scripts/workflow.py doctor
```

`doctor` 会报告 Python、uv、飞书 CLI、FFmpeg 和核心 Python 模块状态。

### 4. 准备本地模型

需要本地离线转写时执行：

```powershell
uv run --project .\runtime --frozen --extra local python .\scripts\prepare_model.py --model large-v3-turbo --download
```

```bash
uv run --project ./runtime --frozen --extra local python ./scripts/prepare_model.py --model large-v3-turbo --download
```

模型下载完成后即可离线运行。也可以传入已有的 CTranslate2 模型目录。

## 在常见 Agent 中安装

Skill 的核心要求是：完整保留本仓库目录，并让其中的 `SKILL.md` 位于 Agent 的 skills 根目录下。clone 到目标目录后再运行安装脚本，可以避免把本机虚拟环境一并复制。

常见 skills 根目录：

| Agent | 推荐目录 |
| --- | --- |
| Codex | `$CODEX_HOME/skills`，默认 `~/.codex/skills` |
| Claude Code | `~/.claude/skills` |
| Gemini CLI | `~/.gemini/skills` |
| Cursor | 项目内 `.cursor/skills`，或 `~/.cursor/skills` |
| OpenCode | 项目内 `.opencode/skills`，或 `~/.config/opencode/skills` |
| 通用 Agent Skills 目录 | 项目内 `.agents/skills`，或 `~/.agents/skills` |

不同客户端版本可能调整发现路径。若目录不同，以对应客户端的 skills 设置为准。

### Windows PowerShell

以下示例安装到 Codex；将 `$skillsRoot` 改为目标 Agent 的目录即可：

```powershell
$repo = "https://github.com/Jiu-Ling/interview-rewind-IRW.git"
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills" } else { Join-Path $HOME ".codex\skills" }
New-Item -ItemType Directory -Force $skillsRoot | Out-Null
git clone $repo (Join-Path $skillsRoot "interview-rewind")
pwsh -NoProfile -File (Join-Path $skillsRoot "interview-rewind\install.ps1") -Profile Local
```

### macOS / Linux

以下示例安装到 Claude Code：

```bash
repo="https://github.com/Jiu-Ling/interview-rewind-IRW.git"
skills_root="$HOME/.claude/skills"
mkdir -p "$skills_root"
git clone "$repo" "$skills_root/interview-rewind"
bash "$skills_root/interview-rewind/install.sh" --profile local
```

### Cursor 项目级安装

```bash
repo="https://github.com/Jiu-Ling/interview-rewind-IRW.git"
project="/path/to/your-project"
mkdir -p "$project/.cursor/skills"
git clone "$repo" "$project/.cursor/skills/interview-rewind"
bash "$project/.cursor/skills/interview-rewind/install.sh" --profile local
```

### Gemini CLI

```bash
repo="https://github.com/Jiu-Ling/interview-rewind-IRW.git"
skills_root="$HOME/.gemini/skills"
mkdir -p "$skills_root"
git clone "$repo" "$skills_root/interview-rewind"
bash "$skills_root/interview-rewind/install.sh" --profile local
```

### OpenCode

```bash
repo="https://github.com/Jiu-Ling/interview-rewind-IRW.git"
project="/path/to/your-project"
mkdir -p "$project/.opencode/skills"
git clone "$repo" "$project/.opencode/skills/interview-rewind"
bash "$project/.opencode/skills/interview-rewind/install.sh" --profile local
```

安装后重启或重新加载 Agent，使 skills 目录重新扫描。首次调用时使用类似下面的提示：

```text
请使用 $interview-rewind 处理这段面试视频，生成逐题复盘和问题清单。
```

## 飞书 CLI

飞书妙记和飞书文档功能需要安装并授权官方 CLI：

```bash
npm install -g @larksuite/cli
lark-cli --version
lark-cli config show
# 尚未配置应用时：
lark-cli config init --new
lark-cli auth status --json --verify
```

按业务域申请授权：

```bash
lark-cli auth login --domain docs,drive,minutes --recommend
```

保存位置是知识库节点时，可把 `wiki` 加入 `--domain`。授权状态由 `lark-cli` 管理，不会写入本仓库的配置文件。

安装脚本会检查 `lark-cli`。缺失时默认打印安装提示；需要把飞书功能作为硬性依赖时，使用 `--require-lark` 或 `-RequireLark`。

## 目录结构

```text
interview-rewind/
├─ SKILL.md
├─ README.md
├─ install.md
├─ install.ps1
├─ install.sh
├─ agents/
├─ config/
├─ references/
├─ runtime/
│  ├─ pyproject.toml
│  └─ uv.lock
└─ scripts/
```

`runtime/` 保存锁定依赖；`config/preferences.json` 保存通用模型和文档偏好。每场面试的转写、截图和运行状态应放在用户指定的独立输出目录，不应写回 skill 目录。

## 隐私与数据

- `Local` 模式下，音视频和逐字稿留在本机，模型推理可离线完成。
- 选择飞书妙记时，只有用户指定的音视频会上传到飞书。
- 发布到飞书时，内容通过当前 `lark-cli` 用户身份写入用户指定的位置。
- 飞书应用凭据和授权令牌由 `lark-cli` 保存，不进入本仓库。
- `config/preferences.json` 只包含模型参数和文档偏好；首次使用时转写模式为空，保存位置为空。

## 开发与测试

```powershell
uv lock --check --project .\runtime
uv run --project .\runtime --frozen --extra local python .\scripts\test_workflow.py
uv run --project .\runtime --frozen --extra local python -m compileall -q .\scripts
```

```bash
uv lock --check --project ./runtime
uv run --project ./runtime --frozen --extra local python ./scripts/test_workflow.py
uv run --project ./runtime --frozen --extra local python -m compileall -q ./scripts
```

测试中的云端操作使用 mock，不需要飞书账号或凭据。

## 许可证

[MIT](LICENSE)
