# Provenance of the pipeline's files

Where the code in `tools/` comes from, byte for byte or changed, and how it was checked (T12.1). Replaces
`spike/SOURCE.md`. SHA-256 of the files as committed (LF).

## Taken byte for byte

From the private pipeline repo `sc-ship-outlines` at `25b4031` (the holo-v3 build; its manifest names `pipelineCommit`
`e6943af`), through `spike/` (S12.0). Not reformatted and not renamed until a task of its own measures a reason
(TASKS.md T12.1): S12.0 showed these exact files give holograms byte-equal to holo-v3 on Ubuntu.

| File | SHA-256 | Checked |
|---|---|---|
| `tools/holo_mesh.py` | `78d7e861df5c0796ae0be5abc2e9646c0d29a836a6765f2308a373bd5a19eb86` | = `spike/SOURCE.md` |
| `tools/simplify.mjs` | `65b029e47d7064118fcaf939a2f111d52f6a8ddec4b4ba5b07d5ac8f8fc53710` | = `spike/SOURCE.md` |
| `tools/package.json` | `86fcea7b17d8e5d1966c49ae118b1100bc13e66357f865ed524d6e78534b67da` | = `spike/SOURCE.md` |
| `tools/package-lock.json` | `a81c953175ea7764cb9a84332b7394ee743d4a9e83a3efdb8265ed771612ab31` | = `spike/SOURCE.md` |
| `tools/requirements.txt` | `d304dd9689ef441312fa5a5bc85e5b6634359bb95a5fb460f1dc0b5cb8c58051` | = `spike/SOURCE.md` |

`package.json` still names the package `sc-ship-outlines`, and `requirements.txt` still carries a Windows comment
(`.venv\Scripts\python`). Both stay as they are, since the files are byte-equal on purpose.

The gate scripts for T12.2 are in `tools/gate/`, unchanged from `spike/`, which wrote them for S12.0:

| File | SHA-256 |
|---|---|
| `tools/gate/pictures.sh` | `b3a3bda0ec38baa130589773d1cbf1f1a9f8e9ade6edb6d2ed916a3e08ac532f` |
| `tools/gate/swap.sh` | `31c6e28530ad51b71b006c8f3eabc1b255c4384a6242e4cf722d6078371983e2` |
| `tools/gate/csvdiff.py` | `0a32122733ccae7e6cd43f5a47a89be97b19a1d767c6e92b49f21e74768a0a1a` |
| `tools/gate/say.sh` | `82403faacb6478a4305ac51c6c5cc9b403208ad5f18a48180eabaf325109cfba` |

## Taken and changed: racks and anchors

From `MRiediger/sc-cargoplan` at `v0.5.1` (`da48270`; `main` has the same `tools/`, `ships/` and `outlines/`).

| File | SHA-256 at v0.5.1 | SHA-256 here |
|---|---|---|
| `tools/ShipJson.ps1` | `ae5f8c3a67d8be276eca3ba618693dbec5b65a3cb2988467117a3ee45c9541a7` | unchanged |
| `tools/import-motherlode.ps1` | `5f7b5122ea5041e1b81a8f1f92c357b37e24b01e40302423adfd32ad4df6f84f` | `bdf8615523fbfcdc6a68ec2797850f906b61b0157cc1200057bce61e89359d5a` |

`import-motherlode.ps1` has four changes (plan T12.1, P6). Each one has a test in `tests/test_import.py`. Each test was
red against the v0.5.1 script and against the change undone once:

1. **Date:** `Read-Catalog` reads with `ConvertFrom-Json -DateKind String` when the parameter exists (pwsh >= 7.5).
   Without it, pwsh 7 writes `updatedAt` into `source` in the culture's date format. Measured in S12.0: 104 of 108
   files differed, and 0 do with the fix.
2. **`-KeyMap` (className -> modelKey):** a ship created without a file or a base ship takes the modelKey under which the
   last release built its model's hologram (`holo.ships.<slug>.model`). Only a className never seen gets a derived key,
   the className in lower case with `-` for `_`.
   **The 29 keys that do not follow this pattern** (for example `crus-mercury-star-runner` for `CRUS_Star_Runner`, or
   `rsi-aurora-mk-i-cl` for `RSI_Aurora_GS_CL`) are older names from the Fleetyards days. They stay through the map and
   are not "repaired": renaming a key renames hologram and outline files the app has cached. For a new className any
   consistent key is right, because hologram and outline are built under that same key.
   A ship without className is no longer written: it has no model.
   An existing file without modelKey gets one from the map too: that is the modelKey loss of v0.5.1 (350r).
