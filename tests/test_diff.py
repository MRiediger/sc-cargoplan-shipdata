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
            'test-gone': {'model': 'TEST_G', 'rawSha256': 'cccccccccccc' + '0' * 52},
            'test-old': {'model': 'fleetyards (holo-v1)'}}
    cat = {'ships': [{'className': 'TEST_A', 'modelUrl': 'https://x/TEST_A-aaaaaaaaaaaa.glb'},
                     {'className': 'TEST_B', 'modelUrl': 'https://x/TEST_B-dddddddddddd.glb'},
                     {'className': 'TEST_N', 'modelUrl': 'https://x/TEST_N-eeeeeeeeeeee.glb'},
                     {'className': 'TEST_V', 'modelUrl': 'https://x/TEST_V-ffffffffffff.glb'}]}
    # TEST_V is a variant's own model: its ship shows the base ship's hologram, so it builds nothing (as the Carrack
    # Expedition on 16 Nov). 'fleetyards (holo-v1)' names a source, not a model.
    m = diff.model_changes(holo, cat, chosen={'TEST_A', 'TEST_B', 'TEST_N'})
    assert (m.same, m.changed, m.new, m.without_url, m.unused) == (['TEST_A'], ['TEST_B'], ['TEST_N'], ['TEST_G'], ['TEST_V'])


# ---------------------------------------------------------------- nothing changed (T12.2 D2, P4)

import pytest  # noqa: E402

PREVIOUS = {'cyclone': {'missingSince': '2026-11-16', 'follows': None},
            'mole_carbon_edition': {'missingSince': None, 'follows': 'mole'},
            'alpha': {'missingSince': None, 'follows': None}}


def test_split_gone_counts_only_ships_newly_gone() -> None:
    """Gone since the last release (missingSince or follows there) is no change; gone for the first time is (D2)."""
    newly, still = diff.split_gone(['alpha', 'cyclone', 'mole_carbon_edition'], PREVIOUS)
    assert (newly, still) == (['alpha'], ['cyclone', 'mole_carbon_edition'])


def quiet() -> dict:
    return dict(changes=diff.ShipChanges(same=['alpha']), models=diff.ModelChanges(same=['TEST_A']), back=[],
                order_changed=[], import_stops=[])


def test_nothing_changed_when_only_long_gone_ships_are_missing() -> None:
    assert diff.nothing_changed(**quiet()) is True


@pytest.mark.parametrize('what, value', [
    ('changes', diff.ShipChanges(changed=['alpha'])),
    ('changes', diff.ShipChanges(new=['fresh'])),
    ('changes', diff.ShipChanges(gone=['alpha'])),
    ('models', diff.ModelChanges(changed=['TEST_A'])),
    ('models', diff.ModelChanges(new=['TEST_N'])),
    ('back', ['cyclone']),
    ('order_changed', ['alpha']),
    ('import_stops', ['alpha']),
])
def test_each_change_counts(what: str, value: object) -> None:
    """P4: back (the manifest must clear missingSince), another grid order and an import stop (overlap, hand check, a
    grid without transform and no override) are changes too: the import writes no file for them, diff would see 'same'
    and the stop would vanish in a heartbeat."""
    args = quiet()
    args[what] = value
    assert diff.nothing_changed(**args) is False
