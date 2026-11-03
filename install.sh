#!/usr/bin/env bash
set -euo pipefail

PROFILE="local"
OFFLINE=0
REQUIRE_LARK=0
NO_UV_INSTALL=0

usage() {
    cat <<'EOF'
Usage: bash ./install.sh [options]

Options:
  --profile local|core  Runtime profile (default: local)
  --local               Alias for --profile local
  --core                Alias for --profile core
  --offline             Use only existing uv caches
  --require-lark        Fail when lark-cli is unavailable
  --no-install-uv       Do not attempt to install uv
  -h, --help            Show this help
EOF
}

while (($#)); do
    case "$1" in
        --profile)
            if (($# < 2)); then
                echo "Missing value for --profile" >&2
                exit 64
            fi
            PROFILE="$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')"
            shift 2
            ;;
        --local)
            PROFILE="local"
            shift
            ;;
        --core)
            PROFILE="core"
            shift
            ;;
        --offline)
            OFFLINE=1
            shift
            ;;
        --require-lark)
            REQUIRE_LARK=1
            shift
            ;;
        --no-install-uv)
            NO_UV_INSTALL=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

if [[ "$PROFILE" != "local" && "$PROFILE" != "core" ]]; then
    echo "Invalid profile: $PROFILE (expected local or core)" >&2
    exit 64
fi

SKILL_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_ROOT="$SKILL_ROOT/runtime"

echo "Interview Rewind (IRW) installer"
echo "Skill:   $SKILL_ROOT"
echo "Profile: $PROFILE"

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

echo
echo "==> Checking uv"
UV_BIN="$(find_uv || true)"
if [[ -z "$UV_BIN" ]]; then
    if [[ "$NO_UV_INSTALL" -eq 1 ]]; then
        echo "uv is not installed." >&2
        echo "Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 2
    fi

    echo "uv was not found; running the official Astral installer..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "curl or wget is required to install uv." >&2
        echo "Follow https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 2
    fi

    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    UV_BIN="$(find_uv || true)"
    if [[ -z "$UV_BIN" ]]; then
        echo "uv is still unavailable. Reopen the terminal and rerun this installer." >&2
        exit 2
    fi
fi
echo "Using uv: $UV_BIN"

echo
echo "==> Synchronizing Python 3.12 runtime"
SYNC_ARGS=(sync --project "$RUNTIME_ROOT" --python 3.12 --frozen)
if [[ "$PROFILE" == "local" ]]; then
    SYNC_ARGS+=(--extra local)
fi
if [[ "$OFFLINE" -eq 1 ]]; then
    SYNC_ARGS+=(--offline)
fi
"$UV_BIN" "${SYNC_ARGS[@]}"

echo
echo "==> Checking runtime components"
RUN_ARGS=(run --project "$RUNTIME_ROOT" --frozen)
if [[ "$PROFILE" == "local" ]]; then
    RUN_ARGS+=(--extra local)
fi
if [[ "$OFFLINE" -eq 1 ]]; then
    RUN_ARGS+=(--offline)
fi
"$UV_BIN" "${RUN_ARGS[@]}" python "$SKILL_ROOT/scripts/workflow.py" doctor

echo
echo "==> Checking Lark CLI"
if command -v lark-cli >/dev/null 2>&1; then
    echo "lark-cli: $(command -v lark-cli)"
else
    echo "lark-cli was not found." >&2
    if ! command -v node >/dev/null 2>&1; then
        echo "Node.js is also missing. Install Node.js 16+ first:" >&2
        echo "  https://nodejs.org/" >&2
    fi
    if ! command -v npm >/dev/null 2>&1; then
        echo "npm is missing. Reopen the terminal after installing Node.js." >&2
    fi
    echo "Install the Feishu CLI with:" >&2
    echo "  npm install -g @larksuite/cli" >&2
    echo "Then run:" >&2
    echo "  lark-cli config show" >&2
    echo "  lark-cli config init --new   # only when no app is configured" >&2
    echo "  lark-cli auth status --json --verify" >&2
    if [[ "$REQUIRE_LARK" -eq 1 ]]; then
        echo "Lark CLI is required by this invocation." >&2
        exit 3
    fi
fi

echo
echo "Installation complete."
echo "Profile: $PROFILE"
if [[ "$PROFILE" == "local" ]]; then
    echo "Prepare the ASR model with:"
    echo "  uv run --project \"$RUNTIME_ROOT\" --frozen --extra local python \"$SKILL_ROOT/scripts/prepare_model.py\" --model large-v3-turbo --download"
fi
