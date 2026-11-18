# Tools and versions

Pinned versions of the ship data pipeline (SD8). **Every pin has one machine-readable source; this table is the copy for
people**, and `tests/test_versions.py` fails when a row and its source disagree, or when the measured version differs from
the pin. Sources of the values: `sc-ship-outlines/TOOLS.md`, `requirements.txt`, `package-lock.json` and `.nvmrc` of the
holo-v3 build (`25b4031`), `global.json` of `MRiediger/sc-cargoplan`. All versions measured in WSL Ubuntu 24.04 by
`tools/local-wsl.sh` (T12.1) and on the runner in S12.0 (run 44090875270).

| Tool | Version | Source (machine-readable) |
|---|---|---|
| Python | 3.14.5 | `.python-version` – `actions/setup-python` `python-version-file`, `tools/local-wsl.sh`. Builds exist for Ubuntu 22.04/24.04 only, hence the runner pin below (S12.0, run 1). |
| numpy | 2.5.3 | `tools/requirements.txt` |
| opencv-python-headless | 5.0.0.93 | `tools/requirements.txt` |
| pytest | 9.2.0 (pluggy 1.7.0, iniconfig 2.3.1, packaging 26.3) | `tools/requirements-dev.txt` |
| Node.js | 24.16.0 | `.nvmrc` – `actions/setup-node` `node-version-file`, `tools/local-wsl.sh` |
| meshoptimizer (npm) | 1.3.0 | `tools/package-lock.json` (and `tools/package.json`) |
| PowerShell | 7.6.10 | `tools/pins.json` `pwsh`. On the runner it comes with the image (ubuntu24 20261111) and is only measured; WSL installs it. The import needs pwsh >= 7.5 for `ConvertFrom-Json -DateKind`. |
| App for the gate | v0.5.1 | `tools/pins.json` `appTag` – `run.py` (`APP_TAG`), the gate's checkout of `sc-cargoplan` |
| Runner (chain) | ubuntu-24.04 | `tools/pins.json` `runner`. YAML cannot read it without logic, so `ship-data.yml` names it too and a test compares both (T12.2). |
| .NET SDK | 10.0.404 | `global.json` of the app (gate job, checked out at `appTag`) |

Sources for the action inputs (checked 18 Nov 2026): `actions/setup-python` `docs/advanced-usage.md` ("python-version-file
input is used for specifying the path to the version file"), `actions/setup-node` `docs/advanced-usage.md` (node-version-file
"for example `.nvmrc`, `.node-version`, `.tool-versions`, `mise.toml`, or `package.json`").

## GitHub Actions (T12.2)

`ship-data.yml` uses first-party actions of GitHub (`actions/*`) only, at the major versions S12.0's spike workflow ran
with (runs 44090875270, 44101340566; inputs checked against the READMEs on 18 Nov 2026). The source of each pin is the
workflow file itself; `tests/test_workflow.py` fails when the workflow uses an action that is not in this table with
the same version. A major tag moves within its major: see SD8, addendum Dependabot.

| Action | Version | Used for |
|---|---|---|
| `actions/checkout@v7` | v7 | this repo; the app at `appTag` in the gate (`repository`, `ref`, `path`); `persist-credentials: false` where nothing is pushed |
| `actions/setup-python@v7` | v7 | `python-version-file: .python-version` |
| `actions/setup-node@v7` | v7 | `node-version-file: .nvmrc` |
| `actions/setup-dotnet@v6` | v6 | `global-json-file: app/global.json` (gate) |
| `actions/cache/restore@v6` | v6 | model cache by SHA, `restore-keys: models-` (never the catalog, SD7) |
| `actions/cache/save@v6` | v6 | model cache after the chain, and pruned after publishing (condition B) |
| `actions/upload-artifact@v7` | v7 | reports only (JSON, CSV of hashes, summaries); several paths keep `work/` and `out/` ("the least common ancestor of all the search paths will be used as the root directory") |
| `actions/download-artifact@v8` | v8 | the reports for gate, pr and heartbeat (`pattern`, `merge-multiple`) |

**pytest** is the only new dependency of T12.1. It is the test runner that `CLAUDE.md` already names: the tests are
plain functions with fixtures (`tmp_path`, `monkeypatch`), and stdlib `unittest` would need classes for the same. It sits
in a file of its own, because `requirements.txt` stays byte-equal to the holo-v3 build.

The holo-v3 manifest records `meshoptimizer 1.3.0, node 24.16.0, python 3.14.5, numpy 2.5.3`; `tools/holo_mesh.py` names
node 24.16.0 in its own manifest writer and stays byte-equal (`docs/provenance.md`).
