# manifest.json of a data release

**Status: ratified with SD2 (T12.0, 18 Nov 2026).** Written by `run.py verify` (and `release --seed`) with
`tools/shipdata/manifest.py`, and read back there with its required fields checked. Drafted in T12.1; `orderKeys`,
`assets` and the flat hologram paths were added in T12.0 (decisions D2, D3 of the T12.1 review) – their writer and
reader come with T12.1b.

A data release `ships-YYYY.MM[.N]` has these assets, all flat (SD4; GitHub assets cannot be folders):

| Asset | Content |
|---|---|
| `manifest.json` | this file; the app reads it first, from `…/releases/latest/download/manifest.json` |
| `NOTICE.md` | licence of the data and holograms (CIG material, not MIT) |
| `ships.zip` | `ships/**` and `outlines.json` – the one archive the app downloads |
| `<slug>.holo` | one hologram per slug, loaded lazily per ship, as from holo-v3 |

```json
{
 "dataVersion": "ships-2026.11",
 "schemaVersion": 6,
 "generatedAt": "2026-11-17T04:23:00Z",
 "builtFrom": {
  "motherlode": {"gameBuild": "4.10.3-LIVE.13165946", "updatedAt": "2026-11-16T11:36:30.299Z"},
  "appTag": "v0.5.1",
  "pipelineCommit": "c823a5e",
  "tools": {"python": "3.14.5", "numpy": "2.5.3", "opencv": "5.0.0.93", "node": "24.16.0",
            "meshoptimizer": "1.3.0", "pwsh": "7.6.10"}
 },
 "assets": {"ships": "ships.zip"},
 "files": {"outlines.json": "<sha256>", "ships/100i.json": "<sha256>", "ships/modules/ts_module.json": "<sha256>"},
 "holo": {
  "formatVersion": 2,
  "ships": {
   "orig-100i": {"file": "orig-100i.holo", "bytes": 93794, "sha256": "f05c9c4f…", "model": "ORIG_100i",
                 "rawSha256": "da8168ea3720…", "budget": 20000, "triangles": 6699, "edges": [..],
                 "passed": true, "metrics": {"errorM": 0.0, "topIou": 1.0, "…": "…"}}
  }
 },
 "ships": {
  "100i": {"source": "cryon.rocks (Motherlode) 4.10.3-LIVE.13165946, 2026-11-16T11:36:30.299Z",
           "modelKey": "orig-100i", "racksSha256": "<sha256>", "orderKeys": ["2x2x1@-1.6,0.0,0.4"],
           "missingSince": null, "follows": null}
 }
}
```

| Field | Meaning | Why (S12.0 question 5 and T12.1) |
|---|---|---|
| `dataVersion` | Tag of the release. `outlines.json` carries it as its stamp. | The app shows it; it is the cache key. |
| `schemaVersion` | Version of the ship JSON, today **6** (`ShipLoader.SupportedSchemaVersion`). The app turns down a release with a version it does not know ("Ship data needs app update"). | A bump only together with an app release. |
| `generatedAt` | When the run wrote the release (UTC). Also the stamp of `outlines.json`. | |
| `builtFrom.motherlode` | `gameBuild` **and** `updatedAt` of the catalog. `--seed` reads both from the ships' `source` lines (condition D). | A re-export comes without a build change (S12.0). The catalog's SHA does not work as a signal: it changes with every fetch. |
| `builtFrom.appTag` | The app version the gate renders with. | Gate checkout (S12.0, K1). |
| `builtFrom.pipelineCommit` | Short Git SHA of this repo. | Without it a hologram is not reproducible (T12.0). |
| `builtFrom.tools` | Versions as measured in the run. | Byte equality depends on the pins (S12.0). |
| `assets` | Asset name of each archive, today only `ships` → `ships.zip`. | The app and `diff --previous` download exactly this archive and the manifest (D3). |
| `files` | `path: sha256` for every file except holograms, manifest and NOTICE. The paths are the paths **inside `ships.zip`**. | The app checks every file it unpacks. |
| `holo` | `null` is the kill switch: the app shows the outline. Otherwise `formatVersion` (SCH2 = 2) and one entry per slug. | The app checks `formatVersion`, `bytes` and `sha256` (S12.0). |
| `holo.ships.<slug>.file` | Asset name of the hologram, flat: `<slug>.holo`. Its URL is `…/releases/download/<dataVersion>/<file>`. | Every release carries all holograms (only the last two releases stay), so the URL follows from `dataVersion` (SD2, SD4). |
| `holo.ships.<slug>.model`, `rawSha256` | The className and the SHA-256 of the model the hologram was built from. Holograms kept from holo-v1 say `fleetyards (holo-v1)`. | `diff` compares it with the hash in the catalog's model URL. That is how a re-export is noticed. |
| `holo.ships.<slug>.budget … metrics` | The judge's numbers, as in the holo-v3 manifest. | The judge compares with the last release: only a change for the worse in a metric stops (SD5, replaces P9). |
| `ships.<id>.source` | Copy of the ship file's stamp. It is never compared (condition C). | |
| `ships.<id>.modelKey` | Hologram and outline of the ship. | The import's key map (P6). |
| `ships.<id>.racksSha256` | SHA-256 of the racks alone. | Rule "variant": a gone variant whose racks were equal to its base ship's takes the base's data (SD6). |
| `ships.<id>.orderKeys` | The ship's grids in catalog order, one `size@x,y,z` each (the import's `OrderKey`: grid size and the catalog transform's translation in the game frame, metres, one decimal; `""` for a grid without transform). | `diff` compares grid order with the last release instead of the last catalog: the same grids in another order would move cargo in saved plans to other racks (app V1, 350r). Derived like `racksSha256`; the catalog stays out of releases and caches (D2, SD7). |
| `ships.<id>.missingSince` | Date of the first run that no longer found the ship in the catalog; otherwise `null`. | Rule "gone": the ship is never deleted. After 3 runs it gets a backlog line. Back in the catalog → `null` again (SD6, rule "back"). |
| `ships.<id>.follows` | The base ship whose data a gone variant takes; otherwise `null`. | Rule "variant"; back in the catalog → `null` (SD6). |

Not in the manifest, on purpose:
- the runner image: hashes are the same across machines;
- a picture threshold: the gate is hash-exact (S12.0, finding 4);
- the catalog's SHA;
- the previous catalog, or anything copied from it beyond derived values (A17, SD7);
- holo `baseUrl`: dropped for good (SD2). Every release holds all its holograms, so the download URL follows from
  `dataVersion`; the app (T12.4) builds it that way.
