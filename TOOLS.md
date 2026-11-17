# Tools and versions

Pinned versions of the ship data pipeline. Sources: `sc-ship-outlines/TOOLS.md`, `requirements.txt`, `package-lock.json`
and `.nvmrc` of the holo-v3 build (`25b4031`), `global.json` of `MRiediger/sc-cargoplan`. All versions measured in WSL
Ubuntu 24.04 by `tools/local-wsl.sh` (T12.1) and on the runner in S12.0. A version that differs from its pin is a finding.

| Tool | Version | Where it is pinned |
|---|---|---|
| Python | 3.14.5 | `actions/setup-python` in the workflow, `tools/local-wsl.sh`. Builds exist for Ubuntu 22.04/24.04 only, so the chain runs on `ubuntu-24.04` (S12.0). |
| numpy | 2.5.3 | `tools/requirements.txt` |
| opencv-python-headless | 5.0.0.93 | `tools/requirements.txt` |
| Node.js | 24.16.0 | `actions/setup-node` in the workflow, `tools/local-wsl.sh` |
| meshoptimizer (npm) | 1.3.0 | `tools/package.json`, `tools/package-lock.json` |
| PowerShell | 7.6.10 | ubuntu24 image 20261111 (S12.0), `tools/local-wsl.sh`. The import needs pwsh >= 7.5 for `ConvertFrom-Json -DateKind`. |
| pytest | 9.2.0 (pluggy 1.7.0, iniconfig 2.3.1, packaging 26.3) | `tools/requirements-dev.txt` |
| .NET SDK | 10.0.404 | `global.json` of the app (gate jobs) |
| App for the gate | v0.5.1 | `tools/run.py` (`APP_TAG`). It moves into the workflow with T12.2. |

**pytest** is the only new dependency of T12.1. It is the test runner that `CLAUDE.md` already names: the tests are
plain functions with fixtures (`tmp_path`, `monkeypatch`), and stdlib `unittest` would need classes for the same. It sits
in a file of its own, because `requirements.txt` stays byte-equal to the holo-v3 build.

The holo-v3 manifest records `meshoptimizer 1.3.0, node 24.16.0, python 3.14.5, numpy 2.5.3`.
