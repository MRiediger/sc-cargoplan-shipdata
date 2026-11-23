"""manifest.json of a data release (docs/manifest-format.md, ratified with SD2). Written from a staged release folder
(ships/, outlines.json, <slug>.holo flat as the assets, SD4), read back at the boundary (a release asset) with its
required fields checked."""
import hashlib
import json
from pathlib import Path

from shipdata.diff import racks_hash

SCHEMA_VERSION = 6              # ship JSON, ShipLoader.SupportedSchemaVersion of the app; a bump only with an app release
HOLO_FORMAT_VERSION = 2         # SCH2, docs/holo-format.md of the app
REQUIRED = ('dataVersion', 'schemaVersion', 'generatedAt', 'builtFrom', 'assets', 'files', 'holo', 'ships')
SHIPS_ZIP = 'ships.zip'         # the one archive the app downloads: ships/** and outlines.json (SD4)
# Flat assets of their own with the section `hauling` (H1, SD14, SD2 addendum): not in files, not in ships.zip - the
# manifest readers of app v0.6.0/v0.7.0 accept only outlines.json and ships/** in files (hauling-data-format.md).
HAULING_FILES = {'templates': 'hauling-templates.json', 'positions': 'positions.json'}


class ManifestError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_files(stage: Path) -> list[str]:
    """Every file of the release except holograms and the manifest, as relative POSIX paths."""
    return sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*')
                  if p.is_file() and p.suffix != '.holo' and p.relative_to(stage).as_posix() not in
                  ('manifest.json', 'NOTICE.md', *HAULING_FILES.values()))


def build(stage: Path, *, data_version: str, generated_at: str, motherlode: dict, app_tag: str, pipeline_commit: str,
          tools: dict, holo_ships: dict[str, dict] | None, ships: dict[str, dict], hauling: dict | None = None) -> dict:
    """holo_ships: slug -> {model, rawSha256, budget, triangles, edges, passed, fails, metrics}; file, bytes and sha256 are taken
    from stage/<slug>.holo, which is also the asset's name. None is the kill switch (holo: null). ships: id -> {missingSince, follows, orderKeys}; source,
    modelKey and racksSha256 come from the ship file; orderKeys (the catalog's grid order, SD2) from `ships` too, None when
    the order is not known (a ship not written from a catalog yet). hauling: the section of the two hauling files in the
    stage (hauling.check.section), None when this release has none (written as null)."""
    holo = None
    if holo_ships is not None:
        files = {p.stem: p for p in sorted(stage.glob('*.holo'))}
        if sorted(files) != sorted(holo_ships):
            raise ManifestError(f'holo files and entries differ: {sorted(set(files) ^ set(holo_ships))}')
        holo = {'formatVersion': HOLO_FORMAT_VERSION, 'ships': {
            slug: dict({'file': f'{slug}.holo', 'bytes': files[slug].stat().st_size, 'sha256': sha256(files[slug])},
                       **{k: v for k, v in holo_ships[slug].items() if k not in ('slug', 'file', 'bytes', 'sha256')})
            for slug in sorted(holo_ships)}}
    entries = {}
    for path in sorted((stage / 'ships').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8-sig'))
        extra = ships.get(path.stem, {})
        entries[path.stem] = {'source': doc.get('source'), 'modelKey': doc.get('modelKey'), 'racksSha256': racks_hash(doc),
                              'orderKeys': extra.get('orderKeys'), 'missingSince': extra.get('missingSince'),
                              'follows': extra.get('follows')}
    return {'dataVersion': data_version, 'schemaVersion': SCHEMA_VERSION, 'generatedAt': generated_at,
            'builtFrom': {'motherlode': motherlode, 'appTag': app_tag, 'pipelineCommit': pipeline_commit, 'tools': tools},
            'assets': {'ships': SHIPS_ZIP}, 'files': {rel: sha256(stage / rel) for rel in data_files(stage)}, 'holo': holo,
            'hauling': hauling, 'ships': entries}


def write(path: Path, m: dict) -> None:
    path.write_text(json.dumps(m, indent=1) + '\n', encoding='utf-8', newline='\n')


def read(path: Path) -> dict:
    try:
        m = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f'{path}: not readable as JSON: {e}') from e
    missing = [k for k in REQUIRED if k not in m]
    if missing:
        raise ManifestError(f'{path}: required fields missing: {", ".join(missing)}')
    if m['schemaVersion'] != SCHEMA_VERSION:
        raise ManifestError(f'{path}: schemaVersion {m["schemaVersion"]}, this pipeline writes {SCHEMA_VERSION}')
    if not isinstance(m['assets'], dict) or not isinstance(m['assets'].get('ships'), str) or '/' in m['assets']['ships']:
        raise ManifestError(f'{path}: assets.ships must name one flat asset, is {m["assets"]!r}')
    # F1 (T12.1b): the judge's case 5 compares with the last release's fails.
    no_fails = [s for s, e in sorted(((m['holo'] or {}).get('ships') or {}).items()) if not isinstance(e.get('fails'), list)]
    if no_fails:
        raise ManifestError(f'{path}: hologram entries without fails: {", ".join(no_fails[:8])}')
    h = m.get('hauling')        # optional (SD2 addendum H1): releases before H1 have none
    if h is not None and not (isinstance(h, dict) and isinstance(h.get('schemaVersion'), int) and all(
            isinstance(h.get(k), dict) and h[k].get('file') == f and isinstance(h[k].get('bytes'), int)
            and isinstance(h[k].get('sha256'), str) for k, f in HAULING_FILES.items())):
        raise ManifestError((f'{path}: hauling must be null or {{schemaVersion, templates, positions}} with the flat files '
                             f"{', '.join(HAULING_FILES.values())}, is {h!r}")[:300])
    bad_order = [s for s, e in sorted(m['ships'].items()) if 'orderKeys' not in e or not (
        e['orderKeys'] is None or (isinstance(e['orderKeys'], list) and all(isinstance(k, str) for k in e['orderKeys'])))]
    if bad_order:
        raise ManifestError(f'{path}: orderKeys: {", ".join(bad_order[:8])} (each a list of strings or null)')
    return m


def check(stage: Path, m: dict, holograms: bool = True) -> list[str]:
    """Every file against the manifest; files on disk that the manifest does not name are problems too. holograms=False
    for the unpacked ships.zip of a last release, which diff reads without its holograms (SD4)."""
    problems = []
    for rel, digest in sorted(m['files'].items()):
        p = stage / rel
        if not p.exists():
            problems.append(f'{rel}: missing')
        elif sha256(p) != digest:
            problems.append(f'{rel}: SHA-256 differs from the manifest')
    problems += [f'{rel}: not in the manifest' for rel in data_files(stage) if rel not in m['files']]
    for slug, e in sorted(((m.get('holo') or {}).get('ships') or {}).items()) if holograms else []:
        p = stage / e['file']
        if not p.exists() or p.stat().st_size != e['bytes'] or sha256(p) != e['sha256']:
            problems.append(f"{e['file']}: size or SHA-256 differs from the manifest")
    for e in (m['hauling'][k] for k in HAULING_FILES) if m.get('hauling') and holograms else []:
        p = stage / e['file']
        if not p.exists() or p.stat().st_size != e['bytes'] or sha256(p) != e['sha256']:
            problems.append(f"{e['file']}: length or SHA-256 differs from the manifest")
    return problems