3. **No anchors at the racks' middle:** a new ship gets `holoOrigin` and `outlineOrigin` from its model's floor, in the
   second import run after its outline exists. Until then the file has no anchors, and `verify` keeps it out of a release.
4. **`-Report <json>`:** each ship's status, detail, className, modelKey, shift and anchorsKept as JSON, so `verify`
   reads the rules instead of parsing the log. Ships not in the catalog are listed as `absent`.

Besides those: the default outlines path uses `Join-Path` instead of a backslash, and the header names the changes.
The 19 C# tests of the import (`sc-cargoplan/tests/CargoPlan.Core.Tests/ImportMotherlodeScriptTests.cs`) stay in the
app repo until T12.5. One of them (`Create_writes_a_ship_without_base_with_anchors_at_the_racks_middle`) describes the
behaviour change 3 removes.

## Ported (new code, same logic)

| Here | From | What |
|---|---|---|
| `tools/shipdata/fetch.py` | `sc-ship-outlines/fetch-motherlode.ps1` (`e1599e0f…`), `spike/probe.py` (`e3e56079…`) | One API call, Retry-After stops the run, User-Agent 1:1, RSC parser, format checks, join by className. From probe.py: models by hash, 200 ms apart, no retry. |
| `tools/shipdata/chain.py` | `spike/chain.sh` (`20e0167f…`, `2565767`) | Step order, arguments and numbers as text, as chain.sh passed them. Byte-equal to holo-v3 (TASKS.md, T12.1 findings). |
| `tools/shipdata/diff.py`, `stages.py` (verify) | `spike/compare_built.py` (`8d2a0857…`) | Comparison without `source`, byte equality per file. |
| `tools/shipdata/compare.py` | `spike/compare.py` (`f6c192b6…`) | Pixel share and share > 8. SSIM is left out (S12.0 finding 4). |
| `tools/shipdata/log.py` | `spike/say.sh` (`82403faa…`) | checked / found / to do, `numbers.tsv`. |
| `tools/local-wsl.sh` | `spike/local-wsl.sh` (`a1f619ae…`) | Toolchain with the pins, then `run.py` in place. |

## Test fixtures

`tests/fixtures/import/` comes unchanged from `sc-cargoplan@v0.5.1`, `tests/CargoPlan.Core.Tests/TestMotherlode/`.
These are synthetic test ships (TEST_*), not game data:

| File | SHA-256 |
|---|---|
| `overlap.json` | `6fd4c1a6583220809d7ead651cfee3c832447761cddd390df0ea75411f6e56af` |
| `ship-outlines.json` | `511b64dcc94582e6b877845b7aeab5a0cf5b6ad83901eda955e42aef32bc9c4a` |
| `ships/overlap_ship.json` | `f8918aeba626979e1c6a9f7ec250e84f877728f58b5ba000a8426d209ac6b524` |

Real catalogs are never committed (A17). They live only in the gitignored `cache/catalogs/<date>/raw/`:
- 16 Nov from `sc-ship-outlines/motherlode`;
- 17 Nov from the Actions cache of S12.0, rescued encrypted (plan T12.1, step 0).

## Secrets scan

Before the copy and once more on every file brought in (17 Nov 2026), these patterns were searched:
- `Bearer [A-Za-z0-9]`
- `api[_-]?key\s*[:=]\s*['"][^'"$]`
- `gh[pousr]_`
- `eyJ` (JWT)
- the key prefix `mlk_`
- long hex/base64 values assigned to key/token/secret

There were **0 hits** in `tools/`, `tests/fixtures/`, the two catalog archives or the rescued Actions cache. The only
mentions name the variable `MOTHERLODE_API_KEY`. The key file `sc-ship-outlines/motherlode/api-key.txt` is gitignored
there, was never committed and was not copied.
