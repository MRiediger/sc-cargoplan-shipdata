#!/usr/bin/env bash
# spike/local-wsl.sh - the chain job of spike.yml locally in WSL Ubuntu 24.04 (the runner's OS), before it goes to a runner.
# Run from Windows: wsl -d Ubuntu-24.04 -- bash <repo in /mnt/c/...>/spike/local-wsl.sh
# 1) Pinned toolchain in ~/s12tools (no sudo): Python 3.14.5 (uv), numpy, opencv, Node 24.16.0, pwsh 7.6.10.
# 2) Copy of this repo + sc-cargoplan@v0.5.1 (sibling folder) in ~/s12run, then spike/chain-job.sh.
# No API call: API answer and page come from ../sc-ship-outlines/motherlode (archive 2026-11-16); the page's 100i URL is set
# to the hash the runner saw on 17 Nov (f982f2636804), so the two-model branch runs as on the runner. PROBE_HEAD=0.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
D=$(dirname "$REPO")
T=~/s12tools
R=~/s12run

# 1) toolchain
mkdir -p "$T"; cd "$T"
[ -x ~/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
~/.local/bin/uv python install 3.14.5 2>&1 | tail -n 1
[ -d node ] || { curl -sSL https://nodejs.org/dist/v24.16.0/node-v24.16.0-linux-x64.tar.xz | tar xJ && mv node-v24.16.0-linux-x64 node; }
[ -d pwsh ] || { mkdir pwsh && curl -sSL https://github.com/PowerShell/PowerShell/releases/download/v7.6.10/powershell-7.6.10-linux-x64.tar.gz | tar xz -C pwsh && chmod +x pwsh/pwsh; }
[ -d venv ] || "$(~/.local/bin/uv python find 3.14.5)" -m venv venv
venv/bin/python -m pip install -q --disable-pip-version-check -r "$REPO/spike/requirements.txt"
echo "python $(venv/bin/python -V) node $(node/bin/node -v) pwsh $(pwsh/pwsh -NoProfile -c '$PSVersionTable.PSVersion.ToString()')"

# 2) run
rm -rf "$R"; mkdir -p "$R/cache/raw"; cd "$R"
tar -C "$REPO" --exclude=node_modules --exclude=.git -cf - . | tar xf -
git clone -q --depth 1 --branch v0.5.1 "$D/sc-cargoplan" app 2>/dev/null
cp "$D/sc-ship-outlines/motherlode/api-2026-11-16.json" cache/raw/api.json
{ printf '{"ships":'; cat "$D/sc-ship-outlines/motherlode/page-2026-11-16.json"; printf '}'; } | sed 's/ORIG_100i-da8168ea3720/ORIG_100i-f982f2636804/' > cache/raw/page.txt
echo "200 0 0" > cache/raw/api.status; echo "200 0 0" > cache/raw/page.status; : > cache/raw/api.headers; : > cache/raw/page.headers
echo "local test, archive 2026-11-16" > cache/raw/fetched-at
export PATH="$T/node/bin:$T/pwsh:$T/venv/bin:$PATH"
export SPIKE_OUT=$R/out HOLO_WORK=$R/work/holo UA='sc-cargoplan-outlines/0.2 (fan project)' APP_REPO=MRiediger/sc-cargoplan \
       APP_TAG=v0.5.1 HOLO_TAG=holo-v3 FETCHED=0 PROBE_HEAD=0 PY=python
npm ci --prefix spike --no-audit --no-fund --silent
rc=0; bash spike/chain-job.sh ORIG_100i || rc=$?
echo "chain-job exit $rc"
