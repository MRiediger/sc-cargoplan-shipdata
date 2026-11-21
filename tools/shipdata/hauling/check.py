"""The two hauling files against schema 1: the app's loader checks (sc-cargoplan/docs/hauling-data-format.md, "Checks of
the loader", with K2: legs >= 1, and K3: names unique per system) plus the pipeline's own rules (enums, sorting, source
fields), and the manifest section `hauling` with length and SHA-256 of each file (as for holograms)."""
from pathlib import Path

from shipdata import manifest
from shipdata.hauling import positions as ps
from shipdata.hauling import templates as ts

SCHEMA_VERSION = 1
TEMPLATES_FILE = manifest.HAULING_FILES['templates']
POSITIONS_FILE = manifest.HAULING_FILES['positions']
FILES = (TEMPLATES_FILE, POSITIONS_FILE)
SOURCE = {TEMPLATES_FILE: ('repository', 'commit', 'gameBuild', 'fetchedAt'),            # V1
          POSITIONS_FILE: ('repository', 'file', 'commit', 'fetchedAt')}
ENUMS = {'contractor': tuple(ts.CONTRACTORS.values()), 'rank': ts.RANKS, 'size': ts.SIZE_VALUES, 'shape': ts.SHAPES,
         'missionType': ts.MISSION_TYPES, 'faction': (None, *ts.FACTIONS), 'system': (None, 'stanton', 'pyro')}


def number(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def head(doc: dict, file: str) -> list[str]:
    out = []
    if doc.get('schemaVersion') != SCHEMA_VERSION:
        out.append(f"{file}: schemaVersion {doc.get('schemaVersion')}, schema {SCHEMA_VERSION} expected")
    out += [f'{file}: source.{k} missing' for k in SOURCE[file] if not isinstance((doc.get('source') or {}).get(k), str)]
    return out


def problems(templates: dict, positions: dict) -> list[str]:
    out = head(templates, TEMPLATES_FILE) + head(positions, POSITIONS_FILE)
    if templates.get('dataVersion') != positions.get('dataVersion'):
        out.append(f"dataVersion differs: {templates.get('dataVersion')} / {positions.get('dataVersion')}")
    pos = positions.get('positions') or []
    names: dict[str, set[str]] = {}
    for x in pos:
        if x.get('system') not in ps.SYSTEMS:
            out.append(f"position {x.get('name')!r}: system {x.get('system')!r}")
        for k in ('x', 'y', 'z'):
            if not number(x.get(k)):
                out.append(f"position {x.get('name')!r}: {k} {x.get(k)!r} is not a number")
        if not isinstance(x.get('contractNames', []), list):
            out.append(f"position {x.get('name')!r}: contractNames is not a list")
        seen = names.setdefault(x.get('system'), set())
        if x.get('name') in seen:
            out.append(f"position {x.get('name')!r} twice in {x.get('system')} (K3)")
        seen.add(x.get('name'))
    keys = [(x.get('system') or '', x.get('name') or '') for x in pos]
    if keys != sorted(keys):
        out.append(f'{POSITIONS_FILE}: not sorted by system, then name')
    everywhere = set().union(*names.values()) if names else set()
    tpls = templates.get('templates') or []
    uuids = [x.get('uuid') for x in tpls]
    if uuids != sorted(set(uuids)):
        out.append(f'{TEMPLATES_FILE}: not sorted by uuid or not unique')
    for x in tpls:
        u = x.get('uuid')
        out += [f"{u}: {k} {x.get(k)!r} unknown" for k, allowed in ENUMS.items() if x.get(k) not in allowed]
        if x.get('shape') == 'aToB' and x.get('stops') != 1:
            out.append(f"{u}: aToB with {x.get('stops')} stops")
        if not isinstance(x.get('stops'), int) or x['stops'] < 1:
            out.append(f"{u}: stops {x.get('stops')!r}")
        if not x.get('legs'):
            out.append(f'{u}: no legs')
        for g in x.get('legs') or []:
            lo, hi, box = g.get('minScu'), g.get('maxScu'), g.get('containerScu')
            if not isinstance(lo, int) or lo < 1:
                out.append(f'{u}: minScu {lo!r}')
            elif not isinstance(hi, int) or lo > hi:
                out.append(f'{u}: minScu {lo} > maxScu {hi}')
            if box not in ts.CONTAINERS:
                out.append(f'{u}: containerScu {box!r}')
        system = x.get('system')
        known = names.get(system, set()) if system else everywhere
        for key in ('pickupPool', 'dropoffPool'):
            out += [f"{u}: {key} {n!r} has no position in {system or 'any system'}" for n in x.get(key) or [] if n not in known]
    return out


def section(folder: Path) -> dict:
    """The manifest section of the two files in `folder` (hauling-data-format.md, "Manifest section hauling")."""
    def entry(name: str) -> dict:
        q = folder / name
        return {'file': name, 'bytes': q.stat().st_size, 'sha256': manifest.sha256(q)}
    return {'schemaVersion': SCHEMA_VERSION, 'templates': entry(TEMPLATES_FILE), 'positions': entry(POSITIONS_FILE)}


def file_problems(folder: Path, sec: dict) -> list[str]:
    out = []
    for key in ('templates', 'positions'):
        e = sec[key]
        q = folder / e['file']
        if not q.exists():
            out.append(f"{e['file']}: missing")
        elif q.stat().st_size != e['bytes'] or manifest.sha256(q) != e['sha256']:
            out.append(f"{e['file']}: length or SHA-256 differs from the manifest")
    return out
