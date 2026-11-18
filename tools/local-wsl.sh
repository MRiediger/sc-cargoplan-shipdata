#!/usr/bin/env bash
# tools/local-wsl.sh - the pipeline in WSL Ubuntu 24.04 (the runner's OS) with the pins of TOOLS.md, before anything goes
# to a runner (TASKS.md, lesson of S12.0). From Windows:
#   wsl -d Ubuntu-24.04 -- bash <repo in /mnt/c/...>/tools/local-wsl.sh setup        toolchain + pip + npm
#   wsl -d Ubuntu-24.04 -- bash <repo in /mnt/c/...>/tools/local-wsl.sh test         pytest tests
#   wsl -d Ubuntu-24.04 -- bash <repo in /mnt/c/...>/tools/local-wsl.sh run <args>   python -I tools/run.py <args>
# Toolchain without sudo in $SHIPDATA_TOOLS (default ~/s12tools, the folder S12.0 set up): Python (uv) from .python-version,
# numpy and opencv from tools/requirements.txt, pytest from tools/requirements-dev.txt, Node from .nvmrc, pwsh from
# tools/pins.json - the same sources the workflow reads (SD8). Runs in place:
# work/, cache/ and out/ are the repo's (gitignored).
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
T=${SHIPDATA_TOOLS:-$HOME/s12tools}
export PATH="$T/node/bin:$T/pwsh:$T/venv/bin:$PATH"
# The repo under /mnt/c belongs to the WSL default user; run as another user (as root), git refuses it as "dubious
# ownership" and verify cannot read pipelineCommit. Trusted for this script's processes only, no global config
# (git-config(1), GIT_CONFIG_COUNT, git >= 2.31).
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$REPO"
cmd=${1:-test}; shift || true
# One source per pin (SD8). Ubuntu's own python3 reads pins.json, since the pinned one may not be installed yet.
PY=$(cat "$REPO/.python-version"); NODE=$(cat "$REPO/.nvmrc")
PWSH=$(python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["pwsh"])' "$REPO/tools/pins.json")

setup() {
    mkdir -p "$T"; cd "$T"
    [ -x ~/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
    ~/.local/bin/uv python install "$PY" 2>&1 | tail -n 1
    [ -d node ] || { curl -sSL "https://nodejs.org/dist/v$NODE/node-v$NODE-linux-x64.tar.xz" | tar xJ && mv "node-v$NODE-linux-x64" node; }
    [ -d pwsh ] || { mkdir pwsh && curl -sSL "https://github.com/PowerShell/PowerShell/releases/download/v$PWSH/powershell-$PWSH-linux-x64.tar.gz" | tar xz -C pwsh && chmod +x pwsh/pwsh; }
    [ -d venv ] || "$(~/.local/bin/uv python find "$PY")" -m venv venv
    venv/bin/python -m pip install -q --disable-pip-version-check -r "$REPO/tools/requirements.txt" -r "$REPO/tools/requirements-dev.txt"
    npm ci --prefix "$REPO/tools" --no-audit --no-fund --silent
}

versions() {
    echo "python $(python -c 'import platform; print(platform.python_version())'), numpy $(python -c 'import numpy; print(numpy.__version__)')," \
         "opencv $(python -m pip show opencv-python-headless | sed -n 's/^Version: //p'), pytest $(python -m pytest --version 2>&1 | cut -d' ' -f2)," \
         "node $(node -v), meshoptimizer $(node -p "require('$REPO/tools/node_modules/meshoptimizer/package.json').version"), pwsh $(pwsh -NoProfile -c '$PSVersionTable.PSVersion.ToString()')"
}

cd "$REPO"
case "$cmd" in
    setup) setup; versions ;;
    test) versions; python -I -m pytest -p no:cacheprovider "$@" ;;
    run) python -I tools/run.py "$@" ;;
    *) echo "usage: local-wsl.sh setup | test [pytest args] | run <run.py args>"; exit 1 ;;
esac
