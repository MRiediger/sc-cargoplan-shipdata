# Tools and versions

Pinned versions of the hologram/outline chain. Sources: `sc-ship-outlines/TOOLS.md`, `requirements.txt`,
`package-lock.json` and `.nvmrc` (pipeline repo, `25b4031`, the holo-v3 build), and `global.json` of
`MRiediger/sc-cargoplan`. The app repo has no `TOOLS.md` of its own; until T12.1 this file is the place for the pins.

| Tool | Version | Where it is pinned |
|---|---|---|
| Python | 3.14.5 | `actions/setup-python` in the workflow; builds exist for Ubuntu 22.04/24.04 only, so the chain runs on `ubuntu-24.04` (S12.0) |
| numpy | 2.5.3 | `spike/requirements.txt` |
| opencv-python-headless | 5.0.0.93 | `spike/requirements.txt` |
| Node.js | 24.16.0 | `actions/setup-node` in the workflow |
| meshoptimizer (npm) | 1.3.0 | `spike/package.json`, `spike/package-lock.json` |
| PowerShell | 7.6.10 (ubuntu24 image 20261111, measured in S12.0) | `fetch-motherlode.ps1`, the app's `tools/import-motherlode.ps1` |
| .NET SDK | 10.0.404 | `global.json` of the app (gate jobs) |

The holo-v3 manifest records `meshoptimizer 1.3.0, node 24.16.0, python 3.14.5, numpy 2.5.3`.
