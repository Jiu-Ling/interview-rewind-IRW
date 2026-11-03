import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

SKILL_DIR = Path(__file__).resolve().parents[1]
PREFERENCES = SKILL_DIR / "config" / "preferences.json"

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def source_fingerprint(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()}

def run_path(value):
    path = Path(value).resolve()
    return path / "run.json" if path.is_dir() else path

def load_run(value):
    path = run_path(value)
    state = load_json(path)
    source = Path(state["source"]["path"])
    if not source.is_file() or source_fingerprint(source) != state["source"]:
        raise ValueError("源文件与 run.json 指纹不符，请为新输入创建独立运行目录")
    return path, state

def cli_prefix():
    binary = shutil.which("lark-cli")
    if not binary:
        raise FileNotFoundError("lark-cli 未安装；请按 references/runtime.md 的 CLI 安装指引处理")
    path = Path(binary)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        ps1 = path.with_suffix(".ps1")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if ps1.is_file() and shell:
            return [shell, "-NoProfile", "-File", str(ps1)]
        raise RuntimeError("lark-cli 的 Windows shim 缺少 PowerShell 入口；请检查 CLI 安装")
    return [binary]

class CliFailure(RuntimeError):
    def __init__(self, response, unknown=False):
        self.response = response
        self.unknown = unknown
        super().__init__(json.dumps(response, ensure_ascii=False))

def cli(args, cwd, timeout=1800):
    try:
        result = subprocess.run(cli_prefix() + list(args), cwd=cwd, text=True,
            encoding="utf-8", errors="replace", capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (subprocess.TimeoutExpired, OSError) as error:
        raise CliFailure({"error": str(error)}, unknown=True) from error
    decoder = json.JSONDecoder()
    response = None
    for output in (result.stdout, result.stderr):
        for index, char in enumerate(output):
            if char == "{":
                try:
                    value, _ = decoder.raw_decode(output[index:])
                    if isinstance(value, dict) and "ok" in value:
                        response = value
                        break
                except json.JSONDecodeError:
                    pass
        if response is not None:
            break
    if response is None:
        raise CliFailure({"exit_code":result.returncode,"error":"CLI 没有返回结构化结果；检查当前进程输出并定位已有资源"}, unknown=True)
    if result.returncode != 0 or response.get("ok") is not True:
        raise CliFailure(response)
    return response

def write_stage(manifest, state, name, operation):
    record = state.setdefault("stages", {}).setdefault(name, {})
    if record.get("status") in {"pending", "unknown"}:
        raise RuntimeError(f"{name} 的上次写入结果未确认，先定位资源再补录状态，不自动重试")
    record["status"] = "pending"
    save_json(manifest, state)
    try:
        response = operation()
    except CliFailure as error:
        # A structured error can follow a partial server-side mutation too.
        record["status"] = "unknown"
        record["error"] = error.response
        save_json(manifest, state)
        raise
    record.update({"status":"complete","response":response.get("data",{})})
    save_json(manifest, state)
    return response
