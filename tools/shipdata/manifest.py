"""manifest.json of a data release (draft, docs/manifest-format.md; ratified in T12.0). Written from a staged release
folder (ships/, outlines.json, holo/), read back at the boundary (a release asset) with its required fields checked."""
import hashlib
import json
from pathlib import Path

from shipdata.diff import racks_hash

SCHEMA_VERSION = 6              # ship JSON, ShipLoader.SupportedSchemaVersion of the app; a bump only with an app release
HOLO_FORMAT_VERSION = 2         # SCH2, docs/holo-format.md of the app
REQUIRED = ('dataVersion', 'schemaVersion', 'generatedAt', 'builtFrom', 'files', 'holo', 'ships')


class ManifestError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_files(stage: Path) -> list[str]:
    """Every file of the release except holograms and the manifest, as relative POSIX paths."""
    return sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*')
                  if p.is_file() and p.suffix != '.holo' and p.name not in ('manifest.json', 'NOTICE.md'))


def build(stage: Path, *, data_version: str, generated_at: str, motherlode: dict, app_tag: str, pipeline_commit: str,
          tools: dict, holo_ships: dict[str, dict] | None, ships: dict[str, dict]) -> dict:
    """holo_ships: slug -> {model, rawSha256, budget, triangles, edges, passed, fails, metrics}; file, bytes and sha256 are taken
    from stage/holo/<slug>.holo. None is the kill switch (holo: null). ships: id -> {missingSince, follows, orderKeys}; source,
    modelKey and racksSha256 come from the ship file; orderKeys (the catalog's grid order, SD2) from `ships` too, None when
    the order is not known (a ship not written from a catalog yet)."""
    holo = None
    if holo_ships is not None:
        files = {p.stem: p for p in sorted((stage / 'holo').glob('*.holo'))} if (stage / 'holo').exists() else {}
        if sorted(files) != sorted(holo_ships):
            raise ManifestError(f'holo files and entries differ: {sorted(set(files) ^ set(holo_ships))}')
        holo = {'formatVersion': HOLO_FORMAT_VERSION, 'ships': {
            slug: dict({'file': f'holo/{slug}.holo', 'bytes': files[slug].stat().st_size, 'sha256': sha256(files[slug])},
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
            'files': {rel: sha256(stage / rel) for rel in data_files(stage)}, 'holo': holo, 'ships': entries}


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
    # F1 (T12.1b): the judge's case 5 compares with the last release's fails.
    no_fails = [s for s, e in sorted(((m['holo'] or {}).get('ships') or {}).items()) if not isinstance(e.get('fails'), list)]
    if no_fails:
        raise ManifestError(f'{path}: hologram entries without fails: {", ".join(no_fails[:8])}')
    bad_order = [s for s, e in sorted(m['ships'].items()) if 'orderKeys' not in e or not (
        e['orderKeys'] is None or (isinstance(e['orderKeys'], list) and all(isinstance(k, str) for k in e['orderKeys'])))]
    if bad_order:
        raise ManifestError(f'{path}: orderKeys: {", ".join(bad_order[:8])} (each a list of strings or null)')
    return m


def check(stage: Path, m: dict) -> list[str]:
    """Every file against the manifest; files on disk that the manifest does not name are problems too."""
    problems = []
    for rel, digest in sorted(m['files'].items()):
        p = stage / rel
        if not p.exists():
            problems.append(f'{rel}: missing')
        elif sha256(p) != digest:
            problems.append(f'{rel}: SHA-256 differs from the manifest')
    problems += [f'{rel}: not in the manifest' for rel in data_files(stage) if rel not in m['files']]
    for slug, e in sorted(((m.get('holo') or {}).get('ships') or {}).items()):
        p = stage / e['file']
        if not p.exists() or p.stat().st_size != e['bytes'] or sha256(p) != e['sha256']:
            problems.append(f"{e['file']}: size or SHA-256 differs from the manifest")
    return problems
