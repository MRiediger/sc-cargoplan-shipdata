"""diff: what changed against the last release - ship files (racks), new and gone ships, and the models (counted apart: a
re-export comes without a build change, S12.0 finding 1).

Stamps are never compared (condition C): `source` of a ship file and `generatedAt` / `dataVersion` of outlines.json are set
on writing from the run's catalog and manifest, so a new catalog date alone changes nothing (S12.0 run 4: 99 files)."""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

STAMPS = ('source', 'generatedAt', 'dataVersion')


def strip_stamps(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in STAMPS}


def content_hash(doc: dict) -> str:
    """SHA-256 of a document without its stamps, keys sorted: equal content gives equal hashes whatever the formatting."""
    return hashlib.sha256(json.dumps(strip_stamps(doc), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def racks_hash(ship: dict) -> str:
    """SHA-256 of the racks alone: a variant and its base ship with the same racks have the same hash (rule "variant")."""
    return hashlib.sha256(json.dumps(ship.get('racks', []), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def order_map(manifest: dict) -> dict[str, list[str]]:
    """id -> orderKeys of the last release, for the import's -PreviousOrder (SD2: the order is compared with the
    manifest, not with an older catalog). Ships with null are left out: their order is not compared."""
    return {sid: e['orderKeys'] for sid, e in sorted(manifest['ships'].items()) if e.get('orderKeys') is not None}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


@dataclass
class ShipChanges:
    changed: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)
    same: list[str] = field(default_factory=list)


def compare_ships(old_dir: Path, new_dir: Path, absent: list[str]) -> ShipChanges:
    """Ship files of the last release against the ones the import wrote. `absent` are the ids the import found in the
    folder but not in the catalog (gone)."""
    out = ShipChanges(gone=sorted(absent))
    for path in sorted(new_dir.glob('*.json')):
        sid = path.stem
        if sid in absent:
            continue
        old = old_dir / path.name
        if not old.exists():
            out.new.append(sid)
        elif content_hash(load(old)) != content_hash(load(path)):
            out.changed.append(sid)
        else:
            out.same.append(sid)
    return out


def split_gone(absent: list[str], previous: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Ships not in the catalog, split by the last manifest (T12.2, D2): gone for the first time (a change) and gone
    already - missingSince or follows set there (no change; verify carries the date or the base on)."""
    still = sorted(s for s in absent if (previous.get(s) or {}).get('missingSince') or (previous.get(s) or {}).get('follows'))
    return sorted(set(absent) - set(still)), still


@dataclass
class ModelChanges:
    same: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    without_url: list[str] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)


CLASS_NAME = re.compile(r'^[A-Za-z0-9_]+$')


def model_changes(holo_ships: dict[str, dict], catalog: dict, chosen: set[str]) -> ModelChanges:
    """The models the last release built its holograms from (holo.ships: slug -> {model, rawSha256}) against the catalog's
    model URLs, whose file name carries the first 12 hex digits of the model's SHA-256. `chosen` are the classNames that
    show a slug now (holo_mesh.slug_models of the import's model map): one of them without hologram is new; a model with
    a URL that shows no slug (a variant's own, a ship kept as it is) is unused. A hologram whose model has no URL any more
    keeps its file (A11). Entries like 'fleetyards (holo-v1)' name a source, not a model, and are left out."""
    built = {e['model']: e['rawSha256'][:12] for e in holo_ships.values() if CLASS_NAME.match(e.get('model') or '') and e.get('rawSha256')}
    urls = {s['className']: s['modelUrl'].rsplit('/', 1)[-1] for s in catalog['ships'] if s.get('className') and s.get('modelUrl')}
    out = ModelChanges()
    for cls in sorted(set(built) | set(urls)):
        if cls not in urls:
            out.without_url.append(cls)
        elif cls not in built:
            (out.new if cls in chosen else out.unused).append(cls)
        elif urls[cls].endswith(f'-{built[cls]}.glb'):
            out.same.append(cls)
        else:
            out.changed.append(cls)
    return out


def nothing_changed(changes: ShipChanges, models: ModelChanges, back: list[str], order_changed: list[str],
                    import_stops: list[str]) -> bool:
    """True when a run has nothing to release (heartbeat only, SD9). `changes.gone` holds the newly gone ships only
    (split_gone). Besides changed, new and newly gone ships and changed or new models, these count (T12.2 P4): ships back
    in the catalog (the manifest must clear missingSince / follows even if the file is the same), another grid order and
    import stops (overlap, hand check, a grid without transform and no override) - the import writes no file for them,
    so the files alone would look the same and the stop would vanish."""
    return not (changes.changed or changes.new or changes.gone or models.changed or models.new or back or order_changed
                or import_stops)
