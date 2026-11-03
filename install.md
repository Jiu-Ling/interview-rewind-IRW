# Interview Rewind（IRW）安装指南

本文覆盖依赖安装、运行模式、飞书 CLI 授权、验证和故障排查。只使用 Agent 中的用户可先看 [README.md](README.md) 的快速开始。

## 1. 运行模式

| 模式 | 安装命令 | 适用场景 |
| --- | --- | --- |
| `Local` | `install.ps1 -Profile Local` 或 `install.sh --profile local` | 本地离线转写，功能完整 |
| `Core` | `install.ps1 -Profile Core` 或 `install.sh --profile core` | 使用飞书妙记转写，安装体积更小 |

安装脚本执行以下操作：

1. 检查 `uv`；缺失时尝试通过 `winget` 或官方安装器安装。
2. 使用 `runtime/uv.lock` 同步 Python 3.12 环境。
3. 运行 `workflow.py doctor` 检查核心依赖。
4. 检查 Node.js、npm 和 `lark-cli`，缺失时打印安装命令。

Python 依赖安装在 `runtime/.venv`，不会修改系统 Python。

## 2. 前置条件

### 所有平台

- Git
- 可访问 Python 包索引的网络；完全离线安装时需预先准备 uv 缓存
- 本地转写需要额外磁盘空间和可用内存

### 飞书功能

- Node.js 16+
- npm
- 官方飞书 CLI：`@larksuite/cli`

## 3. Windows

在仓库目录打开 PowerShell：

```powershell
pwsh -NoProfile -File .\install.ps1 -Profile Local
```

可选参数：

```powershell
# 使用飞书妙记，不安装本地 ASR
pwsh -NoProfile -File .\install.ps1 -Profile Core

# 只使用已有 uv 缓存
pwsh -NoProfile -File .\install.ps1 -Profile Local -Offline

# 飞书 CLI 缺失时让安装失败
pwsh -NoProfile -File .\install.ps1 -Profile Local -RequireLark

# 不尝试自动安装 uv
pwsh -NoProfile -File .\install.ps1 -Profile Local -NoUvInstall
```

如果执行策略阻止本地脚本：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Profile Local
```

### 手动安装 uv

```powershell
winget install --id=astral-sh.uv -e
uv --version
```

无 winget 时按 [uv 官方安装文档](https://docs.astral.sh/uv/getting-started/installation/)操作。

## 4. macOS / Linux

在仓库目录执行：

```bash
bash ./install.sh --profile local
```

可选参数：

```bash
bash ./install.sh --profile core
bash ./install.sh --profile local --offline
bash ./install.sh --profile local --require-lark
bash ./install.sh --profile local --no-install-uv
```

脚本在缺少 uv 时调用 [Astral 官方安装脚本](https://docs.astral.sh/uv/getting-started/installation/)，随后把 `$HOME/.local/bin` 加入当前进程的 `PATH`。如果希望手动安装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

也可以使用 Homebrew：

```bash
brew install uv
```

## 5. 手动同步 Python 环境

安装脚本执行的核心命令等价于：

```bash
# Local
uv sync --project ./runtime --python 3.12 --frozen --extra local
uv run --project ./runtime --frozen --extra local python ./scripts/workflow.py doctor

# Core
uv sync --project ./runtime --python 3.12 --frozen
uv run --project ./runtime --frozen python ./scripts/workflow.py doctor
```

完全离线时追加 `--offline`。只有在所需 Python、wheel 和包缓存都已存在时，离线同步才会成功。

## 6. 飞书 CLI 与授权

安装 CLI：

```bash
npm install -g @larksuite/cli
lark-cli --version
```

初始化应用配置：

```bash
lark-cli config show
# 尚未配置应用时：
lark-cli config init --new
```

按终端提示完成浏览器配置。随后检查授权：

```bash
lark-cli auth status --json --verify
```

申请本技能所需业务域：

```bash
lark-cli auth login --domain docs,drive,minutes --recommend
```

保存到知识库节点时加入 `wiki`：

```bash
lark-cli auth login --domain docs,drive,minutes,wiki --recommend
```

工作流中的云端调用会显式使用 `--as user`。不要在命令历史、脚本或配置文件中写入 App Secret、访问令牌或设备授权码。

## 7. 本地模型

Local profile 安装完成后，模型可由 Agent 在首次任务中准备，也可以手动执行：

```bash
uv run --project ./runtime --frozen --extra local python ./scripts/prepare_model.py --model large-v3-turbo
```

上面的命令只检查缓存。确认磁盘和网络条件后执行下载：

```bash
uv run --project ./runtime --frozen --extra local python ./scripts/prepare_model.py --model large-v3-turbo --download
```

如需复用已有 CTranslate2 模型：

```bash
uv run --project ./runtime --frozen --extra local python ./scripts/prepare_model.py --model /path/to/model
```

模型目录至少应包含 `model.bin` 和 `config.json`。

## 8. 验证安装

```powershell
pwsh -NoProfile -File .\install.ps1 -Profile Local
uv run --project .\runtime --frozen --extra local python .\scripts\test_workflow.py
uv run --project .\runtime --frozen --extra local python -m compileall -q .\scripts
```

```bash
bash ./install.sh --profile local
uv run --project ./runtime --frozen --extra local python ./scripts/test_workflow.py
uv run --project ./runtime --frozen --extra local python -m compileall -q ./scripts
```

`doctor` 输出中的 `lark_cli` 为空表示 CLI 未安装或未进入当前 `PATH`；`ffmpeg` 为空不影响默认媒体后端。

## 9. 更新

保留 `config/preferences.json` 时，可以更新代码和锁定依赖：

```bash
git pull
bash ./install.sh --profile local
```

更新后重新运行 `doctor` 和测试。个人运行目录不应放在仓库内，因此不需要随 skill 更新迁移。

## 10. 常见问题

### 找不到 uv

重新打开终端，然后执行：

```bash
uv --version
```

uv 官方安装器通常把可执行文件放在 `~/.local/bin`。Windows 还可检查 `%USERPROFILE%\.local\bin`。

### 找不到 lark-cli

```bash
node --version
npm --version
npm install -g @larksuite/cli
lark-cli --version
```

安装后重新打开终端。Windows 下请确认 npm 全局 bin 目录已进入 `PATH`。

### 飞书授权失效

```bash
lark-cli auth status --json --verify
lark-cli auth login --domain docs,drive,minutes --recommend
```

按当前错误中的 `missing_scopes` 补充最小授权范围，不要复用过期设备码。

### 离线同步失败

先在联网环境运行同一 profile 的 `uv sync`，确认依赖缓存完整，再追加 `--offline`。本地模型缓存与 uv 包缓存相互独立，需要分别准备。

### Windows 找不到 PowerShell 入口

本技能的云端脚本通过 `lark-cli` 的 PowerShell shim 调用 CLI。确认 `pwsh` 或 Windows PowerShell 可用，并重新安装 npm 全局包。
