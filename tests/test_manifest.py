"""manifest.json of a data release (draft format, docs/manifest-format.md): written from a staged release folder, read
back with its boundary checks, every file hash checked."""
import json
from pathlib import Path

import pytest

from shipdata import manifest

SHIP = {'schemaVersion': 6, 'id': 'alpha', 'modelKey': 'test-alpha', 'source': 'cryon.rocks (Motherlode) 4.10.3-LIVE.1, 2026-11-12',
        'totalScu': 4, 'racks': [{'id': 'rack-0', 'capacityScu': 4}]}
HOLO = {'test-alpha': {'model': 'TEST_A', 'rawSha256': 'a' * 64, 'budget': 20000, 'triangles': 100, 'edges': [1, 2, 3],
                       'passed': True, 'fails': [], 'metrics': {}}}


def stage(tmp: Path, with_holo: bool = True) -> Path:
    s = tmp / 'stage'
    (s / 'ships').mkdir(parents=True)
    (s / 'ships' / 'alpha.json').write_text(json.dumps(SHIP), encoding='utf-8')
    (s / 'outlines.json').write_text('{"schemaVersion":1,"ships":[]}', encoding='utf-8')
    if with_holo:
        (s / 'test-alpha.holo').write_bytes(b'SCH2 bytes')        # flat, as the asset (SD4)
    return s


def build(s: Path, holo: dict | None) -> dict:
    return manifest.build(s, data_version='ships-2026.11', generated_at='2026-11-17T00:00:00Z',
                          motherlode={'gameBuild': '4.10.3-LIVE.1', 'updatedAt': '2026-11-12'}, app_tag='v0.5.1',
                          pipeline_commit='abc1234', tools={'python': '3.14.5'}, holo_ships=holo,
                          ships={'alpha': {'missingSince': None, 'follows': None, 'orderKeys': ['2x2x1@0.0,0.0,0.0']}})


def test_the_manifest_hashes_every_file_and_checks_clean(tmp_path: Path) -> None:
    s = stage(tmp_path)
    m = build(s, HOLO)
    assert sorted(m['files']) == ['outlines.json', 'ships/alpha.json']
    assert m['holo']['ships']['test-alpha']['bytes'] == len(b'SCH2 bytes')
    assert m['holo']['ships']['test-alpha']['file'] == 'test-alpha.holo'
    assert m['assets'] == {'ships': 'ships.zip'}
    assert m['ships']['alpha']['modelKey'] == 'test-alpha' and len(m['ships']['alpha']['racksSha256']) == 64
    assert manifest.check(s, m) == []


def test_a_changed_file_is_a_problem(tmp_path: Path) -> None:
    s = stage(tmp_path)
    m = build(s, HOLO)
    (s / 'ships' / 'alpha.json').write_text('{}', encoding='utf-8')
    assert manifest.check(s, m) == ['ships/alpha.json: SHA-256 differs from the manifest']


def test_holo_null_is_the_kill_switch(tmp_path: Path) -> None:
    s = stage(tmp_path, with_holo=False)
    m = build(s, None)
    assert m['holo'] is None and manifest.check(s, m) == []


def test_a_holo_file_without_entry_is_a_problem(tmp_path: Path) -> None:
    s = stage(tmp_path)
    with pytest.raises(manifest.ManifestError, match='test-alpha'):
        build(s, {})


def test_reading_checks_the_required_fields(tmp_path: Path) -> None:
    s = stage(tmp_path)
    m = build(s, HOLO)
    manifest.write(s / 'manifest.json', m)
    assert manifest.read(s / 'manifest.json') == m
    del m['ships']
    (s / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(manifest.ManifestError, match='ships'):
        manifest.read(s / 'manifest.json')
    m = build(s, HOLO)
    del m['assets']
    (s / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(manifest.ManifestError, match='assets'):
        manifest.read(s / 'manifest.json')


def test_a_hologram_entry_without_fails_is_turned_down(tmp_path: Path) -> None:
    """F1: the judge's case 5 compares with the last release's fails; an entry without them cannot be judged."""
    s = stage(tmp_path)
    m = build(s, HOLO)
    del m['holo']['ships']['test-alpha']['fails']
    manifest.write(s / 'manifest.json', m)
    with pytest.raises(manifest.ManifestError, match='without fails: test-alpha'):
        manifest.read(s / 'manifest.json')


def test_order_keys_are_written_and_checked_on_reading(tmp_path: Path) -> None:
    s = stage(tmp_path)
    m = build(s, HOLO)
    assert m['ships']['alpha']['orderKeys'] == ['2x2x1@0.0,0.0,0.0']
    m['ships']['alpha']['orderKeys'] = None                     # null: order not compared
    manifest.write(s / 'manifest.json', m)
    assert manifest.read(s / 'manifest.json')['ships']['alpha']['orderKeys'] is None
    m['ships']['alpha']['orderKeys'] = '2x2x1@0.0,0.0,0.0'      # a string, not a list
    manifest.write(s / 'manifest.json', m)
    with pytest.raises(manifest.ManifestError, match='orderKeys: alpha'):
        manifest.read(s / 'manifest.json')
