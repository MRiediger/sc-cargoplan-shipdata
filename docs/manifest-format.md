# manifest.json of a data release – draft

**Status: draft from T12.1.** T12.0 ratifies it together with SD2. Written by `run.py verify` (and `release --seed`)
with `tools/shipdata/manifest.py`, and read back there with its required fields checked.

A data release `ships-YYYY.MM[.N]` holds `ships/`, `outlines.json`, `holo/<slug>.holo`, `manifest.json` and
`NOTICE.md`. The manifest describes every other file. The app reads it first, from
`…/releases/latest/download/manifest.json`.

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
 "files": {"outlines.json": "<sha256>", "ships/100i.json": "<sha256>", "ships/modules/ts_module.json": "<sha256>"},
 "holo": {
  "formatVersion": 2,
  "ships": {
   "orig-100i": {"file": "holo/orig-100i.holo", "bytes": 93794, "sha256": "f05c9c4f…", "model": "ORIG_100i",
                 "rawSha256": "da8168ea3720…", "budget": 20000, "triangles": 6699, "edges": [..],
                 "passed": true, "metrics": {"errorM": 0.0, "topIou": 1.0, "…": "…"}}
  }
 },
 "ships": {
  "100i": {"source": "cryon.rocks (Motherlode) 4.10.3-LIVE.13165946, 2026-11-16T11:36:30.299Z",
           "modelKey": "orig-100i", "racksSha256": "<sha256>", "missingSince": null, "follows": null}
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
| `files` | `path: sha256` for every file except holograms, manifest and NOTICE. | The app checks every download. |
| `holo` | `null` is the kill switch: the app shows the outline. Otherwise `formatVersion` (SCH2 = 2) and one entry per slug. | The app checks `formatVersion`, `bytes` and `sha256` (S12.0). |
| `holo.ships.<slug>.model`, `rawSha256` | The className and the SHA-256 of the model the hologram was built from. Holograms kept from holo-v1 say `fleetyards (holo-v1)`. | `diff` compares it with the hash in the catalog's model URL. That is how a re-export is noticed. |
| `holo.ships.<slug>.budget … metrics` | The judge's numbers, as in the holo-v3 manifest. | The judge compares with the last release: only a change for the worse stops (P9). |
| `ships.<id>.source` | Copy of the ship file's stamp. It is never compared (condition C). | |
| `ships.<id>.modelKey` | Hologram and outline of the ship. | The import's key map (P6). |
| `ships.<id>.racksSha256` | SHA-256 of the racks alone. | Rule "variant": a gone variant whose racks were equal to its base ship's takes the base's data. |
| `ships.<id>.missingSince` | Date of the first run that no longer found the ship in the catalog; otherwise `null`. | Rule "gone": the ship is never deleted. After 3 runs it gets a backlog line. |
| `ships.<id>.follows` | The base ship whose data a gone variant takes; otherwise `null`. | Rule "variant". |

Not in the manifest, on purpose:
- the runner image: hashes are the same across machines;
- a picture threshold: the gate is hash-exact (S12.0, finding 4);
- the catalog's SHA;
- holo `baseUrl`: the release's download URL follows from `dataVersion`. The app side (T12.4) decides whether it needs
  the URL spelled out.
