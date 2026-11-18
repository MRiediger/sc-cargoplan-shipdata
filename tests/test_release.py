"""release: --seed builds the first release folder from the app and a holo release (P4, condition D); --dry-run lists the
assets and never touches the model cache; cleaning old model hashes belongs to a published release (condition B)."""
import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from conftest import CLEAN
from shipdata import release, rules

MOTHERLODE = 'cryon.rocks (Motherlode) 4.10.3-LIVE.13165946, 2026-11-12T20:50:33.036Z'


def app(tmp: Path, sources: dict[str, str]) -> Path:
    a = tmp / 'app'
    (a / 'ships' / 'modules').mkdir(parents=True)
    (a / 'outlines').mkdir()
    for sid, src in sources.items():
        doc = {'schemaVersion': 6, 'id': sid, 'modelKey': f'test-{sid}', 'source': src, 'totalScu': 1, 'racks': []}
        (a / 'ships' / f'{sid}.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    (a / 'ships' / 'modules' / 'm.json').write_text('{}', encoding='utf-8')
    (a / 'outlines' / 'ship-outlines.json').write_text('{"schemaVersion":1,"ships":[]}', encoding='utf-8')
    return a


def holo(tmp: Path, slugs: list[str]) -> Path:
    h = tmp / 'holo-v3'
    h.mkdir()
    ships = []
    for slug in slugs:
        data = slug.encode()
        (h / f'{slug}.holo').write_bytes(data)
        ships.append({'slug': slug, 'file': f'{slug}.holo', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'model': 'TEST', 'rawSha256': 'a' * 64, 'budget': 20000, 'triangles': 1, 'edges': [1, 1, 1],
                      'passed': True, 'metrics': dict(CLEAN)})
    (h / 'manifest.json').write_text(json.dumps({'dataVersion': 'holo-v3', 'formatVersion': 2, 'ships': ships}), encoding='utf-8')
    (h / 'NOTICE.md').write_text('notice', encoding='utf-8')
    return h


def test_seed_reads_built_from_out_of_the_source_lines(tmp_path: Path) -> None:
    out = release.seed(app(tmp_path, {'a': MOTHERLODE, 'b': MOTHERLODE,
                                      'cyclone': 'cryon.rocks (Motherlode) 4.10.2-LIVE.12913470, 2026-11-07',
                                      'f7c': 'Fleetyards API (CIG ship matrix), export 2026-01-15'}),
                       holo(tmp_path, ['test-a']), tmp_path / 'out', app_tag='v0.5.1', data_version='ships-2026.11',
                       generated_at='2026-11-17T00:00:00Z', pipeline_commit='abc1234', tools={})
    m = json.loads((out.folder / 'manifest.json').read_text(encoding='utf-8'))
    assert m['builtFrom']['motherlode'] == {'gameBuild': '4.10.3-LIVE.13165946', 'updatedAt': '2026-11-12T20:50:33.036Z'}
    assert out.other_sources == {'cyclone': 'cryon.rocks (Motherlode) 4.10.2-LIVE.12913470, 2026-11-07',
                                 'f7c': 'Fleetyards API (CIG ship matrix), export 2026-01-15'}
    assert (out.folder / 'ships' / 'a.json').read_bytes() == (tmp_path / 'app' / 'ships' / 'a.json').read_bytes()
    assert (out.folder / 'ships' / 'modules' / 'm.json').exists()
    assert (out.folder / 'outlines.json').exists() and (out.folder / 'test-a.holo').exists()
    assert not (out.folder / 'holo').exists()
    assert sorted(m['holo']['ships']) == ['test-a']


def test_seed_keeps_passed_false_and_the_metrics_of_the_holo_release(tmp_path: Path) -> None:
    """holo-v3 published 22 ships with passed=false. The seed carries that over with the fails derived from the metrics
    (F1), so the first run's judge compares a re-export with them (a note), not with nothing (case 4, a stop)."""
    h = holo(tmp_path, ['test-a', 'test-b'])
    doc = json.loads((h / 'manifest.json').read_text(encoding='utf-8'))
    doc['ships'][1].update(passed=False, triangles=39353, budget=40000, metrics=dict(CLEAN, topHausdorff=0.0123))
    (h / 'manifest.json').write_text(json.dumps(doc), encoding='utf-8')
    out = release.seed(app(tmp_path, {'a': MOTHERLODE}), h, tmp_path / 'out', app_tag='v0.5.1', data_version='x',
                       generated_at='x', pipeline_commit='x', tools={})
    entry = json.loads((out.folder / 'manifest.json').read_text(encoding='utf-8'))['holo']['ships']['test-b']
    assert (entry['passed'], entry['triangles'], entry['budget']) == (False, 39353, 40000)
    assert entry['metrics']['topHausdorff'] == 0.0123
    assert entry['fails'] == ['hausdorff']
    pp = {'passed': False, 'triangles': 39353, 'budget': 40000, 'fails': ['hausdorff'], 'topHausdorff': 0.0123,
          'sideHausdorff': 0.0, 'frontHausdorff': 0.0}
    assert rules.judge('test-b', pp, previous=entry, class_name='TEST').stop is False


def test_seed_derives_no_fails_for_a_clean_hologram(tmp_path: Path) -> None:
    out = release.seed(app(tmp_path, {'a': MOTHERLODE}), holo(tmp_path, ['test-a']), tmp_path / 'out', app_tag='v0.5.1',
                       data_version='x', generated_at='x', pipeline_commit='x', tools={})
    assert json.loads((out.folder / 'manifest.json').read_text(encoding='utf-8'))['holo']['ships']['test-a']['fails'] == []


def test_seed_stops_when_passed_and_the_metrics_disagree(tmp_path: Path) -> None:
    h = holo(tmp_path, ['test-a'])
    doc = json.loads((h / 'manifest.json').read_text(encoding='utf-8'))
    doc['ships'][0]['metrics'] = dict(CLEAN, topIou=0.5)          # fails iou, but published as passed
    (h / 'manifest.json').write_text(json.dumps(doc), encoding='utf-8')
    with pytest.raises(release.ReleaseError, match='test-a'):
        release.seed(app(tmp_path, {'a': MOTHERLODE}), h, tmp_path / 'out', app_tag='v0.5.1', data_version='x',
                     generated_at='x', pipeline_commit='x', tools={})


def test_seed_stops_when_ships_of_the_newest_build_disagree_on_the_date(tmp_path: Path) -> None:
    with pytest.raises(release.ReleaseError, match='updatedAt'):
        release.seed(app(tmp_path, {'a': MOTHERLODE, 'b': MOTHERLODE.replace('2026-11-12', '2026-11-13')}),
                     holo(tmp_path, []), tmp_path / 'out', app_tag='v0.5.1', data_version='ships-2026.11',
                     generated_at='x', pipeline_commit='x', tools={})


def test_seed_stops_on_a_holo_file_that_differs_from_its_manifest(tmp_path: Path) -> None:
    h = holo(tmp_path, ['test-a'])
    (h / 'test-a.holo').write_bytes(b'changed')
    with pytest.raises(release.ReleaseError, match='test-a'):
        release.seed(app(tmp_path, {'a': MOTHERLODE}), h, tmp_path / 'out', app_tag='v0.5.1', data_version='x',
                     generated_at='x', pipeline_commit='x', tools={})


def test_seed_order_keys_come_from_the_archive_and_are_null_for_ships_not_in_it() -> None:
    """Martin, 18 Nov: the seed's orderKeys from the catalog v0.5.1 was built from; a ship not in it (another source) or
    kept as it is (a grid without transform) has none: its order is not compared until a run writes it."""
    entries = [{'id': 'a', 'status': 'same', 'orderKeys': ['2x2x1@0.0,0.0,0.0']}, {'id': 'kept', 'status': 'kept', 'orderKeys': None}]
    keys, not_compared = release.seed_order_keys(entries, ['a', 'cyclone', 'kept'])
    assert keys == {'a': ['2x2x1@0.0,0.0,0.0'], 'cyclone': None, 'kept': None}
    assert not_compared == ['cyclone', 'kept']


def test_seed_order_keys_stop_when_the_archive_would_rewrite_a_ship() -> None:
    """The archive is then not the catalog the seed's ship files were built from."""
    with pytest.raises(release.ReleaseError, match='b'):
        release.seed_order_keys([{'id': 'a', 'status': 'same', 'orderKeys': []}, {'id': 'b', 'status': 'updated', 'orderKeys': []}],
                                ['a', 'b'])


def staged(tmp: Path) -> Path:
    return release.seed(app(tmp, {'a': MOTHERLODE, 'b': MOTHERLODE}), holo(tmp, ['test-a', 'test-b']), tmp / 'stage',
                        app_tag='v0.5.1', data_version='ships-2026.11', generated_at='x', pipeline_commit='x', tools={}).folder


def test_pack_writes_exactly_the_flat_assets_and_leaves_the_model_cache_alone(tmp_path: Path) -> None:
    """SD4: manifest.json, NOTICE.md, ships.zip (ships/** + outlines.json) and one <slug>.holo per hologram, nothing else."""
    stage = staged(tmp_path)
    models = tmp_path / 'models'
    models.mkdir()
    (models / 'TEST_A-000000000000.glb').write_bytes(b'old')
    (models / 'TEST_A-111111111111.glb').write_bytes(b'new')
    assets = release.pack(stage, tmp_path / 'release', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    assert sorted(a.name for a in assets) == ['NOTICE.md', 'manifest.json', 'ships.zip', 'test-a.holo', 'test-b.holo']
    assert sorted(p.name for p in (tmp_path / 'release').iterdir()) == sorted(a.name for a in assets)
    m = json.loads((tmp_path / 'release' / 'manifest.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(tmp_path / 'release' / 'ships.zip') as z:
        assert z.namelist() == sorted(m['files'])
        assert all(hashlib.sha256(z.read(n)).hexdigest() == m['files'][n] for n in z.namelist())
    assert len(list(models.iterdir())) == 2


def test_ships_zip_is_the_same_bytes_for_the_same_content(tmp_path: Path) -> None:
    stage = staged(tmp_path)
    release.pack(stage, tmp_path / 'one', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    # Another mtime, the same bytes. Far apart: ZIP keeps times in 2-second steps, so a touch() alone would not show a
    # time in the entries (it kept this test green when provoked, T12.1b).
    os.utime(stage / 'ships' / 'a.json', (1_000_000_000, 1_000_000_000))
    release.pack(stage, tmp_path / 'two', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    assert (tmp_path / 'one' / 'ships.zip').read_bytes() == (tmp_path / 'two' / 'ships.zip').read_bytes()


def test_unpack_reads_manifest_and_zip_without_holograms(tmp_path: Path) -> None:
    """diff --previous needs only manifest.json and ships.zip of the last release (SD4)."""
    release.pack(staged(tmp_path), tmp_path / 'release', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    for h in (tmp_path / 'release').glob('*.holo'):
        h.unlink()
    m = release.unpack(tmp_path / 'release', tmp_path / 'previous')
    assert m['dataVersion'] == 'ships-2026.11'
    assert sorted(p.relative_to(tmp_path / 'previous').as_posix() for p in (tmp_path / 'previous').rglob('*') if p.is_file()) \
        == sorted(m['files'])


def rezip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries.items():
            z.writestr(name, data)


def test_unpack_stops_on_an_entry_that_differs_from_the_manifest(tmp_path: Path) -> None:
    release.pack(staged(tmp_path), tmp_path / 'release', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    with zipfile.ZipFile(tmp_path / 'release' / 'ships.zip') as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries['ships/a.json'] = b'{}'
    rezip(tmp_path / 'release' / 'ships.zip', entries)
    with pytest.raises(release.ReleaseError, match='ships/a.json'):
        release.unpack(tmp_path / 'release', tmp_path / 'previous')


def test_unpack_stops_on_a_path_outside_the_folder(tmp_path: Path) -> None:
    release.pack(staged(tmp_path), tmp_path / 'release', notice=tmp_path / 'holo-v3' / 'NOTICE.md')
    with zipfile.ZipFile(tmp_path / 'release' / 'ships.zip') as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries['ships/../../escape.json'] = b'{}'
    rezip(tmp_path / 'release' / 'ships.zip', entries)
    with pytest.raises(release.ReleaseError, match='escape'):
        release.unpack(tmp_path / 'release', tmp_path / 'previous')
    assert not (tmp_path / 'escape.json').exists()


def test_publishing_is_part_of_t12_2(tmp_path: Path) -> None:
    with pytest.raises(release.ReleaseError, match='T12.2'):
        release.publish(tmp_path, tmp_path / 'models')
