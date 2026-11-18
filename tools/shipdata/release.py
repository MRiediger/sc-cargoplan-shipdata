"""release: the staged folder (ships/, outlines.json, <slug>.holo, manifest.json) packed as the flat assets of a data
release (SD4): manifest.json, NOTICE.md, ships.zip (ships/** + outlines.json) and one <slug>.holo per hologram - GitHub
assets cannot be folders. unpack reads a last release's manifest and ships.zip for diff, without its holograms.

--seed (plan P4) builds the first stage without a run, from the app's data and a hologram release - today
sc-cargoplan@v0.5.1 and holo-v3 - so diff has a last release to compare with, and T12.6 has its first data release.
builtFrom.motherlode comes from the ships' "source" lines (condition D); the hologram entries, passed=false included, come
over with fails derived from their metrics (F1), the orderKeys from the catalog the app's data was built from.
--dry-run packs the stage and lists the assets; it never touches the model cache. Publishing, and with it cleaning older
model hashes (condition B, fetch.prune_models), is workflow.draft_stage and workflow.publish_stage (T12.2)."""
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import PurePosixPath
from dataclasses import dataclass
from pathlib import Path

from shipdata import chain, manifest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import holo_mesh  # noqa: E402  (byte-equal copy; its judge derives the fails of a holo release without them, F1)

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


def derived_fails(e: dict) -> list[str]:
    """The fails of a holo release entry (holo-v3 has none, F1): holo_mesh.judge on its metrics with the chain's sliver
    limit. errorM needs the length, which the entry lacks: error never counts as failed. Checked against the 97 PP.json
    of T12.1's byte-equal build: 97 / 97 equal. An entry whose passed disagrees with its metrics stops the seed."""
    rec = dict(e['metrics'], triangles=e['triangles'], target=e['budget'], lengthM=float('inf'))
    fails = holo_mesh.judge(rec, float(chain.SLIVER_LIMIT))
    if bool(fails) == e['passed']:
        raise ReleaseError(f"{e['slug']}: passed={e['passed']} but its metrics fail {fails or 'nothing'}")
    return fails


def seed_order_keys(entries: list[dict], ship_ids: list[str]) -> tuple[dict[str, list[str] | None], list[str]]:
    """orderKeys of the seed from the import's report against the catalog v0.5.1 was built from (Martin, 18 Nov; the
    import is the one implementation of OrderKey, plan P2). A ship the import would rewrite means the catalog is not that
    one: stop. A ship not in it, or kept as it is (a grid without transform), gets null: order not compared."""
    rewrite = sorted(e['id'] for e in entries if e['status'] in ('updated', 'created', 'handcheck', 'order'))
    if rewrite:
        raise ReleaseError(f'the catalog would rewrite {len(rewrite)} ship files ({", ".join(rewrite[:8])}): '
                           'it is not the catalog these files were built from')
    same = {e['id']: e['orderKeys'] for e in entries if e['status'] == 'same'}
    keys = {sid: same.get(sid) for sid in sorted(ship_ids)}
    return keys, [sid for sid, k in keys.items() if k is None]


def seed(app: Path, holo_dir: Path, out: Path, *, app_tag: str, data_version: str, generated_at: str,
         pipeline_commit: str, tools: dict, order_keys: dict[str, list[str] | None] | None = None) -> Seed:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(app / 'ships', out / 'ships')
    shutil.copyfile(app / 'outlines' / 'ship-outlines.json', out / 'outlines.json')
    holo_manifest = json.loads((holo_dir / 'manifest.json').read_text(encoding='utf-8-sig'))
    holo_ships = {}
    for e in holo_manifest['ships']:
        data = (holo_dir / e['file']).read_bytes()
        if len(data) != e['bytes'] or hashlib.sha256(data).hexdigest() != e['sha256']:
            raise ReleaseError(f"{e['slug']}: {e['file']} differs from the holo release's manifest")
        (out / f"{e['slug']}.holo").write_bytes(data)
        holo_ships[e['slug']] = dict({k: v for k, v in e.items() if k not in ('slug', 'file', 'bytes', 'sha256')},
                                     fails=derived_fails(e))
    sources = {p.stem: json.loads(p.read_text(encoding='utf-8-sig')).get('source') for p in sorted((out / 'ships').glob('*.json'))}
    motherlode, others = motherlode_from_sources(sources)
    m = manifest.build(out, data_version=data_version, generated_at=generated_at, motherlode=motherlode, app_tag=app_tag,
                       pipeline_commit=pipeline_commit, tools=tools, holo_ships=holo_ships,
                       ships={sid: {'orderKeys': k} for sid, k in (order_keys or {}).items()})
    manifest.write(out / 'manifest.json', m)
    return Seed(out, motherlode, others, len(sources), len(holo_ships))


def assets(folder: Path) -> list[Asset]:
    return [Asset(p.relative_to(folder).as_posix(), p.stat().st_size, manifest.sha256(p))
            for p in sorted(folder.rglob('*')) if p.is_file()]


ZIP_TIME = (1980, 1, 1, 0, 0, 0)    # the earliest time a ZIP entry can carry: the same content gives the same bytes


def pack(stage: Path, release_dir: Path, notice: Path) -> list[Asset]:
    """The release assets from a stage checked against its manifest: ships.zip with exactly the files of `files` (sorted,
    fixed time and mode, deflated; Python docs, zipfile.ZipInfo and ZipFile.writestr), the holograms and the manifest byte
    for byte, NOTICE.md from the repo. Nothing else lands in the folder."""
    m = manifest.read(stage / 'manifest.json')
    problems = manifest.check(stage, m)
    if problems:
        raise ReleaseError(f'stage differs from its manifest: {problems[:5]}')
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    with zipfile.ZipFile(release_dir / m['assets']['ships'], 'w') as z:
        for rel in sorted(m['files']):
            info = zipfile.ZipInfo(rel, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (stage / rel).read_bytes())
    for e in ((m['holo'] or {}).get('ships') or {}).values():
        shutil.copyfile(stage / e['file'], release_dir / e['file'])
    shutil.copyfile(notice, release_dir / 'NOTICE.md')
    shutil.copyfile(stage / 'manifest.json', release_dir / 'manifest.json')
    return assets(release_dir)


def unpack(release_dir: Path, into: Path) -> dict:
    """A last release for diff (SD4): its manifest and ships.zip, the holograms are not needed. At the boundary: every
    entry is ships/... or outlines.json inside `into` (no absolute path, no ..), and every unpacked file matches `files`."""
    m = manifest.read(release_dir / 'manifest.json')
    archive = release_dir / m['assets']['ships']
    if not archive.exists():
        raise ReleaseError(f'{archive} is missing: diff needs manifest.json and {m["assets"]["ships"]} of the last release')
    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            parts = PurePosixPath(info.filename).parts
            if info.is_dir() or info.filename.startswith('/') or '..' in parts or '\\' in info.filename or not (
                    info.filename == 'outlines.json' or (parts[0] == 'ships' and len(parts) > 1)):
                raise ReleaseError(f'{archive}: entry {info.filename!r} is not ships/... or outlines.json')
            target = into.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
    problems = manifest.check(into, m, holograms=False)
    if problems:
        raise ReleaseError(f'{archive} differs from its manifest: {problems[:5]}')
    return m
