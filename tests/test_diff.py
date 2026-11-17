"""diff: ship files and outlines compared without their stamps (source, generatedAt, dataVersion; condition C), new and
gone ships, model changes counted apart (a re-export comes without a build change, S12.0)."""
import json
from pathlib import Path

from shipdata import diff

SHIP = {'schemaVersion': 6, 'id': 'alpha', 'name': 'TEST Alpha', 'modelKey': 'test-alpha',
        'source': 'cryon.rocks (Motherlode) 4.10.3-LIVE.1, 2026-11-12T20:50:33.036Z', 'totalScu': 4,
        'racks': [{'id': 'rack-0', 'capacityScu': 4, 'grid': {'length': 2, 'width': 2, 'stack': 1}, 'origin': [0, 0, 0],
                   'stackAxis': '+z'}]}


def put(folder: Path, sid: str, doc: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{sid}.json').write_text(json.dumps(doc, indent=2), encoding='utf-8')


def test_strip_stamps_drops_source_generated_at_and_data_version() -> None:
    doc = {'source': 'a', 'generatedAt': 'b', 'dataVersion': 'c', 'keep': 1}
    assert diff.strip_stamps(doc) == {'keep': 1}


def test_a_new_source_alone_is_no_change(tmp_path: Path) -> None:
    put(tmp_path / 'old', 'alpha', SHIP)
    put(tmp_path / 'new', 'alpha', dict(SHIP, source='cryon.rocks (Motherlode) 4.10.3-LIVE.1, 2026-11-16T11:36:30.299Z'))
    result = diff.compare_ships(tmp_path / 'old', tmp_path / 'new', absent=[])
    assert (result.changed, result.same) == ([], ['alpha'])


def test_new_outline_stamps_alone_are_no_change() -> None:
    a = {'schemaVersion': 1, 'generatedAt': '2026-11-16T13:50:01Z', 'dataVersion': 'holo-v3', 'ships': [{'slug': 'x'}]}
    b = dict(a, generatedAt='2026-12-01T04:23:00Z', dataVersion='ships-2026.12')
    assert diff.content_hash(a) == diff.content_hash(b)
    assert diff.content_hash(a) != diff.content_hash(dict(a, ships=[{'slug': 'y'}]))


def test_a_rack_change_counts(tmp_path: Path) -> None:
    moved = json.loads(json.dumps(SHIP))
    moved['racks'][0]['origin'] = [1, 0, 0]
    put(tmp_path / 'old', 'alpha', SHIP)
    put(tmp_path / 'new', 'alpha', moved)
    assert diff.compare_ships(tmp_path / 'old', tmp_path / 'new', absent=[]).changed == ['alpha']


def test_new_and_gone_ships(tmp_path: Path) -> None:
    put(tmp_path / 'old', 'alpha', SHIP)
    put(tmp_path / 'old', 'gone', dict(SHIP, id='gone'))
    put(tmp_path / 'new', 'alpha', SHIP)
    put(tmp_path / 'new', 'gone', dict(SHIP, id='gone'))
    put(tmp_path / 'new', 'fresh', dict(SHIP, id='fresh'))
    result = diff.compare_ships(tmp_path / 'old', tmp_path / 'new', absent=['gone'])
    assert (result.new, result.gone, result.same) == (['fresh'], ['gone'], ['alpha'])


def test_racks_hash_ignores_everything_but_the_racks() -> None:
    other = dict(SHIP, id='alpha_variant', name='TEST Alpha Variant', source='x')
    assert diff.racks_hash(SHIP) == diff.racks_hash(other)


def test_model_changes_are_counted_by_the_hash_in_the_model_url() -> None:
    holo = {'test-alpha': {'model': 'TEST_A', 'rawSha256': 'aaaaaaaaaaaa' + '0' * 52},
            'test-beta': {'model': 'TEST_B', 'rawSha256': 'bbbbbbbbbbbb' + '0' * 52},
            'test-gone': {'model': 'TEST_G', 'rawSha256': 'cccccccccccc' + '0' * 52}}
    cat = {'ships': [{'className': 'TEST_A', 'modelUrl': 'https://x/TEST_A-aaaaaaaaaaaa.glb'},
                     {'className': 'TEST_B', 'modelUrl': 'https://x/TEST_B-dddddddddddd.glb'},
                     {'className': 'TEST_N', 'modelUrl': 'https://x/TEST_N-eeeeeeeeeeee.glb'}]}
    m = diff.model_changes(holo, cat)
    assert (m.same, m.changed, m.new, m.without_url) == (['TEST_A'], ['TEST_B'], ['TEST_N'], ['TEST_G'])
