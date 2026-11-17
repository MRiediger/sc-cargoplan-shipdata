"""release: the release folder (ships/, outlines.json, holo/, manifest.json, NOTICE.md) and its asset list.

--seed (plan P4) builds the first folder without a catalog, from the app's data and a hologram release - today
sc-cargoplan@v0.5.1 and holo-v3 - so diff has a last release to compare with, and T12.6 has its first data release.
builtFrom.motherlode comes from the ships' "source" lines (condition D); the hologram entries, passed=false included, come
over unchanged (P9), so the first run's judge sees them as published.
--dry-run copies the staged folder and lists the assets; it never touches the model cache. Publishing, and with it
cleaning older model hashes (condition B, fetch.prune_models), comes with the workflow in T12.2."""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from shipdata import manifest

SOURCE = re.compile(r'^cryon\.rocks \(Motherlode\) (?P<build>\d+\.\d+(?:\.\d+)?-[A-Z]+\.\d+), (?P<updated>.+)$')


class ReleaseError(RuntimeError):
    pass


@dataclass
class Seed:
    folder: Path
    motherlode: dict
    other_sources: dict[str, str]
    ships: int
    holos: int


@dataclass
class Asset:
    name: str
    bytes: int
    sha256: str


def build_key(build: str) -> tuple[int, ...]:
    """4.10.3-LIVE.13165946 -> (4, 10, 3, 13165946): the newest build sorts last."""
    version, _, number = build.partition('-')
    return tuple(int(x) for x in version.split('.')) + (int(number.rsplit('.', 1)[-1]),)


def motherlode_from_sources(sources: dict[str, str]) -> tuple[dict, dict[str, str]]:
    """The catalog state of a release without catalog: the newest Motherlode build named in the ships' source lines, and
    the one updatedAt all its ships agree on. Ships of an older build (Cyclone, 4.10.2) or another source (Fleetyards) are
    returned apart: they are not in the newest catalog."""
    parsed = {sid: SOURCE.match(src or '') for sid, src in sources.items()}
    builds = {m['build'] for m in parsed.values() if m}
    if not builds:
        raise ReleaseError('no ship names a Motherlode build in its source line')
    newest = max(builds, key=build_key)
    dates = sorted({m['updated'] for m in parsed.values() if m and m['build'] == newest})
    if len(dates) != 1:
        raise ReleaseError(f'ships of build {newest} disagree on updatedAt: {", ".join(dates)}')
    others = {sid: sources[sid] for sid, m in sorted(parsed.items()) if not m or m['build'] != newest}
    return {'gameBuild': newest, 'updatedAt': dates[0]}, others


def seed(app: Path, holo_dir: Path, out: Path, *, app_tag: str, data_version: str, generated_at: str,
         pipeline_commit: str, tools: dict) -> Seed:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(app / 'ships', out / 'ships')
    shutil.copyfile(app / 'outlines' / 'ship-outlines.json', out / 'outlines.json')
    holo_manifest = json.loads((holo_dir / 'manifest.json').read_text(encoding='utf-8-sig'))
    (out / 'holo').mkdir()
    holo_ships = {}
    for e in holo_manifest['ships']:
        data = (holo_dir / e['file']).read_bytes()
        if len(data) != e['bytes'] or hashlib.sha256(data).hexdigest() != e['sha256']:
            raise ReleaseError(f"{e['slug']}: {e['file']} differs from the holo release's manifest")
        (out / 'holo' / f"{e['slug']}.holo").write_bytes(data)
        holo_ships[e['slug']] = {k: v for k, v in e.items() if k not in ('slug', 'file', 'bytes', 'sha256')}
    sources = {p.stem: json.loads(p.read_text(encoding='utf-8-sig')).get('source') for p in sorted((out / 'ships').glob('*.json'))}
    motherlode, others = motherlode_from_sources(sources)
    m = manifest.build(out, data_version=data_version, generated_at=generated_at, motherlode=motherlode, app_tag=app_tag,
                       pipeline_commit=pipeline_commit, tools=tools, holo_ships=holo_ships, ships={})
    manifest.write(out / 'manifest.json', m)
    return Seed(out, motherlode, others, len(sources), len(holo_ships))


def assets(folder: Path) -> list[Asset]:
    return [Asset(p.relative_to(folder).as_posix(), p.stat().st_size, manifest.sha256(p))
            for p in sorted(folder.rglob('*')) if p.is_file()]


def dry_run(stage: Path, release_dir: Path, notice: Path) -> list[Asset]:
    if release_dir.exists():
        shutil.rmtree(release_dir)
    shutil.copytree(stage, release_dir)
    shutil.copyfile(notice, release_dir / 'NOTICE.md')
    return assets(release_dir)


def publish(stage: Path, models_dir: Path) -> None:
    raise ReleaseError('publishing a release (gh release create, then fetch.prune_models) is part of T12.2; use --dry-run')
