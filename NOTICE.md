# Ship data – source and license note

Data for SC-CargoPlan, published as a data release `ships-YYYY.MM[.N]` of this repository: `ships.zip` with the ships'
cargo racks (`ships/`) and their outlines (`outlines.json`), one hologram per ship (`<slug>.holo`) and `manifest.json`.
The app downloads them on its own; the holograms one file per ship, when the player picks that ship and the setting
"Download ship holograms" is on.

**Source:** cargo grid data and ship models from cryon.rocks (Motherlode), extracted from the Star Citizen game files;
CIG assets, non-commercial fan project. The operators of Motherlode agreed to this use (Discord).
- **Racks:** the game's cargo grids, laid in ship cells (1 cell = 1 SCU = 1.25 m).
- **Outlines:** top views of the ship models: every triangle filled into a raster, small gaps closed, the outer contour
  simplified; they keep the model's origin and size.
- **Holograms:** the models turned into the ship's axes, interior removed, simplified and converted to the SCH2 format
  described in SC-CargoPlan's `docs/holo-format.md`; they keep the game model's origin and size.

A few ships still use data derived from fleetyards.net (Fleetyards agreed to this use by e-mail on 23 October 2026):
the ships whose `source` names Fleetyards, and the outline entries without `floorM`. A ship that left Motherlode's
catalog keeps its last data; `manifest.json` names it with `missingSince`.

**Hauling data** (`hauling-templates.json`, `positions.json`): the hauling contract templates of Covalex and Red Wind
Linehaul and the positions of stations, planets and the places the templates name, from the Star Citizen game files
(CIG material), extracted with [octfx/ScDataDumper](https://github.com/octfx/ScDataDumper) and published by the Star
Citizen Wiki as [StarCitizenWiki/scunpacked-data](https://github.com/StarCitizenWiki/scunpacked-data) - the same
extraction [api.star-citizen.wiki](https://api.star-citizen.wiki) serves. Normalized for SC-CargoPlan: some place names
mapped to the starmap's names, placeholder texts left out, templates without a fixed SCU band left out; nothing is
estimated.

Thanks to Motherlode, Fleetyards, the Star Citizen Wiki and octfx. Not affiliated with Motherlode, Fleetyards, the Star
Citizen Wiki or CIG.

Star Citizen ships are the intellectual property of Cloud Imperium Rights LLC / Cloud Imperium Rights Ltd. These data
are **not** covered by the MIT license of this repository's code (`LICENSE`). They will be withdrawn on request of CIG,
Motherlode, Fleetyards or the Star Citizen Wiki: the release's files are deleted, and the next release sets `holo` (or
`hauling`) to `null` in its manifest, so the app shows the flat outline instead (or plans routes from scans only).
