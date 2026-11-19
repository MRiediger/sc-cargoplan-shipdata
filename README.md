# sc-cargoplan-shipdata

Ship data for [SC-CargoPlan](https://github.com/MRiediger/sc-cargoplan): cargo racks, outlines and holograms of every
Star Citizen ship, built each month from the Motherlode catalog (cryon.rocks) and published as a data release
`ships-YYYY.MM[.N]` ([releases](https://github.com/MRiediger/sc-cargoplan-shipdata/releases)). The app checks for a newer
release on start and offers it; nobody installs anything by hand.

## What happens on the 1st

The workflow `ship-data.yml` runs on the 1st of every month at 04:23 UTC (next: **1 Dec**). It calls the Motherlode API
once, compares the catalog with the last release and ends in one of three ways:

| Result | What you see | What you do |
|---|---|---|
| **nothing** changed | a commit `data: heartbeat … - nothing changed` | nothing |
| **release** | a new release `ships-YYYY.MM[.N]`, marked *Latest*; the app shows *Ship data update available* | nothing |
| **PR** | a pull request from `data/YYYY.MM`: a rule fired and wants a decision | see [When a PR comes](#when-a-pr-comes) |

A run can also end **red** (`gate-red` or `error`): GitHub sends a mail, nothing is published, the last release stays
valid. That means the pipeline itself is wrong, not the data; the fix is a code change.

Every run, red ones included, writes one line to [`state/last-run.json`](state/last-run.json) (`result`, `line`, the
link to the run). That file is the first place to look.

## When a PR comes

**A data PR** (branch `data/YYYY.MM`, opened by the pipeline) means: the new data are built and the render gate is
green, but a rule wants a human (a new ship, a ship that changed its source, a hologram that got worse, grids in another
order, more than three ships gone – see `CLAUDE.md` for the rules).

1. Read the table in the PR: one row per stop, with the rule and the numbers before and after.
2. Look at the contact sheets: they hang on the **draft release** of the same name (Releases, visible only to you), old
   and new picture side by side, the stopped ships first.
3. Decide:
   - **Merge** = publish. The merge starts the job `publish-merged`, which publishes exactly the draft the PR names
     (checked by its manifest hash). If the PR proposes entries for `overrides.json`, they come with the merge.
   - **Close** = publish nothing. The last release stays. The next run replaces the draft and opens a new PR if the rule
     still fires.
4. If the PR lists **grid findings**, report them to Motherlode as well (see below): the grids come from the game files.

You never type a command for a data PR. If a step needs one, that is a bug in the pipeline.

**A code PR** (someone changes `tools/`, `tests/` or the workflow): there is no CI for pull requests yet, so run the tests
locally (`tools/local-wsl.sh test`, below) before merging. Changes go through a branch and a merge commit.

**A PR with a ship file** cannot be taken: this repository holds no ship files. Every file is rebuilt each month from the
game files, so a hand-edited file would be overwritten by the next run. Close it with a pointer to an issue.

## Reporting a wrong grid

A rack in the wrong place, with the wrong size or stacking the wrong way is almost always in the game data itself.

1. Open an issue [here](https://github.com/MRiediger/sc-cargoplan-shipdata/issues) (players can also use the
   *Ship correction* form of the [app](https://github.com/MRiediger/sc-cargoplan/issues/new/choose)).
2. Report it to Motherlode ([cryon.rocks](https://cryon.rocks)), who asked for reports of grids that look wrong in the
   game.

Once Motherlode's catalog is fixed, the next monthly run picks it up and every user gets it with the next data release.

## Pins and pin bumps

The run is reproducible only with the same tool versions. Each pin has one machine-readable source;
[`TOOLS.md`](TOOLS.md) is the copy for people, and `tests/test_versions.py` fails when they disagree.

| Pin | Source |
|---|---|
| Python, Node.js | `.python-version`, `.nvmrc` |
| numpy, OpenCV, pytest | `tools/requirements.txt`, `tools/requirements-dev.txt` |
| meshoptimizer | `tools/package-lock.json` |
| runner, PowerShell, app version for the gate | `tools/pins.json` (`runner`, `pwsh`, `appTag`) |

- **A tool pin bump is a task of its own**, never a drive-by change: bump, run `build --all` on every model, measure
  which holograms and files change, and write the numbers down. A new version can change every hologram by a few bytes.
- **`appTag`** (the app version that renders the gate) is stuck at `v0.5.1` until the gate is rebuilt: since v0.6.0 the
  app repo has no `ships/` folder for the gate to swap. See SD3 in [`docs/decisions.md`](docs/decisions.md).
- The app pins its built-in data release in `build/ship-data.json` of the app repo; that bump is an app change.

## Licenses

- **Code** (`tools/`, `tests/`, workflows): MIT, see [`LICENSE`](LICENSE).
- **Data** (ship files, outlines, holograms in the releases): derived from Star Citizen game files and **not** covered
  by the MIT license. See [`NOTICE.md`](NOTICE.md).

Catalogs, models, pictures and holograms are never committed to this repository. They live only in the gitignored
`cache/` and in release assets.

## How the run works

| Job | Runner | Does |
|---|---|---|
| `chain` | ubuntu-24.04 | tests, `fetch` (the one API call), `previous`, `diff`, `build`, `verify --ci`, `draft` (the release as a draft, `manifest.json` uploaded last) |
| `gate` | windows-latest | renders the last release and the draft with the same app (`sc-cargoplan` at `appTag`), hash-exact; contact sheets to the draft |
| `publish` / `pr` | ubuntu-24.04 | after a green gate: publish the draft (the last two releases stay), or open the PR |
| `publish-merged` | ubuntu-24.04 | on the merge of a data PR (push of `state/pending.json`): publishes exactly the draft the PR named |
| `heartbeat` | ubuntu-24.04 | `state/last-run.json`, committed in every run |

A release has four kinds of assets: `manifest.json` (the contract with the app, [`docs/manifest-format.md`](docs/manifest-format.md)),
`NOTICE.md`, `ships.zip` (ship files and outlines) and one `<slug>.holo` per ship. Artifacts of a run carry reports
only, never game data.

One entry point, `tools/run.py`, with the stages handing on through `work/`:

| Stage | Does |
|---|---|
| `fetch` | the catalog (one API call, or saved answers); model URLs from the cargo page; models cached by hash |
| `diff` | the import writes the racks; ship files compared without their stamps: new, changed, gone, models separately |
| `build` | holograms of changed and new models (or `--all` / `--ship`): flatten, cull, ladder 20k/30k/40k, export, outline; then outlines and anchors |
| `verify` | the rules (gone ships, variants, overlap, missing transform, judge), the manifest, every file against it |
| `release` | `--dry-run`: the staged release and its assets; `--seed`: the first release from the app and a hologram release |

Around them for the workflow: `pins`, `previous`, `draft`, `gate`, `publish`, `pr`, `heartbeat`
(`python -I tools/run.py --help`). Exit codes: 0 done, 1 error, 2 a rule fired (PR path). Every stage ends with three
lines, *checked / found / to do*, on the screen and in the job summary.

Repository settings the run needs: secret `MOTHERLODE_API_KEY`; Settings > Actions > General > Workflow permissions >
**Allow GitHub Actions to create and approve pull requests** (SD12); releases not immutable (the run deletes releases
older than the last two).

### Local runs

WSL Ubuntu 24.04 with the pinned tools:

```bash
wsl -d Ubuntu-24.04 -u root -- bash tools/local-wsl.sh setup     # pinned toolchain (TOOLS.md)
wsl -d Ubuntu-24.04 -u root -- bash tools/local-wsl.sh test      # pytest
wsl -d Ubuntu-24.04 -u root -- bash tools/local-wsl.sh run fetch --saved cache/catalogs/2026-11-17/raw
```

`gh workflow run ship-data.yml -f dry-run=true` runs the chain up to `verify` without a draft, a release or a commit (it
calls the API once).
