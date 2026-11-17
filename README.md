# sc-cargoplan-shipdata

Ship data for [SC-CargoPlan](https://github.com/MRiediger/sc-cargoplan): cargo racks, outlines and holograms of every
Star Citizen ship, built by a pipeline from the Motherlode catalog (cryon.rocks) and published as data releases
`ships-YYYY.MM[.N]`. The app downloads them on its own.

Status: Phase 12, T12.1. The pipeline runs locally (WSL Ubuntu 24.04). The monthly workflow comes with T12.2.

## The pipeline

One entry point, `tools/run.py`, five stages. They hand on through `work/`:

| Stage | Does | Writes |
|---|---|---|
| `fetch` | The catalog: one API call (or saved answers). Model URLs come from the cargo page. Models are cached by hash; a model that is gone (404) counts as unavailable. | `work/catalog.json`, `cache/models/` |
| `diff` | Against the last release: the import writes the racks, then compares ship files without their stamps. Reports new, changed and gone ships, and model changes separately. | `work/ships/`, `work/diff.json` |
| `build` | Builds the changed and new models (or `--all` / `--ship`): flatten, cull, ladder 20k/30k/40k, export, outline. Then the outlines, and the anchors through the import. | `work/holo/`, `work/outlines.json` |
| `verify` | Applies the rules (gone ships, variants, overlap, missing transform, judge), writes the manifest and checks every file against it. | `work/stage/`, `work/verify.json` |
| `release` | `--dry-run`: copies the staged release and lists its assets. `--seed`: builds the first release folder from the app and a hologram release. | `out/release/`, `out/seed/` |

Exit codes: 0 done, 1 error, 2 a rule fired. Exit 2 sends the run to the PR path: no release, a PR with the findings.
Every stage ends with three lines, *checked / found / to do*, on the screen and in the job summary.

```bash
wsl -d Ubuntu-24.04 -- bash tools/local-wsl.sh setup     # pinned toolchain (TOOLS.md)
wsl -d Ubuntu-24.04 -- bash tools/local-wsl.sh test      # pytest
wsl -d Ubuntu-24.04 -- bash tools/local-wsl.sh run fetch --saved cache/catalogs/2026-11-17/raw
```

## Licenses

- **Code** (`tools/`, `tests/`, workflows): MIT, see `LICENSE`.
- **Data** (ship files, outlines, holograms in the releases): derived from Star Citizen game files and **not** covered
  by the MIT license. See `NOTICE.md`.

Catalogs, models, pictures and holograms are never committed to this repository. They live only in the gitignored
`cache/` and in release assets.
